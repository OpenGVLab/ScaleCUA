import os
if "TMPDIR" not in os.environ:
    tmp_dir = "./tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir, exist_ok=True)
    os.environ["TMPDIR"] = tmp_dir
import os.path as osp
import argparse
from ast import literal_eval
import json
import time
import re
from typing import Union

import gradio as gr
import requests
import random
from filelock import FileLock
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
# from qwen_vl_utils import smart_resize
from core.constants import *

from core.utils import (
    build_logger,
    server_error_msg,
    violates_moderation,
    moderation_msg,
    get_log_filename,
    video2base64,
    IMG_EXT,
    VID_EXT,
    # display_result,
    url_to_base64,
    image2base64,
    load_image_from_base64,
    base64_to_bytes,
    smart_resize,
)
import core.record as record
from core.record import Record

logger = build_logger("gradio_web_server", "gradio_web_server.log")

headers = {"User-Agent": "ScaleCUA-Chat Client"}

get_window_url_params = """
function() {
    const params = new URLSearchParams(window.location.search);
    url_params = Object.fromEntries(params);
    console.log(url_params);
    return url_params;
    }
"""

# model_name = "vlm"

# min_pixels = 512*28*28
# max_pixels = 2048*28*28

no_change_btn = gr.Button()
enable_btn = gr.Button(interactive=True)
disable_btn = gr.Button(interactive=False)


def write2file(path, content):
    lock = FileLock(f"{path}.lock")
    with lock:
        with open(path, "a") as fout:
            fout.write(content)


def sort_models(models):
    def custom_sort_key(model_name):
        # InternVL-Chat-V1-5 should be the first item
        if model_name == "InternVL2":
            return (1, model_name)  # 1 indicates highest precedence
        else:
            return (0, model_name)  # 0 indicates normal order

    models.sort(key=custom_sort_key, reverse=True)
    try:  # We have five InternVL-Chat-V1-5 models, randomly choose one to be the first
        first_three = models[:4]
        random.shuffle(first_three)
        models[:4] = first_three
    except:
        pass
    return models


def get_model_list():
    """
    logger.info(f"Call `get_model_list`")
    ret = requests.post(args.controller_url + "/refresh_all_workers")
    logger.info(f"status_code from `get_model_list`: {ret.status_code}")
    assert ret.status_code == 200
    ret = requests.post(args.controller_url + "/list_models")
    logger.info(f"status_code from `list_models`: {ret.status_code}")
    models = ret.json()["models"]
    models = sort_models(models)

    logger.info(f"Models (from {args.controller_url}): {models}")
    """
    if args.model_name is not None:
        logger.info(f"Models: {args.model_name}")
        return [args.model_name]
    else:
        model_worker_url = osp.join(args.model_worker_url, "v1/models")
        model_info = requests.get(model_worker_url).json()["data"]
        models = [item["id"] for item in model_info]
        logger.info(f"Models (from {model_worker_url}): {models}")
        
    return models



def init_state(state=None):
    if state is not None:
        del state
    return Record()


def convert_examples(original_examples):
    """
    Convert examples from [image_path, text, mode] format into the
    nested format used by gr.Examples with MultimodalTextbox.
    
    Input format:
        [
            ["./examples/mac_desktop_1.jpg", "Click on 飞书", "grounding"],
            ["./examples/solitaire.png", "Play the solitaire collection", "grounding"],
            ...
        ]

    Output format:
        [
            [
                {
                    "files": ["./examples/mac_desktop_1.jpg"],
                    "text": "Click on 飞书",
                }
            ],
            [
                {
                    "files": ["./examples/solitaire.png"],
                    "text": "Play the solitaire collection",
                }
            ],
            ...
        ]
    """
    converted = []
    for img_path, text, mode in original_examples:
        item = [
            {
                "files": [img_path],
                "text": text,
            }
        ]
        converted.append(item)
    return converted


