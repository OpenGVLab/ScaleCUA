    
import re
from typing import Any, Dict, Tuple

from openai import OpenAI
import time
import numpy as np
from android_world.env import interface
from android_world.env import json_action
from android_world.agents import base_agent
from transformers.models.qwen2_vl.image_processing_qwen2_vl_fast import smart_resize

def _extract_xy(s: str) -> Tuple[float, float] | None:
    m = re.search(r"x\s*=\s*([0-9.]+)\s*,\s*y\s*=\s*([0-9.]+)", s, re.I)
    return tuple(map(float, m.groups())) if m else None


def _extract_text(s: str, fn: str) -> str | None:
    m = re.search(rf"{fn}\s*\([^)]*?=(['\"])(.*?)\1", s, re.I)
    return m.group(2) if m else None


def _extract_swipe(s: str):
    m = re.search(
        r"swipe\(\s*from_coord\s*=\s*\[\s*([0-9.]+)\s*,\s*([0-9.]+)\]\s*,\s*"
        r"to_coord\s*=\s*\[\s*([0-9.]+)\s*,\s*([0-9.]+)\]\s*\)", s, re.I
    )
    if m:
        return tuple(map(float, m.groups()))
    m = re.search(r"swipe\([^)]*direction\s*=\s*(['\"])(up|down|left|right)\1", s, re.I)
    return m.group(2).lower() if m else None


def _scroll_page_num(s: str) -> float | None:
    m = re.search(r"scroll\([^)]*page\s*=\s*([-+]?[0-9.]+)", s, re.I)
    return float(m.group(1)) if m else None


def _status_from_terminate(s: str) -> str | None:
    m = re.search(r"terminate\([^)]*status\s*=\s*(['\"])(success|failure)\1", s, re.I)
    return m.group(2).lower() if m else None

def reverse_direction(direction: str) -> str:
    if direction == "up":
        return "down"
    elif direction == "down":
        return "up"
    elif direction == "left":
        return "right"
    elif direction == "right":
        return "left"
    else:
        return direction

