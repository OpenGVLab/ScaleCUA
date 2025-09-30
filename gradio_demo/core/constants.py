# --------------------------------------------------------
# ScaleCUA
# Copyright (c) 2025 OpenGVLab
# Licensed under The Apache-2.0 License [see LICENSE for details]
# --------------------------------------------------------

CONTROLLER_HEART_BEAT_EXPIRATION = 30
WORKER_HEART_BEAT_INTERVAL = 15

LOGDIR = 'logs/'

server_error_msg = '**NETWORK ERROR DUE TO HIGH TRAFFIC. PLEASE REGENERATE OR REFRESH THIS PAGE.**'
moderation_msg = 'YOUR INPUT VIOLATES OUR CONTENT MODERATION GUIDELINES. PLEASE TRY AGAIN.'


# SYSTEM PROMPT FOR THREE MODES
import textwrap
SYSTEM_PROMPT_DICT = {
    "Multimodal Chat": """You are a helpful assistant.""",
    "GUI Grounding": textwrap.dedent('''
        You are an autonomous GUI agent capable of operating on desktops, mobile devices, and web browsers. Your primary function is to analyze screen captures and perform appropriate UI actions to complete assigned tasks.
        
        ## Action Space
        def click(
            x: float | None = None,
            y: float | None = None,
            clicks: int = 1,
            button: str = "left",
        ) -> None:
            """Clicks on the screen at the specified coordinates. The `x` and `y` parameter specify where the mouse event occurs. If not provided, the current mouse position is used. The `clicks` parameter specifies how many times to click, and the `button` parameter specifies which mouse button to use ('left', 'right', or 'middle')."""
            pass
                                 
        def doubleClick(
            x: float | None = None,
            y: float | None = None,
            button: str = "left",
        ) -> None:
            """Performs a double click. This is a wrapper function for click(x, y, 2, 'left')."""
            pass
                                 
        def rightClick(x: float | None = None, y: float | None = None) -> None:
            """Performs a right mouse button click. This is a wrapper function for click(x, y, 1, 'right')."""
            pass
                                 
        def moveTo(x: float, y: float) -> None:
            """Move the mouse to the specified coordinates."""
            pass
                                 
        def dragTo(
            x: float | None = None, y: float | None = None, button: str = "left"
        ) -> None:
            """Performs a drag-to action with optional `x` and `y` coordinates and button."""
            pass
                                 
        def swipe(
            from_coord: tuple[float, float] | None = None,
            to_coord: tuple[float, float] | None = None,
            direction: str = "up",
            amount: float = 0.5,
        ) -> None:
            """Performs a swipe action on the screen. The `from_coord` and `to_coord` specify the starting and ending coordinates of the swipe. If `to_coord` is not provided, the `direction` and `amount` parameters are used to determine the swipe direction and distance. The `direction` can be 'up', 'down', 'left', or 'right', and the `amount` specifies how far to swipe relative to the screen size (0 to 1)."""
            pass
                                 
        def long_press(x: float, y: float, duration: int = 1) -> None:
            """Long press on the screen at the specified coordinates. The `duration` specifies how long to hold the press in seconds."""
            pass
                                 
        ## Input Specification
        - Screenshot of the current screen + task description
                                 
        ## Output Format
        <action>
        [A set of executable action command]
        </action>
                                 
        ## Note
        - Avoid action(s) that would lead to invalid states.
        - The generated action(s) must exist within the defined action space.
        - The generated action(s) should be enclosed within <action></action> tags.
    '''),
    "GUI Planning": textwrap.dedent('''
        You are an autonomous GUI agent operating on the desktops, mobile devices, and web browsers. Your primary function is to analyze screen captures and perform appropriate UI actions to complete assigned tasks.

        ## Action Space
        def click(
            x: float | None = None,
            y: float | None = None,
            clicks: int = 1,
            button: str = "left",
        ) -> None:
            \"""Clicks on the screen at the specified coordinates. The `x` and `y` parameter specify where the mouse event occurs. If not provided, the current mouse position is used. The `clicks` parameter specifies how many times to click, and the `button` parameter specifies which mouse button to use ('left', 'right', or 'middle').\"""
            pass


        def doubleClick(
            x: float | None = None,
            y: float | None = None,
            button: str = "left",
        ) -> None:
            \"""Performs a double click. This is a wrapper function for click(x, y, 2, 'left').\"""
            pass


        def rightClick(x: float | None = None, y: float | None = None) -> None:
            \"""Performs a right mouse button click. This is a wrapper function for click(x, y, 1, 'right').\"""
            pass


        def moveTo(x: float, y: float) -> None:
            \"""Move the mouse to the specified coordinates.\"""
            pass


        def dragTo(
            x: float | None = None, y: float | None = None, button: str = "left"
        ) -> None:
            \"""Performs a drag-to action with optional `x` and `y` coordinates and button.\"""
            pass


        def swipe(
            from_coord: list[float, float] | None = None,
            to_coord: list[float, float] | None = None,
            direction: str = "up",
            amount: float = 0.5,
        ) -> None:
            \"""Performs a swipe action on the screen. The `from_coord` and `to_coord` specify the starting and ending coordinates of the swipe. If `to_coord` is not provided, the `direction` and `amount` parameters are used to determine the swipe direction and distance. The `direction` can be 'up', 'down', 'left', or 'right', and the `amount` specifies how far to swipe relative to the screen size (0 to 1).\"""
            pass


        def press(keys: str | list[str], presses: int = 1) -> None:
            \"""Performs a keyboard key press down, followed by a release. The function supports pressing a single key or a list of keys, multiple presses, and customizable intervals between presses.\"""
            pass


        def hotkey(*args: str) -> None:
            \"""Performs key down presses on the arguments passed in order, then performs key releases in reverse order. This is used to simulate keyboard shortcuts (e.g., 'Ctrl-Shift-C').\"""
            pass


        def write(message: str) -> None:
            \"""Write the specified text.\"""
            pass


        def wait(seconds: int = 3) -> None:
            \"""Wait for the change to happen.\"""
            pass


        def response(answer: str) -> None:
            \"""Answer a question or provide a response to an user query.\"""
            pass


        def terminate(status: str = "success", info: str | None = None) -> None:
            \"""Terminate the current task with a status. The `status` specifies the termination status ('success', 'failure'), and the `info` can provide additional information about the termination.\"""
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
        - The reasoning process, operation and action(s) in your response should be enclosed within <think></think>, <operation></operation> and <action></action> tags, respectively.
        - Ensure that all action parameters are provided as explicit key-value pairs (i.e., keyword arguments), not as positional arguments.

    ''')
}


