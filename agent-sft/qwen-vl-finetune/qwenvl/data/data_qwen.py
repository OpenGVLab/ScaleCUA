import os
import copy
import random
import logging
import re
import time
import math
import itertools
import io
import ast
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, List, Tuple
from io import BytesIO
import time
import datetime
from functools import reduce
from collections.abc import Sequence
from func_timeout import func_set_timeout

import numpy as np
import torch
import torch.distributed as dist
from torch.utils.data import Dataset
from torch.utils.data import ConcatDataset
from PIL import Image
from decord import VideoReader
import transformers
from qwen_vl_utils import smart_resize
from qwen_vl_utils.vision_process import MIN_PIXELS, MAX_PIXELS, IMAGE_FACTOR

import json

# Try to import petrel_client for image loading, fallback to PIL if unavailable
try:
    from petrel_client.client import Client
    from petrel_client.common.config import Config

    has_tcs_loader = True
except ImportError as E:
    print("petrel_client is not installed. Using PIL to load images.")
    has_tcs_loader = False

try:
    from . import data_list
    from .rope2d import get_rope_index_25, get_rope_index_2
    import sys

    sys.path.append("../internvl_chat/internvl")
    from conversation import get_conv_template
except ImportError as E:
    pass


IMAGE_FACTOR = 28
IGNORE_INDEX = -100
IMAGE_TOKEN_INDEX = 151655
VIDEO_TOKEN_INDEX = 151656
VISION_START_TOKEN_INDEX = 151652
VISION_END_TOKEN_INDEX = 151653

DEFAULT_IMAGE_TOKEN = "<image>"
DEFAULT_VIDEO_TOKEN = "<video>"


def rank0_print(*args):
    if dist.is_initialized():
        if dist.get_rank() == 0:
            print(f"Rank {dist.get_rank()}: ", *args)
    else:
        print(*args)


class TCSLoader(object):

    def __init__(self, conf_path, sc_config_key="sensecore"):
        rank0_print(f"[TCSLoader] config_path: {conf_path}")
        rank0_print("--> before Client(conf_path)")
        self.client = Client(conf_path)
        self.sc_config_key = sc_config_key
        rank0_print("--> after Client(conf_path)")

    def pil_loader(self, img_str):
        buff = io.BytesIO(img_str)
        img = Image.open(buff)
        return img.convert("RGB")

    def _get(self, fn):
        if has_tcs_loader:
            return self.client.get(fn)
        else:
            raise RuntimeError("petrel_client is not installed. Cannot load images.")

    # @func_set_timeout(5)
    def __call__(self, fn, image_type="image"):
        if image_type == "image":
            start_time = time.time()
            img_value_str = self._get(fn)
            duration = round((time.time() - start_time) * 1000, 2)
            img = self.pil_loader(img_value_str)
            if duration > 1000:
                print(
                    fn,
                    datetime.datetime.fromtimestamp(start_time),
                    " load time: ",
                    duration,
                    "ms",
                )
            return img


def read_jsonl(path):
    with open(path, "r") as f:
        return [json.loads(line) for line in f]


def load_image(image_path, tcs_loader=None) -> Image.Image:
    if "s3://" in image_path:
        if tcs_loader is None:
            raise ValueError("tcs_loader is required to load image from s3://")
        return tcs_loader(image_path)
    return Image.open(image_path).convert("RGB")


def get_image_size(image_size, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS):
    if type(image_size) in [list, tuple]:
        width, height = image_size
    elif type(image_size) == int:
        width, height = image_size, image_size

    input_height, input_width = smart_resize(
        height, width, min_pixels=min_pixels, max_pixels=max_pixels
    )
    return input_width, input_height


def find_bbox(ref_matches, message, image_size):
    image_width, image_height = image_size
    box_matches = re.findall(r"<box>(.*?)</box>", message)

    if not box_matches:
        box_matches = re.findall(r"\[\[.*?\]\]", message)

    if not box_matches:
        return None

    assert len(ref_matches) == len(
        box_matches
    ), f"ref_matches: {ref_matches}, box_matches: {box_matches}, message: {message}"

    formatted_values = []
    for ref, boxes in zip(ref_matches, box_matches):
        if type(boxes) == str:
            boxes = ast.literal_eval(boxes)

        if not isinstance(boxes[0], list):
            boxes = [boxes]

        if len(boxes[0]) != 4:
            return None

        new_boxes = []
        for bbox in boxes:
            # x1, y1, x2, y2 = map(int, bbox)
            x1, y1, x2, y2 = (
                round(bbox[0] / 1000 * image_width),
                round(bbox[1] / 1000 * image_height),
                round(bbox[2] / 1000 * image_width),
                round(bbox[3] / 1000 * image_height),
            )
            item_str = json.dumps(
                {"bbox_2d": [x1, y1, x2, y2], "label": ref}, ensure_ascii=False
            )
            formatted_values.append(item_str)

    if len(formatted_values) > 0:
        return (
            "```json\n" + "[\n    " + ",\n    ".join(formatted_values) + "\n]" + "\n```"
        )

    return message


def find_point(ref_matches, message, image_size):
    image_width, image_height = image_size
    point_matches = re.findall(r"<point>(.*?)</point>", message)

    if not point_matches:
        point_matches = re.findall(r"\[\[.*?\]\]", message)

    if not point_matches:
        return None

    assert len(ref_matches) == len(
        point_matches
    ), f"ref_matches: {ref_matches}, box_matches: {point_matches}, message: {message}"
    formatted_values = []
    for ref, points in zip(ref_matches, point_matches):
        if type(points) == str:
            points = ast.literal_eval(points)
        if not isinstance(points[0], list):
            points = [points]

        if len(points[0]) != 2:
            return None
        
        new_points = []
        for point in points:
            point = [
                round(point[0] / 1000 * image_width),
                round(point[1] / 1000 * image_height),
            ]
            new_points.append(point)
            item_str = json.dumps({"point_2d": point, "label": ref}, ensure_ascii=False)
            formatted_values.append(item_str)
        
    if len(formatted_values) > 0:
        return (
            "```json\n" + "[\n    " + ",\n    ".join(formatted_values) + "\n]" + "\n```"
        )

    return message


