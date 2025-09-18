import base64
import logging
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
import re
import ast
import math

# import pynput


# OpenCUA series agent
# Support for both Internvl and Qwen2.5VL model type

SCREEN_WITDH = 1920
SCREEN_HEIGHT = 1080

# === String Constants ===
INTERNVL3_SYSTEM_PROMPT = """
You are an autonomous GUI agent operating on the **macOS** platform. Your primary function is to analyze screen captures and perform appropriate UI actions to complete assigned tasks.

## Action Space

def click(
    x: float | None = None,
    y: float | None = None,
    clicks: int = 1,
    button: str = "left",
) -> None:
    \"\"\"Clicks on the screen at the specified coordinates. The `x` and `y` parameter specify where the mouse event occurs. If not provided, the current mouse position is used. The `clicks` parameter specifies how many times to click, and the `button` parameter specifies which mouse button to use ('left', 'right', or 'middle').\"\"\"
    pass


def doubleClick(
    x: float | None = None,
    y: float | None = None,
    button: str = "left",
) -> None:
    \"\"\"Performs a double click. This is a wrapper function for click(x, y, 2, 'left').\"\"\"
    pass


def rightClick(x: float | None = None, y: float | None = None) -> None:
    \"\"\"Performs a right mouse button click. This is a wrapper function for click(x, y, 1, 'right').\"\"\"
    pass


def scroll(clicks: int, x: float | None = None, y: float | None = None) -> None:
    \"\"\"Performs a scroll of the mouse scroll wheel at the specified coordinates. The `clicks` specifies how many clicks to scroll. The direction of the scroll (vertical or horizontal) depends on the underlying operating system. Normally, positive values scroll up, and negative values scroll down.\"\"\"
    pass


def moveTo(x: float, y: float) -> None:
    \"\"\"Move the mouse to the specified coordinates.\"\"\"
    pass


def dragTo(
    x: float | None = None, y: float | None = None, button: str = "left"
) -> None:
    \"\"\"Performs a drag-to action with optional `x` and `y` coordinates and button.\"\"\"
    pass


def press(keys: str | list[str], presses: int = 1) -> None:
    \"\"\"Performs a keyboard key press down, followed by a release. The function supports pressing a single key or a list of keys, multiple presses, and customizable intervals between presses.\"\"\"
    pass


def hotkey(*args: str) -> None:
    \"\"\"Performs key down presses on the arguments passed in order, then performs key releases in reverse order. This is used to simulate keyboard shortcuts (e.g., 'Ctrl-Shift-C').\"\"\"
    pass


def keyDown(key: str) -> None:
    \"\"\"Performs a keyboard key press without the release. This will put that key in a held down state.\"\"\"
    pass


def keyUp(key: str) -> None:
    \"\"\"Performs a keyboard key release (without the press down beforehand).\"\"\"
    pass


def write(message: str) -> None:
    \"\"\"Write the specified text.\"\"\"
    pass


def call_user() -> None:
    \"\"\"Call the user.\"\"\"
    pass


def wait(seconds: int = 3) -> None:
    \"\"\"Wait for the change to happen.\"\"\"
    pass


def response(answer: str) -> None:
    \"\"\"Answer a question or provide a response to an user query.\"\"\"
    pass


def terminate(status: str = "success", info: str | None = None) -> None:
    \"\"\"Terminate the current task with a status. The `status` specifies the termination status ('success', 'failure'), and the `info` can provide additional information about the termination.\"\"\"
    pass

## Input Specification
- Screenshot of the current screen + task description + your past interaction history with UI to finish assigned tasks.

## Output Format
```
<think>
[Your reasoning process here]
</think>
<operation>
[Next intended operation description]
</operation>
<action>
[A set of executable action command]
</action>
```

## Note
- Avoid actions that would lead to invalid states.
- The generated action(s) must exist within the defined action space.
- The reasoning process, operation and action(s) in your response should be enclosed within <think></think>, <operation></operation> and <action></action> tags, respectively."""

INTERNVL3_TASK_PROMPT = """
<image>
Please generate the next move according to the UI screenshot, task and previous operations.

Task:
{instruction}
"""

INTERNVL3_HISTORY_PROMPT = """
Previous operations:
{operations}
"""

# Tag constants for parsing
THINK_START = "<think>"
THINK_END = "</think>"
OPERATION_START = "<operation>"
OPERATION_END = "</operation>"
ACTION_START = "<action>"
ACTION_END = "</action>"

