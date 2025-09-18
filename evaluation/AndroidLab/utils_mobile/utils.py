import base64
import json
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import backoff
import cv2
import jsonlines
import openai
import pyshine as ps
from colorama import Fore, Style
from openai import OpenAI
from zhipuai import ZhipuAI

# from evaluation.definition import *
from utils_mobile.xml_tool import UIXMLTree


def get_compressed_xml(xml_path, type="json"):
    xml_parser = UIXMLTree()
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_str = f.read()
    try:
        compressed_xml = xml_parser.process(xml_str, level=1, str_type=type).strip()
    except Exception as e:
        compressed_xml = None
        print(f"XML compressed failure: {e}")
    return compressed_xml

def handle_backoff(details):
    print(f"Retry {details['tries']} for Exception: {details['exception']}")


def handle_giveup(details):
    print(
        "Backing off {wait:0.1f} seconds afters {tries} tries calling fzunction {target} with args {args} and kwargs {kwargs}"
        .format(**details))


@backoff.on_exception(backoff.expo,
                      Exception, 
                      max_tries=5,
                      on_backoff=handle_backoff, 
                      giveup=handle_giveup)  
def get_completion_glm4(prompt, glm4_key):
    client = ZhipuAI(api_key=glm4_key)
    response = client.chat.completions.create(
        model="glm-4", 
        messages=[
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def time_within_ten_secs(time1, time2):
    def parse_time(t):
        if "+" in t:
            t = t.split()[1]
            t = t.split('.')[0] + '.' + t.split('.')[1][:6]
            format = "%H:%M:%S.%f"
        else:
            format = "%H:%M:%S"
        return datetime.strptime(t, format)

    time1_parsed = parse_time(time1)
    time2_parsed = parse_time(time2)

    time_difference = abs(time1_parsed - time2_parsed)

    return time_difference <= timedelta(seconds=10)


def print_with_color(text: str, color=""):
    if color == "red":
        print(Fore.RED + text)
    elif color == "green":
        print(Fore.GREEN + text)
    elif color == "yellow":
        print(Fore.YELLOW + text)
    elif color == "blue":
        print(Fore.BLUE + text)
    elif color == "magenta":
        print(Fore.MAGENTA + text)
    elif color == "cyan":
        print(Fore.CYAN + text)
    elif color == "white":
        print(Fore.WHITE + text)
    elif color == "black":
        print(Fore.BLACK + text)
    else:
        print(text)
    print(Style.RESET_ALL)


def draw_bbox_multi(img_path, output_path, elem_list, record_mode=False, dark_mode=False):
    imgcv = cv2.imread(img_path)
    count = 1
    for elem in elem_list:
        try:
            top_left = elem.bbox[0]
            bottom_right = elem.bbox[1]
            left, top = top_left[0], top_left[1]
            right, bottom = bottom_right[0], bottom_right[1]
            label = str(count)
            if record_mode:
                if elem.attrib == "clickable":
                    color = (250, 0, 0)
                elif elem.attrib == "focusable":
                    color = (0, 0, 250)
                else:
                    color = (0, 250, 0)
                imgcv = ps.putBText(imgcv, label, text_offset_x=(left + right) // 2 + 10,
                                    text_offset_y=(top + bottom) // 2 + 10,
                                    vspace=10, hspace=10, font_scale=1, thickness=2, background_RGB=color,
                                    text_RGB=(255, 250, 250), alpha=0.5)
            else:
                text_color = (10, 10, 10) if dark_mode else (255, 250, 250)
                bg_color = (255, 250, 250) if dark_mode else (10, 10, 10)
                imgcv = ps.putBText(imgcv, label, text_offset_x=(left + right) // 2 + 10,
                                    text_offset_y=(top + bottom) // 2 + 10,
                                    vspace=10, hspace=10, font_scale=1, thickness=2, background_RGB=bg_color,
                                    text_RGB=text_color, alpha=0.5)
        except Exception as e:
            print_with_color(f"ERROR: An exception occurs while labeling the image\n{e}", "red")
        count += 1
    cv2.imwrite(output_path, imgcv)
    return imgcv


def draw_grid(img_path, output_path):
    def get_unit_len(n):
        for i in range(1, n + 1):
            if n % i == 0 and 120 <= i <= 180:
                return i
        return -1

    image = cv2.imread(img_path)
    height, width, _ = image.shape
    color = (255, 116, 113)
    unit_height = get_unit_len(height)
    if unit_height < 0:
        unit_height = 120
    unit_width = get_unit_len(width)
    if unit_width < 0:
        unit_width = 120
    thick = int(unit_width // 50)
    rows = height // unit_height
    cols = width // unit_width
    for i in range(rows):
        for j in range(cols):
            label = i * cols + j + 1
            left = int(j * unit_width)
            top = int(i * unit_height)
            right = int((j + 1) * unit_width)
            bottom = int((i + 1) * unit_height)
            cv2.rectangle(image, (left, top), (right, bottom), color, thick // 2)
            cv2.putText(image, str(label), (left + int(unit_width * 0.05) + 3, top + int(unit_height * 0.3) + 3), 0,
                        int(0.01 * unit_width), (0, 0, 0), thick)
            cv2.putText(image, str(label), (left + int(unit_width * 0.05), top + int(unit_height * 0.3)), 0,
                        int(0.01 * unit_width), color, thick)
    cv2.imwrite(output_path, image)
    return rows, cols


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


import os
import subprocess


def start_screen_record(self, file_name):
    print("Starting screen record")
    command = f'adb shell screenrecord /sdcard/{file_name}.mp4'
    self.process = subprocess.Popen(command, shell=True)


def write_jsonl(data: List[dict], path: str, append: bool = False):
    with jsonlines.open(path, mode='a' if append else 'w') as writer:
        for item in data:
            writer.write(item)


def del_file(path):
    for elm in Path(path).glob('*'):
        elm.unlink() if elm.is_file() else shutil.rmtree(elm)
    if os.path.exists(path):
        os.rmdir(path)


def copy_directory(source_dir, target_dir):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        target_item = os.path.join(target_dir, item)

        if os.path.isdir(source_item):
            shutil.copytree(source_item, target_item)
        else:
            shutil.copy2(source_item, target_item)


def remove_punctuation(input_string):
    punc = u'[\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b]'
    punc_en = r"[!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~\n]"
    st = re.sub(punc, ' ', input_string)
    st = re.sub(punc_en, " ", st)
    return st


def contains_chinese(text):
    pattern = re.compile('[\u4e00-\u9fff]+')
    match = pattern.search(text)
    return bool(match)


def split_chunks(lst, num_chunks):
    avg = len(lst) // num_chunks
    remainder = len(lst) % num_chunks
    chunks = []
    i = 0
    for _ in range(num_chunks):
        chunk_size = avg + (1 if remainder > 0 else 0)
        chunks.append(lst[i:i + chunk_size])
        i += chunk_size
        remainder -= 1
    return chunks


def glm_call(prompt, temperature=0.7, top_p=0.9):
    for i in range(3):
        try:
            client = OpenAI(
                api_key="XqtuAVdoULyAW5P39MNim3u14Zchg2MMXZltzNcCvKLFhxF7GwxYlxdXvbE5amkf",
                base_url="https://api.chatglm.cn/v1",
            )
            res = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="glm-4-public",
                temperature=temperature,
                top_p=top_p,
                stream=False,
                max_tokens=128,
            )
            res = res.choices[0].message.content
            break
        except Exception as e:
            if "404" in e:
                exit(0)
            print(f'Api error, retry times: {i + 1}, error: {e}')
            time.sleep(0.2)
    return res


def get_xml_list(xml_path):
    xml_parser = UIXMLTree()
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_str = f.read()
    try:
        compressed_xml = xml_parser.process(xml_str, level=1, str_type="list")
    except Exception as e:
        compressed_xml = None
        print(f"XML compressed failure: {e}")
    return compressed_xml


def dump_xml(controller, device_name=None, accessiblity=False, task_id="0"):
    save_dir = "logs/auto-test/xmls"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    if accessiblity:
        controller.get_ac_xml(prefix=task_id, save_dir=save_dir)
    else:
        controller.get_xml(prefix=task_id, save_dir=save_dir)
    xml_path = os.path.join(save_dir, f"{task_id}.xml")
    xml_compressed = get_compressed_xml(xml_path)
    print(xml_compressed)
    return json.loads(xml_compressed)


def load_json(path, encoding='utf-8'):
    return json.load(open(path, encoding=encoding))


def save_json(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_jsonl(path, encoding='utf-8'):
    res = []
    with open(path, encoding=encoding) as f:
        for line in f:
            res.append(json.loads(line))
    return res


def save_jsonl(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        for item in obj:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def write_jsonl(data: List[dict], path: str, append: bool = False):
    with jsonlines.open(path, mode='a' if append else 'w') as writer:
        for item in data:
            writer.write(item)


def del_file(path):
    for elm in Path(path).glob('*'):
        elm.unlink() if elm.is_file() else shutil.rmtree(elm)
    if os.path.exists(path):
        os.rmdir(path)


def copy_directory(source_dir, target_dir):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        target_item = os.path.join(target_dir, item)

        if os.path.isdir(source_item):
            shutil.copytree(source_item, target_item)
        else:
            shutil.copy2(source_item, target_item)


def remove_punctuation(input_string):
    punc = u'[\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b]'
    punc_en = r"[!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~\n]"
    st = re.sub(punc, ' ', input_string)
    st = re.sub(punc_en, " ", st)
    return st


def contains_chinese(text):
    pattern = re.compile('[\u4e00-\u9fff]+')
    match = pattern.search(text)
    return bool(match)


def split_chunks(lst, num_chunks):
    avg = len(lst) // num_chunks
    remainder = len(lst) % num_chunks
    chunks = []
    i = 0
    for _ in range(num_chunks):
        chunk_size = avg + (1 if remainder > 0 else 0)
        chunks.append(lst[i:i + chunk_size])
        i += chunk_size
        remainder -= 1
    return chunks


def glm_call(prompt, temperature=0.7, top_p=0.9):
    for i in range(3):
        try:
            client = OpenAI(
                api_key="XqtuAVdoULyAW5P39MNim3u14Zchg2MMXZltzNcCvKLFhxF7GwxYlxdXvbE5amkf",
                base_url="https://api.chatglm.cn/v1",
            )
            res = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="glm-4-public",
                temperature=temperature,
                top_p=top_p,
                stream=False,
                max_tokens=128,
            )
            res = res.choices[0].message.content
            break
        except Exception as e:
            if "404" in e:
                exit(0)
            print(f'Api error, retry times: {i + 1}, error: {e}')
            time.sleep(0.2)
    return res


class OpenAIEngine:
    def __init__(
            self,
            api_key: str,
            api_base: str,
            model_name: str = 'gpt-4-turbo-2024-04-09',
            max_new_tokens: int = 2048,
            temperature: float = 0.7,
            top_p: float = 0.9,
            retries: int = 3,  # Adding a parameter for retries
            backoff_factor: float = 1.0,  # Adding a parameter for backoff
            **kwargs
    ) -> None:
        self.client = openai.OpenAI(api_key=api_key, base_url=api_base)
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.kwargs = kwargs

    def generate(self, messages) -> str:
        attempt = 0
        while attempt < self.retries:
            try:
                r = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=self.max_new_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p
                )
                return r.choices[0].message.content
            except Exception as e:
                attempt += 1
                if attempt == self.retries:
                    raise e
                time.sleep(self.backoff_factor * (2 ** (attempt - 1)))


def extract_bounds(node, path=""):
    result = []
    for key, value in node.items():
        current_path = f"{path}{key} "
        if isinstance(value, dict):
            result.extend(extract_bounds(value, current_path))
        elif key == "bounds":
            result.append({"key": path.strip(), "value": value})
    return result