# Create example images for GUI grounding
def prepare_grounding_examples():
    examples_dir = "examples"
    os.makedirs(examples_dir, exist_ok=True)

    # Example list - store image paths, text and modes separately
    examples = [
        ["./examples/mac_screenshot_1.jpg", "Click on 飞书", "grounding"],
        ["./examples/solitaire.png", "Play the solitaire collection", "grounding"],
        ["./examples/weather_ui.png", "Open map", "grounding"],
        ["./examples/football_live.png", "click team 1 win", "grounding"],
        ["./examples/windows_panel.png", "switch to documents", "grounding"],
        ["./examples/paint_3d.png", "rotate left", "grounding"],
        ["./examples/finder.png", "view files from airdrop", "grounding"],
        ["./examples/amazon.jpg", "Search bar at the top of the page", "grounding"],
        ["./examples/semantic.jpg", "Home", "grounding"],
        ["./examples/accweather.jpg", "Select May", "grounding"],
        ["./examples/arxiv.jpg", "Home", "grounding"],
        ["./examples/health.jpg", "text labeled by 2023/11/26", "grounding"],
        ["./examples/ios_setting.png", "Turn off Do not disturb.", "grounding"],
        ["./examples/vscode.png", "Open the 'debug.sh' file to modify the content.", "grounding"]
    ]

    # Check if example images exist
    valid_examples = []
    for example in examples:
        if os.path.exists(example[0]):
            valid_examples.append(example)
        else:
            logger.warning(f"Example image does not exist: {example[0]}")

    valid_examples = convert_examples(valid_examples)
    return valid_examples


# Create example images for GUI Planning
def prepare_planning_examples():
    examples_dir = "examples"
    os.makedirs(examples_dir, exist_ok=True)

    # Example list - store image paths, text and modes separately
    examples = []

    # Check if example images exist
    valid_examples = []
    for example in examples:
        if os.path.exists(example[0]):
            valid_examples.append(example)
        else:
            logger.warning(f"Example image does not exist: {example[0]}")

    valid_examples = convert_examples(valid_examples)
    return valid_examples


# Create example images for chat
def prepare_chat_examples():
    examples_dir = "examples"
    os.makedirs(examples_dir, exist_ok=True)

    # Example list - store image paths, text and modes separately
    examples = [
        ["./examples/mac_screenshot_1.jpg", "Please describe this image", "chat"],
        ["./examples/math_1.png", "请根据图片内容，计算WiFi密码", "chat"],
        ["./examples/1-2.png", "Please generate Python code based on the flow chart in the image.", "chat"],
        ["./examples/windows_panel.png", "请检测Paint的bounding box，并以json格式输出", "chat"],
        ["./examples/menu2.png", "Please recognize all words in the image and then translate them into English", "chat"],
    ]

    # Check if example images exist
    valid_examples = []
    for example in examples:
        if os.path.exists(example[0]):
            valid_examples.append(example)
        else:
            logger.warning(f"Example image does not exist: {example[0]}")

    valid_examples = convert_examples(valid_examples)
    return valid_examples


def draw_bbox_on_image(image, bbox_dict, input_height, input_width):
    draw = ImageDraw.Draw(image)
    is_draw_bbox = False
    if type(bbox_dict) == dict:
        new_bbox_dict = []
        if "bbox_2d" in bbox_dict and "label" in bbox_dict:
            new_bbox_dict.append(bbox_dict)
        else:
            for key, value in bbox_dict.items():
                if isinstance(value, list):
                    new_results.extend(value)
            
        bbox_dict = new_bbox_dict
        
    width, height = image.size
    for result in bbox_dict:
        line_width = max(1, int(min(width, height) / 200))
        random_color = (
            random.randint(0, 128),
            random.randint(0, 128),
            random.randint(0, 128),
        )
        if "bbox_2d" not in result:
            continue
        
        coordinates = result["bbox_2d"]
        copy_result = result.copy()
        copy_result.pop("bbox_2d")
        category_name = result.get("label", result.get("text_content", str(list(copy_result.values()))))
        coordinates = [
            (
                round(float(x[0]) / input_width * width),
                round(float(x[1]) / input_height * height),
                round(float(x[2]) / input_width * width),
                round(float(x[3]) / input_height * height),
            )
            for x in coordinates
        ]
        for box in coordinates:
            draw.rectangle(box, outline=random_color, width=line_width)
            font = ImageFont.truetype("assets/SimHei.ttf", int(20 * line_width / 2))
            text_size = font.getbbox(category_name)
            text_width, text_height = (
                text_size[2] - text_size[0],
                text_size[3] - text_size[1],
            )
            text_position = (box[0], max(0, box[1] - text_height))
            draw.rectangle(
                [
                    text_position,
                    (text_position[0] + text_width, text_position[1] + text_height),
                ],
                fill=random_color,
            )
            draw.text(text_position, category_name, fill="white", font=font)
            is_draw_bbox = True
    return image, is_draw_bbox
            

