import base64
import logging
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
import re
import ast
import math
from PIL import Image
from io import BytesIO
import requests
import json
# import pynput


# For online qwen2.5vl agent testing
# Testing code for MMBench-GUI Qwen2.5VL Model

KEY_MAP = {
    "enter":   "pynput.keyboard.Key.enter",
    "space":   "pynput.keyboard.Key.space",
    "shift":   "pynput.keyboard.Key.shift",
    "ctrl":    "pynput.keyboard.Key.ctrl",
    "alt":     "pynput.keyboard.Key.alt",
    "cmd":     "pynput.keyboard.Key.cmd",
    "command": "pynput.keyboard.Key.cmd",
    "tab":     "pynput.keyboard.Key.tab",
    "esc":     "pynput.keyboard.Key.esc",
}

class SimpleQwenvlAgent:
    def __init__(
        self,
        platform: str = "macos",
        model: str = "simple_qwenvl",
        url: str = None,
        # base_url: str = "http://10.140.60.36:10017/v1",
        api_key: str = "empty",
        max_tokens: int = 1500,
        temperature: float = 0.5,
        action_space: str = "pyautogui",
        observation_type: str = "screenshot",
        max_trajectory_length: int = 5,
        user_id = "os_macos&task-macos-env"
    ):
        self.platform = platform
        self.model = model
        self.url = url 
        if self.url is not None:
            self.base_url = self.url
        else:
            self.base_url = "http://10.140.60.1:11012"
            # self.base_url = base_url
            if self.model == "gui_v91":
                self.base_url = "http://10.140.60.93:10017/v1"
            elif self.model == "gui_v99":
                self.base_url = "http://10.140.60.23:10019/v1"
        # else:
        #     raise ValueError("Unspported Model Name")
            
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.action_space = action_space
        self.observation_type = observation_type
        self.max_trajectory_length = max_trajectory_length
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.thoughts: List[str] = []
        self.actions: List[List[str]] = []
        self.observations: List[Dict] = []
        self.operations = []
        self.user_id = user_id + self.model
        self.logger = logging.getLogger(__name__)

    def encode_image_with_info(self, image_bytes: bytes, width=1920, height=1080):
        # NOTE: change image size here if needed
        img_base64 = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "base64": img_base64,
            "width": width,
            "height": height,
            "format": 'PNG'
        }
        


    def key_mapping(self, key: str) -> str:
        k = key.lower()
        if k in KEY_MAP:
            return KEY_MAP[k]
        return repr(key)


    # def parse_response(self, content: str) -> Dict[str, List[str]]:
    #     think = self.parse_between_tags(content, THINK_START, THINK_END) or ""
    #     op = self.parse_between_tags(content, OPERATION_START, OPERATION_END) or ""
    #     act_blk = self.parse_between_tags(content, ACTION_START, ACTION_END) or ""
    #     raw = [line.strip() for line in act_blk.splitlines() if line.strip()]
    #     return {"think": [think], "operation": [op], "raw_actions": raw}

    def _parse_kwargs(self, arg_str: str) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Parse the argument string and return a tuple of (positional_args, keyword_args).
        Uses AST for robust parsing; falls back to regex if AST fails.
        """
        try:
            tree = ast.parse(f"f({arg_str})", mode='eval').body
            args = [ast.literal_eval(node) for node in tree.args]
            kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in tree.keywords}
            return args, kwargs
        except Exception:
            parts = [p.strip() for p in re.split(r',(?=(?:[^\'\"]|\'[^\']*\'|\"[^\"]*\")*$)', arg_str) if p.strip()]
            args: List[Any] = []
            kwargs: Dict[str, Any] = {}
            for part in parts:
                if '=' in part:
                    key, val = part.split('=', 1)
                    val = val.strip()
                    try:
                        parsed = ast.literal_eval(val)
                    except Exception:
                        parsed = val
                    kwargs[key.strip()] = parsed
                else:
                    try:
                        parsed = ast.literal_eval(part)
                    except Exception:
                        parsed = part
                    args.append(parsed)
            return args, kwargs

    def transform_action(self, a: str) -> str:
        """
        Convert a raw action signature into executable Python code.
        Supports both positional and keyword arguments.
        """
        m = re.match(r"^(\w+)\((.*)\)$", a)
        if not m:
            return f"# Unhandled action: {a}"

        action, arg_str = m.group(1), m.group(2)
        args, kwargs = self._parse_kwargs(arg_str)

        def get_arg(name: str, pos: int, default=None):
            if name in kwargs:
                return kwargs[name]
            if len(args) > pos:
                return args[pos]
            return default

        # Mouse move
        if action == "mouse_move":
            x = get_arg('x', 0, None)
            y = get_arg('y', 1, None)
            if x is None or y is None:
                return ""
            return f"pyautogui.moveTo({x}, {y})"

        # Left click
        if action == "left_click":
            x = get_arg('x', 0, None)
            y = get_arg('y', 1, None)
            if x is None or y is None:
                return "mouse = pynput.mouse.Controller(); mouse.click(pynput.mouse.Button.left, 1)"
            return (
                "from pynput.mouse import Controller, Button;"
                f"mouse=Controller(); mouse.position=({x},{y}); mouse.click(Button.left,1)"
            )

        # Right click
        if action == "right_click":
            x = get_arg('x', 0, None)
            y = get_arg('y', 1, None)
            if x is None or y is None:
                return "mouse = pynput.mouse.Controller(); mouse.click(pynput.mouse.Button.right, 1)"
            return (
                "from pynput.mouse import Controller, Button;"
                f"mouse=Controller(); mouse.position=({x},{y}); mouse.click(Button.right,1)"
            )

        # Middle click
        if action == "middle_click":
            x = get_arg('x', 0, None)
            y = get_arg('y', 1, None)
            if x is None or y is None:
                return "mouse = pynput.mouse.Controller(); mouse.click(pynput.mouse.Button.middle, 1)"
            return (
                "from pynput.mouse import Controller, Button;"
                f"mouse=Controller(); mouse.position=({x},{y}); mouse.click(Button.middle,1)"
            )

        # Double click
        if action == "double_click":
            x = get_arg('x', 0, None)
            y = get_arg('y', 1, None)
            if x is None or y is None:
                return ""
            return (
                "from pynput.mouse import Controller, Button;"
                f"mouse=Controller(); mouse.position=({x},{y}); mouse.click(Button.left,2)"
            )

        # Drag with left click
        if action == "left_click_drag":
            to_x = get_arg('to_x', 0, None)
            to_y = get_arg('to_y', 1, None)
            if to_x is None or to_y is None:
                return ""
            return f"pyautogui.dragTo({to_x}, {to_y}, button='left')"

        # Type text
        if action == "type":
            text = get_arg('content', 0, '')
            return f"keyboard.write({repr(text)})"

        # Key combination
        if action == "key":
            try:
                call = ast.parse(f"key({arg_str})", mode="eval").body
                keys = [ast.literal_eval(node) for node in call.keywords]
            except Exception:
                keys = [arg_str]
            seq = []
            for k in keys:
                k = k.strip("'")
                mapped = self.key_mapping(str(k))
                seq.append(f"kb.press({mapped})")
            for k in reversed(keys):
                k = k.strip("'")
                mapped = self.key_mapping(str(k))
                seq.append(f"kb.release({mapped})")
            return (
                "from pynput.keyboard import Controller as KeyboardController;"
                "kb=KeyboardController(); " + "; ".join(seq)
            )

        # Scroll
        if action == "scroll":
            pixels = get_arg('pixels', 0, 0)
            return f"mouse = pynput.mouse.Controller(); mouse.scroll(0, {pixels})"

        # Wait
        if action == "wait":
            secs = get_arg('time', 0, 1)
            return f"time.sleep({secs})"

        # Terminate
        if action == "terminate" or action == "stop":
            status = get_arg('status', 0, 'success')
            return "DONE"

        return f"# Unhandled action: {a}"

    def chat_with_agent(self, image_info, task, task_id):
        curr_screenshots_b64 = f"data:image/{image_info['format'].lower()};base64,{image_info['base64']}"
        payload = {
            "text": f"{task}",
            "image_base64": curr_screenshots_b64,
            "metadata": {
                "height": image_info['height'],
                "width": image_info['width'],
                "min_pixels": 3136,
                "max_pixels": 12845056
            },
            "user_id": task_id
        }
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat",
                json=payload,
                headers={"Authorization": f"Bearer {task_id}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                # print(f"low_level_action: {data['low_level_action']}")
                # # print(f"pyautogui code: {data['pyautogui_code']}")
                # print(f"original content: {data['original_content']}")
                # print(f"metadata: {data['metadata']}")
                # print(f"resized_hw: {data['resized_hw']}")
                # print(f"session_id: {data['session_id']}")
                # print(f"processing_time: {data['processing_time']}")
                return data
            else:
                print(f"Error: {response.status_code}")
                print(f"Error info: {response.text}")
                return None
        except Exception as e:
            print(f"raise error: {e}")
            return None

    def predict(self, instruction: str, obs: Dict, last_action_after_obs: Optional[Dict] = None) -> Tuple[str, List[str]]:
        assert len(self.observations) == len(self.actions) == len(self.thoughts)
        self.observations.append(obs)
        message = None
        try:
            message = self.chat_with_agent(self.encode_image_with_info(obs['screenshot']), task=instruction, task_id=self.user_id)
            raw = message['actions_params']
        except:
            raw = "[wait(3)]"
        print(f"raw action params: {raw!r}")
        # if it's already a list, leave it; if it's a string like "['foo', 'bar']", literal_eval it
        if isinstance(raw, str) and raw.strip().startswith('['):
            try:
                content_list = ast.literal_eval(raw)
            except Exception:
                # fallback: treat whole raw as single action
                content_list = [raw]
        else:
            content_list = raw if isinstance(raw, list) else [raw]

        print(f"parsed actions: {content_list}")
        # print(f"output action: {content}")
        self.thoughts.append(content_list)
        execs = [self.transform_action(a) for a in content_list]
        print(f"exec action: {execs}")
        self.actions.append(content_list)
        self.operations.append(content_list)
        # truncate
        if len(self.actions) > self.max_trajectory_length:
            self.observations = self.observations[-self.max_trajectory_length:]
            self.thoughts = self.thoughts[-self.max_trajectory_length:]
            self.actions = self.actions[-self.max_trajectory_length:]
            self.operations = self.operations[-self.max_trajectory_length:]
        return message.get("original_content", "") if message is not None else "Error Occurred", execs

    def reset(self) -> None:
        self.thoughts.clear()
        self.actions.clear()
        self.observations.clear()
        self.operations.clear()
        self.clear_task_session(self.user_id)
        
    def clear_task_session(self, task_id):
        clear_response = requests.post(
            f"{self.base_url}/v1/clear",
            json={"user_id": task_id},
            headers={"Authorization": f"Bearer {task_id}"}
        )
        if clear_response.status_code == 200:
            data = clear_response.json()
            print(data)
        else:
            print(f"Error: {clear_response.status_code}")
            print(f"Error info: {clear_response.text}")
        
if __name__ == "__main__":
    import os
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Initialize the agent
    agent = SimpleQwenvlAgent()
    print(agent.transform_action("type(\"haha\")"))

    # # Load test screenshot
    # img_path = "/home/pipiwu/macos_env/Codes/evalkit_macos/tmp/snapshot.png"
    # if not os.path.exists(img_path):
    #     raise FileNotFoundError(f"Screenshot not found: {img_path}")
    # with open(img_path, "rb") as f:
    #     img_bytes = f.read()

    # # Define instruction
    # instruction = "Open the Calendar application"

    # # Perform prediction
    # raw_output, actions = agent.predict(instruction, {"screenshot": img_bytes})

    # # Display results
    # print("Raw model output:")
    # print(raw_output)
    # print("Parsed executable actions:")
    # for act in actions:
    #     print(act)