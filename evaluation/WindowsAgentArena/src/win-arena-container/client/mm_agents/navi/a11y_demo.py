import os
import random
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import xml.etree.ElementTree as ET
from anytree import Node, RenderTree
import numpy as np

# Hardcoded URLs
A11Y_URL = "http://20.20.20.21:5000/accessibility?backend=uia"
SCREENSHOT_URL = "http://20.20.20.21:5000/screenshot"
CACHE_DIR = ".cache"


def get_a11y(reuse=False):
    cache_path = os.path.join(CACHE_DIR, "a11y.txt")

    if os.path.exists(cache_path) and reuse:
        with open(cache_path, "r") as f:
            a11y_data = f.read()
    else:
        req = requests.get(A11Y_URL)
        a11y_data = req.json()["AT"]
        with open(cache_path, "w") as f:
            f.write(a11y_data)

    return a11y_data


def get_screen(reuse=False):
    cache_path = os.path.join(CACHE_DIR, "screenshot.png")

    if os.path.exists(cache_path) and reuse:
        image = Image.open(cache_path)
    else:
        req = requests.get(SCREENSHOT_URL)
        image = Image.open(BytesIO(req.content))
        image.save(cache_path)

    return image


def is_leaf_node(node):
    return len(list(node)) == 0


def is_visible(node):
    visible = node.get("{uri:deskat:state.at-spi.gnome.org}visible", "false")
    return visible == "true"


def is_enabled(node):
    visible = node.get("{uri:deskat:state.at-spi.gnome.org}enabled", "false")
    return visible == "true"


def has_coords(node):
    position = node.get("{uri:deskat:component.at-spi.gnome.org}screencoord", "")
    size = node.get("{uri:deskat:component.at-spi.gnome.org}size", "")
    return bool(position) and bool(size)


def has_name(node):
    return node.attrib.get("name", "")


def heuristic(node):
    return (
        is_leaf_node(node)
        and is_visible(node)
        and is_enabled(node)
        and has_coords(node)
    )  # and has_name(node)


def center_of_bbox(position, size):
    center_x = position[0] + size[0] // 2
    center_y = position[1] + size[1] // 2
    return center_x, center_y


def rect_overlaps(center, bbox_position, bbox_size):
    x, y = center
    bbox_left = bbox_position[0]
    bbox_top = bbox_position[1]
    bbox_right = bbox_left + bbox_size[0]
    bbox_bottom = bbox_top + bbox_size[1]
    return bbox_left <= x <= bbox_right and bbox_top <= y <= bbox_bottom


def overlap_ratio(bbox1_position, bbox1_size, bbox2_position, bbox2_size):
    bbox1_area = bbox1_size[0] * bbox1_size[1]
    bbox2_area = bbox2_size[0] * bbox2_size[1]
    if bbox1_area == 0 or bbox2_area == 0:
        return 0

    x1, y1 = bbox1_position
    x2, y2 = bbox2_position
    x_overlap = max(0, min(x1 + bbox1_size[0], x2 + bbox2_size[0]) - max(x1, x2))
    y_overlap = max(0, min(y1 + bbox1_size[1], y2 + bbox2_size[1]) - max(y1, y2))
    overlap_area = x_overlap * y_overlap
    return overlap_area * 2 / (bbox1_area + bbox2_area)


def filter_reduntant_bboxes(bboxes, th=0.9):
    # compare pairwise and remove the one with more than th overlap
    for i in range(len(bboxes)):
        for j in range(i + 1, len(bboxes)):
            if (
                overlap_ratio(bboxes[i][0], bboxes[i][1], bboxes[j][0], bboxes[j][1])
                > th
            ):
                bboxes.pop(j)
                break
    return bboxes


def filter_reduntant_entities(entities, th=0.8):
    # compare pairwise and remove the one with more than th overlap
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            if (
                overlap_ratio(
                    (entities[i]["shape"]["x"], entities[i]["shape"]["y"]),
                    (entities[i]["shape"]["width"], entities[i]["shape"]["height"]),
                    (entities[j]["shape"]["x"], entities[j]["shape"]["y"]),
                    (entities[j]["shape"]["width"], entities[j]["shape"]["height"]),
                )
                > th
            ):
                entities.pop(j)
                break
    return entities


