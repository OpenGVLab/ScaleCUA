import io
import os
import xml.etree.ElementTree as ET
from typing import Tuple, List
import json
import copy
import click

from PIL import Image, ImageDraw, ImageFont


def find_leaf_nodes(xlm_file_str):
    if not xlm_file_str:
        return []

    root = ET.fromstring(xlm_file_str)

    # Recursive function to traverse the XML tree and collect leaf nodes
    def collect_leaf_nodes(node, leaf_nodes):
        # If the node has no children, it is a leaf node, add it to the list
        if not list(node):
            leaf_nodes.append(node)
        # If the node has children, recurse on each child
        for child in node:
            collect_leaf_nodes(child, leaf_nodes)

    # List to hold all leaf nodes
    leaf_nodes = []
    collect_leaf_nodes(root, leaf_nodes)
    return leaf_nodes


state_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/state"
state_ns_windows = "https://accessibility.windows.example.org/ns/state"
component_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/component"
component_ns_windows = "https://accessibility.windows.example.org/ns/component"
value_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/value"
value_ns_windows = "https://accessibility.windows.example.org/ns/value"
class_ns_windows = "https://accessibility.windows.example.org/ns/class"

A11Y_TREE_SPLIT_TAG = "@@@"


def judge_node(node: ET, platform="ubuntu", check_image=False) -> bool:
    if platform == "ubuntu":
        _state_ns = state_ns_ubuntu
        _component_ns = component_ns_ubuntu
    elif platform == "windows":
        _state_ns = state_ns_windows
        _component_ns = component_ns_windows
    else:
        raise ValueError("Invalid platform, must be 'ubuntu' or 'windows'")

    keeps: bool = (
        node.tag.startswith("document")
        or node.tag.endswith("item")
        or node.tag.endswith("button")
        or node.tag.endswith("heading")
        or node.tag.endswith("label")
        or node.tag.endswith("scrollbar")
        or node.tag.endswith("searchbox")
        or node.tag.endswith("textbox")
        or node.tag.endswith("link")
        or node.tag.endswith("tabelement")
        or node.tag.endswith("textfield")
        or node.tag.endswith("textarea")
        or node.tag.endswith("menu")
        or node.tag
        in {
            "alert",
            "canvas",
            "check-box",
            "combo-box",
            "entry",
            "icon",
            "image",
            "paragraph",
            "scroll-bar",
            "section",
            "slider",
            "static",
            "table-cell",
            "terminal",
            "text",
            "netuiribbontab",
            "start",
            "trayclockwclass",
            "traydummysearchcontrol",
            "uiimage",
            "uiproperty",
            "uiribboncommandbar",
        }
    )
    keeps = (
        keeps
        and (
            platform == "ubuntu"
            and node.get("{{{:}}}showing".format(_state_ns), "false") == "true"
            and node.get("{{{:}}}visible".format(_state_ns), "false") == "true"
            or platform == "windows"
            and node.get("{{{:}}}visible".format(_state_ns), "false") == "true"
        )
        and (
            node.get("{{{:}}}enabled".format(_state_ns), "false") == "true"
            or node.get("{{{:}}}editable".format(_state_ns), "false") == "true"
            or node.get("{{{:}}}expandable".format(_state_ns), "false") == "true"
            or node.get("{{{:}}}checkable".format(_state_ns), "false") == "true"
        )
        and (
            node.get("name", "") != ""
            or node.text is not None
            and len(node.text) > 0
            or check_image
            and node.get("image", "false") == "true"
        )
    )

    coordinates: Tuple[int, int] = eval(
        node.get("{{{:}}}screencoord".format(_component_ns), "(-1, -1)")
    )
    sizes: Tuple[int, int] = eval(
        node.get("{{{:}}}size".format(_component_ns), "(-1, -1)")
    )
    keeps = (
        keeps
        and coordinates[0] >= 0
        and coordinates[1] >= 0
        and sizes[0] > 0
        and sizes[1] > 0
    )
    return keeps


sidebar_nodes = json.load(
    open(
        os.path.join(os.path.abspath(os.path.dirname(__file__)), "sidebar_nodes.json"),
        "r",
    )
)


def is_sidebar_node(node: ET, platform="ubuntu"):
    if platform == "ubuntu":
        _state_ns = state_ns_ubuntu
        _component_ns = component_ns_ubuntu
    elif platform == "windows":
        _state_ns = state_ns_windows
        _component_ns = component_ns_windows
    else:
        raise ValueError("Invalid platform, must be 'ubuntu' or 'windows'")

    name = node.get("name", "")
    tag = node.tag
    coords_str = node.attrib.get("{{{:}}}screencoord".format(_component_ns))
    size_str = node.attrib.get("{{{:}}}size".format(_component_ns))

    if coords_str and size_str:
        if (
            name in sidebar_nodes
            and sidebar_nodes[name]["coords_str"] == coords_str
            and sidebar_nodes[name]["size_str"] == size_str
            and sidebar_nodes[name]["tag"] == tag
        ):
            return True
    return False