def format_grounding_internvl2qwenvl(
    message,
    role,
    raw_image_size,
    new_image_size,
    # image_width=None,
    # image_height=None,
) -> Dict:
    """
    Convert the grounding data format to qwen2vl grd.
    """
    if raw_image_size is None or new_image_size is None:
        return message

    if role in ("human", "user"):
        box_pattern = r"\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]"
        point_pattern = r"\[(\d+),\s*(\d+)\]"

        def replace_match1(match):
            bbox_or_point = list(map(int, match.groups()))
            if len(bbox_or_point) == 4:
                ori_x1 = round(bbox_or_point[0] / 1000 * new_image_size[0])
                ori_y1 = round(bbox_or_point[1] / 1000 * new_image_size[1])
                ori_x2 = round(bbox_or_point[2] / 1000 * new_image_size[0])
                ori_y2 = round(bbox_or_point[3] / 1000 * new_image_size[1])
                return json.dumps([ori_x1, ori_y1, ori_x2, ori_y2], ensure_ascii=False)
            elif len(bbox_or_point) == 2:
                ori_x = round(bbox_or_point[0] / 1000 * new_image_size[0])
                ori_y = round(bbox_or_point[1] / 1000 * new_image_size[1])
                return json.dumps([ori_x, ori_y])
            else:
                raise ValueError("Invalid match length")

        message = re.sub(box_pattern, replace_match1, message)
        message = re.sub(point_pattern, replace_match1, message)
        # message = message.replace("<box>", "").replace("</box>", "")
    elif role in ("assistant", "gpt"):
        if "<ref>" in message and "</ref>" in message:
            ref_matches = re.findall(r"<ref>(.*?)</ref>", message, re.DOTALL)
            if "<point>" in message and "</point>" in message:
                message = find_point(ref_matches, message, new_image_size)
            elif "<box>" in message and "</box>" in message:
                # some bboxes are like [[x1, y1, x2, y2]] wiithout <box> </box>
                message = find_bbox(ref_matches, message, new_image_size)
            else:
                new_message = find_bbox(ref_matches, message, new_image_size)
                if new_message is not None:
                    message = new_message
                else:
                    new_message = find_point(ref_matches, message, new_image_size)
                message = new_message
        else:
            box_pattern = r"\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]"
            point_pattern = r"\[(\d+),\s*(\d+)\]"
            def replace_match2(match):
                bbox_or_point = list(map(int, match.groups()))
                if len(bbox_or_point) == 4:
                    ori_x1 = round(bbox_or_point[0] / 1000 * new_image_size[0])
                    ori_y1 = round(bbox_or_point[1] / 1000 * new_image_size[1])
                    ori_x2 = round(bbox_or_point[2] / 1000 * new_image_size[0])
                    ori_y2 = round(bbox_or_point[3] / 1000 * new_image_size[1])
                    return f"[{ori_x1}, {ori_y1}, {ori_x2}, {ori_y2}]"
                elif len(bbox_or_point) == 2:
                    ori_x = round(bbox_or_point[0] / 1000 * new_image_size[0])
                    ori_y = round(bbox_or_point[1] / 1000 * new_image_size[1])
                    return f"[{ori_x}, {ori_y}]"
                else:
                    raise ValueError("Invalid match length")

            message = re.sub(box_pattern, replace_match2, message)
            message = re.sub(point_pattern, replace_match2, message)

    return message


def format_grounding_internvl2qwenvl_2(
    message,
    role,
    raw_image_size,
    new_image_size,
) -> Dict:
    """
    Convert the grounding data format to qwen2vl grd.
    """
    if raw_image_size is None or new_image_size is None:
        return message

    box_pattern = r"\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]"
    point_pattern = r"\[(\d+),\s*(\d+)\]"

    def replace_match1(match):
        bbox_or_point = list(map(int, match.groups()))
        if len(bbox_or_point) == 4:
            ori_x1 = round(bbox_or_point[0] / 1000 * new_image_size[0])
            ori_y1 = round(bbox_or_point[1] / 1000 * new_image_size[1])
            ori_x2 = round(bbox_or_point[2] / 1000 * new_image_size[0])
            ori_y2 = round(bbox_or_point[3] / 1000 * new_image_size[1])
            return json.dumps([ori_x1, ori_y1, ori_x2, ori_y2], ensure_ascii=False)
        elif len(bbox_or_point) == 2:
            ori_x = round(bbox_or_point[0] / 1000 * new_image_size[0])
            ori_y = round(bbox_or_point[1] / 1000 * new_image_size[1])
            return json.dumps([ori_x, ori_y])
        else:
            raise ValueError("Invalid match length")

    message = re.sub(box_pattern, replace_match1, message)
    message = re.sub(point_pattern, replace_match1, message)

    return message


def extract_image_references(text):
    pattern = r"((?:Image-\d+: <image>\n?)+)|(<image>)"
    matches = re.findall(pattern, text)

    results = []
    for group1, group2 in matches:
        if group1:
            results.append(group1.strip())
        elif group2:
            results.append(group2.strip())

    if not results:
        return ""

    return results[0]


def format_human_input(input_text):
    image_ref = extract_image_references(input_text)
    # Extract instruction
    instruction_match = re.search(
        r"Instruction:(.*?)\n+Previous actions:", input_text, re.DOTALL
    )
    instruction = instruction_match.group(1).strip() if instruction_match else ""

    # Extract previous actions
    actions_match = re.search(r"Previous actions:(.*?)$", input_text, re.DOTALL)
    actions = actions_match.group(1).strip() if actions_match else ""

    if instruction == "":
        return input_text

    if actions == "":
        actions = None
    #
    new_header = "Please generate the next move according to the UI screenshot, the task and previous operations.\n\n"
    target_format = (
        new_header + f"Task:\n{instruction}\n\nPrevious operations:\n{actions}"
    )
    return image_ref + "\n" + target_format


