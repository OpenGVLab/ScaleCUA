from mm_agents.navi.screenparsing_oss.omniparser.utils import (
    get_som_labeled_img,
    check_ocr_box,
    get_caption_model_processor,
    get_yolo_model,
    get_parsed_content_icon,
    get_parsed_content_icon_phi3v,
)
import torch
from ultralytics import YOLO
from PIL import Image
from typing import Dict, Tuple, List
import io
import base64
import tempfile
from pathlib import Path
import numpy as np

defaultconfig = {
    "som_model_path": "/models/omni/icon_detect/model.pt",
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "caption_model_path": "/models/omni/icon_caption_florence",
    "draw_bbox_config": {
        "text_scale": 0.8,
        "text_thickness": 2,
        "text_padding": 3,
        "thickness": 3,
    },
    "BOX_TRESHOLD": 0.05,
}


class Omniparser(object):
    def __init__(self, config: Dict = {}):
        self.config = {**defaultconfig, **config}

        if not (som_path := Path(self.config["som_model_path"])).exists():
            som_path_st = som_path.with_suffix(".safetensors")
            print(f"Warning: missing omniparser det model {str(som_path)}")
            if som_path_st.exists():
                print("Automagically converting omniparser .safetensors to .pt...")
                # convert safetensors to pt
                from ultralytics.nn.tasks import DetectionModel
                from safetensors.torch import load_file

                tensor_dict = load_file(str(som_path_st))
                model = DetectionModel(str(som_path.with_suffix(".yaml")))
                model.load_state_dict(tensor_dict)
                torch.save({"model": model}, str(som_path.with_suffix(".pt")))
            else:
                raise FileNotFoundError(
                    f"Missing omniparser det model: {str(som_path_st)}"
                )

        self.som_model = get_yolo_model(model_path=self.config["som_model_path"])
        self.caption_model_processor = get_caption_model_processor(
            model_path=self.config["caption_model_path"], device=self.config["device"]
        )

    def parse(self, image_path: str):
        print("Parsing image:", image_path)
        ocr_bbox_rslt, is_goal_filtered = check_ocr_box(
            image_path,
            display_img=False,
            output_bb_format="xyxy",
            goal_filtering=None,
            easyocr_args={"paragraph": False, "text_threshold": 0.9},
        )
        text, ocr_bbox = ocr_bbox_rslt

        draw_bbox_config = self.config["draw_bbox_config"]
        BOX_TRESHOLD = self.config["BOX_TRESHOLD"]
        dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image_path,
            model=self.som_model,
            BOX_TRESHOLD=BOX_TRESHOLD,
            output_coord_in_ratio=False,
            ocr_bbox=ocr_bbox,
            draw_bbox_config=draw_bbox_config,
            caption_model_processor=None,
            ocr_text=text,
            use_local_semantics=False,
        )

        image = Image.open(io.BytesIO(base64.b64decode(dino_labled_img)))
        # formating output
        return_list = [
            {
                "from": "omniparser",
                "shape": {
                    "x": coord[0],
                    "y": coord[1],
                    "width": coord[2],
                    "height": coord[3],
                },
                "text": ": ".join(parsed_content_list[i].split(": ")[1:]),
                "type": "text",
            }
            for i, (k, coord) in enumerate(label_coordinates.items())
            if i < len(parsed_content_list)
        ]
        return_list += [
            {
                "from": "omniparser",
                "shape": {
                    "x": coord[0],
                    "y": coord[1],
                    "width": coord[2],
                    "height": coord[3],
                },
                "text": "",
                "type": "icon",
            }
            for i, (k, coord) in enumerate(label_coordinates.items())
            if i >= len(parsed_content_list)
        ]

        return [image, return_list]

    def caption_ents(self, image: Image, ents: List[Dict]):
        # get all the unlabeled entities (omni icon output, a11y output) and their corresponding PIL bboxes (min xy, max xy)
        width, height = image.size
        ents_rects = [
            (
                ent,
                (
                    ent["shape"]["x"] / width,
                    ent["shape"]["y"] / height,
                    (ent["shape"]["x"] + ent["shape"]["width"]) / width,
                    (ent["shape"]["y"] + ent["shape"]["height"]) / height,
                ),
            )
            for ent in ents
            if not ent.get("text", "").strip()
        ]
        filtered_ents, filtered_rects = [list(tup) for tup in zip(*ents_rects)]

        # use omni to label them
        caption_model = self.caption_model_processor["model"]
        image_np = np.asarray(image.convert("RGB"))
        if "phi3_v" in caption_model.config.model_type:
            parsed_content_icon = get_parsed_content_icon_phi3v(
                filtered_rects, None, image_np, self.caption_model_processor
            )
        else:
            parsed_content_icon = get_parsed_content_icon(
                filtered_rects, None, image_np, self.caption_model_processor
            )

        # mutate the ents
        for i, txt in enumerate(parsed_content_icon):
            filtered_ents[i]["text"] = txt
            filtered_ents[i]["text_from"] = "omni"

        return parsed_content_icon

    def propose_ents(self, image: Image, with_captions: bool = True) -> List[Dict]:
        # Save image to temporary location
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name)

        # Parse image to get entities
        _, ents = self.parse(tmp.name)
        if with_captions:
            self.caption_ents(image, ents)
        return [
            {
                **ent,
                "shape": {
                    "x": int(ent["shape"]["x"]),
                    "y": int(ent["shape"]["y"]),
                    "width": int(ent["shape"]["width"]),
                    "height": int(ent["shape"]["height"]),
                },
            }
            for ent in ents
        ]


if __name__ == "__main__":
    config = defaultconfig
    parser = Omniparser(config)
    image_path = "1360x768_cnn.png"
    image_pil = Image.open(image_path)

    #  time icon det
    import time

    s = time.time()
    ents = parser.propose_ents(image_pil, with_captions=True)
    device = config["device"]
    print(f"Time taken for Omniparser on {device}:", time.time() - s)

    import json

    print(json.dumps(ents, indent=2, ensure_ascii=False))
