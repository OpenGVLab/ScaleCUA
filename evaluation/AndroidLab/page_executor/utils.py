import textwrap

import cv2
import requests


def _add_text(instruction, image):
    screen_height, screen_width, _ = image.shape

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5  # adjust this as needed
    font_thickness = 2
    wrap_width = int(
        screen_width / cv2.getTextSize("a", font, font_scale, font_thickness)[0][0]
    )

    x, y = 5, 50  # Text starting position
    line_spacing = 45  # adjust this as needed

    # Split text into multiple lines
    wrapped_text = textwrap.wrap(instruction, width=wrap_width)

    for i, line in enumerate(wrapped_text):
        y_new = y + i * int(
            cv2.getTextSize(line, font, font_scale, font_thickness)[0][1] + line_spacing
        )

        # Drawing Text Background
        textSize = cv2.getTextSize(line, font, font_scale, font_thickness)[0]
        text_box_y = y_new - textSize[1] - 5  # adjust 5 for better alignment
        cv2.rectangle(
            image,
            (x, text_box_y),
            (screen_width, text_box_y + textSize[1] + 10),
            (0, 0, 0),
            -1,
        )

        # Drawing Text
        cv2.putText(
            image,
            line,
            (x, y_new),
            font,
            font_scale,
            (255, 255, 255),
            font_thickness,
            cv2.LINE_AA,
        )

    return image


def plot_bbox(bbox, screenshot, instruction=None):
    image = cv2.imread(screenshot)
    cv2.rectangle(image, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
    cv2.circle(
        image,
        (int(bbox[0] + bbox[2] / 2), int(bbox[1] + bbox[3] / 2)),
        radius=0,
        color=(0, 255, 0),
        thickness=2,
    )
    if instruction is not None:
        image = _add_text(instruction, image)

    cv2.imwrite(screenshot.replace(".png", "-bbox.png"), image)


def call_dino(instruction, screenshot_path):
    files = {"image": open(screenshot_path, "rb")}
    response = requests.post(
        "http://172.19.128.24:24020/v1/executor",
        files=files,
        data={"text_prompt": f"{instruction}"},
    )
    return [int(s) for s in response.json()["response"].split(",")]


def get_relative_bbox_center(page, instruction, screenshot):
    relative_bbox = call_dino(instruction, screenshot)

    viewport_size = page.viewport_size
    # print(viewport_size)
    viewport_width = viewport_size["width"]
    viewport_height = viewport_size["height"]

    center_x = (relative_bbox[0] + relative_bbox[2]) / 2 * viewport_width / 1000
    center_y = (relative_bbox[1] + relative_bbox[3]) / 2 * viewport_height / 1000
    width_x = (relative_bbox[2] - relative_bbox[0]) * viewport_width / 1000
    height_y = (relative_bbox[3] - relative_bbox[1]) * viewport_height / 1000

    # print(center_x, center_y)
    plot_bbox(
        [
            int(center_x - width_x / 2),
            int(center_y - height_y / 2),
            int(width_x),
            int(height_y),
        ],
        screenshot,
    )

    return (int(center_x), int(center_y)), relative_bbox