def format_cot_process(input_text):
    # Extract the observation, thought, and action from the input text
    observation_match = re.search(r"Observation:(.*?)\nThought:", input_text, re.DOTALL)
    observation = observation_match.group(1).strip() if observation_match else ""

    thought_match = re.search(r"Thought:(.*?)\nAction:", input_text, re.DOTALL)
    thought = thought_match.group(1).strip() if thought_match else ""

    action_match = re.search(r"Action:(.*?)$", input_text, re.DOTALL)
    action = action_match.group(1).strip() if action_match else ""

    # Format the extracted content into the desired format
    think_content = f"{observation} {thought}".strip()
    operation_content = action
    if think_content == "":
        target_format = f"<operation>\n{operation_content}\n</operation>"
    else:
        target_format = f"<think>\n{think_content}\n</think>\n<operation>\n{operation_content}\n</operation>"

    return target_format


def preprocess_qwen_2_visual(
    sources,
    tokenizer: transformers.PreTrainedTokenizer,
    grid_thw: List = [],
    visual_type: str = "image",
) -> Dict:
    roles = {"system": "system", "human": "user", "gpt": "assistant"}
    system_message = "You are a helpful assistant."
    if visual_type not in ["image", "video"]:
        raise ValueError("visual_type must be either 'image' or 'video'")

    tokenizer = copy.deepcopy(tokenizer)
    chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
    tokenizer.chat_template = chat_template

    visual_replicate_index = 0
    input_ids, targets = [], []

    for i, source in enumerate(sources):
        try:
            if roles[source[0]["from"]] == "system":
                if "InternVL" not in source[0]["value"]:
                    system_message = source[0]["value"]

            cnt = 0
            while roles[source[cnt]["from"]] != roles["human"]:
                cnt += 1
            source = source[cnt:]
        except:
            import traceback

            traceback.print_exc()
            print(sources)

        input_id, target = [], []

        input_id += tokenizer.apply_chat_template(
            [{"role": "system", "content": system_message}]
        )
        target += [IGNORE_INDEX] * len(input_id)
        # image_tokens = 0
        # image_features = 0
        for conv in source:
            try:
                role = conv["role"]
                content = conv["content"]
            except:
                role = conv["from"]
                content = conv["value"]

            role = roles.get(role, role)
            if (
                role == "user"
                and visual_type in content
                and grid_thw is not None
                and len(grid_thw) > 0
            ):
                visual_tag = f"<{visual_type}>"
                if visual_tag in content:
                    parts = content.split(visual_tag)
                    new_parts = []
                    for i in range(len(parts) - 1):
                        new_parts.append(parts[i])
                        replacement = (
                            "<|vision_start|>"
                            + f"<|{visual_type}_pad|>"
                            * grid_thw[visual_replicate_index]
                            + "<|vision_end|>"
                        )
                        new_parts.append(replacement)
                        visual_replicate_index += 1
                    new_parts.append(parts[-1])
                    content = "".join(new_parts)

            conv = [{"role": role, "content": content}]
            encode_id = tokenizer.apply_chat_template(conv, truncation=False)
            input_id += encode_id
            if role in ["user", "system"]:
                target += [IGNORE_INDEX] * len(encode_id)
            else:
                target_mask = encode_id.copy()
                target_mask[:3] = [IGNORE_INDEX] * 3
                target += target_mask

        # decoded_input = tokenizer.batch_decode(
        #     [torch.tensor(input_id), ],
        #     skip_special_tokens=False,
        #     clean_up_tokenization_spaces=False,
        # )[0]
        # rank0_print(f"decoded_input: {decoded_input}")
        # decoded_mask_input = tokenizer.batch_decode(
        #     [torch.tensor(input_id)[torch.tensor(target) != IGNORE_INDEX],],
        #     skip_special_tokens=False,
        #     clean_up_tokenization_spaces=False,
        # )[0]
        # rank0_print(f"decoded_unmask_input: {decoded_mask_input}")
        assert len(input_id) == len(target), f"{len(input_id)} != {len(target)}"
        # input_id = input_id * 10000
        if grid_thw is not None and len(input_id) >= tokenizer.model_max_length:
            # find the last image token or vision end token (VISION_END_TOKEN_INDEX)
            sub_input_id = input_id[tokenizer.model_max_length :]
            if VISION_END_TOKEN_INDEX in sub_input_id:
                raise ValueError(
                    f"Input length {len(input_id)} exceeds model max length {tokenizer.model_max_length}."
                )
        input_ids.append(input_id)
        targets.append(target)

    input_ids = torch.tensor(input_ids, dtype=torch.long)
    targets = torch.tensor(targets, dtype=torch.long)

    return dict(
        input_ids=input_ids,
        labels=targets,
    )