def find_bounding_boxes(state, response):
    if "<ref>" in response and "</ref>" in response:
        pattern = re.compile(r"<ref>\s*(.*?)\s*</ref>\s*<box>\s*(\[\[.*?\]\])\s*</box>")
        matches = pattern.findall(response)
    else:
        pattern = re.compile(r"<box>\s*(\[\[.*?\]\])\s*</box>")
        matches = pattern.findall(response)
        matches = [("", match) for match in matches]
    results = []
    for match in matches:
        # results.append((match[0], eval(match[1])))
        results.append({"label": match[0], "bbox_2d": literal_eval(match[1])})

    # returned_image = None
    latest_image_path = state.get_images(source=state.USER)[-1]
    returned_image = Image.open(latest_image_path).convert("RGB")
    # returned_image = latest_image.copy()
    width, height = returned_image.size
    input_height, input_width = smart_resize(
        height, width, min_pixels=record.min_pixels, max_pixels=record.max_pixels
    )
    returned_image, is_drawing_bbox = draw_bbox_on_image(returned_image, results, input_height, input_width)

    if is_drawing_bbox:
        return returned_image
    return None


def find_bounding_boxes_qwenvl(state, response):
    pattern = re.compile(r"```json\n([\s\S]*?)\n```")
    match = re.search(pattern, response)
    results = []
    if match:
        try:
            results = literal_eval(match.group(1).strip())
        except Exception as e:
            logger.error(f"Error parsing JSON: {match.group(1).strip()}")
            return None, False
    
    # returned_image = None
    latest_image_path = state.get_images(source=state.USER)[-1]
    returned_image = Image.open(latest_image_path).convert("RGB")
    width, height = returned_image.size
    input_height, input_width = smart_resize(
        height, width, min_pixels=record.min_pixels, max_pixels=record.max_pixels
    )
    if type(results) == dict:
        new_results = []
        if "bbox_2d" in results and "label" in results:
            new_results.append(results)
        else:
            for key, value in results.items():
                if isinstance(value, list):
                    new_results.extend(value)
        results = new_results

    for result in results:
        if "bbox_2d" in result and type(result["bbox_2d"][0]) == int:
            result["bbox_2d"] = [result["bbox_2d"]]
    
    returned_image, is_drawing_bbox = draw_bbox_on_image(returned_image, results, input_height, input_width)
    
    if is_drawing_bbox:
        return returned_image
    return None


def draw_point_area(image, point):
    x, y = round(point[0] * image.width), round(point[1] * image.height)
    draw = ImageDraw.Draw(image)
    x_size = 25
    draw.line([(x - x_size, y - x_size), (x + x_size, y + x_size)], fill="red", width=8)
    draw.line([(x - x_size, y + x_size), (x + x_size, y - x_size)], fill="red", width=8)
    return image


