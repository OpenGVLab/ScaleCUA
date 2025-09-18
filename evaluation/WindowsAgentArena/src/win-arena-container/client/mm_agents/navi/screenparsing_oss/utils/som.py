import random
import re
import os
from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional

from matplotlib import pyplot as plt

default_font = os.path.join(os.path.dirname(__file__), "arial.ttf")


def draw_som(image, entities: List[dict], color_mapping: dict = None):
    """Annotate a screen with entities."""
    image = image.copy()

    STYLE_BOX_RANDOMCOLOR = {"outlineWidth": 2, "stroke": "rand(0)", "padding": "2 5"}
    STYLE_LABEL_RANDOMCOLOR = {
        "font_size": 12,
        "anchor": "top_right",
        "position": "bottom_right",
        "stroke": "white",
        "background": "rand(0)",
        "padding": "2 5",
    }

    if not color_mapping:
        image = draw_bboxes(image, entities, default_style=STYLE_BOX_RANDOMCOLOR)
        image = draw_labels(image, entities, default_style=STYLE_LABEL_RANDOMCOLOR)
    else:
        bbox_styles = {}
        label_styles = {}

        for ent_type in color_mapping.keys():
            bbox_styles[ent_type] = {
                **STYLE_BOX_RANDOMCOLOR,
                "stroke": color_mapping[ent_type],
            }

            label_styles[ent_type] = {
                **STYLE_LABEL_RANDOMCOLOR,
                "background": color_mapping[ent_type],
            }

        image = draw_bboxes(image, entities, styles=bbox_styles, default_style=None)
        image = draw_labels(image, entities, styles=label_styles, default_style=None)

    return image


# def draw_som(image, entities: List[dict]):
#     """Annotate a screen with entities."""
#     image = image.copy()

#     bbox_style = {
#         'outlineWidth': 2,
#         'stroke': 'rand(0)',
#         'padding': '2 5',
#     }

#     label_style = {
#         'font_size': 12,
#         'anchor': 'top_right',
#         'position': 'bottom_right',
#         'stroke': 'white',
#         'background': 'rand(0)',
#         'padding': '2 5',
#     }

#     image = draw_bboxes(image, entities, default_style=bbox_style)
#     image = draw_labels(image, entities, default_style=label_style)

#     return image


def filter_entities(entities: List[dict]):
    def is_valid(ent):
        s = ent["shape"]
        # x,y,width,height must be positive
        if s["x"] < 0 or s["y"] < 0 or s["width"] <= 0 or s["height"] <= 0:
            return False
        # width * height must be >1
        if s["width"] * s["height"] <= 1:
            return False
        return True

    return [entity for entity in entities if is_valid(entity)]


def add_labels(
    entities: List[dict], template: Optional[str] = "{type}_{i}", shuffle=True
):
    """Apply random labels to entities."""

    # Shuffle the order of the entities
    if shuffle:
        random.shuffle(entities)
    for i, entity in enumerate(entities):
        entity["label"] = template.format(i=i, **entity)
    return entities


def draw_bboxes(
    image: Image,
    entities: List[dict],
    styles: dict = {},
    default_style: Optional[dict] = None,
):
    """Mark entities on an image."""
    for entity in entities:
        if entity["type"] in styles or default_style is not None:
            image = draw_bbox(
                image,
                bbox=entity["shape"],
                style=styles.get(entity["type"], default_style),
            )
    return image


def draw_labels(
    image: Image,
    entities: List[dict],
    styles: dict = {},
    default_style: Optional[dict] = None,
):
    """Add non-overlapping entity box labels."""
    positions_anchors = [
        # Outer corners
        ("bottom_right", "top_right"),
        ("bottom_left", "top_left"),
        ("top_left", "bottom_left"),
        ("top_right", "bottom_right"),
        # Inner corners
        ("bottom_right", "bottom_right"),
        ("bottom_left", "bottom_left"),
        ("top_left", "top_left"),
        ("top_right", "top_right"),
    ]
    # drawn_rects = []
    drawn_rects = [
        (
            entity["shape"]["x"] + 1,
            entity["shape"]["y"] + 1,
            entity["shape"]["width"] - 1,
            entity["shape"]["height"] - 1,
        )
        for entity in entities
        if entity["type"] in ["text"]
    ]

    for entity in entities:
        if entity["type"] in styles or default_style is not None:
            style = styles.get(entity["type"], default_style)
            for i, (position, anchor) in enumerate(positions_anchors):
                style["position"] = position
                style["anchor"] = anchor

                rect = calc_label(
                    bbox=entity["shape"], label=entity["label"], style=style
                )

                if not any(
                    check_overlap(rect, drawn_rect) for drawn_rect in drawn_rects
                ) or (i == len(positions_anchors) - 1):
                    image = draw_label(
                        image=image,
                        bbox=entity["shape"],
                        label=entity["label"],
                        style=style,
                    )
                    drawn_rects.append(rect)
                    break

    return image