def is_interactive_node(node: ET, platform="ubuntu"):
    interactive_tags = ["button", "box", "menu", "entry", "link", "bar", "item"]
    noninteractive_tags = [
        "heading",
        "static",
        "document",
        "label",
        "cell",
        "text",
        "icon",
        "paragraph",
        "section",
    ]  # FIXME: cell?

    tag = node.tag
    interactive = False
    for t in interactive_tags:
        if t in tag:
            interactive = True
            break

    return interactive


def is_wrong_node(node: ET, platform="ubuntu"):
    libreoffice_menu_names = [
        "File",
        "Edit",
        "View",
        "Insert",
        "Format",
        "Tools",
        "Window",
        "Help",
        "Styles",
        "Slide",
        "Slide Show",
        "Sheet",
        "Data",
        "Table",
        "Form",
    ]
    tag = node.tag
    name = node.get("name", "")
    text = node.text
    return name in libreoffice_menu_names and tag == "menu" and name == text


def is_undo_or_redo_node(node: ET, platform="ubuntu"):
    name = node.get("name", "")
    return name in ["Undo", "Redo"]


def judge_overlap_node(node_list, node, platform="ubuntu", ratio=1.0):
    if platform == "ubuntu":
        _state_ns = state_ns_ubuntu
        _component_ns = component_ns_ubuntu
    elif platform == "windows":
        _state_ns = state_ns_windows
        _component_ns = component_ns_windows
    else:
        raise ValueError("Invalid platform, must be 'ubuntu' or 'windows'")

    def _get_node_coord_and_size(node):
        coords_str = node.attrib.get("{{{:}}}screencoord".format(_component_ns))
        size_str = node.attrib.get("{{{:}}}size".format(_component_ns))
        coords = tuple(map(int, coords_str.strip("()").split(", ")))
        size = tuple(map(int, size_str.strip("()").split(", ")))
        return coords, size

    coords, size = _get_node_coord_and_size(node)
    x, y = coords
    w, h = size

    new_node_list = []
    keep = True
    for _node in node_list:
        if not keep:
            new_node_list.append(_node)
            continue
        _coords, _size = _get_node_coord_and_size(_node)
        _x, _y = _coords
        _w, _h = _size
        # Compute overlap rectangle
        x_overlap = max(0, min(x + w, _x + _w) - max(x, _x))
        y_overlap = max(0, min(y + h, _y + _h) - max(y, _y))
        if w * h < _w * _h:
            overlap_ratio = x_overlap * y_overlap / w * h
            if overlap_ratio >= ratio:
                # new node is smaller and overlapped by the current node
                keep = False
        else:
            overlap_ratio = x_overlap * y_overlap / _w * _h
            if overlap_ratio >= ratio:
                # current node is smaller and overlapped by the new node
                continue
        new_node_list.append(_node)

    return keep, new_node_list


def is_close_node(node: ET, platform="ubuntu"):
    if platform == "ubuntu":
        _state_ns = state_ns_ubuntu
        _component_ns = component_ns_ubuntu
    elif platform == "windows":
        _state_ns = state_ns_windows
        _component_ns = component_ns_windows
    else:
        raise ValueError("Invalid platform, must be 'ubuntu' or 'windows'")

    name = node.get("name", "")
    return name == "Close" or name == "close"


def filter_nodes(
    root: ET, platform="ubuntu", check_image=False, mode="", overlap_ratio=1.0
):
    filtered_nodes = []

    for node in root.iter():
        if judge_node(node, platform, check_image):
            keep = True
            if "nosidebar" in mode:
                keep = keep and not is_sidebar_node(node, platform)
            if "interactive" in mode:
                keep = keep and is_interactive_node(node, platform)
            if "noclose" in mode:
                keep = keep and not is_close_node(node, platform)
            if "nowrong" in mode:
                keep = keep and not is_wrong_node(node, platform)
            if "nounre" in mode:
                keep = keep and not is_undo_or_redo_node(node, platform)
            if keep and "nonoverlap" in mode:
                keep, filtered_nodes = judge_overlap_node(
                    filtered_nodes, node, platform, overlap_ratio
                )
            if keep:
                filtered_nodes.append(node)
                # print(ET.tostring(node, encoding="unicode"))

    return filtered_nodes