class LazySupervisedDataset(Dataset):
    """Dataset for supervised fine-tuning."""

    def __init__(self, tokenizer: transformers.PreTrainedTokenizer, data_args):
        super(LazySupervisedDataset, self).__init__()

        self.tcs_loader = None
        if has_tcs_loader:
            self.tcs_loader = TCSLoader("~/petreloss.conf")

        rank0_print(f"Loading datasets: {data_args.data_path}")
        self.video_max_total_pixels = getattr(
            data_args, "video_max_total_pixels", 1664 * 28 * 28
        )
        self.video_min_total_pixels = getattr(
            data_args, "video_min_total_pixels", 256 * 28 * 28
        )
        self.model_type = data_args.model_type
        self.coord_norm = data_args.coord_norm

        self.rng = random.Random(getattr(data_args, "custom_seed", 42))
        if data_args.model_type == "qwen2.5vl":
            self.get_rope_index = get_rope_index_25
        else:
            self.get_rope_index = get_rope_index_2

        list_data_dict = []
        list_data_root = []
        list_conv_style = []
        list_task = []
        assert data_args.data_path != "" or data_args.meta_path != ""
        if data_args.data_path != "":
            data = self.load_json(data_args.data_path, parse_line=True)
            if type(data) == list:
                meta = {}
                for item in data:
                    meta.update(self.load_json(item, parse_line=True))
            else:
                meta = data
        else:
            path_list = self.load_json(data_args.meta_path)
            meta = {}
            for item in path_list:
                meta.update(self.load_json(item, parse_line=True))

        for name, item in meta.items():
            rank0_print(f"Loading {name}")
            repeat_time = item.get("repeat_time", 1)
            if repeat_time == 0:
                rank0_print(f"Skipping {name} due to repeat_time=0")
                continue
            elif repeat_time == 1:
                sampling_strategy = "all"
            elif 0 < repeat_time < 1:
                sampling_strategy = f"random:{round(item['repeat_time'] * 100)}%"
            elif repeat_time > 1:
                sampling_strategy = f"repeat:{item['repeat_time']}"

            new_meta = {
                "json_path": item["annotation"],
                "images_folder": item.get("root", None),
                "conv_style": item.get("conv_style", data_args.conv_style),
                "sampling_strategy": sampling_strategy,
            }
            cur_data_dict, images_folder = self.load_ann(new_meta)
            list_data_dict.extend(cur_data_dict)
            list_data_root.extend([images_folder] * len(cur_data_dict))
            list_conv_style.extend(
                [item.get("conv_style", data_args.conv_style)] * len(cur_data_dict)
            )
            list_task.extend([item.get("task", "chat")] * len(cur_data_dict))

        rank0_print(f"Total training samples: {len(list_data_dict)}")

        import gc

        gc.collect()
        rank0_print("Formatting inputs...Skip in lazy mode")
        self.tokenizer = tokenizer
        self.list_data_dict = list_data_dict
        self.list_data_root = list_data_root
        self.list_conv_style = list_conv_style
        self.list_task = list_task
        self.data_args = data_args
        self.data_args.image_processor.max_pixels = data_args.max_pixels
        self.data_args.image_processor.min_pixels = data_args.min_pixels
        self.data_args.image_processor.size["longest_edge"] = data_args.max_pixels
        self.data_args.image_processor.size["shortest_edge"] = data_args.min_pixels
        rank0_print(f"Resize images between {data_args.min_pixels} to {data_args.max_pixels}")

        self.mm_samples = [
            i for i in range(len(self.list_data_root)) if self.check_mm_input(i)
        ]
        self.text_samples = [
            i for i in range(len(self.list_data_root)) if not self.check_mm_input(i)
        ]

    def load_json(self, path, parse_line=False):
        try:
            if path.endswith(".jsonl"):
                if "s3://" in path:
                    ann_bytes = self.tcs_loader.client.get(path)
                    items = ann_bytes.decode("utf-8").split("\n")
                else:
                    with open(path, "r") as f:
                        items = f.readlines()
                data_list = [
                    json.loads(line) if parse_line else line
                    for line in items
                    if line.strip() != ""
                ]
            elif path.endswith(".json"):
                if "s3://" in path:
                    ann_bytes = self.tcs_loader.client.get(path)
                    data_list = json.loads(ann_bytes.decode("utf-8"))
                else:
                    with open(path, "r") as f:
                        data_list = json.loads(f.read())
            else:
                raise ValueError(f"Unsupported file type: {path}")
        except Exception as e:
            print(f"Failed to load json file {path}. Exception:", e)
            raise ValueError(f"Failed to load json file {path}")
        return data_list

    def load_ann(self, data_meta):
        json_path = data_meta.get("json_path")
        sampling_strategy = data_meta.get("sampling_strategy", "all")
        images_folder = data_meta.get("images_folder", None)
        if images_folder and images_folder.strip() == "":
            images_folder = None

        sampling_number = None

        rank0_print(f"Loading {json_path} with {sampling_strategy} sampling strategy")

        cur_data_dict = self.load_json(json_path, True)

        if ":" in sampling_strategy:
            sampling_strategy, sampling_number = sampling_strategy.split(":")
            if "%" in sampling_number:
                sampling_number = round(
                    int(sampling_number.split("%")[0]) * len(cur_data_dict) / 100
                )
            else:
                sampling_number = ast.literal_eval(sampling_number)

        # Apply the sampling strategy
        if sampling_strategy == "first" and sampling_number is not None:
            sampling_number = int(sampling_number)
            cur_data_dict = cur_data_dict[:sampling_number]
        elif sampling_strategy == "end" and sampling_number is not None:
            sampling_number = int(sampling_number)
            cur_data_dict = cur_data_dict[-sampling_number:]
        elif sampling_strategy == "random" and sampling_number is not None:
            # random.shuffle(cur_data_dict)
            self.rng.shuffle(cur_data_dict)
            cur_data_dict = cur_data_dict[:sampling_number]
        elif sampling_strategy == "repeat" and sampling_number is not None:
            fractional_number = round(sampling_number * len(cur_data_dict)) % len(
                cur_data_dict
            )
            cur_data_dict = (
                cur_data_dict * math.floor(sampling_number)
                + cur_data_dict[:fractional_number]
            )

        rank0_print(f"Loaded {len(cur_data_dict)} samples from {json_path}")
        return cur_data_dict, images_folder

    def __len__(self):
        return len(self.list_data_dict)

    @property
    def lengths(self):
        length_list = []
        for sample in self.list_data_dict:
            img_tokens = 128 if "image" in sample else 0
            length_list.append(
                sum(len(conv["value"].split()) for conv in sample["conversations"])
                + img_tokens
            )
        return length_list

    @property
    def modality_lengths(self):
        length_list = []
        for sample in self.list_data_dict:
            cur_len = sum(
                len(conv["value"].split()) for conv in sample["conversations"]
            )
            cur_len = (
                cur_len if ("image" in sample) or ("video" in sample) else -cur_len
            )
            length_list.append(cur_len)
        return length_list

    @property
    def pre_calculated_length(self):
        if "num_tokens" in self.list_data_dict[0]:
            length_list = [sample["num_tokens"] for sample in self.list_data_dict]
            return np.array(length_list)
        else:
            print("No pre-calculated length available.")
            return np.array([1] * len(self.list_data_dict))

    def check_mm_input(self, idx: int) -> bool:
        """
        Check if the input at the given index is multimodal.
        """
        return self.list_data_root[idx] and self.list_data_dict[idx].get("image", None)

    def process_image_unified(self, image_file):
        processor = copy.deepcopy(self.data_args.image_processor)
        # image = Image.open(image_file).convert("RGB")
        image = load_image(image_file, tcs_loader=self.tcs_loader)

        visual_processed = processor.preprocess(image, return_tensors="pt")
        image_tensor = visual_processed["pixel_values"]
        if isinstance(image_tensor, List):
            image_tensor = image_tensor[0]
        grid_thw = visual_processed["image_grid_thw"][0]
        return image_tensor, grid_thw, image.size

    def process_video(self, video_file):
        if not os.path.exists(video_file):
            print(f"File not exist: {video_file}")
        vr = VideoReader(video_file, num_threads=4)
        total_frames = len(vr)
        avg_fps = vr.get_avg_fps()
        video_length = total_frames / avg_fps
        interval = getattr(self.data_args, "base_interval", 4)

        num_frames_to_sample = round(video_length / interval)
        video_min_frames = getattr(self.data_args, "video_min_frames", 4)
        video_max_frames = getattr(self.data_args, "video_max_frames", 8)

        target_frames = min(
            max(num_frames_to_sample, video_min_frames), video_max_frames
        )
        frame_idx = np.linspace(0, total_frames - 1, target_frames, dtype=int)
        frame_idx = np.unique(frame_idx)
        video = vr.get_batch(frame_idx).asnumpy()
        fps = len(frame_idx) / video_length
        processor = copy.deepcopy(self.data_args.image_processor)
        processor.max_pixels = self.data_args.video_max_frame_pixels
        processor.min_pixels = self.data_args.video_min_frame_pixels
        processor.size["longest_edge"] = processor.max_pixels
        processor.size["shortest_edge"] = processor.min_pixels
        video_processed = processor.preprocess(
            images=None, videos=video, return_tensors="pt"
        )
        video_tensor = video_processed["pixel_values_videos"]
        grid_thw = video_processed["video_grid_thw"][0]
        second_per_grid_ts = [
            self.data_args.image_processor.temporal_patch_size / fps
        ] * len(grid_thw)
        return video_tensor, grid_thw, second_per_grid_ts

    def transform_coordinates(self, text, new_image_size):
        # 定义正则表达式模式，匹配x和y的值
        pattern = r"(x=|y=)(0?\.\d+)"

        def replace_match_1(match):
            prefix = match.group(1)  # x= 或 y=
            value = float(match.group(2))
            # 根据x或y乘以不同的参数
            if prefix == "x=":
                return f"{prefix}{round(value * new_image_size[0])}"
            else:
                return f"{prefix}{round(value * new_image_size[1])}"

        point_pattern = r"\[(0?\.\d+),\s*(0?\.\d+)\]"

        def replace_match_2(match):
            bbox_or_point = list(map(float, match.groups()))
            if len(bbox_or_point) == 4:
                ori_x1 = round(bbox_or_point[0] * new_image_size[0])
                ori_y1 = round(bbox_or_point[1] * new_image_size[1])
                ori_x2 = round(bbox_or_point[2] * new_image_size[0])
                ori_y2 = round(bbox_or_point[3] * new_image_size[1])
                return json.dumps([ori_x1, ori_y1, ori_x2, ori_y2], ensure_ascii=False)
            elif len(bbox_or_point) == 2:
                ori_x = round(bbox_or_point[0] * new_image_size[0])
                ori_y = round(bbox_or_point[1] * new_image_size[1])
                return json.dumps([ori_x, ori_y])
            else:
                raise ValueError("Invalid match length")

        # 对每条命令应用替换
        transformed_text = re.sub(pattern, replace_match_1, text)
        transformed_text = re.sub(point_pattern, replace_match_2, transformed_text)
        return transformed_text

    def preprocess_conversation_format(
        self,
        sources,
        conv_style: str,
        image_size: tuple | list,
    ) -> Dict:
        conversations = sources[0]
        if len(conversations) < 2:
            return []

        conv_temp = get_conv_template(conv_style)
        sys_prompt = []
        if "system" != conversations[0]["from"]:
            if conv_style in [
                "chat",
                "internvl2_5",
                "internvl3",
                "internvl_grounding",
                "internvl_referring",
            ]:
                sys_prompt = [
                    {
                        "from": "system",
                        "value": "You are a helpful assistant.",
                    }
                ]
            else:
                sys_prompt = [
                    {
                        "from": "system",
                        "value": conv_temp.system_message,
                    }
                ]
            conversations = sys_prompt + conversations

        if len(image_size) == 1:
            new_image_size = get_image_size(
                image_size[0],
                self.data_args.min_pixels,
                self.data_args.max_pixels,
            )
        else:
            new_image_size = None

        new_conversations = []
        for conv in conversations:
            msg = conv["value"]

            if conv_style.startswith("internvl"):
                if (
                    conv_style.startswith(("internvl_grounding", "internvl_referring"))
                    and conv["from"] != "system"
                ):
                    msg = format_grounding_internvl2qwenvl(
                        msg,
                        conv["from"],
                        image_size,
                        new_image_size,
                    )

                # process GUI data
                if (
                    "_grounding_v" in conv_style
                    or "_navigation_v" in conv_style
                    or "_planning_cot_v" in conv_style
                ):
                    if conv["from"] == "gpt":
                        assert (
                            "<action>" in msg and "</action>" in msg
                        ), f"Message {msg} does not contain <action> and </action> tags"
                        if not self.coord_norm and new_image_size is not None:
                            msg = self.transform_coordinates(msg, new_image_size)

            new_conversations.append(
                {
                    "from": conv["from"],
                    "value": msg,
                }
            )
        if int(os.environ.get("DEBUG", "0")) > 0:
            rank0_print(conversations)
            print("-" * 40)
            rank0_print(new_conversations)
            print("-" * 40)
            print(f"raw_image_size: {image_size}, new_image_size: {new_image_size}")
            print("*" * 40)
        return [new_conversations]

    def __getitem__(self, i) -> Dict[str, torch.Tensor]:
        num_base_retries = 1
        num_final_retries = 30

        # try the current sample first
        for attempt_idx in range(num_base_retries):
            try:
                sample = self._get_item(i)
                return sample
            except Exception as e:
                import traceback

                traceback.print_exc()
                # sleep 1s in case it is a cloud disk issue
                print(
                    f"[Try #{attempt_idx}] Failed to fetch sample {i} in {self.list_data_root[i]}. Exception: {e}"
                )
                print(f"Problematic sample: {self.list_data_dict[i]}")
                # time.sleep(1)

        next_index = i
        # try other samples, in case it is file corruption issue
        for attempt_idx in range(num_final_retries):
            try:
                if self.check_mm_input(i):
                    next_index = self.rng.choice(self.mm_samples)
                else:
                    next_index = self.rng.choice(self.text_samples)
                # sample_idx = random.choice(range(len(self)))
                if (
                    self.list_data_root[next_index] is None
                    and self.list_data_root[i] is None
                ):
                    sample = self._get_item(next_index)
                elif (
                    self.list_data_root[next_index] is not None
                    and self.list_data_root[i] is not None
                ):
                    sample = self._get_item(next_index)
                else:
                    raise ValueError("The data root is not consistent.")
                return sample
            except Exception as e:
                # no need to sleep
                import traceback

                traceback.print_exc()
                print(
                    f"[Try other #{attempt_idx}] Failed to fetch sample {next_index} in {self.list_data_root[next_index]}. Exception: {e}"
                )
                print(f"Problematic sample: {self.list_data_dict[next_index]}")
        try:
            sample = self._get_item(i)
            return sample
        except Exception as e:
            raise e

    def try_to_fix_image_tokens(self, image_file, sources):
        image_tokens = 0
        first_user_input_idx = -1
        for idx, conv in enumerate(sources[0]["conversations"]):
            if conv["from"] in ("human", "user"):
                image_tokens += conv["value"].count("<image>")
                conv["value"] = conv["value"].replace("<image>", "")
                first_user_input_idx = (
                    idx if first_user_input_idx == -1 else first_user_input_idx
                )

        if image_tokens == 0 and first_user_input_idx != -1:
            msg = sources[0]["conversations"][first_user_input_idx]["value"]
            msg = "<image>" * len(image_file) + msg
            sources[0]["conversations"][first_user_input_idx]["value"] = msg
            rank0_print("Fixed image tokens in the conversation")
            return sources
        if len(image_file) == 1 and image_tokens > 1:
            msg = sources[0]["conversations"][first_user_input_idx]["value"]
            msg = "<image>" * len(image_file) + msg
            sources[0]["conversations"][first_user_input_idx]["value"] = msg
            rank0_print("Fixed image tokens in the conversation")
            return sources

        return None

    def _get_item(self, i) -> Dict[str, torch.Tensor]:
        sources = self.list_data_dict[i]
        if isinstance(i, int):
            sources = [sources]
        assert len(sources) == 1, "Don't know why it is wrapped to a list"  # FIXME

        video = None
        if "image" in sources[0] and sources[0]["image"] is not None:
            image_folder = self.list_data_root[i]
            image_file = self.list_data_dict[i]["image"]
            image_wh = self.list_data_dict[i].get("image_wh", [])
            sizes = image_wh + [
                [
                    self.list_data_dict[i].get("height", 100),
                    self.list_data_dict[i].get("width", 100),
                ]
            ]
            sizes = reduce(lambda x, y: x + y, sizes)
            if min(sizes) < 28:
                raise ValueError(
                    f"Image size {sizes} is too small. Minimum size is 28."
                )
            if isinstance(image_file, str):
                image_file = [
                    image_file,
                ]
            if len(image_file) >= 10:
                raise ValueError(f"Image file (#{len(image_file)}) list is too long.")
            if (
                len(image_file) == 0
                or image_file[0] is None
                or image_file[0].strip() == ""
            ):
                raise ValueError(
                    f"Image file list is empty for {self.list_data_dict[i]}"
                )

            if not self.check_image_token(image_file, sources):
                sources = self.try_to_fix_image_tokens(image_file, sources)
                if sources is None or len(sources) == 0:
                    raise ValueError(
                        f"Number of image tokens {image_file} does not match number of images {sources}"
                    )
            image_file = [os.path.join(image_folder, file) for file in image_file]
            results = [self.process_image_unified(file) for file in image_file]
            image, grid_thw, image_size = zip(*results)

            grid_thw_merged = copy.deepcopy(grid_thw)
            if not isinstance(grid_thw, Sequence):
                grid_thw_merged = [grid_thw_merged]
                grid_thw = [grid_thw]
            grid_thw_merged = [
                merged_thw.prod() // self.data_args.image_processor.merge_size**2
                for merged_thw in grid_thw_merged
            ]
            conv_style = self.data_args.conv_style
            if len(self.list_conv_style) > i and self.list_conv_style[i] is not None:
                conv_style = self.list_conv_style[i]
            sources = copy.deepcopy([e["conversations"] for e in sources])
            if conv_style.startswith(("internvl", "general")):
                sources = self.preprocess_conversation_format(
                    sources, conv_style, image_size
                )
            data_dict = preprocess_qwen_2_visual(
                sources, self.tokenizer, grid_thw=grid_thw_merged, visual_type="image"
            )
            position_ids, _ = self.get_rope_index(
                self.data_args.image_processor.merge_size,
                data_dict["input_ids"],
                torch.stack(grid_thw, dim=0),
            )
        elif "video" in sources[0]:
            video_file = self.list_data_dict[i]["video"]
            video_folder = self.list_data_root[i]
            if isinstance(video_file, List):
                if len(video_file) > 1:
                    video_file = [
                        os.path.join(video_folder, file) for file in video_file
                    ]
                    results = [self.process_video(file) for file in video_file]
                    video, grid_thw, second_per_grid_ts = zip(*results)
                else:
                    video_file = video_file[0]
                    video_file = os.path.join(video_folder, video_file)
                    video, grid_thw, second_per_grid_ts = self.process_video(video_file)
                    video = [video]
            else:
                video_file = os.path.join(video_folder, video_file)
                video, grid_thw, second_per_grid_ts = self.process_video(video_file)
                video = [video]
            grid_thw_merged = copy.deepcopy(grid_thw)
            if not isinstance(grid_thw, Sequence):
                grid_thw_merged = [grid_thw_merged]
                grid_thw = [grid_thw]
            grid_thw_merged = [
                merged_thw.prod() // self.data_args.image_processor.merge_size**2
                for merged_thw in grid_thw_merged
            ]
            sources = copy.deepcopy([e["conversations"] for e in sources])
            data_dict = preprocess_qwen_2_visual(
                sources, self.tokenizer, grid_thw=grid_thw_merged, visual_type="video"
            )
            position_ids, _ = self.get_rope_index(
                self.data_args.image_processor.merge_size,
                data_dict["input_ids"],
                video_grid_thw=torch.stack(grid_thw, dim=0),
                second_per_grid_ts=second_per_grid_ts,
            )
        else:
            grid_thw_merged = None
            sources = copy.deepcopy([e["conversations"] for e in sources])
            data_dict = preprocess_qwen_2_visual(
                sources, self.tokenizer, grid_thw=grid_thw_merged
            )
            position_ids = (
                torch.arange(0, data_dict["input_ids"].size(1))
                .view(1, -1)
                .unsqueeze(0)
                .expand(3, -1, -1)
            )

        if isinstance(i, int):
            data_dict = dict(
                input_ids=data_dict["input_ids"][0],
                labels=data_dict["labels"][0],
                position_ids=position_ids,
            )

        if (
            "image" in self.list_data_dict[i]
            and self.list_data_dict[i]["image"] is not None
        ):
            data_dict["pixel_values"] = image
            data_dict["image_grid_thw"] = grid_thw
        # video exist in the data
        elif (
            "video" in self.list_data_dict[i]
            and self.list_data_dict[i]["image"] is not None
        ):
            data_dict["pixel_values_videos"] = video
            data_dict["video_grid_thw"] = grid_thw
        return data_dict

    def check_image_token(self, image_files, sources):
        image_tokens = 0
        for conv in sources[0]["conversations"]:
            if conv["from"] in ("human", "user"):
                image_tokens += conv["value"].count("<image>")

        num_images = len(image_files)
        if image_tokens != num_images:
            rank0_print(
                f"Number of image tokens {image_tokens} does not match number of images {num_images}"
            )
            return False
        return True