MESSAGES = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "",
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                    },
                },
                {
                    "type": "text", 
                    "text": None
                },
            ],
        },
    ]

OPENAI_API_BASE = "http://10.140.66.159:10024/v1"
MODEL_NAME = "ScaleCUA-7B"

# UI
title_html = """
<h2> <span class="gradient-text" id="text">ScaluCUA</span><span class="plain-text">: Scaling Open-Source Computer Use Agents with Cross-Platform Data</span></h2>
<a href="https://huggingface.co/papers/2509.15221">[📖 HF Paper]</a>
<a href="https://github.com/OpenGVLab/ScaleCUA">[🌟 GitHub]</a> 
<a href="https://huggingface.co/spaces/OpenGVLab/ScaleCUA-Demo">[🤗 Demo]</a> 
<a href="https://huggingface.co/collections/OpenGVLab/scalecua-68c912cf56f7ff4c8e034003">[🤗 Models]</a> 
<a href="https://huggingface.co/datasets/OpenGVLab/ScaleCUA-Data">[⛁ Dataset]</a> 
"""


tos_markdown = """
### Terms of use
By using this service, users are required to agree to the following terms:
The service is a research preview intended for non-commercial use only. It only provides limited safety measures and may generate offensive content. It must not be used for any illegal, harmful, violent, racist, or sexual purposes. The service may collect user dialogue data for future research.
Please click the "Flag" button if you get any inappropriate answer! We will collect those to keep improving our moderator.
For an optimal experience, please use desktop computers for this demo, as mobile devices may compromise its quality.
"""


learn_more_markdown = """
### License
The service is a research preview intended for non-commercial use only, subject to the model [License](https://github.com/facebookresearch/llama/blob/main/MODEL_CARD.md) of LLaMA, [Terms of Use](https://openai.com/policies/terms-of-use) of the data generated by OpenAI, and [Privacy Practices](https://chrome.google.com/webstore/detail/sharegpt-share-your-chatg/daiacboceoaocpibfodeljbdfacokfjb) of ShareGPT. Please contact us if you find any potential violation.

### Acknowledgement
This demo is modified from LLaVA's demo. Thanks for their awesome work!
"""
# .gradio-container {margin: 5px 10px 0 10px !important};
block_css = """
.gradio-container {margin: 0.1% 1% 0 1% !important; max-width: 98% !important;};
#buttons button {
    min-width: min(120px,100%);
}

.gradient-text {
    font-size: 28px;
    width: auto;
    font-weight: bold;
    background: linear-gradient(45deg, red, orange, yellow, green, blue, indigo, violet);
    background-clip: text;
    -webkit-background-clip: text;
    color: transparent;
}

.plain-text {
    font-size: 22px;
    width: auto;
    font-weight: bold;
}
"""

js = """
function createWaveAnimation() {
    const text = document.getElementById('text');
    var i = 0;
    setInterval(function() {
        const colors = [
            'red, orange, yellow, green, blue, indigo, violet, purple',
            'orange, yellow, green, blue, indigo, violet, purple, red',
            'yellow, green, blue, indigo, violet, purple, red, orange',
            'green, blue, indigo, violet, purple, red, orange, yellow',
            'blue, indigo, violet, purple, red, orange, yellow, green',
            'indigo, violet, purple, red, orange, yellow, green, blue',
            'violet, purple, red, orange, yellow, green, blue, indigo',
            'purple, red, orange, yellow, green, blue, indigo, violet',
        ];
        const angle = 45;
        const colorIndex = i % colors.length;
        text.style.background = `linear-gradient(${angle}deg, ${colors[colorIndex]})`;
        text.style.webkitBackgroundClip = 'text';
        text.style.backgroundClip = 'text';
        text.style.color = 'transparent';
        text.style.fontSize = '28px';
        text.style.width = 'auto';
        text.textContent = 'ScaleCUA';
        text.style.fontWeight = 'bold';
        i += 1;
    }, 200);
    const params = new URLSearchParams(window.location.search);
    url_params = Object.fromEntries(params);
    // console.log(url_params);
    // console.log('hello world...');
    // console.log(window.location.search);
    // console.log('hello world...');
    // alert(window.location.search)
    // alert(url_params);
    return url_params;
}

"""