def draw_bounding_boxes(
    nodes, image_file_content, down_sampling_ratio=1.0, platform="ubuntu"
):

    if platform == "ubuntu":
        _state_ns = state_ns_ubuntu
        _component_ns = component_ns_ubuntu
        _value_ns = value_ns_ubuntu
    elif platform == "windows":
        _state_ns = state_ns_windows
        _component_ns = component_ns_windows
        _value_ns = value_ns_windows
    else:
        raise ValueError("Invalid platform, must be 'ubuntu' or 'windows'")

    # Load the screenshot image
    image_stream = io.BytesIO(image_file_content)
    image = Image.open(image_stream)
    if float(down_sampling_ratio) != 1.0:
        image = image.resize(
            (
                int(image.size[0] * down_sampling_ratio),
                int(image.size[1] * down_sampling_ratio),
            )
        )
    draw = ImageDraw.Draw(image)
    marks = []
    drew_nodes = []
    text_informations: List[str] = ["index\ttag\tname\ttext"]

    try:
        # Adjust the path to the font file you have or use a default one
        font = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        # Fallback to a basic font if the specified font can't be loaded
        font = ImageFont.load_default()

    index = 1

    # Loop over all the visible nodes and draw their bounding boxes
    for _node in nodes:
        coords_str = _node.attrib.get("{{{:}}}screencoord".format(_component_ns))
        size_str = _node.attrib.get("{{{:}}}size".format(_component_ns))

        if coords_str and size_str:
            try:
                # Parse the coordinates and size from the strings
                coords = tuple(map(int, coords_str.strip("()").split(", ")))
                size = tuple(map(int, size_str.strip("()").split(", ")))

                import copy

                original_coords = copy.deepcopy(coords)
                original_size = copy.deepcopy(size)

                if float(down_sampling_ratio) != 1.0:
                    # Downsample the coordinates and size
                    coords = tuple(int(coord * down_sampling_ratio) for coord in coords)
                    size = tuple(int(s * down_sampling_ratio) for s in size)

                # Check for negative sizes
                if size[0] <= 0 or size[1] <= 0:
                    raise ValueError(f"Size must be positive, got: {size}")

                # Calculate the bottom-right corner of the bounding box
                bottom_right = (coords[0] + size[0], coords[1] + size[1])

                # Check that bottom_right > coords (x1 >= x0, y1 >= y0)
                if bottom_right[0] < coords[0] or bottom_right[1] < coords[1]:
                    raise ValueError(
                        f"Invalid coordinates or size, coords: {coords}, size: {size}"
                    )

                # Check if the area only contains one color
                cropped_image = image.crop((*coords, *bottom_right))
                if len(set(list(cropped_image.getdata()))) == 1:
                    continue

                # Draw rectangle on image
                draw.rectangle([coords, bottom_right], outline="red", width=1)

                # Draw index number at the bottom left of the bounding box with black background
                text_position = (
                    coords[0],
                    bottom_right[1],
                )  # Adjust Y to be above the bottom right
                text_bbox: Tuple[int, int, int, int] = draw.textbbox(
                    text_position, str(index), font=font, anchor="lb"
                )
                # offset: int = bottom_right[1]-text_bbox[3]
                # text_bbox = (text_bbox[0], text_bbox[1]+offset, text_bbox[2], text_bbox[3]+offset)

                # draw.rectangle([text_position, (text_position[0] + 25, text_position[1] + 18)], fill='black')
                draw.rectangle(text_bbox, fill="black")
                draw.text(
                    text_position, str(index), font=font, anchor="lb", fill="white"
                )

                # each mark is an x, y, w, h tuple
                marks.append(
                    [
                        original_coords[0],
                        original_coords[1],
                        original_size[0],
                        original_size[1],
                    ]
                )
                drew_nodes.append(_node)

                if _node.text:
                    node_text = (
                        _node.text
                        if '"' not in _node.text
                        else '"{:}"'.format(_node.text.replace('"', '""'))
                    )
                elif _node.get("{{{:}}}class".format(class_ns_windows), "").endswith(
                    "EditWrapper"
                ) and _node.get("{{{:}}}value".format(_value_ns)):
                    node_text = _node.get("{{{:}}}value".format(_value_ns), "")
                    node_text = (
                        node_text
                        if '"' not in node_text
                        else '"{:}"'.format(node_text.replace('"', '""'))
                    )
                else:
                    node_text = '""'
                # attr = _node.attrib.get("{{{:}}}toolkit".format("https://accessibility.windows.example.org/ns/attribute"), "")
                # text_information: str = "{:d}\t{:}\t{:}\t{:}\t{:}".format(index, _node.tag, _node.get("name", ""), node_text, attr)
                text_information: str = "{:d}\t{:}\t{:}\t{:}".format(
                    index, _node.tag, _node.get("name", ""), node_text
                )
                text_informations.append(text_information)

                # image.save(f'./imgs/{index}.png', format='PNG')
                # sidebar_nodes[_node.get("name", "")] = {
                #     'tag' : f'{_node.tag}',
                #     'coords_str': coords_str,
                #     'size_str': size_str,
                # }

                # print(ET.tostring(_node, encoding="unicode"))
                # print(text_information)
                index += 1

            except ValueError:
                pass
    # with open('./sidebar_nodes.json', "w") as f:
    #     json.dump(sidebar_nodes, fp=f, indent=4)
    # import ipdb; ipdb.set_trace()
    output_image_stream = io.BytesIO()
    image.save(output_image_stream, format="PNG")
    # image.save(f'./som.png', format='PNG')
    image_content = output_image_stream.getvalue()

    return marks, drew_nodes, A11Y_TREE_SPLIT_TAG.join(text_informations), image_content