def pad_and_cat(tensor_list):
    max_length = max(tensor.shape[2] for tensor in tensor_list)

    padded_tensors = []
    for tensor in tensor_list:
        pad_length = max_length - tensor.shape[2]
        padded_tensor = torch.nn.functional.pad(tensor, (0, pad_length), "constant", 1)
        padded_tensors.append(padded_tensor)

    stacked_tensor = torch.cat(padded_tensors, dim=1)

    return stacked_tensor


@dataclass
class DataCollatorForSupervisedDataset(object):
    """Collate examples for supervised fine-tuning."""

    tokenizer: transformers.PreTrainedTokenizer

    def __call__(self, instances: Sequence[Dict]) -> Dict[str, torch.Tensor]:
        input_ids, labels, position_ids = tuple(
            [instance[key] for instance in instances]
            for key in ("input_ids", "labels", "position_ids")
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = (
                0  # This gets the best result. Don't know why.
            )
        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids, batch_first=True, padding_value=self.tokenizer.pad_token_id
        )
        labels = torch.nn.utils.rnn.pad_sequence(
            labels, batch_first=True, padding_value=IGNORE_INDEX
        )
        position_ids = pad_and_cat(position_ids)
        input_ids = input_ids[:, : self.tokenizer.model_max_length]
        labels = labels[:, : self.tokenizer.model_max_length]
        position_ids = position_ids[:, : self.tokenizer.model_max_length]
        batch = dict(
            input_ids=input_ids,
            labels=labels,
            attention_mask=input_ids.ne(self.tokenizer.pad_token_id),
        )
        images = list(
            itertools.chain(
                *(
                    instance["pixel_values"]
                    for instance in instances
                    if "pixel_values" in instance
                )
            )
        )
        videos = list(
            itertools.chain(
                *(
                    instance["pixel_values_videos"]
                    for instance in instances
                    if "pixel_values_videos" in instance
                )
            )
        )
        if len(images) != 0:
            concat_images = torch.cat([image for image in images], dim=0)
            grid_thw = list(
                itertools.chain(
                    *(
                        instance["image_grid_thw"]
                        for instance in instances
                        if "image_grid_thw" in instance
                    )
                )
            )
            grid_thw = torch.stack(grid_thw, dim=0)
        else:
            concat_images = None
            grid_thw = None

        if len(videos) != 0:
            concat_videos = torch.cat([video for video in videos], dim=0)
            video_grid_thw = list(
                itertools.chain(
                    *(
                        instance["video_grid_thw"]
                        for instance in instances
                        if "video_grid_thw" in instance
                    )
                )
            )
            video_grid_thw = torch.stack(video_grid_thw, dim=0)
        else:
            concat_videos = None
            video_grid_thw = None

        batch["pixel_values"] = concat_images
        batch["image_grid_thw"] = grid_thw
        batch["pixel_values_videos"] = concat_videos
        batch["video_grid_thw"] = video_grid_thw
        batch["position_ids"] = position_ids
        return batch