def _dir_from_coords(x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    return ("right" if dx > 0 else "left") if abs(dx) > abs(dy) \
           else ("down" if dy > 0 else "up")


def action_transform(action: str, width: int, height: int) -> Dict[str, Any] | None:
    a = action.strip()
    # click / long_press
    if a.lower().startswith(("click(", "long_press(")):
        kind = "click" if a.lower().startswith("click") else "long_press"
        x, y = 0.0, 0.0
        if (xy := _extract_xy(a)):
            x, y = xy
            if x <= 1 and y <= 1:
                x, y = x * width, y * height
            
        return {"action_type": kind, "x": x, "y": y}

    # write → input_text
    if a.lower().startswith("write("):
        txt = _extract_text(a, "write") or ""
        d: Dict[str, Any] = {"action_type": "input_text", "text": txt}
        if (xy := _extract_xy(a)):
            x, y = xy
            if x <= 1 and y <= 1:
                x, y = x * width, y * height
            d.update({"x": x, "y": y})
        return d

    # swipe / scroll
    if a.lower().startswith("swipe("):
        sw = _extract_swipe(a)
        if isinstance(sw, str):       
            return {"action_type": "scroll", "direction": reverse_direction(sw)}
        if isinstance(sw, tuple):       
            x0, y0, x1, y1 = sw
            return {"action_type": "scroll", "direction": reverse_direction(_dir_from_coords(x0, y0, x1, y1))}
        return {"action_type": "scroll", "direction": ""}

    if a.lower().startswith("scroll("):
        n = _scroll_page_num(a)
        dir_ = None
        if n is not None:
            dir_ = "up" if n < 0 else "down"
        return {"action_type": "scroll", "direction": reverse_direction(dir_)}

    # open_app
    if a.lower().startswith("open_app("):
        app = _extract_text(a, "open_app") or ""
        return {"action_type":"open_app", "app_name": app}

    # wait / keyboard_enter / navigate_*
    if a.lower().startswith("wait(") or a.lower() == "wait()":
        return {"action_type": "wait"}
    if a.lower().startswith("keyboard_enter(") or a.lower() == "keyboard_enter()":
        return {"action_type": "keyboard_enter"}
    if a.lower().startswith("navigate_home(") or a.lower() == "navigate_home()":
        return {"action_type": "navigate_home"}
    if a.lower().startswith("navigate_back(") or a.lower() == "navigate_back()":
        return {"action_type": "navigate_back"}

    # call_user → open Phone
    if a.lower().startswith("call_user(") or a.lower() == "call_user()":
        return {"action_type": "open_app", "app_name": "Phone"}

    # response(answer="…") → answer
    if a.lower().startswith("response("):
        ans = _extract_text(a, "response") or ""
        return {"action_type": "answer", "text": ans}

    # terminate(status=…) → status
    if a.lower().startswith("terminate("):
        st = _status_from_terminate(a)
        if st:
            return {"action_type": "status", "goal_status": "complete" if st == "success" else "infeasible"}

    # answer(text="…")
    if a.lower().startswith("answer("):
        txt = _extract_text(a, "answer") or ""
        return {"action_type": "answer", "text": txt}

    # status(goal_status="…")
    if a.lower().startswith("status("):
        gs = _extract_text(a, "goal_status") or ""
        if gs in ("complete", "infeasible"):
            return {"action_type": "status", "goal_status": gs}

    return None


def action_coord(action):
    def extract_click_json(s):
        m = re.search(r"x\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*y\s*=\s*([0-9]+(?:\.[0-9]+)?)", s)
        if m:
            x_val, y_val = map(float, m.groups())
            return x_val, y_val
        return None
    
    def extract_write_json(s):
        m = re.search(r'write\(message=(["\'])(.*?)\1\)', s)
        if m:
            return m.group(2)
        return None

    def extract_swipe_json(s):
        m = re.search(
            r"swipe\(\s*from_coord=\[\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*\]"
            r"\s*,\s*to_coord=\[\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*\]\s*\)",
            s
        )
        if m:
            return tuple(map(float, m.groups()))
        m = re.search(r'swipe\(direction=(["\'])(up|down|left|right)\1\)', s)
        if m:
            dir_ = m.group(2)
            if dir_ == "up":
                return (0, 1, 0, 0)
            elif dir_ == "down":
                return (0, 0, 0, 1)
            elif dir_ == "left":
                return (1, 0, 0, 0)
            elif dir_ == "right":
                return (0, 0, 1, 0)
        return None

    def extract_open_app_json(s):
        m = re.search(r'open_app\(app_name=(["\'])(.*?)\1\)', s)
        if m:
            return m.group(2)
        return None

    def extract_scroll_page_json(s):
        m = re.search(r'scroll\(page=(-?[0-9]+(?:\.[0-9]+)?)\)', s)
        if m:
            try:
                # Extract the number string (group 1) and convert to float
                return float(m.group(1))
            except ValueError:
                return None # Should not happen with this regex, but good practice
        return None

    def get_swipe_direction(start_x, start_y, end_x, end_y, tolerance=1e-6):
        delta_x = end_x - start_x
        delta_y = end_y - start_y

        abs_delta_x = abs(delta_x)
        abs_delta_y = abs(delta_y)
        
        if abs_delta_x > abs_delta_y:
            if delta_x > 0:
                return "right"
            else:
                return "left"
        else:
            if delta_y > 0:
                return "down"
            else:
                return "up"

    if "click" in action:
        out = extract_click_json(action)
        if out == None:
            return 0.5, 0.5
        x, y = out
        if x is not None and y is not None:
            return x, y
        else:
            # assert False, "Invalid click action"
            return 0.5, 0.5
        
    if "long_press" in action:
        out = extract_click_json(action)
        if out == None:
            return 0, 0
        x, y = out
        if x is not None and y is not None:
            return x, y
        else:
            return 0, 0
    
    if "swipe" in action:
        swipe = extract_swipe_json(action)
        if swipe is not None:
            start_x, start_y, end_x, end_y = swipe
            return (start_x + end_x) / 2, (start_y + end_y) / 2
        else:
            # assert False, "Invalid swipe action"
            return 0.5, 0.5
    
    if "scroll" in action:
        return 0.5, 0.5

    else: 
        return None

import re
from typing import Any, Dict, Optional

def uitars_action_transform(action: str, width: float, height: float) -> Optional[Dict[str, Any]]:
    a = action.strip()
    
    # click(start_box='(x,y)')
    m = re.match(
        r"""^click\(\s*start_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*\)$""",
        a, re.I
    )
    if m:
        raw_x, raw_y = map(float, m.groups())
        x = raw_x / 1000 * width
        y = raw_y / 1000 * height
        # x = raw_x
        # y = raw_y
        return {'action_type': 'click', 'x': x, 'y': y}

    # long_press(start_box='(x,y)')
    m = re.match(
        r"""^long_press\(\s*start_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*\)$""",
        a, re.I
    )
    if m:
        raw_x, raw_y = map(float, m.groups())
        x = raw_x / 1000 * width
        y = raw_y / 1000 * height
        # x = raw_x
        # y = raw_y
        return {'action_type': 'long_press', 'x': x, 'y': y}

    # type(content='…')
    m = re.match(
        r"""^type\(\s*content=['"](.*)['"]\s*\)$""",
        a, re.I
    )
    if m:
        txt = m.group(1).replace("\\'", "'")
        return {'action_type': 'input_text', 'text': txt}

    # scroll(start_box='(x,y)', direction='dir') — dir: up, down, left, right
    m = re.match(
        r"""^scroll\(\s*start_box=['"]\(\s*[\d.]+\s*,\s*[\d.]+\s*\)['"]\s*,\s*direction=['"](up|down|left|right)['"]\s*\)$""",
        a, re.I
    )
    if m:
        dir_ = m.group(1).lower()
        return {'action_type': 'scroll', 'direction': reverse_direction(dir_)}

    m = re.match(
        r"""^drag\(\s*start_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*,\s*end_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*\)$""",
        a, re.I
    )
    if m:
        raw_x1, raw_y1, raw_x2, raw_y2 = map(float, m.groups())
        x1, y1 = raw_x1 / 1000 * width, raw_y1 / 1000 * height
        x2, y2 = raw_x2 / 1000 * width, raw_y2 / 1000 * height
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) > abs(dy):
            direction = 'right' if dx > 0 else 'left'
        else:
            direction = 'down' if dy > 0 else 'up'
        return {'action_type': 'scroll', 'direction': reverse_direction(direction)}

    # open_app(app_name='Foo')
    m = re.match(
        r"""^open_app\(\s*app_name=['"](.+?)['"]\s*\)$""",
        a, re.I
    )
    if m:
        app = m.group(1).replace("\\'", "'")
        return {'action_type': 'open_app', 'app_name': app}

    # press_home()
    if re.match(r"^press_home\(\s*\)$", a, re.I):
        return {'action_type': 'navigate_home'}

    # press_back()
    if re.match(r"^press_back\(\s*\)$", a, re.I):
        return {'action_type': 'navigate_back'}

    # finished(content='xxx')
    m = re.match(
        r"""^finished\(\s*content=['"](.*)['"]\s*\)$""",
        a, re.I
    )
    if m:
        txt = m.group(1).replace("\\'", "'")
        if txt:
            return {'action_type': 'answer', 'text': txt}
        else:
            return {'action_type': 'status', 'goal_status': 'complete'}

    return None