IMAGE_FACTOR = 28
MIN_PIXELS = 3136
# MAX_PIXELS = 2007040
MAX_PIXELS = 69 * 39 * 28 * 28
MAX_RATIO = 200


def round_by_factor(number: int, factor: int) -> int:
    """Returns the closest integer to 'number' that is divisible by 'factor'."""
    return round(number / factor) * factor


def ceil_by_factor(number: int, factor: int) -> int:
    """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
    return math.ceil(number / factor) * factor


def floor_by_factor(number: int, factor: int) -> int:
    """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
    return math.floor(number / factor) * factor


def linear_resize(
    height: int,
    width: int,
    factor: int = IMAGE_FACTOR,
    min_pixels: int = MIN_PIXELS,
    max_pixels: int = MAX_PIXELS,
) -> tuple[int, int]:
    if width * height > max_pixels:
        resize_factor = math.sqrt(max_pixels / (width * height))
        width, height = int(width * resize_factor), int(height * resize_factor)
    if width * height < min_pixels:
        resize_factor = math.sqrt(min_pixels / (width * height))
        width, height = math.ceil(width * resize_factor), math.ceil(
            height * resize_factor
        )

    return height, width


def smart_resize(
    height: int,
    width: int,
    factor: int = IMAGE_FACTOR,
    min_pixels: int = MIN_PIXELS,
    max_pixels: int = MAX_PIXELS,
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


KEY_MAP = {
    "enter": "pynput.keyboard.Key.enter",
    "space": "pynput.keyboard.Key.space",
    "shift": "pynput.keyboard.Key.shift",
    "ctrl": "pynput.keyboard.Key.ctrl",
    "alt": "pynput.keyboard.Key.alt",
    "cmd": "pynput.keyboard.Key.cmd",
    "command": "pynput.keyboard.Key.cmd",
    "tab": "pynput.keyboard.Key.tab",
    "esc": "pynput.keyboard.Key.esc",
}


class InternvlAgent:
    def __init__(
        self,
        platform: str = "macos",
        model: str = "gui_v91",
        url: str = None,
        # base_url: str = "http://10.140.60.36:10017/v1",
        api_key: str = "empty",
        max_tokens: int = 1500,
        temperature: float = 0.5,
        action_space: str = "pyautogui",
        observation_type: str = "screenshot",
        max_trajectory_length: int = 20,
    ):
        self.platform = platform
        self.model = model
        self.url = url
        if self.url:
            self.base_url = self.url
        else:
            if self.model == "gui_v91":
                self.base_url = "http://10.140.60.93:10017/v1"
            elif self.model == "gui_v99":
                self.base_url = "http://10.140.60.23:10019/v1"
            elif self.model == "gui_v108":
                self.base_url = "http://10.140.60.107:10025/v1"
            elif self.model == "gui_v113":
                self.base_url = "http://10.140.60.116:10029/v1"
            elif self.model == "gui_v126":
                self.base_url = "http://10.140.66.139:10025/v1"
            else:
                raise ValueError("Unspported Model Name")

        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.action_space = action_space
        self.observation_type = observation_type
        self.max_trajectory_length = max_trajectory_length
        self.client = OpenAI(
            base_url=self.base_url, api_key=self.api_key
        )  # API Wrapper, for vllm or lmdeploy, leave api_key='empty' is ok
        self.thoughts: List[str] = []
        self.actions: List[List[str]] = []
        self.observations: List[Dict] = []
        self.operations = []
        self.logger = logging.getLogger(__name__)

    def encode_image(self, image_bytes: bytes) -> str:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def key_mapping(self, key: str) -> str:
        k = key.lower()
        if k in KEY_MAP:
            return KEY_MAP[k]
        return repr(key)

    def build_messages(self, instruction: str, obs: Dict) -> List[Dict]:
        screenshot_uri = self.encode_image(obs["screenshot"])
        if self.operations:
            flat_ops = [step for op_list in self.operations for step in op_list]
            prev = "\n".join(f"Step {i+1}: {line}" for i, line in enumerate(flat_ops))
        else:
            prev = "None"
        # content = {"instruction": instruction, "previous_actions": prev, "screenshot": screenshot_uri}
        return [
            {
                "role": "system",
                "content": [{"type": "text", "text": INTERNVL3_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": INTERNVL3_TASK_PROMPT.format(instruction=instruction)
                        + "\n"
                        + INTERNVL3_HISTORY_PROMPT.format(operations=prev),
                    }
                ],
            },
            # {"role": "user", "content":[{
            #     "type": "text",
            #     "text": INTERNVL3_HISTORY_PROMPT.format(operations=prev)
            # }]},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": screenshot_uri}}
                ],
            },
        ]

    def parse_between_tags(
        self, text: str, start_tag: str, end_tag: str
    ) -> Optional[str]:
        pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    def parse_response(self, content: str) -> Dict[str, List[str]]:
        think = self.parse_between_tags(content, THINK_START, THINK_END) or ""
        op = self.parse_between_tags(content, OPERATION_START, OPERATION_END) or ""
        act_blk = self.parse_between_tags(content, ACTION_START, ACTION_END) or ""
        raw = [line.strip() for line in act_blk.splitlines() if line.strip()]
        return {"think": [think], "operation": [op], "raw_actions": raw}

    def _parse_kwargs(self, arg_str: str) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Parse the argument string and return a tuple of (positional_args, keyword_args).
        Uses AST for robust parsing; falls back to regex if AST fails.
        """
        try:
            # Wrap in a dummy function call to capture args and keywords
            tree = ast.parse(f"f({arg_str})", mode="eval").body
            args = [ast.literal_eval(node) for node in tree.args]
            kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in tree.keywords}
            return args, kwargs
        except Exception:
            # Fallback: split on top-level commas and distinguish args/kwargs
            parts = [
                p.strip()
                for p in re.split(r",(?=(?:[^\'\"]|\'[^\']*\'|\"[^\"]*\")*$)", arg_str)
                if p.strip()
            ]
            args: List[Any] = []
            kwargs: Dict[str, Any] = {}
            for part in parts:
                if "=" in part:
                    key, val = part.split("=", 1)
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
        # Compute resized dimensions
        smart_h, smart_w = smart_resize(
            SCREEN_HEIGHT, SCREEN_WITDH, IMAGE_FACTOR, MIN_PIXELS, MAX_PIXELS
        )

        # Match the function name and argument list
        m = re.match(r"^(\w+)\((.*)\)$", a)
        if not m:
            return f"# Unhandled action: {a}"

        func_name, arg_str = m.group(1), m.group(2)
        args, kwargs = self._parse_kwargs(arg_str)

        # Helper to fetch either keyword or positional argument
        def get_arg(name: str, pos: int, default=None):
            if name in kwargs:
                return kwargs[name]
            if len(args) > pos:
                return args[pos]
            return default

        # click
        if func_name == "click":
            x = get_arg("x", 0, None)
            y = get_arg("y", 1, None)
            if x is not None:
                x = f"{float(x) * SCREEN_WITDH:.4f}"
            if y is not None:
                y = f"{float(y) * SCREEN_HEIGHT:.4f}"
            if self.model != "gui_v91" and x is not None and y is not None:
                x = str(float(x) / smart_w)
                y = str(float(y) / smart_h)
            clicks = get_arg("clicks", 2, 1)
            button = get_arg("button", 3, "left")
            return (
                f"pyautogui.click(x={x}, y={y}, clicks={clicks}, button={repr(button)})"
            )

        # doubleClick
        if func_name == "doubleClick":
            x = get_arg("x", 0, None)
            y = get_arg("y", 1, None)
            if x is not None:
                x = f"{float(x) * SCREEN_WITDH:.4f}"
            if y is not None:
                y = f"{float(y) * SCREEN_HEIGHT:.4f}"
            if self.model != "gui_v91" and x and y:
                x = str(float(x) / smart_w)
                y = str(float(y) / smart_h)
            return (
                "from pynput.mouse import Controller, Button;"
                f"mouse=Controller(); mouse.position=({x},{y}); mouse.click(Button.left,2)"
            )

        # rightClick
        if func_name == "rightClick":
            x = get_arg("x", 0, None)
            y = get_arg("y", 1, None)
            if x is not None:
                x = f"{float(x) * SCREEN_WITDH:.4f}"
            if y is not None:
                y = f"{float(y) * SCREEN_HEIGHT:.4f}"
            if self.model != "gui_v91" and x and y:
                x = str(float(x) / smart_w)
                y = str(float(y) / smart_h)
            return (
                "from pynput.mouse import Controller, Button;"
                f"mouse=Controller(); mouse.position=({x},{y}); mouse.click(Button.right,1)"
            )

        # scroll
        if func_name == "scroll":
            clicks = get_arg("clicks", 0, 0)
            return f"mouse = pynput.mouse.Controller(); mouse.scroll(0, {clicks})"

        # moveTo
        if func_name == "moveTo":
            x = get_arg("x", 0, None)
            y = get_arg("y", 1, None)
            if x is not None and y is not None:
                x = f"{float(x) * SCREEN_WITDH:.4f}"
                y = f"{float(y) * SCREEN_HEIGHT:.4f}"
                if self.model != "gui_v91":
                    x = str(float(x) / smart_w)
                    y = str(float(y) / smart_h)
                return f"pyautogui.moveTo({x}, {y})"
            return ""

        # dragTo
        if func_name == "dragTo":
            x = get_arg("x", 0, None)
            y = get_arg("y", 1, None)
            button = get_arg("button", 2, "left")
            if x is not None and y is not None:
                x = f"{float(x) * SCREEN_WITDH:.4f}"
                y = f"{float(y) * SCREEN_HEIGHT:.4f}"
                if self.model != "gui_v91":
                    x = str(float(x) / smart_w)
                    y = str(float(y) / smart_h)
                return (
                    f"pyautogui.dragTo({x}, {y}, button={repr(button)}, duration=1.0)"
                )
            return ""

        # press
        if func_name == "press":
            raw = get_arg("keys", 0, [])
            presses = get_arg("presses", 1, 1)
            keys_list = raw if isinstance(raw, list) else [raw]
            seq = []
            for key in keys_list:
                mapped = self.key_mapping(str(key))
                for _ in range(presses):
                    seq.append(f"kb.press({mapped})")
                    seq.append(f"kb.release({mapped})")
            return (
                "from pynput.keyboard import Controller as KeyboardController;"
                "kb=KeyboardController(); " + "; ".join(seq)
            )

        # hotkey
        if func_name == "hotkey":
            try:
                call = ast.parse(f"{func_name}({arg_str})", mode="eval").body
                args_list = [ast.literal_eval(node) for node in call.args]
            except Exception:
                args_list = [s.strip().strip("\"'") for s in arg_str.split(",")]
            # map Ctrl to cmd for common combos
            if (
                len(args_list) == 2
                and args_list[0].lower() == "ctrl"
                and args_list[1].lower() in {"a", "c", "v", "s"}
            ):
                args_list[0] = "cmd"
            seq = []
            for key in args_list:
                mapped = self.key_mapping(str(key))
                seq.append(f"kb.press({mapped})")
            for key in reversed(args_list):
                mapped = self.key_mapping(str(key))
                seq.append(f"kb.release({mapped})")
            return (
                "from pynput.keyboard import Controller as KeyboardController;"
                "kb=KeyboardController(); " + "; ".join(seq)
            )

        # keyDown
        if func_name == "keyDown":
            key = get_arg("key", 0, None)
            return f"kb = pynput.keyboard.Controller(); kb.press({key})"

        # keyUp
        if func_name == "keyUp":
            key = get_arg("key", 0, None)
            return f"kb = pynput.keyboard.Controller(); kb.release({key})"

        # write
        if func_name == "write":
            raw = get_arg("message", 0, None) or get_arg("text", 0, None) or ""
            print(raw)
            if isinstance(raw, int):
                raw = str(raw)
            return f"keyboard.write({repr(raw)})"

        # wait
        if func_name == "wait":
            secs = get_arg("seconds", 0, 1)
            return f"time.sleep({secs})"

        # terminate or response
        if func_name == "terminate":
            return "DONE"

        # fallback for unhandled actions
        return f"# Unhandled action: {a}"

    def predict(
        self, instruction: str, obs: Dict, last_action_after_obs: Optional[Dict] = None
    ) -> Tuple[str, List[str]]:
        assert len(self.observations) == len(self.actions) == len(self.thoughts)
        self.observations.append(obs)
        messages = self.build_messages(instruction, obs)
        print(messages[1])
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        content = resp.choices[0].message.content
        print(content)
        self.thoughts.append(content)
        parsed = self.parse_response(content)
        raw = parsed["raw_actions"]
        print(raw)
        execs = [self.transform_action(a) for a in raw]
        self.actions.append(parsed["raw_actions"])
        self.operations.append(parsed["operation"])
        # truncate
        if len(self.actions) > self.max_trajectory_length:
            self.observations = self.observations[-self.max_trajectory_length :]
            self.thoughts = self.thoughts[-self.max_trajectory_length :]
            self.actions = self.actions[-self.max_trajectory_length :]
            self.operations = self.operations[-self.max_trajectory_length :]
        return content, execs

    def reset(self) -> None:
        self.thoughts.clear()
        self.actions.clear()
        self.observations.clear()
        self.operations.clear()


if __name__ == "__main__":
    import os

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Initialize the agent
    agent = InternvlAgent()
    print(agent.transform_action("write(message='233')"))