@dataclass
class FlattenedDataCollatorForSupervisedDataset(DataCollatorForSupervisedDataset):
    """Collate examples into packed sequence with multi-modal support."""

    tokenizer: transformers.PreTrainedTokenizer

    def __call__(self, instances: Sequence[Dict]) -> Dict[str, torch.Tensor]:
        input_ids, labels, position_ids = tuple(
            [instance[key] for instance in instances]
            for key in ("input_ids", "labels", "position_ids")
        )
        # Filter the input_ids and labels based on the model max length
        for i, _input_ids in enumerate(input_ids):
            if len(_input_ids) > self.tokenizer.model_max_length:
                input_ids[i] = input_ids[i][: self.tokenizer.model_max_length]
                labels[i] = labels[i][: self.tokenizer.model_max_length]
                position_ids[i] = position_ids[i][
                    :, :, : self.tokenizer.model_max_length
                ]

        seq_lens = torch.tensor(
            [0] + [len(seq) for seq in input_ids], dtype=torch.int32
        )

        cumsum_seq_lens = torch.cumsum(seq_lens, dim=0, dtype=torch.int32)
        if cumsum_seq_lens[-1] > self.tokenizer.model_max_length:
            max_idx = (
                torch.searchsorted(
                    cumsum_seq_lens, self.tokenizer.model_max_length, right=True
                )
                - 1
            )

            rank0_print(
                f"Token indices sequence length is longer than the specified maximum sequence "
                f"length ({cumsum_seq_lens[-1]} > {self.tokenizer.model_max_length}) for "
                f"{len(instances)} sample(s). Truncating to {cumsum_seq_lens[max_idx]} with {max_idx} samples."
            )
            cumsum_seq_lens = cumsum_seq_lens[: max_idx + 1]
            input_ids = input_ids[:max_idx]
            labels = labels[:max_idx]
            position_ids = position_ids[:max_idx]
            instances = instances[:max_idx]

        input_ids = torch.cat(input_ids, dim=0)
        labels = torch.cat(labels, dim=0)
        position_ids = torch.cat(position_ids, dim=2)

        batch = dict(
            input_ids=input_ids.unsqueeze(0),
            labels=labels.unsqueeze(0),
            attention_mask=cumsum_seq_lens,
            position_ids=position_ids,
        )

        images = list(
            itertools.chain(
                *(
                    instance["pixel_values"]
                    for instance in instances
                    if "pixel_values" in instance
                )
            )
        )
        videos = list(
            itertools.chain(
                *(
                    instance["pixel_values_videos"]
                    for instance in instances
                    if "pixel_values_videos" in instance
                )
            )
        )
        if len(images) != 0:
            concat_images = torch.cat([image for image in images], dim=0)
            grid_thw = list(
                itertools.chain(
                    *(
                        instance["image_grid_thw"]
                        for instance in instances
                        if "image_grid_thw" in instance
                    )
                )
            )
            grid_thw = torch.stack(grid_thw, dim=0)
        else:
            concat_images = None
            grid_thw = None

        if len(videos) != 0:
            concat_videos = torch.cat([video for video in videos], dim=0)
            video_grid_thw = list(
                itertools.chain(
                    *(
                        instance["video_grid_thw"]
                        for instance in instances
                        if "video_grid_thw" in instance
                    )
                )
            )
            video_grid_thw = torch.stack(video_grid_thw, dim=0)
        else:
            concat_videos = None
            video_grid_thw = None

        batch["pixel_values"] = concat_images
        batch["image_grid_thw"] = grid_thw
        batch["pixel_values_videos"] = concat_videos
        batch["video_grid_thw"] = video_grid_thw
        return batch


