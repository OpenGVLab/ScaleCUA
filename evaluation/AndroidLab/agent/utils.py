import base64
import copy
import re


_PATTERNS = {
    "click": re.compile(r"^click\(\s*x=([^,]+),\s*y=([^)]+)\)$"),
    "long_press": re.compile(
        r"^long_press\(\s*x=([^,]+),\s*y=([^,]+),\s*duration=([^)]+)\)$"
    ),
    "swipe_precise": re.compile(
        r"^swipe\(\s*from_coord=\s*([\(\[])\s*([^,]+)\s*,\s*([^,\)\]]+)\s*[\)\]]\s*,\s*"
        r"to_coord=\s*([\(\[])\s*([^,]+)\s*,\s*([^,\)\]]+)\s*[\)\]]"
        r"(?:\s*,\s*[^=]+=[^,)]*)*\s*\)$"
    ),
    "swipe_dir": re.compile(
        r'^swipe\(\s*direction=(["\'])(.+?)\1\s*,\s*amount=([^)]+)\)$'
    ),
    "write": re.compile(r'^write\(\s*message=(["\'])(.+?)\1\)$'),
    "open_app": re.compile(r'^open_app\(\s*app_name=(["\'])(.+?)\1\)$'),
    "wait": re.compile(r"^wait\(\s*seconds=([^)]+)\)$"),
    "response": re.compile(r'^response\(\s*answer=(["\'])(.+?)\1\)$'),
    "terminate_status_only": re.compile(r"^terminate\(\s*status=(['\"])(.+?)\1\s*\)$"),
    "terminate_with_info": re.compile(
        r'^terminate\(\s*status=(["\'])(?:.*?)\1\s*,\s*info=(["\'])(.+?)\2\)$'
    ),
}


def reverse_map_call_to_do(call_str: str) -> str:
    call_str = call_str.strip()

    m = _PATTERNS["click"].match(call_str)
    if m:
        x, y = m.group(1).strip(), m.group(2).strip()
        return f'do(action="Tap", element=[{x}, {y}])'

    m = _PATTERNS["long_press"].match(call_str)
    if m:
        x, y, d = (g.strip() for g in m.groups())
        return f'do(action="Long Press", element=[{x}, {y}], duration={d})'

    m = _PATTERNS["swipe_precise"].match(call_str)
    if m:
        x1, y1, x2, y2 = (
            m.group(2).strip(),
            m.group(3).strip(),
            m.group(5).strip(),
            m.group(6).strip(),
        )
        return f'do(action="Swipe Precise", start=[{x1}, {y1}], end=[{x2}, {y2}])'

    m = _PATTERNS["swipe_dir"].match(call_str)
    if m:
        direction, amt = m.group(2), m.group(3).strip()
        return f'do(action="Swipe", direction="{direction}", dist={amt})'

    m = _PATTERNS["write"].match(call_str)
    if m:
        text = m.group(2)
        return f'do(action="Type", text="{text}")'

    m = _PATTERNS["open_app"].match(call_str)
    if m:
        pkg = m.group(2)
        return f'do(action="Launch", app="{pkg}")'

    if call_str == "navigate_home()":
        return 'do(action="Home")'

    if call_str == "navigate_back()":
        return 'do(action="Back")'

    if call_str == "enter()":
        return 'do(action="Enter")'

    m = _PATTERNS["wait"].match(call_str)
    if m:
        secs = m.group(1).strip()
        return f'do(action="Wait", seconds={secs})'

    if call_str == "call_user()":
        return 'do(action="Call_API")'

    m = _PATTERNS["response"].match(call_str)
    if m:
        ans = m.group(2)
        return f'do(message="{ans}")'

    m = _PATTERNS["terminate_with_info"].match(call_str)
    if m:
        msg = m.group(3)
        return f'do(action="finish", message="{msg}")'

    m = _PATTERNS["terminate_status_only"].match(call_str)
    if m:
        return 'do(action="finish")'

    return f'do(message="Unrecognized call: {call_str}")'


def parse_sections(text: str):
    pattern = re.compile(r"<(think|operation|action)>(.*?)</\1>", re.DOTALL)
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(text)}


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def replace_image_url(messages, throw_details=False, keep_path=False):
    new_messages = copy.deepcopy(messages)
    for message in new_messages:
        if message["role"] == "user":
            for content in message["content"]:
                if isinstance(content, str):
                    continue
                if content["type"] == "image_url":
                    image_url = content["image_url"]["url"]
                    image_url_parts = image_url.split(";base64,")
                    if not keep_path:
                        content["image_url"]["url"] = (
                            image_url_parts[0] + ";base64," + image_url_parts[1]
                        )
                    else:
                        content["image_url"]["url"] = f"file://{image_url_parts[1]}"
                    if throw_details:
                        content["image_url"].pop("detail", None)
    return new_messages