import json

def map_claude_action(claude_json: str, width: int, height: int) -> dict:
    """
    Parse Claude's JSON action string, convert any 'x','y' from 0–1000 range
    to actual pixel coordinates based on screen width/height.

    Parameters:
      claude_json: JSON string output by Claude, e.g. '{"action_type":"click","x":420,"y":880}'
      width:  actual screen width in pixels
      height: actual screen height in pixels

    Returns:
      A dict representing the mapped action, with 'x' and 'y' replaced by pixel values.
    """
    action = json.loads(claude_json)
    if 'x' in action and 'y' in action:
        # Scale from 0–1000 to pixel coordinates
        action['x'] = int(action['x'] * width)
        action['y'] = int(action['y'] * height)
    return action

def map_claude_action(claude_json: str, width: int, height: int) -> dict:
    """
    Parse Claude's JSON action string, convert any 'x','y' from 0–1000 range
    to actual pixel coordinates based on screen width/height.

    Parameters:
      claude_json: JSON string output by Claude, e.g. '{"action_type":"click","x":420,"y":880}'
      width:  actual screen width in pixels
      height: actual screen height in pixels

    Returns:
      A dict representing the mapped action, with 'x' and 'y' replaced by pixel values.
    """
    action = json.loads(claude_json)
    if 'x' in action and 'y' in action:
        # Scale from 0–1000 to pixel coordinates
        action['x'] = int(action['x'] * width)
        action['y'] = int(action['y'] * height)
    return action

