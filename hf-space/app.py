import os
import base64
import re
import io
import math
import gradio as gr
import random
from PIL import ImageDraw, Image
import requests
from datetime import datetime
import json
import uuid
import logging
from constants import *

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs("./temp", exist_ok=True)
os.environ["GRADIO_TEMP_DIR"] = "./temp"


# Create examples directory and example images
def prepare_examples():
    examples_dir = "examples"
    os.makedirs(examples_dir, exist_ok=True)

    # Example list - store image paths, text and modes separately
    examples = [
        ["./examples/mac_desktop_1.jpg", "Click on 飞书", "grounding"],
        ["./examples/solitaire.png", "Play the solitaire collection", "grounding"],
        ["./examples/weather_ui.png", "Open map", "grounding"],
        ["./examples/football_live.png", "click team 1 win", "grounding"],
        ["./examples/windows_panel.png", "switch to documents", "grounding"],
        ["./examples/paint_3d.png", "rotate left", "grounding"],
        ["./examples/finder.png", "view files from airdrop", "grounding"],
        ["./examples/amazon.jpg", "Search bar at the top of the page", "grounding"],
        ["./examples/semantic.jpg", "Home", "grounding"],
        ["./examples/accweather.jpg", "Select May", "grounding"],
        ["./examples/arxiv.jpg", "Home", "grounding"],
        ["./examples/health.jpg", "text labeled by 2023/11/26", "grounding"],
        ["./examples/ios_setting.png", "Turn off Do not disturb.", "grounding"],
        ["./examples/vscode.png", "Open the 'debug.sh' file to modify the content.", "grounding"]
    ]

    # Check if example images exist
    valid_examples = []
    for example in examples:
        if os.path.exists(example[0]):
            valid_examples.append(example)
        else:
            logger.warning(f"Example image does not exist: {example[0]}")

    return valid_examples


# Helper functions
def round_by_factor(number: int, factor: int) -> int:
    """Returns the integer closest to 'number' that is divisible by 'factor'."""
    return round(number / factor) * factor


def ceil_by_factor(number: int, factor: int) -> int:
    """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
    return math.ceil(number / factor) * factor


def floor_by_factor(number: int, factor: int) -> int:
    """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
    return math.floor(number / factor) * factor


def smart_resize(height: int, width: int, factor: int = IMAGE_FACTOR,
                 min_pixels: int = MIN_PIXELS, max_pixels: int = MAX_PIXELS) -> tuple[int, int]:
    """
    Resize an image to meet the following criteria:
    1. Height and width are both divisible by 'factor'
    2. Total pixel count is within ['min_pixels', 'max_pixels']
    3. Aspect ratio is preserved as much as possible
    """
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"Aspect ratio must be less than {MAX_RATIO}, but current ratio is {max(height, width) / min(height, width)}"
        )
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(int(height / beta), factor)
        w_bar = floor_by_factor(int(width / beta), factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = ceil_by_factor(int(height * beta), factor)
        w_bar = ceil_by_factor(int(width * beta), factor)
    return h_bar, w_bar


def draw_point_area(image, point):
    x, y = round(point[0] * image.width), round(point[1] * image.height)
    draw = ImageDraw.Draw(image)
    x_size = 25
    draw.line([(x - x_size, y - x_size), (x + x_size, y + x_size)], fill="red", width=8)
    draw.line([(x - x_size, y + x_size), (x + x_size, y - x_size)], fill="red", width=8)
    return image


def parse_point(output_text, image):
    w, h = image.size
    new_h, new_w = smart_resize(h, w, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)

    # Pattern 1: Match x=number, y=number format
    pattern1 = r"x=(\d+\.?\d*),\s*y=(\d+\.?\d*)"
    match = re.search(pattern1, output_text)
    if match:
        click_xy = [float(match.group(1)) / new_w, float(match.group(2)) / new_h]
        result_image = draw_point_area(image.copy(), click_xy)
        return result_image, click_xy

    # Pattern 2: Match [number,number,number,number] format (x1,y1,x2,y2)
    pattern2 = r"\[(\d+\.?\d*),\s*(\d+\.?\d*),\s*(\d+\.?\d*),\s*(\d+\.?\d*)\]"
    match = re.search(pattern2, output_text)
    if match:
        # Extract coordinates and calculate center point
        x1 = float(match.group(1))
        y1 = float(match.group(2))
        x2 = float(match.group(3))
        y2 = float(match.group(4))

        # Calculate center point
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        # Convert to relative coordinates
        click_xy = [center_x / new_w, center_y / new_h]
        result_image = draw_point_area(image.copy(), click_xy)
        return result_image, click_xy

    # If no coordinates are matched, return the original image
    return image.copy(), None


# OpenAI API request function
def query_openai_api(messages, **generation_config):
    headers = {
        "Content-Type": "application/json"
    }

    print(f'generation  config: {generation_config}')
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": generation_config["max_output_tokens"] if "max_output_tokens" in generation_config else 1024,
        "temperature": generation_config["temperature"] if "temperature" in generation_config else 0.1,
        "top_p": generation_config["top_p"] if "top_p" in generation_config else 0.7,
        "repetition_penalty": generation_config["repetition_penalty"] if "repetition_penalty" in generation_config else 1.1,
    }

    try:
        response = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            return f"Error: {response.status_code} - {response.text}"

        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"API call error: {str(e)}"


