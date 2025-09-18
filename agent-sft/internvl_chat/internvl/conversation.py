"""
Conversation prompt templates.

We kindly request that you import fastchat instead of copying this file if you wish to use it.
If you have changes in mind, please contribute back so the community can benefit collectively and continue to maintain these valuable templates.
"""

import dataclasses
from enum import IntEnum, auto
from typing import Any, Dict, List, Tuple, Union


class SeparatorStyle(IntEnum):
    """Separator styles."""

    ADD_COLON_SINGLE = auto()
    ADD_COLON_TWO = auto()
    ADD_COLON_SPACE_SINGLE = auto()
    NO_COLON_SINGLE = auto()
    NO_COLON_TWO = auto()
    ADD_NEW_LINE_SINGLE = auto()
    LLAMA2 = auto()
    CHATGLM = auto()
    CHATML = auto()
    CHATINTERN = auto()
    DOLLY = auto()
    RWKV = auto()
    PHOENIX = auto()
    ROBIN = auto()
    FALCON_CHAT = auto()
    CHATGLM3 = auto()
    INTERNVL_ZH = auto()
    MPT = auto()


@dataclasses.dataclass
class Conversation:
    """A class that manages prompt templates and keeps all conversation history."""

    # The name of this template
    name: str
    # The template of the system prompt
    system_template: str = "{system_message}"
    # The system message
    system_message: str = ""
    # The names of two roles
    roles: Tuple[str] = ("USER", "ASSISTANT")
    # All messages. Each item is (role, message).
    messages: List[List[str]] = ()
    # The number of few shot examples
    offset: int = 0
    # The separator style and configurations
    sep_style: SeparatorStyle = SeparatorStyle.ADD_COLON_SINGLE
    sep: str = "\n"
    sep2: str = None
    # Stop criteria (the default one is EOS token)
    stop_str: Union[str, List[str]] = None
    # Stops generation if meeting any token in this list
    stop_token_ids: List[int] = None

    def get_prompt(self) -> str:
        """Get the prompt for generation."""
        system_prompt = self.system_template.format(system_message=self.system_message)
        if self.sep_style == SeparatorStyle.ADD_COLON_SINGLE:
            ret = system_prompt + self.sep
            for role, message in self.messages:
                if message:
                    ret += role + ": " + message + self.sep
                else:
                    ret += role + ":"
            return ret
        elif self.sep_style == SeparatorStyle.ADD_COLON_TWO:
            seps = [self.sep, self.sep2]
            ret = system_prompt + seps[0]
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret += role + ": " + message + seps[i % 2]
                else:
                    ret += role + ":"
            return ret
        elif self.sep_style == SeparatorStyle.ADD_COLON_SPACE_SINGLE:
            ret = system_prompt + self.sep
            for role, message in self.messages:
                if message:
                    ret += role + ": " + message + self.sep
                else:
                    ret += role + ": "  # must be end with a space
            return ret
        elif self.sep_style == SeparatorStyle.ADD_NEW_LINE_SINGLE:
            ret = "" if system_prompt == "" else system_prompt + self.sep
            for role, message in self.messages:
                if message:
                    ret += role + "\n" + message + self.sep
                else:
                    ret += role + "\n"
            return ret
        elif self.sep_style == SeparatorStyle.NO_COLON_SINGLE:
            ret = system_prompt
            for role, message in self.messages:
                if message:
                    ret += role + message + self.sep
                else:
                    ret += role
            return ret
        elif self.sep_style == SeparatorStyle.NO_COLON_TWO:
            seps = [self.sep, self.sep2]
            ret = system_prompt
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret += role + message + seps[i % 2]
                else:
                    ret += role
            return ret
        elif self.sep_style == SeparatorStyle.RWKV:
            ret = system_prompt
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret += (
                        role
                        + ": "
                        + message.replace("\r\n", "\n").replace("\n\n", "\n")
                    )
                    ret += "\n\n"
                else:
                    ret += role + ":"
            return ret
        elif self.sep_style == SeparatorStyle.LLAMA2:
            seps = [self.sep, self.sep2]
            if self.system_message:
                ret = system_prompt
            else:
                ret = "[INST] "
            for i, (role, message) in enumerate(self.messages):
                tag = self.roles[i % 2]
                if message:
                    if i == 0:
                        ret += message + " "
                    else:
                        ret += tag + " " + message + seps[i % 2]
                else:
                    ret += tag
            return ret
        elif self.sep_style == SeparatorStyle.CHATGLM:
            # source: https://huggingface.co/THUDM/chatglm-6b/blob/1d240ba371910e9282298d4592532d7f0f3e9f3e/modeling_chatglm.py#L1302-L1308
            # source2: https://huggingface.co/THUDM/chatglm2-6b/blob/e186c891cf64310ac66ef10a87e6635fa6c2a579/modeling_chatglm.py#L926
            round_add_n = 1 if self.name == "chatglm2" else 0
            if system_prompt:
                ret = system_prompt + self.sep
            else:
                ret = ""

            for i, (role, message) in enumerate(self.messages):
                if i % 2 == 0:
                    ret += f"[Round {i//2 + round_add_n}]{self.sep}"

                if message:
                    ret += f"{role}：{message}{self.sep}"
                else:
                    ret += f"{role}："
            return ret
        elif self.sep_style == SeparatorStyle.CHATML:
            ret = "" if system_prompt == "" else system_prompt + self.sep + "\n"
            for role, message in self.messages:
                if message:
                    ret += role + "\n" + message + self.sep + "\n"
                else:
                    ret += role + "\n"
            return ret
        elif self.sep_style == SeparatorStyle.CHATGLM3:
            ret = ""
            if self.system_message:
                ret += system_prompt
            for role, message in self.messages:
                if message:
                    ret += role + "\n" + " " + message
                else:
                    ret += role
            return ret
        elif self.sep_style == SeparatorStyle.CHATINTERN:
            # source: https://huggingface.co/internlm/internlm-chat-7b-8k/blob/bd546fa984b4b0b86958f56bf37f94aa75ab8831/modeling_internlm.py#L771
            seps = [self.sep, self.sep2]
            ret = system_prompt
            for i, (role, message) in enumerate(self.messages):
                # if i % 2 == 0:
                #     ret += "<s>"
                if message:
                    ret += role + ":" + message + seps[i % 2] + "\n"
                else:
                    ret += role + ":"
            return ret
        elif self.sep_style == SeparatorStyle.DOLLY:
            seps = [self.sep, self.sep2]
            ret = system_prompt
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret += role + ":\n" + message + seps[i % 2]
                    if i % 2 == 1:
                        ret += "\n\n"
                else:
                    ret += role + ":\n"
            return ret
        elif self.sep_style == SeparatorStyle.PHOENIX:
            ret = system_prompt
            for role, message in self.messages:
                if message:
                    ret += role + ": " + "<s>" + message + "</s>"
                else:
                    ret += role + ": " + "<s>"
            return ret
        elif self.sep_style == SeparatorStyle.ROBIN:
            ret = system_prompt + self.sep
            for role, message in self.messages:
                if message:
                    ret += role + ":\n" + message + self.sep
                else:
                    ret += role + ":\n"
            return ret
        elif self.sep_style == SeparatorStyle.FALCON_CHAT:
            ret = ""
            if self.system_message:
                ret += system_prompt + self.sep
            for role, message in self.messages:
                if message:
                    ret += role + ": " + message + self.sep
                else:
                    ret += role + ":"

            return ret
        elif self.sep_style == SeparatorStyle.INTERNVL_ZH:
            seps = [self.sep2, self.sep]
            ret = self.system_message + seps[0]
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret += role + ": " + message + seps[i % 2]
                else:
                    ret += role + ":"
            return ret
        elif self.sep_style == SeparatorStyle.MPT:
            ret = system_prompt + self.sep
            for role, message in self.messages:
                if message:
                    if type(message) is tuple:
                        message, _, _ = message
                    ret += role + message + self.sep
                else:
                    ret += role
            return ret
        else:
            raise ValueError(f"Invalid style: {self.sep_style}")

    def set_system_message(self, system_message: str):
        """Set the system message."""
        self.system_message = system_message

    def append_message(self, role: str, message: str):
        """Append a new message."""
        self.messages.append([role, message])

    def update_last_message(self, message: str):
        """Update the last output.

        The last message is typically set to be None when constructing the prompt,
        so we need to update it in-place after getting the response from a model.
        """
        self.messages[-1][1] = message

    def to_gradio_chatbot(self):
        """Convert the conversation to gradio chatbot format."""
        ret = []
        for i, (role, msg) in enumerate(self.messages[self.offset :]):
            if i % 2 == 0:
                ret.append([msg, None])
            else:
                ret[-1][-1] = msg
        return ret

    def to_openai_api_messages(self):
        """Convert the conversation to OpenAI chat completion format."""
        ret = [{"role": "system", "content": self.system_message}]

        for i, (_, msg) in enumerate(self.messages[self.offset :]):
            if i % 2 == 0:
                ret.append({"role": "user", "content": msg})
            else:
                if msg is not None:
                    ret.append({"role": "assistant", "content": msg})
        return ret

    def copy(self):
        return Conversation(
            name=self.name,
            system_template=self.system_template,
            system_message=self.system_message,
            roles=self.roles,
            messages=[[x, y] for x, y in self.messages],
            offset=self.offset,
            sep_style=self.sep_style,
            sep=self.sep,
            sep2=self.sep2,
            stop_str=self.stop_str,
            stop_token_ids=self.stop_token_ids,
        )

    def dict(self):
        return {
            "template_name": self.name,
            "system_message": self.system_message,
            "roles": self.roles,
            "messages": self.messages,
            "offset": self.offset,
        }