def parse_point(output_text, image):
    w, h = image.size
    new_h, new_w = smart_resize(h, w, min_pixels=record.min_pixels, max_pixels=record.max_pixels)

    # Pattern 1: Match x=number, y=number format
    pattern1 = r"x=(\d+\.?\d*),\s*y=(\d+\.?\d*)"
    match = re.search(pattern1, output_text)
    if match:
        click_xy = [float(match.group(1)) / new_w, float(match.group(2)) / new_h]
        result_image = draw_point_area(image.copy(), click_xy)
        return result_image, click_xy

    # Pattern 2: Match [number,number,number,number] format (x1,y1,x2,y2)
    pattern2 = r"\[(\d+\.?\d*),\s*(\d+\.?\d*),\s*(\d+\.?\d*),\s*(\d+\.?\d*)\]"
    match = re.search(pattern2, output_text)
    if match:
        # Extract coordinates and calculate center point
        x1 = float(match.group(1))
        y1 = float(match.group(2))
        x2 = float(match.group(3))
        y2 = float(match.group(4))

        # Calculate center point
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        # Convert to relative coordinates
        click_xy = [center_x / new_w, center_y / new_h]
        result_image = draw_point_area(image.copy(), click_xy)
        return result_image, click_xy

    # If no coordinates are matched, return the original image
    return None, None


def load_demo(url_params, request: gr.Request = None):
    if not request:
        logger.info(f"load_demo. ip: {request.client.host}. params: {url_params}")

    dropdown_update = gr.Dropdown(visible=True)
    if "model" in url_params:
        model = url_params["model"]
        if model in models:
            dropdown_update = gr.Dropdown(value=model, visible=True)

    state = init_state()
    return state, dropdown_update


def load_demo_refresh_model_list(request: gr.Request):
    if request:
        logger.info(f"load_demo. ip: {request.client.host}")
    models = get_model_list()
    state = init_state()
    dropdown_update = gr.Dropdown(
        choices=models, value=models[0] if len(models) > 0 else ""
    )
    return state, dropdown_update


def vote_last_response(state, liked, model_selector, request: gr.Request):
    conv_data = {
        "tstamp": round(time.time(), 4),
        "like": liked,
        "model": model_selector,
        "state": state.dict(),
        "ip": request.client.host,
    }
    write2file(get_log_filename(), json.dumps(conv_data) + "\n")


def upvote_last_response(state, model_selector, request: gr.Request):
    logger.info(f"upvote. ip: {request.client.host}")
    vote_last_response(state, True, model_selector, request)
    textbox = gr.MultimodalTextbox(value=None, interactive=True)
    return (textbox,) + (disable_btn,) * 3


def downvote_last_response(state, model_selector, request: gr.Request):
    logger.info(f"downvote. ip: {request.client.host}")
    vote_last_response(state, False, model_selector, request)
    textbox = gr.MultimodalTextbox(value=None, interactive=True)
    return (textbox,) + (disable_btn,) * 3


def vote_selected_response(
    state, model_selector, request: gr.Request, data: gr.LikeData
):
    logger.info(
        f"Vote: {data.liked}, index: {data.index}, value: {data.value} , ip: {request.client.host}"
    )
    conv_data = {
        "tstamp": round(time.time(), 4),
        "like": data.liked,
        "index": data.index,
        "model": model_selector,
        "state": state.dict(),
        "ip": request.client.host,
    }
    write2file(get_log_filename(), json.dumps(conv_data) + "\n")
    return


def flag_last_response(state, model_selector, request: gr.Request):
    logger.info(f"flag. ip: {request.client.host}")
    vote_last_response(state, "flag", model_selector, request)
    textbox = gr.MultimodalTextbox(value=None, interactive=True)
    return (textbox,) + (disable_btn,) * 3


def regenerate(state, system_prompt, request: gr.Request):
    logger.info(f"regenerate. ip: {request.client.host}")
    state.set_system_message(system_prompt)
    state.delete_last_message(role=state.ASSISTANT)
    state.skip_next = False
    textbox = gr.MultimodalTextbox(value=None, interactive=True)
    return (state, state.to_gradio_chatbot(), textbox) + (disable_btn,) * 5


