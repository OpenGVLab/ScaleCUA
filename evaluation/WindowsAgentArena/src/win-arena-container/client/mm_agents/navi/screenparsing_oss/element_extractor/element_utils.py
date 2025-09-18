from PIL import Image
import torch
from screenparsing.element_extractor.utils import draw_bbox, draw_multiple_bboxes
from screenparsing.groundingdino.groundingdino import GroundingDino as DinoProposer
from screenparsing.ocr.oneocr import OneOcr as OCRProposer
import copy

SCREENAI_CLASSES = (
    "Text",
    "Image",
    "Table",
    "Container",
    "Menu",
    "Toolabr",
    "AddressBar",
    "Toolpane",
    "TabBar",
    "TitleBar",
)


def get_rect_list(all_regions):
    id_list = []
    rect_list = []
    for region_type in all_regions:
        for region_id in all_regions[region_type]:
            id_list.append(region_id)
            rect_list.append(all_regions[region_type][region_id]["rect"])
    return id_list, rect_list


def create_synthetic_html(all_regions):
    rect_list = []

    # create the image elements first
    image_list_text = []
    for region_id in all_regions["images"]:
        image_list_text.append(all_regions["images"][region_id]["text"])
        rect_list.append(all_regions["images"][region_id]["rect"])
    image_descriptions_html = ['<img alt="' + x + '">' for x in image_list_text]

    # create the ocr elements
    ocr_list = []
    for region_id in all_regions["ocr"]:
        ocr_list.append(all_regions["ocr"][region_id]["text"])
        rect_list.append(all_regions["ocr"][region_id]["rect"])
    ocr_list = ["<button>" + x + "</button>" for x in ocr_list]

    # create the icon elements
    icon_list_text = []
    for region_id in all_regions["icons"]:
        icon_list_text.append(all_regions["icons"][region_id]["text"])
        rect_list.append(all_regions["icons"][region_id]["rect"])
    icon_list_text = ["<icon>" + x + "</icon>" for x in icon_list_text]

    # terrible caption quality
    # icon_list_image = []
    # for region_id in all_regions["icons"]:
    #     icon_list_image.append(all_regions["icons"][region_id]["image"])
    # icon_descriptions_raw = self.image_captioner.gen_caption(icon_list_image)
    # icon_descriptions_html = ['<img alt="'+x+'">' for x in icon_descriptions_raw]
    # html_elements["icons_image"] = icon_descriptions_html

    text_list = image_descriptions_html + ocr_list + icon_list_text

    return text_list, rect_list


def create_text_list(all_regions, width, height):
    list_of_text = "ID | Type | Text content or description | Normalized location [x1, y1, x2, y2]\n"
    # create a list of all the elements in the form
    # ID | Type | Text | Normalized location (x1, y1, x2, y2)
    for region_type in all_regions:
        if region_type not in ["rendered_text"]:  # ["rendered_text", "images", "icons"]
            for region_id in all_regions[region_type]:
                region = all_regions[region_type][region_id]
                location = region["rect"]
                location = [
                    round(location[0] / width, 2),
                    round(location[1] / height, 2),
                    round(location[2] / width, 2),
                    round(location[3] / height, 2),
                ]
                # check if the key exists
                if "text" in region:
                    list_of_text += (
                        f"{region_id} | {region_type} | {region['text']} | {location}\n"
                    )
                else:
                    list_of_text += (
                        f"{region_id} | {region_type} | {'-'} | {location}\n"
                    )
    return list_of_text