# Convert image to base64
def image_to_base64(image):
    if image is None:
        return None

    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# Dictionary to store user sessions
sessions = {}


def regenerate(history, session_id, temperature, top_p, repetition_penalty, max_output_tokens):
    # Check if session ID exists
    if session_id is None or session_id not in sessions:
        return history, gr.MultimodalTextbox(value=None, interactive=True)

    generation_config = {
        "temperature": temperature,
        "top_p": top_p,
        "repetition_penalty": repetition_penalty,
        "max_output_tokens": max_output_tokens
    }

    # If history is empty, return directly
    if len(history) < 2:
        return history, gr.MultimodalTextbox(value=None, interactive=True)

    # Remove the last assistant message (and possible image marker message)
    while len(history) > 0 and history[-1]["role"] == "assistant":
        history.pop()  # Remove the assistant's last reply

    # Remove the last assistant message from session messages
    if len(sessions[session_id]["messages"]) > 0 and sessions[session_id]["messages"][-1]["role"] == "assistant":
        sessions[session_id]["messages"].pop()

    # Get the current processed image
    current_image = sessions[session_id]["current_image"]

    # Resend to API to generate new response
    response = query_openai_api(
        messages=sessions[session_id]["messages"],
        **generation_config
    )
    print(f'Regenerated model response: {response}')

    # Add new assistant reply to API message history
    sessions[session_id]["messages"].append({"role": "assistant", "content": response})

    # Add new assistant reply to Gradio chat history
    history.append({"role": "assistant", "content": response})

    # If there's an image and coordinates are detected, mark coordinates on the image
    if current_image:
        marked_image, _ = parse_point(response, current_image)
        if marked_image is not current_image:  # If the image was modified
            history.append({"role": "assistant", "content": gr.Image(marked_image)})

    return history, gr.MultimodalTextbox(value=None, interactive=True)


# Process multimodal input
def add_message(history, message, mode, session_id, temperature, top_p, repetition_penalty, max_output_tokens):
    generation_config = {
        "temperature": temperature,
        "top_p": top_p,
        "repetition_penalty": repetition_penalty,
        "max_output_tokens": max_output_tokens
    }

    if session_id is None:
        session_id = str(uuid.uuid4())

    # Get or create user session
    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],  # Store OpenAI format message history
            "current_image": None,  # Store current processed image
            "mode": mode  # Store current mode
        }

    # If mode has changed, clear message history
    if sessions[session_id]["mode"] != mode:
        sessions[session_id]["messages"] = []
        sessions[session_id]["mode"] = mode
        history = []  # Clear Gradio chat history

    # Add system message (if message history is empty)
    if len(sessions[session_id]["messages"]) == 0 and SYSTEM_PROMPT_DICT[mode]:
        sessions[session_id]["messages"].append({
            "role": "system",
            "content": SYSTEM_PROMPT_DICT[mode]
        })

    # Process uploaded files (images)
    image = None
    if message["files"] and len(message["files"]) > 0:
        # Process the first uploaded image
        image_path = message["files"][0]
        try:
            image = Image.open(image_path)
            sessions[session_id]["current_image"] = image

            # Add image to Gradio chat history
            history.append({"role": "user", "content": {"path": image_path}})
        except Exception as e:
            print(f"Image processing error: {str(e)}")

    # Process text message
    if message["text"]:
        # Add text to Gradio chat history
        history.append({"role": "user", "content": message["text"]})

        # Prepare API request
        current_image = sessions[session_id]["current_image"]

        if current_image:
            # If there's an image, create multimodal message
            base64_image = image_to_base64(current_image)
            user_message = {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                    {"type": "text", "text": message["text"]}
                ]
            }
        else:
            # If no image, send text only
            user_message = {"role": "user", "content": message["text"]}

        sessions[session_id]["messages"].append(user_message)

        # Send to API
        response = query_openai_api(messages=sessions[session_id]["messages"],
                                    generation_config=generation_config)
        print(f'Model response: {response}')

        # Add assistant reply to API message history
        sessions[session_id]["messages"].append({"role": "assistant", "content": response})

        # Add assistant reply to Gradio chat history
        history.append({"role": "assistant", "content": response})

        # If there's an image and coordinates are detected, mark coordinates on the image
        if current_image:
            marked_image, _ = parse_point(response, current_image)
            if marked_image is not current_image:  # If the image was modified
                history.append({"role": "assistant", "content": gr.Image(marked_image)})

    return history, gr.MultimodalTextbox(value=None, interactive=True), session_id


def change_mode(mode):
    # Clear chat history when switching modes
    return []