import re
from typing import Any, Dict, Optional

def reverse_direction(direction: Optional[str]) -> str:
    return {
        "up":   "down",
        "down": "up",
        "left": "right",
        "right":"left",
    }.get(direction, "")

def _dir_from_coords(x0: float, y0: float, x1: float, y1: float) -> str:
    dx, dy = x1 - x0, y1 - y0
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    else:
        return "down"  if dy > 0 else "up"

def aguvis_action_transform(call: str, width: int, height: int) -> Optional[Dict[str, Any]]:
    a = call.strip()

    # 1. pyautogui.click(x=…, y=…)
    m = re.match(r'pyautogui\.click\(\s*x\s*=\s*([0-9.]+)\s*,\s*y\s*=\s*([0-9.]+)\s*\)', a, re.I)
    if m:
        x, y = map(float, m.groups())
        if x <= 1 and y <= 1:
            x, y = x * width, y * height
        return {"action_type":"click", "x":x, "y":y}

    # 2. pyautogui.write(message=…, [x=…, y=…])
    m = re.match(
        r'pyautogui\.write\(\s*message\s*=\s*([\'"])(.*?)\1'                 # text
        r'(?:\s*,\s*x\s*=\s*([0-9.]+)\s*,\s*y\s*=\s*([0-9.]+))?'            # optional coords
        r'\s*\)', a, re.I
    )
    if m:
        text = m.group(2)
        d: Dict[str, Any] = {"action_type":"input_text", "text": text}
        if m.group(3) and m.group(4):
            x, y = float(m.group(3)), float(m.group(4))
            if x <= 1 and y <= 1:
                x, y = x * width, y * height
            d.update({"x": x, "y": y})
        return d

    # 3. mobile.swipe(...)
    m = re.match(
        r'mobile\.swipe\(\s*from_coord\s*=\s*\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]\s*,'
        r'\s*to_coord\s*=\s*\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]\s*\)', a, re.I
    )
    if m:
        x0, y0, x1, y1 = map(float, m.groups())
        dir_ = _dir_from_coords(x0, y0, x1, y1)
        return {"action_type":"scroll", "direction": reverse_direction(dir_)}

    # 4. mobile.home()
    if re.match(r'mobile\.home\(\s*\)', a, re.I):
        return {"action_type":"navigate_home"}

    # 5. mobile.back()
    if re.match(r'mobile\.back\(\s*\)', a, re.I):
        return {"action_type":"navigate_back"}

    # 6. mobile.wait()
    if re.match(r'mobile\.wait\(\s*\)', a, re.I):
        return {"action_type":"wait"}

    # 7. mobile.long_press(x=…, y=…)
    m = re.match(r'mobile\.long_press\(\s*x\s*=\s*([0-9.]+)\s*,\s*y\s*=\s*([0-9.]+)\s*\)', a, re.I)
    if m:
        x, y = map(float, m.groups())
        if x <= 1 and y <= 1:
            x, y = x * width, y * height
        return {"action_type":"long_press", "x":x, "y":y}

    # 8. terminate(status=…) — status: success/failure/other
    m = re.match(r'(?:mobile\.)?terminate\(\s*status\s*=\s*([\'"])(.*?)\1\s*\)', a, re.I)
    if m:
        status = m.group(2).lower()
        if status in ("success", "failure"):
            gs = "complete" if status == "success" else "infeasible"
            return {"action_type":"status", "goal_status": gs}
        else:
            return {"action_type":"answer", "text": m.group(2)}

    # 9. answer(text=…) or response(answer=…)
    m = re.match(r'(?:answer|response)\(\s*(?:text|answer)\s*=\s*([\'"])(.*?)\1\s*\)', a, re.I)
    if m:
        return {"action_type":"answer", "text": m.group(2)}

    return None