# A global registry for all conversation templates
conv_templates: Dict[str, Conversation] = {}


def register_conv_template(template: Conversation, override: bool = False):
    """Register a new conversation template."""
    if not override:
        assert (
            template.name not in conv_templates
        ), f"{template.name} has been registered."

    conv_templates[template.name] = template


def get_conv_template(name: str) -> Conversation:
    """Get a conversation template."""
    return conv_templates[name].copy()


# InternVL-Chat-V1-1 template
register_conv_template(
    Conversation(
        name="internvl_zh",
        system_template="",
        roles=("<human>", "<bot>"),
        sep_style=SeparatorStyle.INTERNVL_ZH,
        sep="</s>",
        sep2=" ",
    )
)


# Both Hermes-2 and internlm2-chat are chatml-format conversation templates. The difference
# is that during training, the preprocessing function for the Hermes-2 template doesn't add
# <s> at the beginning of the tokenized sequence, while the internlm2-chat template does.
# Therefore, they are completely equivalent during inference.
register_conv_template(
    Conversation(
        name="Hermes-2",
        system_template="<|im_start|>system\n{system_message}",
        # note: The new system prompt was not used here to avoid changes in benchmark performance.
        # system_message='我是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。',
        system_message="你是由上海人工智能实验室联合商汤科技开发的书生多模态大模型，英文名叫InternVL, 是一个有用无害的人工智能助手。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>",
        stop_str="<|endoftext|>",
    )
)


