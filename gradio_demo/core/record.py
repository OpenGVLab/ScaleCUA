import os
import re
import dataclasses
import copy
import hashlib
import datetime
import json
from io import BytesIO
from PIL import Image
from typing import Any, List, Dict, Union, Optional
from dataclasses import field
from gradio import ChatMessage
from matplotlib.widgets import EllipseSelector

from .utils import (
    LOGDIR,
    image2base64,
    video2base64,
    resize_img,
    url_to_base64,
    load_image_from_base64,
    base64_to_bytes,
)


min_pixels = 3136
# max_pixels = 937664  # 720P
# max_pixels = 2109744  # 1080P
max_pixels = 3750656  # 2K


@dataclasses.dataclass
class Record:
    """A class that keeps all conversation history."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

    roles: List[str] = field(
        default_factory=lambda: [
            Record.SYSTEM,
            Record.USER,
            Record.ASSISTANT,
        ]
    )
    # mandatory_system_message: Optional[str] = 'Your name is "开放世界助手" developed by Tsinghua University.'
    mandatory_system_message: Optional[str] = None
    system_message: str = "You are a helpful assistant."
    messages: List[Dict[str, Any]] = field(default_factory=lambda: [])
    files: Dict[str, Any] = field(default_factory=lambda: {})
    max_image_limit: int = 4
    skip_next: bool = False
    streaming_placeholder: str = "▌"
    task: str | None = None

    def get_system_message(self):
        if self.mandatory_system_message is None:
            return self.system_message

        return self.mandatory_system_message + "\n\n" + self.system_message

    def set_system_message(self, system_message: str):
        self.system_message = system_message
        return self

    def get_prompt(self, show_file_path=False):
        messages = copy.deepcopy(self.messages)
        if show_file_path:
            return messages

        """
        for msg in messages:
            if type(msg["content"]) is list:
                for item in msg["content"]:
                    if msg["role"] == self.USER and item["type"] != "text":
                        if item[item["type"]]["url"].startswith("Path: "):
                            file_key = item["type"]
                            path = self.get_filepath(item)
                            item[file_key]["url"] = self.files[path][file_key]["url"]
        """
        new_messages = []
        if self.system_message is not None:
            new_messages.append({"role": self.SYSTEM, "content": self.get_system_message()})
        for msg in messages:
            new_messages.append({"role": msg["role"], "content": []})
            if type(msg["content"]) is str:
                new_messages[-1]["content"].append(
                    {"type": "text", "text": msg["content"]}
                )
                continue

            assert (
                type(msg["content"]) is list
            ), f"Invalid content type: {type(msg['content'])}"
            if msg["role"] == self.USER:
                for item in msg["content"]:
                    if item["type"] != "text" and item[item["type"]]["url"].startswith(
                        "Path: "
                    ):
                        # file_key = item["type"]
                        path = self.get_filepath(item)
                        # item[file_key]["url"] = self.files[path][file_key]["url"]
                        new_messages[-1]["content"].append(
                            {
                                "type": item["type"],
                                item["type"]: {
                                    "url": self.files[path][item["type"]]["url"],
                                    "min_pixels": item[item["type"]].get(
                                        "min_pixels", min_pixels
                                    ),
                                    "max_pixels": item[item["type"]].get(
                                        "max_pixels", max_pixels
                                    ),
                                },
                            }
                        )
                    else:
                        new_messages[-1]["content"].append(item)
            else:
                for item in msg["content"]:
                    if item["type"] == "text":
                        new_messages[-1]["content"].append(item)

        return new_messages

    def append_message(
        self,
        role,
        content=None,
        file_list=[],
    ):
        msg_content = []
        # if content is not None:
        #     msg_content.append({"type": "text", "text": content})

        if len(file_list) > 0:
            files = []
            for file_item in file_list:
                if file_item["type"] == "image":
                    files.append(
                        {
                            "type": "image_url",
                            "min_pixels": min_pixels,
                            "max_pixels": max_pixels,
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + image2base64(file_item["value"])
                            },
                        }
                    )
                elif file_item["type"] == "video":
                    if isinstance(file_item["value"], list):
                        files.append(
                            {
                                "type": "frame_url",
                                "min_pixels": min_pixels,
                                "max_pixels": max_pixels,
                                "frame_url": {
                                    "url": "data:image/png;base64,"
                                    + image2base64(file_item["value"])
                                },
                            }
                        )
                    elif isinstance(file_item["value"], str):
                        ext = file_item["value"].split(".")[-1]
                        files.append(
                            {
                                "type": "video_url",
                                "video_url": {
                                    "url": f"data:video/{ext};base64,"
                                    + video2base64(file_item["value"])
                                },
                            }
                        )
            files = self.save_files(files, cached=True)
            msg_content += files

        if content is not None:
            msg_content.append({"type": "text", "text": content})

        self.messages.append(
            {
                "role": role,
                "content": msg_content,
            }
        )

    def get_filepath(self, item):
        file_url = item[item["type"]]["url"]
        if file_url.startswith("Path: "):
            return file_url[6:].strip()

        return self.save_files([item], cached=True)

    def get_files(
        self,
        source: Union[str, None] = None,
    ):
        assert source in [self.USER, self.ASSISTANT, None], f"Invalid source: {source}"
        files = []
        for _, msg in enumerate(self.messages):
            if source and msg["role"] != source:
                continue

            for item in msg.get("content", []):
                if item["type"] == "text":
                    continue

                files.append(self.get_filepath(item))

        return files
    
    def get_images(
        self,
        source: Union[str, None] = None,
    ):
        # files = self.get_files(source)
        # files = [f for f in files if "image" in f["type"]]
        assert source in [self.USER, self.ASSISTANT, None], f"Invalid source: {source}"
        files = []
        for _, msg in enumerate(self.messages):
            if source and msg["role"] != source:
                continue

            for item in msg.get("content", []):
                if "image" in item["type"] and item["type"] != "text":
                    files.append(self.get_filepath(item))
        return files

    def extract_function(self, text):
        pattern = r"<function=\s*(\w+)>(\{.*?\})\s*</function>"
        while "<function=" in text and "</function>" in text:
            match = re.search(pattern, text)

            if match:
                function_name = match.group(1)
                arguments = match.group(2)
                new_format = {"name": function_name, "arguments": json.loads(arguments)}

                text = re.sub(
                    pattern,
                    f"\n{json.dumps(new_format, ensure_ascii=False)}\n",
                    text,
                    count=1,
                )

        return text

    def to_gradio_chatbot(self, streaming=True):
        history = []
        for i, msg in enumerate(self.messages):
            if msg["role"] == self.SYSTEM:
                continue

            alt_str = "uploaded image" if msg["role"] == self.USER else "output image"
            text_content = ""
            file_list = []
            for item in msg["content"]:
                if item["type"] == "text":
                    text_content += item["text"]
                    # text_item = {"role": msg["role"], "content": item["text"]}
                elif item["type"] in ["image_url", "video_url", "frame_url"]:
                    file_list.append(
                        {
                            "role": msg["role"],
                            "content": {"path": self.get_filepath(item)},
                        }
                    )
                else:
                    raise ValueError(f"Invalid item type: {item['type']}")

            use_tool = False
            if msg["role"] == self.USER:
                history.extend(file_list)
                if text_content.strip != "":
                    history.append({"role": msg["role"], "content": text_content})
            elif msg["role"] == self.ASSISTANT:
                if text_content.strip != "":
                    history.append({"role": msg["role"], "content": text_content})
                history.extend(file_list)
            else:
                if "<function=" in text_content:
                    if "</function>" in text_content:
                        text_content = self.extract_function(text_content)
                        # msg_str = text_content + " ".join(file_str_list)
                    else:
                        idx = text_content.find("<function=")
                        text_content = text_content[:idx]
                    use_tool = True
                if streaming and i == len(self.messages) - 1:
                    text_content += self.streaming_placeholder

                item = {"role": msg["role"], "content": text_content}
                # if use_tool:
                #     item["metadata"] = {"title": "🛠️ Calling tool"}
                history.append(item)
                history.extend(file_list)
        return history

    def update_message(self, role, content, files=None, idx=-1, mode="append"):
        assert len(self.messages) > 0, "No message in the conversation."

        idx = (idx + len(self.messages)) % len(self.messages)

        assert (
            self.messages[idx]["role"] == role
        ), f"Role mismatch: {role} vs {self.messages[idx]['role']}"

        if mode == "append":
            self.messages[idx]["content"][0]["text"] += content
        elif mode == "flush":
            self.messages[idx]["content"][0]["text"] = content
        else:
            raise ValueError(f"Invalid mode: {mode}")

        if files:
            files = self.save_files(files, cached=True)
            self.messages[idx]["content"] += files

    def return_last_message(self):
        return self.messages[-1]["content"]

    def end_of_current_turn(self):
        assert len(self.messages) > 0, "No message in the conversation."
        assert (
            self.messages[-1]["role"] == self.ASSISTANT
        ), f"It should end with the message from assistant instead of {self.messages[-1]['role']}."

        if len(self.messages[-1]["content"][0]["text"]) == 0:
            return 
        
        if self.messages[-1]["content"][0]["text"][-1] != self.streaming_placeholder:
            return

        self.update_message(
            self.ASSISTANT,
            self.messages[-1]["content"][0]["text"][:-1],
            None,
            mode="replace",
        )

    def delete_last_message(self, role=None):
        if self.messages[-1]["role"] == role:
            self.messages.pop()

    def copy(self):
        return Record(
            mandatory_system_message=copy.deepcopy(self.mandatory_system_message),
            system_message=copy.deepcopy(self.system_message),
            roles=copy.deepcopy(self.roles),
            messages=copy.deepcopy(self.messages),
            files=copy.deepcopy(self.files),
        )

    def dict(self):
        return {
            "mandatory_system_message": self.mandatory_system_message,
            "system_message": self.system_message,
            "roles": self.roles,
            "messages": self.messages,
        }

    def generate_filepath(self, file_bytes, ext):
        t = datetime.datetime.now()
        image_hash = hashlib.md5(file_bytes).hexdigest()
        filename = os.path.join(
            LOGDIR,
            "serve_images",
            f"{t.year}-{t.month:02d}-{t.day:02d}",
            f"{image_hash}.{ext}",
        )
        if not os.path.isfile(filename):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        return filename

    def save_image(self, image: Image.Image, ext: str) -> str:
        path = self.generate_filepath(image.tobytes(), ext)
        image.save(path)
        return path

    def save_video(self, video: bytes, ext: str) -> str:
        path = self.generate_filepath(video, ext)
        with open(path, "wb") as f:
            f.write(video)

        return path

    def save_files(
        self, file_urls: List[Dict[str, Any]], cached: bool = True
    ) -> List[Dict[str, Any]]:
        saved_files = []
        for file_item in file_urls:
            base64, ext = url_to_base64(file_item[file_item["type"]]["url"])
            copy_file_item = copy.deepcopy(file_item)
            if file_item["type"] == "image_url":
                filepath = self.save_image(load_image_from_base64(base64), ext)
                copy_file_item[file_item["type"]]["url"] = f"Path: {filepath}"
                saved_files.append(copy_file_item)
            elif file_item["type"] == "video_url":
                video_bytes = base64_to_bytes(base64)
                filepath = self.save_video(video_bytes, ext)
                copy_file_item[file_item["type"]]["url"] = f"Path: {filepath}"
                saved_files.append(copy_file_item)
            else:
                raise ValueError(f"Invalid file type: {file_item['type']}")
            if cached:
                self.files[filepath] = file_item

        return saved_files