def filter_nonvis_and_oob_entities(entities, width, height):
    new_ents = []
    for ent in entities:
        x, y = ent["shape"]["x"], ent["shape"]["y"]
        w, h = ent["shape"]["width"], ent["shape"]["height"]

        x = min(width, max(0, x))
        y = min(height, max(0, y))
        x2 = min(width, max(0, x + w))
        y2 = min(height, max(0, y + h))

        w, h = x2 - x, y2 - y
        if x2 < x or y2 < y or w * h < 5:
            continue

        ent["shape"] = {"x": x, "y": y, "width": w, "height": h}
        new_ents.append(ent)
    return new_ents


def get_mask_from_entities(entities, width, height):
    mask = np.zeros((height, width))
    for ent in entities:
        x, y = ent["shape"]["x"], ent["shape"]["y"]
        w, h = ent["shape"]["width"], ent["shape"]["height"]
        # clip the mask to the image size
        x = max(0, min(width, x))
        y = max(0, min(height, y))
        w = max(0, min(width, w))
        h = max(0, min(height, h))

        mask[y : y + h, x : x + w] = 1
    return mask


def filter_entities_with_mask(entities, mask, th=0.3):
    # filter all entities that are already represented in the mask
    new_entities = []
    for ent in entities:
        x, y = ent["shape"]["x"], ent["shape"]["y"]
        w, h = ent["shape"]["width"], ent["shape"]["height"]
        area = w * h
        overlap = mask[y : y + h, x : x + w].sum()
        if overlap / area < th:
            new_entities.append(ent)

    return new_entities


def detections_to_entities(detections):
    entities = []
    for detec_type, detec_content in detections.items():
        for detection in detec_content.values():
            x1, y1, x2, y2 = detection["rect"]

            text = detection.get(
                "label",
                detection.get(
                    "text",
                    str(detection.get("words", "ocr_" + str(detection.get("id", "")))),
                ),
            )
            entities.append(
                {
                    "type": detec_type,
                    "shape": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                    "text": text,
                }
            )
    return entities


def fix_a11y(accessibility_tree):
    desktop_node = ET.fromstring(accessibility_tree)

    if desktop_node is not None:
        children = list(desktop_node)[::-1]

        desktop_node.clear()
        for child in children:
            desktop_node.append(child)

    return ET.tostring(desktop_node, encoding="unicode")


def extract_bounding_boxes(accessibility_tree):
    desktop = ET.fromstring(accessibility_tree)
    bounding_boxes = []

    for window in desktop:
        window_position = window.get(
            "{uri:deskat:component.at-spi.gnome.org}screencoord", ""
        )
        window_size = window.get("{uri:deskat:component.at-spi.gnome.org}size", "")
        window_position = [
            int(coord.strip("()")) for coord in window_position.split(",")
        ]
        window_size = [int(dim.strip("()")) for dim in window_size.split(",")]

        # Remove all boxes that this window overlaps
        bounding_boxes = [
            bb
            for bb in bounding_boxes
            if not rect_overlaps(
                center_of_bbox(bb[0], bb[1]), window_position, window_size
            )
        ]

        for node in window.iter():
            if heuristic(node):
                name = node.attrib.get("name", "")
                position = node.get(
                    "{uri:deskat:component.at-spi.gnome.org}screencoord", ""
                )
                size = node.get("{uri:deskat:component.at-spi.gnome.org}size", "")

                if position and size:
                    position = [int(coord.strip("()")) for coord in position.split(",")]
                    size = [int(dim.strip("()")) for dim in size.split(",")]
                    bounding_boxes.append((position, size, name))

    return bounding_boxes


def draw_bounding_boxes(image, bounding_boxes):
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for position, size, name in bounding_boxes:
        top_left = (position[0], position[1])
        bottom_right = (position[0] + size[0], position[1] + size[1])
        color = tuple(random.randint(0, 255) for _ in range(3))

        # Draw filled rectangle
        draw.rectangle([top_left, bottom_right], fill=color)

        # Draw the name inside the box
        text_position = (position[0] + 5, position[1] + 5)  # Padding from top-left
        draw.text(text_position, name, fill="black", font=font)

    return image