register_conv_template(
    Conversation(
        name="internlm2-chat",
        system_template="<|im_start|>system\n{system_message}",
        # note: The new system prompt was not used here to avoid changes in benchmark performance.
        # system_message='我是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。',
        system_message="你是由上海人工智能实验室联合商汤科技开发的书生多模态大模型，英文名叫InternVL, 是一个有用无害的人工智能助手。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>",
    )
)


register_conv_template(
    Conversation(
        name="phi3-chat",
        system_template="<|system|>\n{system_message}",
        # note: The new system prompt was not used here to avoid changes in benchmark performance.
        # system_message='我是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。',
        system_message="你是由上海人工智能实验室联合商汤科技开发的书生多模态大模型，英文名叫InternVL, 是一个有用无害的人工智能助手。",
        roles=("<|user|>\n", "<|assistant|>\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|end|>",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5",
        system_template="<|im_start|>system\n{system_message}",
        system_message="你是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl_grounding",
        system_template="<|im_start|>system\n{system_message}",
        system_message="你是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl_referring",
        system_template="<|im_start|>system\n{system_message}",
        system_message="你是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_aguvis",
        system_template="<|im_start|>system\n{system_message}",
        system_message="你是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_aguvis_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message="你是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_aguvis_v3",
        system_template="<|im_start|>system\n{system_message}",
        system_message="You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform a series of pyautogui actions to complete the task.",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_aguvis_v4",
        system_template="<|im_start|>system\n{system_message}",
        system_message="You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform a series of pyautogui actions to complete the task.",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_private_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message="你是书生·万象，英文名是InternVL，是由上海人工智能实验室、清华大学及多家合作单位联合开发的多模态大语言模型。",
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


# GUI

# Shared actions for desktop, web and mobile
click = """def click(
    x: float | None = None,
    y: float | None = None,
    clicks: int = 1,
    button: str = "left",
) -> None:
    \"\"\"Clicks on the screen at the specified coordinates. The `x` and `y` parameter specify where the mouse event occurs. If not provided, the current mouse position is used. The `clicks` parameter specifies how many times to click, and the `button` parameter specifies which mouse button to use ('left', 'right', or 'middle').\"\"\"
    pass
"""


write = """def write(message: str) -> None:
    \"\"\"Write the specified text.\"\"\"
    pass
"""

call_user = """def call_user() -> None:
    \"\"\"Call the user.\"\"\"
    pass
"""

wait = """def wait(seconds: int = 3) -> None:
    \"\"\"Wait for the change to happen.\"\"\"
    pass
"""

response = """def response(answer: str) -> None:
    \"\"\"Answer a question or provide a response to an user query.\"\"\"
    pass
"""

terminate = """def terminate(status: str = "success", info: str | None = None) -> None:
    \"\"\"Terminate the current task with a status. The `status` specifies the termination status ('success', 'failure'), and the `info` can provide additional information about the termination.\"\"\"
    pass
"""

# Shared action for desktop and web

doubleClick = """def doubleClick(
    x: float | None = None,
    y: float | None = None,
    button: str = "left",
) -> None:
    \"\"\"Performs a double click. This is a wrapper function for click(x, y, 2, 'left').\"\"\"
    pass
"""

rightClick = """def rightClick(x: float | None = None, y: float | None = None) -> None:
    \"\"\"Performs a right mouse button click. This is a wrapper function for click(x, y, 1, 'right').\"\"\"
    pass
"""

hotkey = """def hotkey(*args: str) -> None:
    \"\"\"Performs key down presses on the arguments passed in order, then performs key releases in reverse order. This is used to simulate keyboard shortcuts (e.g., 'Ctrl-Shift-C').\"\"\"
    pass
"""

scroll = """def scroll(clicks: int, x: float | None = None, y: float | None = None) -> None:
    \"\"\"Performs a scroll of the mouse scroll wheel at the specified coordinates. The `clicks` specifies how many clicks to scroll. The direction of the scroll (vertical or horizontal) depends on the underlying operating system. Normally, positive values scroll up, and negative values scroll down.\"\"\"
    pass
"""

moveTo = """def moveTo(x: float, y: float) -> None:
    \"\"\"Move the mouse to the specified coordinates.\"\"\"
    pass
"""

dragTo = """def dragTo(
    x: float | None = None, y: float | None = None, button: str = "left"
) -> None:
    \"\"\"Performs a drag-to action with optional `x` and `y` coordinates and button.\"\"\"
    pass
"""

press = """def press(keys: str | list[str], presses: int = 1) -> None:
    \"\"\"Performs a keyboard key press down, followed by a release. The function supports pressing a single key or a list of keys, multiple presses, and customizable intervals between presses.\"\"\"
    pass
"""

keyDown = """def keyDown(key: str) -> None:
    \"\"\"Performs a keyboard key press without the release. This will put that key in a held down state.\"\"\"
    pass
"""

keyUp = """def keyUp(key: str) -> None:
    \"\"\"Performs a keyboard key release (without the press down beforehand).\"\"\"
    pass
"""

# Shared actions for web and mobile
swipe = """def swipe(
    from_coord: list[float, float] | None = None,
    to_coord: list[float, float] | None = None,
    direction: str = "up",
    amount: float = 0.5,
) -> None:
    \"\"\"Performs a swipe action on the screen. The `from_coord` and `to_coord` specify the starting and ending coordinates of the swipe. If `to_coord` is not provided, the `direction` and `amount` parameters are used to determine the swipe direction and distance. The `direction` can be 'up', 'down', 'left', or 'right', and the `amount` specifies how far to swipe relative to the screen size (0 to 1).\"\"\"
    pass
"""

# Actions for web

select_option = """def select_option(x: float, y: float, value: str) -> None:
    \"\"\"Select an option from a dropdown menu. It is only available for web.\"\"\"
    pass
"""

open_url = """def open_url(url: str) -> None:
    \"\"\"Open a URL in the browser.\"\"\"
    pass
"""

go_forward = """def go_forward() -> None:
    \"\"\"Go forward in the browser.\"\"\"
    pass
"""

go_backward = """def go_backward() -> None:
    \"\"\"Go backward in the browser.\"\"\"
    pass
"""

# Actions for mobile

navigate_home = """def navigate_home() -> None:
    \"\"\"Press the home button.\"\"\"
    pass
"""

navigate_back = """def navigate_back() -> None:
    \"\"\"Press the back button.\"\"\"
    pass
"""

long_press = """def long_press(x: float, y: float, duration: int = 1) -> None:
    \"\"\"Long press on the screen at the specified coordinates. The `duration` specifies how long to hold the press in seconds.\"\"\"
    pass
"""

open_app = """def open_app(app_name: str) -> None:
    \"\"\"Open an app on the device.\"\"\"
    pass
"""


ACTIONS = [
    {
        "name": "click",
        "desc": click,
        "platform": ["desktop", "web", "mobile", "mind2web"],
    },
    {"name": "doubleClick", "desc": doubleClick, "platform": ["desktop", "web"]},
    {"name": "rightClick", "desc": rightClick, "platform": ["desktop", "web"]},
    {"name": "scroll", "desc": scroll, "platform": ["desktop"]},
    {"name": "moveTo", "desc": moveTo, "platform": ["desktop", "web"]},
    {"name": "dragTo", "desc": dragTo, "platform": ["desktop", "web"]},
    {"name": "swipe", "desc": swipe, "platform": ["web", "mobile"]},
    {"name": "press", "desc": press, "platform": ["desktop", "web"]},
    {"name": "hotkey", "desc": hotkey, "platform": ["desktop", "web"]},
    {"name": "keyDown", "desc": keyDown, "platform": ["desktop", "web"]},
    {"name": "keyUp", "desc": keyUp, "platform": ["desktop", "web"]},
    {"name": "select_option", "desc": select_option, "platform": ["mind2web"]},
    {"name": "open_url", "desc": open_url, "platform": ["web"]},
    {"name": "go_forward", "desc": go_forward, "platform": ["web"]},
    {"name": "go_backward", "desc": go_backward, "platform": ["web"]},
    {"name": "long_press", "desc": long_press, "platform": ["mobile"]},
    {"name": "open_app", "desc": open_app, "platform": ["mobile"]},
    {"name": "navigate_home", "desc": navigate_home, "platform": ["mobile"]},
    {"name": "navigate_back", "desc": navigate_back, "platform": ["mobile"]},
    {
        "name": "write",
        "desc": write,
        "platform": ["desktop", "web", "mobile", "mind2web"],
    },
    {"name": "call_user", "desc": call_user, "platform": ["desktop", "web", "mobile"]},
    {"name": "wait", "desc": wait, "platform": ["desktop", "web", "mobile"]},
    {"name": "response", "desc": response, "platform": ["desktop", "web", "mobile"]},
    {"name": "terminate", "desc": terminate, "platform": ["desktop", "web", "mobile"]},
]


GRD_ACTIONS = [
    {"name": "click", "desc": click, "platform": ["desktop", "web", "mobile"]},
    {"name": "doubleClick", "desc": doubleClick, "platform": ["desktop", "web"]},
    {"name": "rightClick", "desc": rightClick, "platform": ["desktop", "web"]},
    {"name": "moveTo", "desc": moveTo, "platform": ["desktop", "web"]},
    {"name": "dragTo", "desc": dragTo, "platform": ["desktop", "web"]},
    {"name": "swipe", "desc": swipe, "platform": ["web", "mobile"]},
    # {"name": "select_option", "desc": select_option, "platform": ["mind2web"]},
    {"name": "long_press", "desc": long_press, "platform": ["mobile"]},
]


grounding_system_prompt = """You are an autonomous GUI agent capable of operating on desktops, mobile devices, and web browsers. Your primary function is to analyze screen captures and perform appropriate UI actions to complete assigned tasks.

## Action Space
{action_space}

## Input Specification
- Screenshot of the current screen + task description

## Output Format
<action>
[A set of executable action command]
</action>

## Note
- Avoid action(s) that would lead to invalid states.
- The generated action(s) must exist within the defined action space.
- The generated action(s) should be enclosed within <action></action> tags."""


navigation_system_prompt = """You are an autonomous GUI agent operating on the **{platform}** platform(s). Your primary function is to analyze screen captures and perform appropriate UI actions to complete assigned tasks.

## Action Space
{action_space}

## Input Specification
- Screenshot of the current screen + task description + your past interaction history with UI to finish assigned tasks.

## Output Format
<operation>
[Next intended operation description]
</operation>
<action>
[A set of executable action commands]
</action>

## Note
- Avoid action(s) that would lead to invalid states.
- The generated action(s) must exist within the defined action space.
- The generated operation and action(s) should be enclosed within <operation></operation> and <action></action> tags, respectively."""


planning_system_prompt = """You are an autonomous GUI agent operating on the **{platform}** platform. Your primary function is to analyze screen captures and perform appropriate UI actions to complete assigned tasks.

## Action Space
{action_space}

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


os_genesis_mobile_system_prompt = """You are a Mobile GUI Agent trained to assist with executing user instructions on Android devices by interacting with the graphical user interface (GUI). At each step, you will be given a high-level instruction (or a low-level reasoning step), a history of past actions, a screenshot of the current screen, and its corresponding accessibility tree. Your task is to reason about the next step and decide the most appropriate action to take using the available action space.

You must select from the following **action space**:

* `click`: Clicks at the target element.
* `long_press`: Presses and holds on the target element.
* `type`: Types the specified text at the current cursor location.
* `scroll`: Scrolls in a specified direction on the screen.
* `navigate_home`: Navigates to the device’s home screen.
* `navigate_back`: Returns to the previous screen or page.
* `open_app`: Launches the specified application.
* `wait`: Waits without taking any immediate action.
* `terminate`: Indicates the task has been completed.
* `keyboard_enter`: Presses the Enter key.


You must base your decision on the visual and structural information provided in the screenshot and accessibility tree, as well as the task instruction and previous actions. Respond only with the next step to take."""


os_genesis_web_system_prompt = """You are a highly capable Web Use Agent designed to assist with completing web-based tasks through intelligent, step-by-step interaction with user interfaces. At each step, you will receive a high-level task instruction, the current webpage screenshot, the corresponding accessibility tree, and a history of previous actions. Your objective is to reason over this input and select the most appropriate next action to progress toward completing the task.

You must select from the following **action space**:

* `click [id]`: Clicks on an element identified by its unique accessibility ID.
* `type [id] [content] [press_enter_after=0|1]`: Types the provided content into the field with the specified ID. Optionally presses "Enter" after typing (1 = press, 0 = don’t press).
* `hover [id]`: Moves the cursor to hover over the element with the given ID.
* `press [key_comb]`: Simulates keyboard input for the given key combination (e.g., `Ctrl+v`).
* `scroll [direction=down|up]`: Scrolls the page vertically in the specified direction.
* `new_tab`: Opens a new empty browser tab.
* `tab_focus [tab_index]`: Switches focus to a tab by its index.
* `close_tab`: Closes the currently focused tab.
* `goto [url]`: Navigates directly to the specified URL.
* `go_back`: Navigates to the previous page in the tab history.
* `go_forward`: Navigates to the next page if previously navigated back.
* `stop [answer]`: Ends the task. Provide the final answer in brackets, or `"N/A"` if the task is impossible to complete.


You must base your decision on the visual and structural information provided in the screenshot and accessibility tree, as well as the task instruction and previous actions. Respond only with the next step to take."""


odyssey_plus_systemp_prompt = '''You are an intelligent Mobile Use Agent trained to complete goal-driven tasks on mobile interfaces by observing screen images and reasoning step-by-step. At each step, your objective is to analyze the current UI screenshot, understand the user’s high-level instruction, review prior actions, and determine the next most appropriate low-level UI operation.

**Action Space:**
You may output only one of the following actions per step:

* `"CLICK"`: Tap a specific screen coordinate.
  Format: `{ "action": "CLICK", "args": { "x": float, "y": float } }` where `x` and `y` are normalized to [0,1] relative to screen width and height.

* `"LONG_PRESS"`: Long press on the screen at a specific screen coordinate.
  Format: `{ "action": "LONG_PRESS", "args": { "x": float, "y": float } }` where `x` and `y` are normalized to [0,1] relative to screen width and height.

* `"TEXT"`: Input a text string into a selected input field.
  Format: `{ "action": "TEXT", "args": { "content": "string" } }`

* `"SCROLL"`: Perform a swipe gesture.
  Format: `{ "action": "SCROLL", "args": { "start": [x1, y1], "end": [x2, y2] } }` with coordinates normalized to [0,1].

* `"KEY_HOME"`, `"KEY_BACK"`, `"KEY_APPSELECT"`: Simulate hardware key press.
  Format: `{ "action": "KEY_HOME", "args": {} }` (and similar for others)

* `"COMPLETE"`: Task finished successfully.

  * Format: `{ "action": "COMPLETE", "args": {} }`

* `"INCOMPLETE"`: Task cannot be completed.

  * Format: `{ "action": "INCOMPLETE", "args": {} }`

**Your Input:**

* Task description
* History of prior operations
* Current UI screenshot

**Your Output:**

* Reasoning should precede the action to explain your decision-making
* One structured JSON action

Do not skip steps. Always reason before acting.'''

register_conv_template(
    Conversation(
        name="internvl2_5_windows_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "desktop" in item["platform"]]
            ),
            # platform="Windows",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_ubuntu_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "desktop" in item["platform"]]
            ),
            # platform="Ubuntu",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_macos_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "desktop" in item["platform"]]
            ),
            # platform="macOS",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_web_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "web" in item["platform"]]
            ),
            # platform="Browser",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_mind2web_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [
                    item["desc"]
                    for item in GRD_ACTIONS
                    if "web" in item["platform"] or "mind2web" in item["platform"]
                ]
            ),
            platform="Browser",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_android_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "mobile" in item["platform"]]
            ),
            # platform="Android",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_iphone_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "mobile" in item["platform"]]
            ),
            # platform="iOS",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_ipad_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "mobile" in item["platform"]]
            ),
            # platform="iPadOS",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_mobile_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in GRD_ACTIONS if "mobile" in item["platform"]]
            ),
            # platform="Phone & Tablet",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_all_grounding_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=grounding_system_prompt.format(
            action_space="\n\n".join([item["desc"] for item in GRD_ACTIONS]),
            # platform="Windows & Ubuntu & Browser & Phone & Tablet",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_android_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mobile" in item["platform"]]
            ),
            platform="Android",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_android_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mobile" in item["platform"]]
            ),
            platform="Android",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_android_planning_cot_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mobile" in item["platform"]]
            ),
            platform="Android",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_mobile_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mobile" in item["platform"]]
            ),
            platform="Mobile Phone & Tablet",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_mobile_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mobile" in item["platform"]]
            ),
            platform="Mobile Phone & Tablet",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_mobile_planning_cot_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mobile" in item["platform"]]
            ),
            platform="Mobile Phone & Tablet",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_web_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "web" in item["platform"]]
            ),
            platform="Web Browser",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_web_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "web" in item["platform"]]
            ),
            platform="Web Browser",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_web_planning_cot_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "web" in item["platform"]]
            ),
            platform="Web Browser",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_mind2web_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mind2web" in item["platform"]]
            ),
            platform="Mind2Web",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_mind2web_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "mind2web" in item["platform"]]
            ),
            platform="Mind2Web",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_ubuntu_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="Linux (Ubuntu)",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_ubuntu_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="Linux (Ubuntu)",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_ubuntu_planning_cot_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="Linux (Ubuntu)",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_windows_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="Windows",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_windows_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="Windows",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_windows_planning_cot_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="Windows",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_mac_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="macOS",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_mac_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="macOS",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_mac_planning_cot_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="macOS",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_desktop_planning_cot_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="desktop (Windows/Linux/macOS)",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_desktop_planning_cot_v2",
        system_template="<|im_start|>system\n{system_message}",
        system_message=planning_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="desktop (Windows/Linux/macOS)",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_desktop_navigation_v1",
        system_template="<|im_start|>system\n{system_message}",
        system_message=navigation_system_prompt.format(
            action_space="\n\n".join(
                [item["desc"] for item in ACTIONS if "desktop" in item["platform"]]
            ),
            platform="desktop (Windows/Linux/macOS)",
        ),
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_mobile_os_genesis",
        system_template="<|im_start|>system\n{system_message}",
        system_message=os_genesis_mobile_system_prompt,
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)


register_conv_template(
    Conversation(
        name="internvl2_5_web_os_genesis",
        system_template="<|im_start|>system\n{system_message}",
        system_message=os_genesis_web_system_prompt,
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

register_conv_template(
    Conversation(
        name="internvl2_5_mobile_odyssey_plus",
        system_template="<|im_start|>system\n{system_message}",
        system_message=odyssey_plus_systemp_prompt,
        roles=("<|im_start|>user\n", "<|im_start|>assistant\n"),
        sep_style=SeparatorStyle.MPT,
        sep="<|im_end|>\n",
    )
)

GUI_CONV_TEMPLATE = [
    "internvl2_5_all_grounding_v1",
    "internvl2_5_windows_grounding_v1",
    "internvl2_5_ubuntu_grounding_v1",
    "internvl2_5_macos_grounding_v1",
    "internvl2_5_iphone_grounding_v1",
    "internvl2_5_android_grounding_v1",
    "internvl2_5_mobile_grounding_v1",
    "internvl2_5_web_grounding_v1",
    "internvl2_5_android_navigation_v1",
    "internvl2_5_mobile_navigation_v1",
    "internvl2_5_web_navigation_v1",
    "internvl2_5_android_planning_cot_v1",
    "internvl2_5_mobile_planning_cot_v1",
    "internvl2_5_web_planning_cot_v1",
    "internvl2_5_mind2web_navigation_v1",
    "internvl2_5_mind2web_planning_cot_v1",
    "internvl_grounding",
    "internvl_referring",
    "internvl2_5_mobile_odyssey_plus",
    "internvl2_5_web_os_genesis",
    "internvl2_5_mobile_os_genesis",
    "internvl2_5_desktop_navigation_v1",
    "internvl2_5_desktop_planning_cot_v1",
    "internvl2_5_mac_planning_cot_v1",
    "internvl2_5_mac_navigation_v1",
    "internvl2_5_windows_planning_cot_v1",
    "internvl2_5_windows_navigation_v1",
    "internvl2_5_ubuntu_planning_cot_v1",
    "internvl2_5_ubuntu_navigation_v1",
]

if __name__ == "__main__":
    platform = ["Windows", "Ubuntu", "macOS", "Browser", "Android", "iOS", "iPadOS"]
    print(conv_templates["internvl2_5_ubuntu_planning_cot_v1"].system_message)