from PIL import Image
import matplotlib.pyplot as plt

import json
import base64
from io import BytesIO
from PIL import Image

import math

IMAGE_FACTOR = 28
MIN_PIXELS = 100 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28
MAX_RATIO = 200

VIDEO_MIN_PIXELS = 128 * 28 * 28
VIDEO_MAX_PIXELS = 768 * 28 * 28
FRAME_FACTOR = 2
FPS = 2.0
FPS_MIN_FRAMES = 4
FPS_MAX_FRAMES = 768

def round_by_factor(number: int, factor: int) -> int:
    """Returns the closest integer to 'number' that is divisible by 'factor'."""
    return round(number / factor) * factor

def ceil_by_factor(number: int, factor: int) -> int:
    """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
    return math.ceil(number / factor) * factor

def floor_by_factor(number: int, factor: int) -> int:
    """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
    return math.floor(number / factor) * factor

def smart_resize_uitars(
    height: int, width: int, factor: int = IMAGE_FACTOR, min_pixels: int = MIN_PIXELS, max_pixels: int = MAX_PIXELS
) -> tuple[int, int]:
    """
    Rescales the image so that the following conditions are met:

    1. Both dimensions (height and width) are divisible by 'factor'.

    2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].

    3. The aspect ratio of the image is maintained as closely as possible.
    """
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"absolute aspect ratio must be smaller than {MAX_RATIO}, got {max(height, width) / min(height, width)}"
        )
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(height / beta, factor)
        w_bar = floor_by_factor(width / beta, factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = ceil_by_factor(height * beta, factor)
        w_bar = ceil_by_factor(width * beta, factor)
    return h_bar, w_bar

import re
from typing import Any, Dict, Optional

def uitars1d5_action_transform(action: str, width: float, height: float) -> Optional[Dict[str, Any]]:
    a = action.strip()
    
    # click(start_box='(x,y)')
    m = re.match(
        r"""^click\(\s*start_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*\)$""",
        a, re.I
    )
    if m:
        raw_x, raw_y = map(float, m.groups())
        # x = raw_x / 1000 * width
        # y = raw_y / 1000 * height
        x = raw_x
        y = raw_y
        return {'action_type': 'click', 'x': x, 'y': y}

    # long_press(start_box='(x,y)')
    m = re.match(
        r"""^long_press\(\s*start_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*\)$""",
        a, re.I
    )
    if m:
        raw_x, raw_y = map(float, m.groups())
        # x = raw_x / 1000 * width
        # y = raw_y / 1000 * height
        x = raw_x
        y = raw_y
        return {'action_type': 'long_press', 'x': x, 'y': y}

    # type(content='…')
    m = re.match(
        r"""^type\(\s*content=['"](.*)['"]\s*\)$""",
        a, re.I
    )
    if m:
        txt = m.group(1).replace("\\'", "'")
        return {'action_type': 'input_text', 'text': txt}

    # scroll(start_box='(x,y)', direction='dir') — dir: up, down, left, right
    m = re.match(
        r"""^scroll\(\s*start_box=['"]\(\s*[\d.]+\s*,\s*[\d.]+\s*\)['"]\s*,\s*direction=['"](up|down|left|right)['"]\s*\)$""",
        a, re.I
    )
    if m:
        dir_ = m.group(1).lower()
        return {'action_type': 'scroll', 'direction': reverse_direction(dir_)}

    m = re.match(
        r"""^drag\(\s*start_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*,\s*end_box=['"]\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)['"]\s*\)$""",
        a, re.I
    )
    if m:
        raw_x1, raw_y1, raw_x2, raw_y2 = map(float, m.groups())
        # x1, y1 = raw_x1 / 1000 * width, raw_y1 / 1000 * height
        # x2, y2 = raw_x2 / 1000 * width, raw_y2 / 1000 * height
        x1, y1 = raw_x1, raw_y1
        x2, y2 = raw_x2, raw_y2
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) > abs(dy):
            direction = 'right' if dx > 0 else 'left'
        else:
            direction = 'down' if dy > 0 else 'up'
        return {'action_type': 'scroll', 'direction': reverse_direction(direction)}

    # open_app(app_name='Foo')
    m = re.match(
        r"""^open_app\(\s*app_name=['"](.+?)['"]\s*\)$""",
        a, re.I
    )
    if m:
        app = m.group(1).replace("\\'", "'")
        return {'action_type': 'open_app', 'app_name': app}

    # press_home()
    if re.match(r"^press_home\(\s*\)$", a, re.I):
        return {'action_type': 'navigate_home'}

    # press_back()
    if re.match(r"^press_back\(\s*\)$", a, re.I):
        return {'action_type': 'navigate_back'}

    # finished(content='xxx')
    m = re.match(
        r"""^finished\(\s*content=['"](.*)['"]\s*\)$""",
        a, re.I
    )
    if m:
        txt = m.group(1).replace("\\'", "'")
        if txt:
            return {'action_type': 'answer', 'text': txt}
        else:
            return {'action_type': 'status', 'goal_status': 'complete'}

    return None