def clear_conversation(mode, session_id):
    if session_id is None or session_id not in sessions:
        return []

    # Clear Session
    sessions[session_id] = {
        "messages": [],
        "current_image": None,
        "mode": mode
    }
    return []


# Handle example selection
def select_example(example_data):
    # Parse example data
    image_path, prompt_text, _ = example_data

    # Build multimodal message
    message = {
        "files": [image_path],
        "text": prompt_text
    }

    # Automatically switch to grounding mode
    return "grounding", message, []


# Handle example selection
def set_example(example_image, example_text, example_mode):
    return {
        "files": [example_image],
        "text": example_text
    }, example_mode


with gr.Blocks(css=block_css) as demo:
    session_id = gr.State(None)

    gr.Markdown(title_markdown)

    example_image = gr.State()
    example_text = gr.State()
    example_mode = gr.State()

    with gr.Row():
        with gr.Column(scale=2, elem_id="chat-container"):
            mode_selector = gr.Radio(
                choices=["general", "grounding", "planning"],
                value="general",
                label="Chat mode"
            )

            chatbot = gr.Chatbot(
                elem_id="chatbox",
                height=500,
                type="messages",
                allow_tags=True,
                avatar_images=[
                    "assets/human.png",
                    "assets/assistant.png",
                ]
            )

            chat_input = gr.MultimodalTextbox(
                interactive=True,
                file_count="single",
                file_types=["image"],
                placeholder="Enter message or upload file...",
                show_label=False,
                sources=["upload"],
                label="Input"
            )

            with gr.Row():
                clear_button = gr.Button("Clear")
                regenerate_button = gr.Button("Regenerate")

            gr.Markdown(tos_markdown)
            gr.Markdown(learn_more_markdown)
            gr.Markdown(code_adapt_markdown)

        with gr.Column(scale=1, elem_id="image-container"):
            gr.Markdown("## Settings", elem_id="examples-header")
            with gr.Accordion("Settings", open=False) as setting_row:
                temperature = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    value=0.2,
                    step=0.1,
                    interactive=True,
                    label="Temperature",
                )
                top_p = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    value=0.7,
                    step=0.1,
                    interactive=True,
                    label="Top P",
                )
                repetition_penalty = gr.Slider(
                    minimum=1.0,
                    maximum=1.5,
                    value=1.1,
                    step=0.02,
                    interactive=True,
                    label="Repetition penalty",
                )
                max_output_tokens = gr.Slider(
                    minimum=0,
                    maximum=4096,
                    value=1024,
                    step=64,
                    interactive=True,
                    label="Max output tokens",
                )

            gr.Markdown("## Examples", elem_id="examples-header")
            examples_data = prepare_examples()
            with gr.Accordion("Examples", open=False) as example_row:
                # Two examples per group
                with gr.Row(elem_classes="examples-container"):
                    for i in range(0, len(examples_data), 2):
                        with gr.Row(elem_classes="examples-row"):
                            # Process current example
                            if i < len(examples_data):
                                img_path, text, mode = examples_data[i]
                                with gr.Column(elem_classes="example-item"):
                                    gr.Image(img_path, elem_classes="example-image", height=120)
                                    gr.Markdown(f"**{text}**", elem_classes="example-text")
                                    example_btn = gr.Button("Try this example")
                                    example_btn.click(
                                        fn=lambda path=img_path, txt=text, m=mode: set_example(path, txt, m),
                                        inputs=None,
                                        outputs=[chat_input, mode_selector]
                                    )

                            # Process next example (if exists)
                            if i + 1 < len(examples_data):
                                img_path, text, mode = examples_data[i + 1]
                                with gr.Column(elem_classes="example-item"):
                                    gr.Image(img_path, elem_classes="example-image", height=120)
                                    gr.Markdown(f"**{text}**", elem_classes="example-text")
                                    example_btn = gr.Button("Try this example")
                                    example_btn.click(
                                        fn=lambda path=img_path, txt=text, m=mode: set_example(path, txt, m),
                                        inputs=None,
                                        outputs=[chat_input, mode_selector]
                                    )

    # Event handling
    chat_input.submit(
        add_message,
        [chatbot, chat_input, mode_selector, session_id, temperature, top_p, repetition_penalty, max_output_tokens],
        [chatbot, chat_input, session_id]
    )

    # Default has session_id, if no session_id, this button does nothing
    regenerate_button.click(
        regenerate,
        [chatbot, session_id, temperature, top_p, repetition_penalty, max_output_tokens],
        [chatbot, chat_input]
    )

    # Update clear button functionality
    clear_button.click(
        clear_conversation,
        inputs=[mode_selector, session_id],
        outputs=[chatbot]
    )
    # Update mode switching handling - ensure chat history is cleared
    mode_selector.change(
        change_mode,
        inputs=[mode_selector],
        outputs=[chatbot]
    )

if __name__ == "__main__":
    demo.launch(share=False, server_port=10039, server_name="0.0.0.0")