from PIL import Image, ImageDraw, ImageFont
import copy


def draw_colored_image(image, regions, color_mapping, draw_numbers=True):
    image_drawn = copy.copy(image)
    for region_type in regions:
        if region_type not in color_mapping:
            continue
        color = color_mapping[region_type]
        for region_id in regions[region_type]:
            # check if it's an int
            if isinstance(region_id, int):
                try:
                    if draw_numbers:
                        image_drawn = draw_bbox(
                            image_drawn,
                            regions[region_type][region_id]["rect"],
                            region_id,
                            color,
                        )
                    else:
                        image_drawn = draw_bbox(
                            image_drawn,
                            regions[region_type][region_id]["rect"],
                            None,
                            color,
                        )
                except Exception as e:
                    print(
                        "Error drawing bounding box with region id:",
                        region_id,
                        "Error:",
                        e,
                    )
    return image_drawn


def draw_bbox(image, box, number=None, color="blue"):
    draw = ImageDraw.Draw(image)
    draw.rectangle(box, outline=color, width=2)

    # number_position = "external_bottom_left"
    # number_position = "internal_top_left"
    number_position = "internal_bottom_right"

    if number is not None:
        # font_size = int((box[3] - box[1])*0.15)  # Adjust size according to your preference
        # font_size = max(12, min(40, font_size))  # Ensure the font size is not too small or too big
        font_size = 10
        font = ImageFont.truetype("arial.ttf", font_size)

        text = str(number)
        bbox_text_sizes = font.getbbox(text)  # returns (left, top, right, bottom)
        # reduce by 0.5
        bbox_text_sizes = [x * 0.5 for x in bbox_text_sizes]
        text_width, text_height = (
            bbox_text_sizes[2] - bbox_text_sizes[0],
            bbox_text_sizes[3] - bbox_text_sizes[1],
        )

        if number_position == "external_bottom_left":
            # Calculate the position of the solid background square
            box_bottom = box[3]
            background_box = [
                box[0],
                box_bottom,
                box[0] + text_width + 10,
                box_bottom + text_height + 10,
            ]
            # Adjust the text position to be centered in the background box
            text_position = (box[0] + 1, box_bottom + 1)
        elif number_position == "internal_top_left":
            background_box = [
                box[0],
                box[1],
                box[0] + text_width + 10,
                box[1] + text_height + 10,
            ]
            draw.rectangle(background_box, fill=color)
            text_position = (box[0] + 1, box[1] + 1)
        elif number_position == "internal_bottom_right":
            background_box = [
                box[2] - text_width - 10,
                box[3] - text_height - 10,
                box[2],
                box[3],
            ]
            draw.rectangle(background_box, fill=color)
            text_position = (box[2] - text_width - 9, box[3] - text_height - 9)

        # Draw the solid background square
        draw.rectangle(background_box, fill=color)

        # Draw the text
        draw.text(
            text_position, text, font=font, fill="white"
        )  # Assuming white text on colored background
        # draw.text((box[0]+5, box[1]+5), str(number), font=font, fill=color)
    return image


def draw_multiple_bboxes(image, boxes, numbers=None, color="blue"):
    for i, box in enumerate(boxes):
        image = draw_bbox(image, box, numbers[i] if numbers else None, color=color)
    return image


def in_box(box, target):
    if (
        (box[0] >= target[0])
        and (box[1] >= target[1])
        and (box[2] <= target[2])
        and (box[3] <= target[3])
    ):
        return True
    else:
        print("Error: Bounding box dim not within image!")
        return False


def crop_image(image, box, position):
    w, h = image.size
    if position == "left":
        bound = [0, 0, w / 2, h]
    elif position == "right":
        bound = [w / 2, 0, w, h]
    elif position == "top":
        bound = [0, 0, w, h / 2]
    elif position == "bottom":
        bound = [0, h / 2, w, h]
    elif position == "top left":
        bound = [0, 0, w / 2, h / 2]
    elif position == "top right":
        bound = [w / 2, 0, w, h / 2]
    elif position == "bottom left":
        bound = [0, h / 2, w / 2, h]
    elif position == "bottom right":
        bound = [w / 2, h / 2, w, h]
    else:
        bound = [0, 0, w, h]

    if in_box(box, bound):
        return image.crop(box)
    else:
        return None