### STYLE RENDERING ###

colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]


def read_color(style: dict, key: str, default: str, seed=None):
    """Read a color from a style."""
    if seed:
        random.seed(seed)
    color = style.get(key, default)
    if not color or color == "transparent":
        return None
    if "rand(" in color:
        match = re.search(r"rand\((\d+)\)", color)
        offset = int(match.group(1)) if match else 0
        return colors[(offset + random.randint(0, len(colors))) % len(colors)]
    return color


def read_padding(style: dict, key: str, default: str):
    padding_str = style.get(key, default)
    padding_values = list(map(int, padding_str.split()))
    if len(padding_values) == 1:
        return padding_values * 4
    elif len(padding_values) == 2:
        return padding_values * 2
    elif len(padding_values) == 3:
        return padding_values + padding_values[:1]
    elif len(padding_values) == 4:
        return padding_values
    else:
        raise ValueError("Invalid padding value")


### ENTITY RENDERING ###


def draw_bbox(image: Image, bbox: dict, style: dict):
    """Draw a bounding box on an image."""
    draw = ImageDraw.Draw(image)
    x, y = bbox["x"], bbox["y"]
    width, height = bbox.get("width", 0), bbox.get("height", 0)
    seed = x + y + width + height
    draw.rectangle(
        [x, y, x + width, y + height],
        outline=read_color(style, "stroke", "red", seed=seed),
        fill=read_color(style, "background", None, seed=seed),
        width=style.get("outlineWidth", 1),
    )
    return image


def get_label_rect(
    label: str,
    bbox: dict,
    style: dict,
    padding: List[int],
    font: ImageFont.FreeTypeFont,
):
    """Calculate the rectangle for the label."""
    x, y = bbox["x"], bbox["y"]
    width, height = bbox.get("width", 0), bbox.get("height", 0)

    anchors = {
        "center": (0.5, 0.5),
        "top_left": (0, 0),
        "top_right": (1, 0),
        "bottom_left": (0, 1),
        "bottom_right": (1, 1),
    }

    text_bbox = font.getbbox(label)
    text_width = text_bbox[2] - text_bbox[0] + padding[1] + padding[3]
    text_height = text_bbox[3] - text_bbox[1] + padding[0] + padding[2]

    position = style.get("position", "center")
    anchor = style.get("anchor", "center")

    x = x + width * anchors[position][0] - text_width * anchors[anchor][0]
    y = y + height * anchors[position][1] - text_height * anchors[anchor][1]

    return x, y, text_width, text_height


def check_overlap(rect1, rect2):
    """Check if two rectangles overlap."""
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def calc_label(bbox: dict, label: str, style: dict = {}):
    padding = read_padding(style, "padding", "0 0 0 0")
    font_size = style.get("font_size", 12)
    font = ImageFont.truetype(style.get("font", default_font), font_size)

    x, y, text_width, text_height = get_label_rect(label, bbox, style, padding, font)
    return (x, y, text_width, text_height)


def draw_label(image: Image, bbox: dict, label: str, style: dict = {}):
    """Draw a label on an image."""
    draw = ImageDraw.Draw(image)
    seed = bbox["x"] + bbox["y"] + bbox.get("width", 0) + bbox.get("height", 0)

    stroke = read_color(style, "stroke", None, seed=seed)
    background = read_color(style, "background", None, seed=seed)
    padding = read_padding(style, "padding", "0 0 0 0")
    font_size = style.get("font_size", 12)
    font = ImageFont.truetype(style.get("font", default_font), font_size)

    x, y, text_width, text_height = get_label_rect(label, bbox, style, padding, font)

    if background:
        draw.rectangle([x, y, x + text_width, y + text_height], fill=background)
    if stroke:
        draw.text((x + padding[3], y + (padding[0] / 2)), label, font=font, fill=stroke)

    return image