def get_clickable_elements(html_str, platform="ubuntu"):
    """Return List[Dict[str, Any]]"""
    root = ET.fromstring(html_str)
    nodes = filter_nodes(
        root, platform="ubuntu", check_image=True, mode="nosidebar_interactive"
    )

    if platform == "ubuntu":
        _state_ns = state_ns_ubuntu
        _component_ns = component_ns_ubuntu
        _value_ns = value_ns_ubuntu
    elif platform == "windows":
        _state_ns = state_ns_windows
        _component_ns = component_ns_windows
        _value_ns = value_ns_windows
    else:
        raise ValueError("Invalid platform, must be 'ubuntu' or 'windows'")

    index = 0
    clickable_elements = []
    for _node in nodes:
        coords_str = _node.attrib.get("{{{:}}}screencoord".format(_component_ns))
        size_str = _node.attrib.get("{{{:}}}size".format(_component_ns))
        if coords_str and size_str:
            try:
                # Parse the coordinates and size from the strings
                coords = tuple(map(int, coords_str.strip("()").split(", ")))
                size = tuple(map(int, size_str.strip("()").split(", ")))

                # Check for negative sizes
                if size[0] <= 0 or size[1] <= 0:
                    raise ValueError(f"Size must be positive, got: {size}")

                # Calculate the bottom-right corner of the bounding box
                bottom_right = (coords[0] + size[0], coords[1] + size[1])

                # Check that bottom_right > coords (x1 >= x0, y1 >= y0)
                if bottom_right[0] < coords[0] or bottom_right[1] < coords[1]:
                    raise ValueError(
                        f"Invalid coordinates or size, coords: {coords}, size: {size}"
                    )

                if _node.text:
                    node_text = (
                        _node.text
                        if '"' not in _node.text
                        else '"{:}"'.format(_node.text.replace('"', '""'))
                    )
                elif _node.get("{{{:}}}class".format(class_ns_windows), "").endswith(
                    "EditWrapper"
                ) and _node.get("{{{:}}}value".format(_value_ns)):
                    node_text = _node.get("{{{:}}}value".format(_value_ns), "")
                    node_text = (
                        node_text
                        if '"' not in node_text
                        else '"{:}"'.format(node_text.replace('"', '""'))
                    )
                else:
                    node_text = ""

                clickable_elements.append(
                    {
                        "id": index,
                        "bbox": [
                            coords[0],
                            coords[1],
                            bottom_right[0],
                            bottom_right[1],
                        ],
                        "text": node_text,
                        "name": _node.get("name", ""),
                    }
                )

                index += 1
            except ValueError:
                pass

    return clickable_elements


def print_nodes_with_indent(nodes, indent=0):
    for node in nodes:
        print(" " * indent, node.tag, node.attrib)
        print_nodes_with_indent(node, indent + 2)


@click.command()
@click.option("--step-idx", type=int, required=True, help="Step index value")
@click.option("--root", type=str, required=True, help="Root directory path")
@click.option("--filter_mode", type=str, default="nosidebar_interactive")
def main(step_idx, root, filter_mode):
    with open(os.path.join(root, f"a11y_tree_at_step_{step_idx}.txt")) as f:
        tree = ET.parse(f)
    with open(os.path.join(root, f"step_{step_idx}.png"), "rb") as f:
        screenshot = f.read()
    filtered_nodes = filter_nodes(
        tree.getroot(),
        platform="ubuntu",
        check_image=True,
        mode=filter_mode,
        overlap_ratio=1.0,
    )
    marks, drew_nodes, element_list, tagged_screenshot = draw_bounding_boxes(
        filtered_nodes, screenshot
    )
    element_list = element_list.split(A11Y_TREE_SPLIT_TAG)
    for info in element_list:
        print(info)


if __name__ == "__main__":
    main()