def clear_history(request: gr.Request):
    logger.info(f"clear_history. ip: {request.client.host}")
    state = init_state()
    textbox = gr.MultimodalTextbox(value=None, interactive=True)
    return (state, state.to_gradio_chatbot(), textbox) + (disable_btn,) * 5


def change_system_prompt(state, system_prompt, request: gr.Request):
    logger.info(f"Change system prompt. ip: {request.client.host}")
    state.set_system_message(system_prompt)
    return state


def add_text(state, message, system_prompt, model_selector, request: gr.Request):
    if not state:
        state = init_state()
    gradio_files = message.get("files", [])
    text = message.get("text", "").strip()
    logger.info(f"add_text. ip: {request.client.host}. len: {len(text)}")
    textbox = gr.MultimodalTextbox(value=None, interactive=False)
    if len(text) <= 0 and len(gradio_files) == 0:
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), textbox) + (no_change_btn,) * 5
    if args.moderate:
        flagged = violates_moderation(text)
        if flagged:
            state.skip_next = True
            textbox = gr.MultimodalTextbox(
                value={"text": moderation_msg}, interactive=True
            )
            return (state, state.to_gradio_chatbot(), textbox) + (no_change_btn,) * 5

    files = []
    for item in gradio_files:
        if item.endswith(IMG_EXT):
            files.append({"type": "image", "value": item})
        elif item.endswith(VID_EXT):
            files.append({"type": "video", "value": item})
        else:
            raise ValueError("Invalid file path.")

    if len(files) > 0 and len(state.get_files(source=state.USER)) > 0:
        state = init_state(state)
    state.set_system_message(system_prompt)
    state.append_message(Record.USER, text, files)
    state.skip_next = False
    return (state, state.to_gradio_chatbot(), textbox, model_selector) + (
        disable_btn,
    ) * 5


def http_bot(
    state,
    model_selector,
    temperature,
    top_p,
    repetition_penalty,
    max_new_tokens,
    request: gr.Request,
):
    logger.info(f"http_bot. ip: {request.client.host}")
    model_name = model_selector
    # start_tstamp = time.time()
    for iter in chat_with_vlm(
        state,
        model_selector if state.task is None else state.task,
        temperature,
        top_p,
        repetition_penalty,
        max_new_tokens,
        request,
    ):
        yield iter

    return (
        state,
        state.to_gradio_chatbot(streaming=False),
        gr.MultimodalTextbox(interactive=True),
    ) + (enable_btn,) * 5


