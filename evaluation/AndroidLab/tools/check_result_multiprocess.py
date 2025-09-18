import json
import math
import os
from multiprocessing import Pool

import chardet
import jsonlines
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from tqdm import tqdm

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def draw_cross_on_image(img, coordinates):
    draw = ImageDraw.Draw(img)
    x, y = coordinates
    cross_length = 100
    line_width = 20
    draw.line(
        (x - cross_length // 2, y, x + cross_length // 2, y),
        fill="green",
        width=line_width,
    )
    draw.line(
        (x, y - cross_length // 2, x, y + cross_length // 2),
        fill="green",
        width=line_width,
    )
    return img


def draw_arrow_on_image(img, start, end):
    draw = ImageDraw.Draw(img)
    arrow_length = 50
    arrow_angle = math.pi / 6
    draw.line([start, end], fill="green", width=10)
    angle = math.atan2(end[1] - start[1], end[0] - start[0]) + math.pi
    arrow_point1 = (
        end[0] + arrow_length * math.cos(angle - arrow_angle),
        end[1] + arrow_length * math.sin(angle - arrow_angle),
    )
    arrow_point2 = (
        end[0] + arrow_length * math.cos(angle + arrow_angle),
        end[1] + arrow_length * math.sin(angle + arrow_angle),
    )
    draw.polygon([end, arrow_point1, arrow_point2], fill="green")
    return img


def create_text_image(
    text, base_image, font_size=24, font_name="Songti SC", log_path=None
):
    if log_path is None:
        log_path = ".."
    text_image_path = os.path.join(log_path, "text_image.png")

    # base_image = Image.open(base_image_path)
    base_width, base_height = base_image.size

    plt.rcParams["font.sans-serif"] = [font_name]
    plt.rcParams["font.size"] = font_size
    plt.rcParams["savefig.transparent"] = True

    width = base_width / 100
    height = (base_height / 10) / 100
    dpi = 100
    fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)
    ax.text(
        0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes, color="red"
    )
    ax.axis("off")

    fig.savefig(text_image_path, format="png", transparent=True)
    plt.close(fig)

    return text_image_path


def merge_text(img, text_image, position=(0, 0)):
    base_image = img
    text_image = Image.open(text_image).convert("RGBA")
    base_width, base_height = base_image.size
    new_text_height = base_height // 10
    text_image_resized = text_image.resize((base_width, new_text_height))
    new_image = Image.new("RGBA", base_image.size)
    new_image.paste(base_image, (0, 0))
    new_image.paste(text_image_resized, position, text_image_resized)

    return new_image


def merge_text_up(img, text_image, position=(0, 0)):
    base_image = img
    text_image = Image.open(text_image).convert("RGBA")
    base_width, base_height = base_image.size

    new_text_height = base_height // 10
    text_image_resized = text_image.resize((base_width, new_text_height))

    new_image_height = base_height + new_text_height
    new_image = Image.new("RGBA", (base_width, new_image_height))

    new_image.paste(text_image_resized, position)

    base_image_position = (0, new_text_height)
    new_image.paste(base_image, base_image_position)

    return new_image


def merge_images(images):
    total_area = sum(im.size[0] * im.size[1] for im in images)
    max_width = max(im.size[0] for im in images)
    max_height = max(im.size[1] for im in images)

    side_length = int((total_area) ** 0.5)

    cols = max(max_height, side_length) // min(max_height, max_width)
    rows = len(images) // cols + (1 if len(images) % cols > 0 else 0)

    total_width = max_width * cols
    total_height = max_height * rows

    new_im = Image.new("RGBA", (total_width, total_height))

    x_offset = 0
    y_offset = 0
    for i, im in enumerate(images):
        if x_offset + im.size[0] > total_width:
            x_offset = 0
            y_offset += max_height

        new_im.paste(im, (x_offset, y_offset))
        x_offset += im.size[0]

        if (i + 1) % cols == 0:
            x_offset = 0
            y_offset += max_height

    return new_im


def make_merge_pic(log_path, save_path=None):
    trace_file = os.path.join(log_path, "traces", "trace.jsonl")
    all_images = []
    task_description = None

    def detect_encoding(file_path):
        with open(file_path, "rb") as f:
            result = chardet.detect(f.read())
        return result["encoding"]

    trace_file_encoding = detect_encoding(trace_file)
    have_finish = False

    with open(trace_file, "r") as f:
        for obj in f:
            obj = json.loads(obj)
            if task_description is None:
                task_description = obj["prompt"]
            img_path_orgin = obj["image"]
            image_filename = os.path.basename(img_path_orgin)
            image_path = os.path.join(log_path, "Screen", image_filename)
            img = Image.open(image_path)
            window = obj["window"]
            if img.size != window:
                if img.size[0] == window[1] and img.size[1] == window[0]:
                    img = img.rotate(270, expand=True)
            parsed_action = obj["parsed_action"]

            if (
                parsed_action["action"] == "Tap"
                or parsed_action["action"] == "Long Press"
            ):
                parsed_action["position_start"] = [
                    (
                        parsed_action["kwargs"]["element"][0]
                        + parsed_action["kwargs"]["element"][2]
                    )
                    / 2,
                    (
                        parsed_action["kwargs"]["element"][1]
                        + parsed_action["kwargs"]["element"][3]
                    )
                    / 2,
                ]
                start_pos = (
                    parsed_action["position_start"][0],
                    parsed_action["position_start"][1],
                )
                processed_img = draw_cross_on_image(img, start_pos)
            elif parsed_action["action"] == "Swipe":
                parsed_action["position_start"] = [
                    (
                        parsed_action["kwargs"]["element"][0]
                        + parsed_action["kwargs"]["element"][2]
                    )
                    / 2,
                    (
                        parsed_action["kwargs"]["element"][1]
                        + parsed_action["kwargs"]["element"][3]
                    )
                    / 2,
                ]
                start_pos = (
                    parsed_action["position_start"][0],
                    parsed_action["position_start"][1],
                )
                if parsed_action["kwargs"]["direction"] == "up":
                    end_pos = (
                        parsed_action["position_start"][0],
                        parsed_action["position_start"][1] - 100,
                    )
                elif parsed_action["kwargs"]["direction"] == "down":
                    end_pos = (
                        parsed_action["position_start"][0],
                        parsed_action["position_start"][1] + 100,
                    )
                elif parsed_action["kwargs"]["direction"] == "left":
                    end_pos = (
                        parsed_action["position_start"][0] - 100,
                        parsed_action["position_start"][1],
                    )
                elif parsed_action["kwargs"]["direction"] == "right":
                    end_pos = (
                        parsed_action["position_start"][0] + 100,
                        parsed_action["position_start"][1],
                    )
                processed_img = draw_arrow_on_image(img, start_pos, end_pos)
            elif parsed_action["action"] in ["Type"]:
                text = f"{parsed_action['action']}: {parsed_action['kwargs']['text']}"
                text_img = create_text_image(text, img, 48, log_path=log_path)
                processed_img = merge_text(img, text_img, position=(0, 0))
            elif parsed_action["action"] == "Press Back":
                text = "Press Back"
                text_img = create_text_image(text, img, 48, log_path=log_path)
                processed_img = merge_text(img, text_img, position=(0, 0))
            elif parsed_action["action"] == "Launch":
                text = f"{parsed_action}"
                text_img = create_text_image(text, img, 48, log_path=log_path)
                processed_img = merge_text(img, text_img, position=(0, 0))
            elif parsed_action["action"] == "finish":
                screens = os.listdir(os.path.join(log_path, "Screen"))
                for screen in screens:
                    if "end" in screen:
                        image_filename = os.path.join(log_path, "Screen", screen)
                        break
                image_path = os.path.join(log_path, "Screen", image_filename)
                img = Image.open(image_path)
                text = (
                    f"{parsed_action['action']}: {parsed_action['kwargs']['message']}"
                )
                text_img = create_text_image(text, img, 48, log_path=log_path)
                processed_img = merge_text(img, text_img, position=(0, 0))
                have_finish = True
            else:
                print("Unknown action: ", parsed_action["action"])

            if processed_img:
                all_images.append(processed_img)

    if not have_finish:
        return
    # Assuming all_images now contains all processed images
    final_image = merge_images(all_images)
    task_description = task_description.split("following task: ")[-1]
    text_img = create_text_image(
        "Task: " + task_description, final_image, 48, log_path=log_path
    )
    final_image = merge_text_up(final_image, text_img, position=(0, 0))
    if save_path is None:
        save_path = log_path
    else:
        if not os.path.exists(save_path):
            os.makedirs(save_path)
    filename = os.path.basename(log_path)
    final_image_path = os.path.join(save_path, f"{filename}_final_combined_image.png")
    final_image.save(final_image_path)
    print(f"Saved final image to {final_image_path}")


def single_worker(all_log_path, log, save_path):
    try:
        log_path = os.path.join(all_log_path, log)
        make_merge_pic(log_path, save_path)
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Error processing {log}: {e}")


def check_all_log(all_log_path, save_path=None):
    def err_call_back(err):
        print(f"error：{str(err)}")

    with Pool(processes=200) as pool:
        for log in tqdm(os.listdir(all_log_path)):
            pool.apply_async(
                single_worker,
                args=(
                    all_log_path,
                    log,
                    save_path,
                ),
                error_callback=err_call_back,
            )
        pool.close()
        pool.join()


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--directory_path", default="logs/evaluation", type=str)
    arg_parser.add_argument("--save_path", default="logs/pic", type=str)

    directory_path = arg_parser.parse_args().directory_path
    save_path = arg_parser.parse_args().save_path

    subfolders = [f.name for f in os.scandir(directory_path) if f.is_dir()]

    combined_paths = [
        os.path.join(directory_path, subfolder) for subfolder in subfolders
    ]
    combined_save_paths = [
        os.path.join(save_path, subfolder) for subfolder in subfolders
    ]

    for all_log_path, save_path in zip(combined_paths, combined_save_paths):
        check_all_log(all_log_path, save_path)