def qwen_action_transform(action: str, width: int, height: int, smart_resize_option=False, min_pixels=None, max_pixels=None) -> Dict[str, Any] | None:
    a = action.strip()
    # click / long_press
    if a.lower().startswith(("click(", "long_press(")):
        kind = "click" if a.lower().startswith("click") else "long_press"
        x, y = 0.0, 0.0
        if (xy := _extract_xy(a)):
            x, y = xy
            if x <= 1 and y <= 1:
                x, y = x * width, y * height
            elif smart_resize:
                resized_height, resized_width = smart_resize(
                    height,
                    width,
                    min_pixels=min_pixels,
                    max_pixels=max_pixels,
                )
                x = x / resized_width * width
                y = y / resized_height * height
        return {"action_type": kind, "x": x, "y": y}

    # write → input_text
    if a.lower().startswith("write("):
        txt = _extract_text(a, "write") or ""
        d: Dict[str, Any] = {"action_type": "input_text", "text": txt}
        if (xy := _extract_xy(a)):
            x, y = xy
            if x <= 1 and y <= 1:
                x, y = x * width, y * height
            elif smart_resize:
                resized_height, resized_width = smart_resize(
                    height,
                    width,
                    min_pixels=min_pixels,
                    max_pixels=max_pixels,
                )
                x = round(x / resized_width * width)
                y = round(y / resized_height * height)
            d.update({"x": x, "y": y})
        return d

    # swipe / scroll
    if a.lower().startswith("swipe("):
        sw = _extract_swipe(a)
        if isinstance(sw, str):           
            return {"action_type": "scroll", "direction": reverse_direction(sw)}
        if isinstance(sw, tuple):      
            x0, y0, x1, y1 = sw
            return {"action_type": "scroll", "direction": reverse_direction(_dir_from_coords(x0, y0, x1, y1))}
        return {"action_type": "scroll", "direction": ""}

    if a.lower().startswith("scroll("):
        n = _scroll_page_num(a)
        dir_ = None
        if n is not None:
            dir_ = "up" if n < 0 else "down"
        return {"action_type": "scroll", "direction": reverse_direction(dir_)}

    # open_app
    if a.lower().startswith("open_app("):
        app = _extract_text(a, "open_app") or ""
        return {"action_type":"open_app", "app_name": app}

    # wait / keyboard_enter / navigate_*
    if a.lower().startswith("wait(") or a.lower() == "wait()":
        return {"action_type": "wait"}
    if a.lower().startswith("keyboard_enter(") or a.lower() == "keyboard_enter()":
        return {"action_type": "keyboard_enter"}
    if a.lower().startswith("navigate_home(") or a.lower() == "navigate_home()":
        return {"action_type": "navigate_home"}
    if a.lower().startswith("navigate_back(") or a.lower() == "navigate_back()":
        return {"action_type": "navigate_back"}

    # call_user → open Phone
    if a.lower().startswith("call_user(") or a.lower() == "call_user()":
        return {"action_type": "open_app", "app_name": "Phone"}

    # response(answer="…") → answer
    if a.lower().startswith("response("):
        ans = _extract_text(a, "response") or ""
        return {"action_type": "answer", "text": ans}

    # terminate(status=…) → status
    if a.lower().startswith("terminate("):
        st = _status_from_terminate(a)
        if st:
            return {"action_type": "status", "goal_status": "complete" if st == "success" else "infeasible"}

    # answer(text="…")
    if a.lower().startswith("answer("):
        txt = _extract_text(a, "answer") or ""
        return {"action_type": "answer", "text": txt}

    # status(goal_status="…")
    if a.lower().startswith("status("):
        gs = _extract_text(a, "goal_status") or ""
        if gs in ("complete", "infeasible"):
            return {"action_type": "status", "goal_status": gs}

    return None