def chat_with_vlm(
    state,
    model_selector,
    temperature,
    top_p,
    repetition_penalty,
    max_new_tokens,
    request: gr.Request,
):
    start_tstamp = time.time()
    model_name = model_selector
    state.append_message(Record.ASSISTANT, "")
    if hasattr(state, "skip_next") and state.skip_next:
        # This generate call is skipped due to invalid inputs
        yield (
            state,
            state.to_gradio_chatbot(),
            gr.MultimodalTextbox(interactive=False),
        ) + (no_change_btn,) * 5
        return

    # worker_addr = get_model_addr(model_name)
    worker_addr = args.model_worker_url
    logger.info(f"model_name: {model_name}, worker_addr: {worker_addr}")
    # No available worker
    if worker_addr == "":
        # state.messages[-1][-1] = server_error_msg
        state.update_message(Record.ASSISTANT, server_error_msg)
        yield (
            state,
            state.to_gradio_chatbot(),
            gr.MultimodalTextbox(interactive=False),
            disable_btn,
            disable_btn,
            disable_btn,
            enable_btn,
            enable_btn,
        )
        return

    all_files = state.get_files(source=state.USER)
    # all_image_paths = [state.save_image(image) for image in all_images]
    # Make requests
    pload = {
        "model": model_name,
        "messages": state.get_prompt(show_file_path=True),
        "temperature": float(temperature),
        "top_p": float(top_p),
        "max_new_tokens": max_new_tokens,
        "repetition_penalty": repetition_penalty,
        "files": f"List of {len(all_files)} files: {all_files}",
        "stream": True,
        "min_pixels": record.min_pixels,
        "max_pixels": record.max_pixels,
    }
    logger.info(f"==== request ====\n{pload}")
    pload.pop("files")
    pload["messages"] = state.get_prompt()
    yield (
        state,
        state.to_gradio_chatbot(),
        gr.MultimodalTextbox(interactive=False),
    ) + (disable_btn,) * 5
    try:
        # Stream output
        response = requests.post(
            worker_addr + "/v1/chat/completions",
            headers=headers,
            json=pload,
            stream=True,
            timeout=20,
        )
        for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\n\n"):
            if chunk:
                data_str = chunk.decode()
                assert data_str.startswith("data:"), f"Invalid data: {data_str}"
                data_str = ":".join(data_str.split(":")[1:])
                if isinstance(data_str, str) and data_str.strip() == "[DONE]":
                    break

                data = json.loads(data_str)
                if "error_code" not in data:
                    output = data["choices"][0]["delta"]["content"]
                    mode = data["choices"][0]["delta"].get("mode", "append")
                    # output += state.streaming_placeholder

                    files = []
                    if "image_urls" in data["choices"][0]["delta"]:
                        images = data["choices"][0]["delta"]["image_urls"]
                        files = [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            }
                            for image_url in images
                        ]
                    if "video_urls" in data["choices"][0]["delta"]:
                        videos = data["choices"][0]["delta"]["video_urls"]
                        files += [
                            {
                                "type": "video_url",
                                "video_url": {"url": video_url},
                            }
                            for video_url in videos
                        ]

                    state.update_message(Record.ASSISTANT, output, files, mode=mode)
                    yield (
                        state,
                        state.to_gradio_chatbot(),
                        gr.MultimodalTextbox(interactive=False),
                    ) + (disable_btn,) * 5
                else:
                    output = (
                        f"**{data['text']}**" + f" (error_code: {data['error_code']})"
                    )

                    state.update_message(Record.ASSISTANT, output, None)
                    yield (
                        state,
                        state.to_gradio_chatbot(),
                        gr.MultimodalTextbox(interactive=True),
                    ) + (
                        disable_btn,
                        disable_btn,
                        disable_btn,
                        enable_btn,
                        enable_btn,
                    )
                    return
    except requests.exceptions.RequestException as e:
        state.update_message(Record.ASSISTANT, server_error_msg, None)
        yield (
            state,
            state.to_gradio_chatbot(streaming=False),
            gr.MultimodalTextbox(interactive=True),
        ) + (
            disable_btn,
            disable_btn,
            disable_btn,
            enable_btn,
            enable_btn,
        )
        return

    # """
    ai_response = state.return_last_message()
    msg = state.return_last_message()
    if type(msg) == list:
        for item in msg:
            assert isinstance(item, dict)
            if item["type"] == "text":
                msg = item[item["type"]]
                break
    
    print(f"msg: {msg}")
    returned_image = None
    if "```json\n" in msg:
        returned_image = find_bounding_boxes_qwenvl(state, msg)
        
    if "<box>" in msg and "</box>" in msg:
        returned_image = find_bounding_boxes(state, msg)
        
    if "<action>" in msg and "</action>" in msg:
        latest_image_path = state.get_images(source=state.USER)[-1]
        returned_image = Image.open(latest_image_path).convert("RGB")
        returned_image, _ = parse_point(msg, returned_image)
    
    if returned_image:
        state.update_message(
            Record.ASSISTANT,
            "",
            [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64," + image2base64(returned_image)
                    },
                }
            ],
        )
        
    state.end_of_current_turn()

    finish_tstamp = time.time()
    logger.info(f"Received message: {state.get_prompt(True)[-1]}")
    data = {
        "tstamp": round(finish_tstamp, 4),
        "like": None,
        "model": model_name,
        "start": round(start_tstamp, 4),
        "finish": round(start_tstamp, 4),
        "state": state.dict(),
        "files": all_files,
        "ip": request.client.host,
    }
    # write2file(get_log_filename(), json.dumps(data) + "\n")
    
    yield (
        state,
        state.to_gradio_chatbot(streaming=False),
        gr.MultimodalTextbox(interactive=True),
    ) + (enable_btn,) * 5