def build_tree(node, parent=None):
    position = node.get("{uri:deskat:component.at-spi.gnome.org}screencoord", "")
    size = node.get("{uri:deskat:component.at-spi.gnome.org}size", "")

    description = f"{node.tag} '{node.attrib.get('name', '')}' "
    if position and size:
        description += f" ({position}, {size})"

    tree_node = Node(description, parent=parent, text=node.text)
    for child in node:
        build_tree(child, tree_node)

    return tree_node


def propose_ents(accessibility_tree):

    if accessibility_tree is None:
        print(
            "*********************** No accessibility tree data available. ***********************"
        )
        return []
    print(
        f"*********************** There are {len(accessibility_tree)} elements ***********************"
    )
    desktop = ET.fromstring(fix_a11y(accessibility_tree))
    xy_ents = []

    def iter_tree(node, xy_ents):
        if is_visible(node):
            if heuristic(node):
                name = node.attrib.get("name", "")
                position = node.get(
                    "{uri:deskat:component.at-spi.gnome.org}screencoord", ""
                )
                size = node.get("{uri:deskat:component.at-spi.gnome.org}size", "")

                if position and size:
                    position = [int(coord.strip("()")) for coord in position.split(",")]
                    size = [int(dim.strip("()")) for dim in size.split(",")]
                    xy_ents.append(
                        (
                            center_of_bbox(position, size),
                            {
                                "from": "a11y",
                                "type": "a11y",
                                "shape": {
                                    "x": position[0],
                                    "y": position[1],
                                    "width": size[0],
                                    "height": size[1],
                                },
                                "text": name,
                            },
                        )
                    )
            for child in node:
                iter_tree(child, xy_ents)

    for window in desktop:
        if not is_visible(window):
            continue
        window_position = window.get(
            "{uri:deskat:component.at-spi.gnome.org}screencoord", ""
        )
        window_size = window.get("{uri:deskat:component.at-spi.gnome.org}size", "")
        window_position = [
            int(coord.strip("()")) for coord in window_position.split(",")
        ]
        window_size = [int(dim.strip("()")) for dim in window_size.split(",")]

        # Remove all ents that this window overlaps
        xy_ents = [
            (xy, e)
            for xy, e in xy_ents
            if not rect_overlaps(xy, window_position, window_size)
        ]

        # Add ents from the window
        iter_tree(window, xy_ents)

    entities = [ent for _, ent in xy_ents]
    entities = filter_reduntant_entities(entities, th=0.8)
    return entities


if __name__ == "__main__":
    print("Running accessibility demo...")
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)

    screenshot = get_screen(reuse=False)
    a11y = get_a11y(reuse=False)

    regions = propose_ents(a11y)
    rects = [
        [
            int(ent["shape"]["x"]),
            int(ent["shape"]["y"]),
            int((ent["shape"]["x"] + ent["shape"]["width"])),
            int((ent["shape"]["y"] + ent["shape"]["height"])),
        ]
        for ent in regions
    ]
    color_mapping_debug = {"a11y": "red"}
    color_mapping_prompt = {"a11y": "red"}

    import os, sys

    os.chdir("/client")
    sys.path.append("/client")

    from mm_agents.navi.screenparsing_oss.utils.obs import parser_to_prompt

    image_debug, image_prompt, list_of_text = parser_to_prompt(
        screenshot, regions, color_mapping_debug, color_mapping_prompt
    )
    image_debug.save("test_debug.png")

    # Fix the accessibility tree ordering
    fixed_a11y = fix_a11y(a11y)

    bounding_boxes = extract_bounding_boxes(fixed_a11y)

    screenshot_with_boxes = draw_bounding_boxes(screenshot, bounding_boxes)
    screenshot_with_boxes.save("test_with_boxes.png")
    screenshot_with_boxes.show()

    # Build and print the fixed accessibility tree
    root = ET.fromstring(fixed_a11y)
    tree_root = build_tree(root)
    for pre, fill, node in RenderTree(tree_root):
        print("%s%s" % (pre, node.name if node.name else node.tag))