import base64
import requests
import os
from PIL import Image
from io import BytesIO

BASE_URL = "http://0.0.0.0:8000"


def encode_image_path_with_info(image_path):
    assert os.path.exists(image_path)
    with Image.open(image_path) as img:
        width, height = img.size

        buffered = BytesIO()
        img.save(buffered, format=img.format or 'PNG')
        img_bytes = buffered.getvalue()

        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    return {
        "base64": img_base64,
        "width": width,
        "height": height,
        "format": img.format
    }

def encode_image_with_info(img: Image):

    assert isinstance(img, Image.Image)
    width, height = img.size

    buffered = BytesIO()
    img.save(buffered, format=img.format or 'PNG') 
    img_bytes = buffered.getvalue()

    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    return {
        "base64": img_base64,
        "width": width,
        "height": height,
        "format": img.format
    }


def chat_with_agent(image_info, task, task_id, BASE_URL):
    curr_screenshots_b64 = f"data:image/png;base64,{image_info['base64']}"
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
            f"{BASE_URL}/v1/chat",
            json=payload,
            headers={"Authorization": f"Bearer {task_id}"},
            timeout=2000
        )
        
        if response.status_code == 200:
            data = response.json()
            print(data)
            return data
            print(f"low_level_action: {data['low_level_action']}")
            print(f"pyautogui code: {data['pyautogui_code']}")
            print(f"original content: {data['original_content']}")
            print(f"metadata: {data['metadata']}")
            print(f"resized_hw: {data['resized_hw']}")
            print(f"session_id: {data['session_id']}")
            print(f"processing_time: {data['processing_time']}")
            return data
        else:
            print(f"Error: {response.status_code}")
            print(f"Error info: {response.text}")
            return False
    except Exception as e:
        print(f"raise error: {e}")
        return False