def change_mode(mode):
    if mode == "GUI Grounding":
        visiblities = [gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)]
    elif mode == "GUI Planning":
        visiblities = [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)]
    elif mode == "Multimodal Chat":
        visiblities = [gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)]
    
    return [], SYSTEM_PROMPT_DICT[mode], *visiblities
    

def build_demo(embed_mode, show_example=False):
    textbox = gr.MultimodalTextbox(
        interactive=True,
        file_types=["image", "video"],
        placeholder="Enter message or upload file...",
        show_label=False,
    )

    with gr.Blocks(
        title="Chat",
        theme=gr.themes.Default(),
        css=block_css,
    ) as demo:
        state = gr.State()
        models = get_model_list()
        if not embed_mode:
            # gr.Markdown(title_markdown)
            gr.HTML(title_html)
            # gr.Markdown(title_markdown)

        with gr.Row():
            with gr.Column(scale=2):

                with gr.Row(elem_id="model_selector_row"):
                    model_selector = gr.Dropdown(
                        choices=models,
                        value=models[0] if len(models) > 0 else "",
                        # value="InternVL-Chat-V1-5",
                        interactive=True,
                        show_label=False,
                        container=False,
                    )

                with gr.Accordion("System Prompt", open=False) as system_prompt_row:
                    system_prompt = gr.Textbox(
                        # value="You are a helpful assistant.",
                        value=SYSTEM_PROMPT_DICT["GUI Grounding"],
                        label="System Prompt",
                        interactive=True,
                    )
                with gr.Accordion("Parameters", open=False) as parameter_row:
                    temperature = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.7,
                        step=0.1,
                        interactive=True,
                        label="Temperature",
                    )
                    top_p = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.9,
                        step=0.1,
                        interactive=True,
                        label="Top P",
                    )
                    repetition_penalty = gr.Slider(
                        minimum=1.0,
                        maximum=1.5,
                        value=1.1,
                        step=0.02,
                        interactive=True,
                        label="Repetition penalty",
                    )
                    max_output_tokens = gr.Slider(
                        minimum=0,
                        maximum=4096,
                        value=1024,
                        step=64,
                        interactive=True,
                        label="Max output tokens",
                    )
                    
                with gr.Row(visible=True) as grounding_examples:
                    gr.Examples(
                        examples=prepare_grounding_examples() if show_example else [],
                        inputs=[textbox],
                        examples_per_page=5,
                        label="GUI Grounding Examples",
                    )
                with gr.Row(visible=False) as planning_examples:
                    gr.Examples(
                        examples=prepare_planning_examples() if show_example else [],
                        inputs=[textbox],
                        examples_per_page=5,
                        label="GUI Planning Examples",
                        # visible=False,
                    )
                with gr.Row(visible=False) as chat_examples:
                    gr.Examples(
                        examples=prepare_chat_examples() if show_example else [],
                        inputs=[textbox],
                        examples_per_page=5,
                        label="Chat Examples",
                        # visible=False,
                    )
            with gr.Column(scale=8):
                mode_selector = gr.Radio(
                    choices=["GUI Grounding", "GUI Planning", "Multimodal Chat"],
                    value="GUI Grounding",
                    label="Chat Mode"
                )
                chatbot = gr.Chatbot(
                    elem_id="chatbot",
                    label="ScaleCUA",
                    height=600,
                    show_copy_button=True,
                    show_share_button=True,
                    avatar_images=[
                        "assets/human.png",
                        "assets/assistant.png",
                    ],
                    bubble_full_width=False,
                    type="messages",
                )
                with gr.Row():
                    with gr.Column(scale=8):
                        textbox.render()
                    with gr.Column(scale=1, min_width=50):
                        submit_btn = gr.Button(value="Send", variant="primary")
                with gr.Row(elem_id="buttons") as button_row:
                    upvote_btn = gr.Button(value="👍  Upvote", interactive=False)
                    downvote_btn = gr.Button(value="👎  Downvote", interactive=False)
                    flag_btn = gr.Button(value="⚠️  Flag", interactive=False)
                    # stop_btn = gr.Button(value="⏹️  Stop Generation", interactive=False)
                    regenerate_btn = gr.Button(
                        value="🔄  Regenerate", interactive=False
                    )
                    clear_btn = gr.Button(value="🗑️  Clear", interactive=False)

        if not embed_mode:
            gr.Markdown(tos_markdown)
            gr.Markdown(learn_more_markdown)
        url_params = gr.JSON(visible=False)

        # Register listeners
        mode_selector.change(
            change_mode,
            inputs=[mode_selector],
            outputs=[chatbot, system_prompt, grounding_examples, planning_examples, chat_examples],
        )
        btn_list = [upvote_btn, downvote_btn, flag_btn, regenerate_btn, clear_btn]
        upvote_btn.click(
            upvote_last_response,
            [state, model_selector],
            [textbox, upvote_btn, downvote_btn, flag_btn],
        )
        downvote_btn.click(
            downvote_last_response,
            [state, model_selector],
            [textbox, upvote_btn, downvote_btn, flag_btn],
        )
        chatbot.like(
            vote_selected_response,
            [state, model_selector],
            [],
        )
        flag_btn.click(
            flag_last_response,
            [state, model_selector],
            [textbox, upvote_btn, downvote_btn, flag_btn],
        )
        regenerate_btn.click(
            regenerate,
            [state, system_prompt],
            [state, chatbot, textbox] + btn_list,
        ).then(
            http_bot,
            [
                state,
                model_selector,
                temperature,
                top_p,
                repetition_penalty,
                max_output_tokens,
            ],
            [state, chatbot, textbox] + btn_list,
        )
        clear_btn.click(clear_history, None, [state, chatbot, textbox] + btn_list)

        textbox.submit(
            add_text,
            [state, textbox, system_prompt, model_selector],
            [state, chatbot, textbox, model_selector] + btn_list,
        ).then(
            http_bot,
            [
                state,
                model_selector,
                temperature,
                top_p,
                repetition_penalty,
                max_output_tokens
            ],
            [state, chatbot, textbox] + btn_list,
        )
        submit_btn.click(
            add_text,
            [state, textbox, system_prompt, model_selector],
            [state, chatbot, textbox, model_selector] + btn_list,
        ).then(
            http_bot,
            [
                state,
                model_selector,
                temperature,
                top_p,
                repetition_penalty,
                max_output_tokens,
            ],
            [state, chatbot, textbox] + btn_list,
        )

        # NOTE: The following code will be not triggered when deployed on HF space.
        # It's very strange. I don't know why.
        # """
        if args.model_list_mode == "once":
            demo.load(
                load_demo,
                [url_params],
                [state, model_selector],
                js=js,
            )
        elif args.model_list_mode == "reload":
            demo.load(
                load_demo_refresh_model_list,
                None,
                [state, model_selector],
                js=js,
            )
        else:
            raise ValueError(f"Unknown model list mode: {args.model_list_mode}")
        # """

    return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=10024)
    parser.add_argument("--model-worker-url", type=str, default=None)
    parser.add_argument("--model-name", type=str, default=None)
    parser.add_argument("--concurrency-count", type=int, default=10)
    parser.add_argument(
        "--model-list-mode", type=str, default="reload", choices=["once", "reload"]
    )
    parser.add_argument("--share", action="store_true")
    parser.add_argument("--moderate", action="store_true")
    parser.add_argument("--embed", action="store_true")
    # parser.add_argument("--show-example", action="store_true")
    args = parser.parse_args()
    
    models = get_model_list()
    logger.info(f"models: {models}")
    logger.info(args)
    demo = build_demo(args.embed, show_example=True)
    demo.queue(api_open=False, max_size=3, default_concurrency_limit=3).launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        max_threads=args.concurrency_count,
    )