def make_supervised_data_module(
    tokenizer: transformers.PreTrainedTokenizer, data_args
) -> Dict:
    """Make dataset and collator for supervised fine-tuning."""
    train_dataset = LazySupervisedDataset(tokenizer=tokenizer, data_args=data_args)
    if data_args.data_flatten:
        data_collator = FlattenedDataCollatorForSupervisedDataset(tokenizer=tokenizer)
        return dict(
            train_dataset=train_dataset, eval_dataset=None, data_collator=data_collator
        )
    data_collator = DataCollatorForSupervisedDataset(tokenizer=tokenizer)
    return dict(
        train_dataset=train_dataset, eval_dataset=None, data_collator=data_collator
    )


def make_supervised_data_module_1(
    tokenizer: transformers.PreTrainedTokenizer, data_args
) -> Dict:
    """Make dataset and collator for supervised fine-tuning."""
    ds_collections = json.loads(open(data_args.meta_path).read())
    train_dataset = []
    for ds_idx, ds_name in enumerate(ds_collections.keys()):
        dataset = LazySupervisedDataset(
            tokenizer=tokenizer,
            dataset_meta=ds_collections[ds_name],
            data_args=data_args,
        )
        train_dataset.append(dataset)
    train_dataset = ConcatDataset(train_dataset)
    # train_dataset = LazySupervisedDataset(tokenizer=tokenizer, data_args=data_args)
    if data_args.data_flatten:
        data_collator = FlattenedDataCollatorForSupervisedDataset(tokenizer=tokenizer)
        return dict(
            train_dataset=train_dataset, eval_dataset=None, data_collator=data_collator
        )
    data_collator = DataCollatorForSupervisedDataset(tokenizer=tokenizer)
    return dict(
        train_dataset=train_dataset, eval_dataset=None, data_collator=data_collator
    )


if __name__ == "__main__":
    pass