def clear_task_session(task_id, BASE_URL):
    clear_response = requests.post(
        f"{BASE_URL}/v1/clear",
        json={"user_id": task_id},
        headers={"Authorization": f"Bearer {task_id}"}
    )
    if clear_response.status_code == 200:
        data = clear_response.json()
        print(data)
    else:
        print(f"Error: {clear_response.status_code}")
        print(f"Error info: {clear_response.text}")


import re
from typing import Any, Dict, Optional, Tuple, Union

def _extract_floats(s: str, *keys: str) -> Optional[Tuple[float, ...]]:
    vals = []
    for k in keys:
        m = re.search(rf"{k}\s*=\s*([-+]?[0-9]*\.?[0-9]+)", s)
        if not m:
            return None
        vals.append(float(m.group(1)))
    return tuple(vals)

def _extract_str(s: str, key: str) -> Optional[str]:
    m = re.search(rf"{key}\s*=\s*(['\"])(.*?)\1", s)
    return m.group(2) if m else None

def qweneqa_action_transform(action: str, width: int, height: int) -> Optional[Dict[str, Any]]:
    a = action.strip()

    # 1. click(x=2, y=3)
    if a.startswith("click(") or a.startswith("left_click"):
        if xy := _extract_floats(a, "x", "y"):
            x, y = xy
            return {"action_type": "click", "x": x, "y": y}

    # 2. long_press(x=100, y=300, time=2)
    if a.startswith("long_press("):
        if xy := _extract_floats(a, "x", "y"):
            x, y = xy
            return {"action_type": "long_press", "x": x, "y": y}

    # 3. swipe(from_x=2, from_y=3, to_x=28, to_y=90)
    if a.startswith("swipe("):
        if coords := _extract_floats(a, "from_x", "from_y", "to_x", "to_y"):
            x0, y0, x1, y1 = coords
            dx, dy = x1 - x0, y1 - y0
            dir_ = ("right" if abs(dx) > abs(dy) and dx>0
                    else "left" if abs(dx)>abs(dy)
                    else "down" if dy>0
                    else "up")
            rev = {"up":"down","down":"up","left":"right","right":"left"}.get(dir_, dir_)
            return {"action_type": "scroll", "direction": rev}

    # 4. type(content="Shanghai")
    if a.startswith("type("):
        txt = _extract_str(a, "content") or ""
        return {"action_type": "input_text", "text": txt}

    # 5. system_button(button="Back, Home, Menu, or Enter")
    if a.startswith("system_button("):
        btn = _extract_str(a, "button") or ""
        mapping = {
            "Back":       {"action_type": "navigate_back"},
            "Home":       {"action_type": "navigate_home"},
            "Enter":      {"action_type": "keyboard_enter"},
            "Menu":       {"action_type": "wait"},
        }
        return mapping.get(btn, {"action_type": "wait"})

    # 6. open(name="QQ Music")
    if a.startswith("open("):
        app = _extract_str(a, "name") or ""
        return {"action_type": "open_app", "app_name": app}

    # 7. wait(time=3)
    if a.startswith("wait("):
        return {"action_type": "wait"}

    # 8. terminate(status="success or failure")
    if a.startswith("terminate("):
        st = _extract_str(a, "status")
        if st in ("success", "failure"):
            return {
                "action_type": "status",
                "goal_status": "complete" if st=="success" else "infeasible"
            }

    # 9. key(key_str="volume_down")
    if a.startswith("key("):
        # k = _extract_str(a, "key_str") or ""
        # return {"action_type": "key", "key_str": k}
        return None

    # 10. answer(content="this is a book")
    if a.startswith("answer("):
        ans = _extract_str(a, "content") or ""
        return {"action_type": "answer", "text": ans}

    return None
