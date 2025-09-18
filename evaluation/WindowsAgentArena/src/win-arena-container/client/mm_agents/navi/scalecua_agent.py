# -*- coding: utf-8 -*-
"""
This script defines the ScaleCUAAgent, an agent designed to interact with a computer's GUI
based on natural language instructions. It can operate in two modes:
1.  A single-model mode where a multi-modal model directly generates pyautogui actions.
2.  A planner-executor mode where a planner model first generates a high-level plan,
    and an executor model (grounding model) refines the specific actions (e.g., coordinates).

The agent processes visual information from screenshots and user instructions to generate
executable Python code for GUI automation.
"""

# --- Standard Library Imports ---
import ast
import base64
import json
import logging
import math
import os
import re
import tempfile
import time
from http import HTTPStatus
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

# --- Third-Party Imports ---
import backoff
import openai
import requests
from google.api_core.exceptions import (BadRequest, InternalServerError,
                                        InvalidArgument, ResourceExhausted)
from openai import OpenAI
from PIL import Image
from requests.exceptions import SSLError

# --- Local Application Imports ---
# Note: These are assumed to be part of the project structure.
from mm_agents.navi.prompts import (AGUVIS_PLANNER_SYS_PROMPT,
                                    SCALECUA_GROUNDING_SYSTEM_PROMPT,
                                    SCALECUA_NAVIGATION_SYSTEM_PROMPT,
                                    SCALECUA_SYSTEM_PROMPT,
                                    SCALECUA_USER_PROMPT)

# --- Constants ---
# Image resizing parameters
IMAGE_FACTOR = 28
MIN_PIXELS = 3136
MAX_PIXELS = 2109744
MAX_RATIO = 200

# Default screen logical size
SCREEN_LOGIC_SIZE = (1280, 800)

# --- Logger Setup ---
# The logger is initialized globally and set in the agent's reset method.
logger: Optional[logging.Logger] = None

# set your proxy
os.environ['http_proxy'] = 'http://your_proxy:port'
os.environ['https_proxy'] = 'http://your_proxy:port'

# set openai key
os.environ['OPENAI_KEY'] = 'your_openai_key'

# ==============================================================================
# Utility Functions
# ==============================================================================

def smart_resize(height: int, width: int) -> tuple[int, int]:
    """
    Resizes image dimensions to be compatible with model requirements.

    The new dimensions will meet these conditions:
    1. Both height and width are divisible by IMAGE_FACTOR.
    2. The total number of pixels is between MIN_PIXELS and MAX_PIXELS.
    3. The original aspect ratio is maintained as closely as possible.

    Args:
        height: The original height of the image.
        width: The original width of the image.

    Returns:
        A tuple containing the new height and width.

    Raises:
        ValueError: If the image's aspect ratio exceeds MAX_RATIO.
    """
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"Aspect ratio must be smaller than {MAX_RATIO}, "
            f"but got {max(height, width) / min(height, width)}"
        )

    # Helper functions to round to the nearest multiple of a factor
    def round_by_factor(num, factor):
        return round(num / factor) * factor

    def floor_by_factor(num, factor):
        return math.floor(num / factor) * factor

    def ceil_by_factor(num, factor):
        return math.ceil(num / factor) * factor

    # Initial rounding
    h_bar = max(IMAGE_FACTOR, round_by_factor(height, IMAGE_FACTOR))
    w_bar = max(IMAGE_FACTOR, round_by_factor(width, IMAGE_FACTOR))

    # Adjust if total pixels are outside the allowed range
    if h_bar * w_bar > MAX_PIXELS:
        beta = math.sqrt((height * width) / MAX_PIXELS)
        h_bar = floor_by_factor(height / beta, IMAGE_FACTOR)
        w_bar = floor_by_factor(width / beta, IMAGE_FACTOR)
    elif h_bar * w_bar < MIN_PIXELS:
        beta = math.sqrt(MIN_PIXELS / (height * width))
        h_bar = ceil_by_factor(height * beta, IMAGE_FACTOR)
        w_bar = ceil_by_factor(width * beta, IMAGE_FACTOR)

    return h_bar, w_bar


def extract_coordinates(text: str, screen_height: int, screen_width: int) -> Optional[Tuple[str, str]]:
    """
    Extracts (x, y) coordinates from a string and scales them to the screen size.

    Args:
        text: The string containing coordinates, e.g., "click at (x=123, y=456)".
        screen_height: The height of the screen for scaling.
        screen_width: The width of the screen for scaling.

    Returns:
        A tuple of (x, y) coordinates as formatted strings, or None if not found.
    """
    # This pattern matches coordinates like (123, 456) or (x=123, y=456)
    pattern = r'\((?:x=)?([-+]?\d*\.\d+|\d+),\s*(?:y=)?([-+]?\d*\.\d+|\d+)\)'
    match = re.search(pattern, text)

    if match:
        x = float(match.group(1))
        y = float(match.group(2))

        # Scale coordinates from the model's resized view to the actual screen size
        resize_h, resize_w = smart_resize(screen_height, screen_width)
        scaled_x = f"{x / resize_w * screen_width:.4f}"
        scaled_y = f"{y / resize_h * screen_height:.4f}"
        return (scaled_x, scaled_y)

    return None


def pil_to_base64(image: Image.Image) -> str:
    """
    Converts a PIL Image object to a Base64 encoded string.

    Args:
        image: The PIL Image to convert.

    Returns:
        The Base64 encoded string representation of the image.
    """
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def encode_image(image_content: bytes) -> str:
    """
    Encodes image bytes into a Base64 string.

    Args:
        image_content: The image data in bytes.

    Returns:
        The Base64 encoded string.
    """
    return base64.b64encode(image_content).decode('utf-8')


def encoded_img_to_pil_img(data_str: str) -> Image.Image:
    """
    Converts a Base64 encoded string back to a PIL Image.

    Args:
        data_str: The Base64 string, potentially with a data URI prefix.

    Returns:
        The decoded PIL Image object.
    """
    # Remove the "data:image/png;base64," prefix if it exists
    base64_str = re.sub(r'^data:image/png;base64,', '', data_str)
    image_data = base64.b64decode(base64_str)
    return Image.open(BytesIO(image_data))


def save_to_tmp_img_file(data_str: str) -> str:
    """
    Decodes a Base64 image string and saves it to a temporary file.

    Args:
        data_str: The Base64 string of the image.

    Returns:
        The file path to the saved temporary image.
    """
    image = encoded_img_to_pil_img(data_str)
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, "tmp_img.png")
    image.save(temp_path)
    return temp_path


def parse_code_from_planner_response(input_string: str) -> List[str]:
    """
    Parses executable code snippets from a planner's formatted response.
    It extracts code from markdown-style blocks (```...```).

    Args:
        input_string: The raw string response from the planner model.

    Returns:
        A list of cleaned code snippets or commands ('WAIT', 'DONE', 'FAIL').
    """
    # Clean up input by removing empty lines and extra whitespace
    input_string = "\n".join([line.strip() for line in input_string.split(';') if line.strip()])

    if input_string.strip() in ['WAIT', 'DONE', 'FAIL']:
        return [input_string.strip()]

    # Regex to find code within ```python ... ``` or ``` ... ``` blocks
    pattern = r"```(?:\w+\s*)?(.*?)```"
    matches = re.findall(pattern, input_string, re.DOTALL)

    codes = []
    for match in matches:
        match = match.strip()
        commands = ['WAIT', 'DONE', 'FAIL']

        # Handle standalone commands or commands appearing at the end of a code block
        if match in commands:
            codes.append(match)
        elif match.split('\n')[-1] in commands:
            code_block = "\n".join(match.split('\n')[:-1])
            if code_block:
                codes.append(code_block)
            codes.append(match.split('\n')[-1])
        else:
            codes.append(match)

    return codes


def split_args(args_str: str) -> List[str]:
    """
    Splits a string of arguments, correctly handling arguments within quotes.

    Args:
        args_str: A string containing comma-separated arguments.

    Returns:
        A list of argument strings.
    """
    args = []
    current_arg = ''
    in_string = False
    string_char = ''
    prev_char = ''

    for char in args_str:
        if char in ['"', "'"] and not in_string:
            in_string = True
            string_char = char
        elif in_string and prev_char != '\\' and char == string_char:
            in_string = False

        if char == ',' and not in_string:
            args.append(current_arg.strip())
            current_arg = ''
        else:
            current_arg += char
        prev_char = char

    if current_arg:
        args.append(current_arg.strip())

    return args


def correct_pyautogui_arguments(code: str) -> str:
    """
    Corrects common incorrect keyword arguments in generated pyautogui code.
    LLMs sometimes hallucinate incorrect argument names (e.g., 'text' instead of 'message').

    Args:
        code: A string of generated Python code.

    Returns:
        The corrected code string.
    """
    # Mappings of incorrect to correct argument names for specific functions
    function_corrections = {
        'write': {'incorrect_args': ['text'], 'correct_args': [], 'keyword_arg': 'message'},
        'press': {'incorrect_args': ['key', 'button'], 'correct_args': [], 'keyword_arg': None},
        'hotkey': {'incorrect_args': ['key1', 'key2', 'keys'], 'correct_args': [], 'keyword_arg': None},
    }

    corrected_lines = []
    for line in code.strip().split('\n'):
        line = line.strip()
        match = re.match(r'(pyautogui\.(\w+))\((.*)\)', line)

        if match:
            full_func_call, func_name, args_str = match.groups()
            if func_name in function_corrections:
                func_info = function_corrections[func_name]
                args = split_args(args_str)
                corrected_args = []

                for arg in args:
                    kwarg_match = re.match(r'(\w+)\s*=\s*(.*)', arg)
                    if kwarg_match:
                        arg_name, arg_value = kwarg_match.groups()
                        # If the argument name is in the list of incorrect ones, replace it
                        if arg_name in func_info['incorrect_args']:
                            if func_info['keyword_arg']:
                                corrected_args.append(f"{func_info['keyword_arg']}={arg_value}")
                            else:
                                corrected_args.append(arg_value) # Use as positional arg
                        else:
                            corrected_args.append(arg) # Keep original
                    else:
                        corrected_args.append(arg) # Positional arg

                corrected_args_str = ', '.join(corrected_args)
                corrected_lines.append(f'{full_func_call}({corrected_args_str})')
            else:
                corrected_lines.append(line) # No correction needed for this function
        else:
            corrected_lines.append(line) # Not a function call

    return '\n'.join(corrected_lines)


# ==============================================================================
# ScaleCUAAgent Class
# ==============================================================================

class ScaleCUAAgent:
    """
    An agent that interprets natural language instructions and screenshots to
    generate and execute GUI automation commands.
    """
    def __init__(
        self,
        platform: str = "windows",
        screen_width: int = 1280,
        screen_height: int = 800,
        planner_model: Optional[str] = None,
        executor_model: str = "ScaleCUA-7B",
        enable_thinking: bool = True,
        max_tokens: int = 1500,
        top_p: float = 0.001,
        top_k: float = 1,
        temperature: float = 0.0,
        action_space: str = "pyautogui",
        observation_type: str = "screenshot",
        api_url: str = "",
    ):
        """Initializes the ScaleCUAAgent."""
        self.platform = platform
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.planner_model = planner_model
        self.executor_model = executor_model
        self.enable_thinking = enable_thinking
        self.api_url = api_url
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k
        self.temperature = temperature
        self.action_space = action_space
        self.observation_type = observation_type
        self.history: List[str] = []

        assert self.executor_model is not None, "Executor model cannot be None"
        assert self.action_space == "pyautogui", "Invalid action space"
        assert self.observation_type == "screenshot", "Invalid observation type"

    def reset(self, _logger: Optional[logging.Logger] = None) -> None:
        """
        Resets the agent's state for a new episode.

        Args:
            _logger: An optional logger instance. If not provided, a new one is created.
        """
        global logger
        logger = _logger if _logger is not None else logging.getLogger("desktopenv.scalecua_agent")
        self.history = []

    def predict(self, instruction: str, obs: Dict) -> Tuple[str, List[str], Dict[str, Any], Optional[Any]]:
        """
        Predicts the next action(s) based on the instruction and observation.

        Args:
            instruction: The high-level user command (e.g., "Open Notepad and type hello").
            obs: A dictionary containing the current observation, primarily the 'screenshot'.

        Returns:
            A tuple containing:
            - The raw model response string.
            - A list of generated pyautogui action strings.
            - A dictionary of logs for debugging.
            - None (placeholder for compatibility).
        """
        logs: Dict[str, Any] = {
            'instruction': instruction,
            'raw_obs_keys': list(obs.keys()),
            'previous_actions_in_episode_count': len(self.history),
        }

        current_screenshot_bytes = obs.get("screenshot")
        if current_screenshot_bytes:
            try:
                # Ensure screenshot is in bytes format
                if isinstance(current_screenshot_bytes, str):
                    if current_screenshot_bytes.startswith('data:image'):
                        current_screenshot_bytes = base64.b64decode(current_screenshot_bytes.split(',')[1])
                    else:
                        current_screenshot_bytes = base64.b64decode(current_screenshot_bytes)
                
                pil_image = Image.open(BytesIO(current_screenshot_bytes))
                logs['current_screenshot_pil_original_size'] = pil_image.size
                logs['foreground_window_pil_preview'] = pil_image.copy()
            except Exception as e:
                logger.error(f"Failed to process screenshot: {e}")
                logs['current_screenshot_pil_error'] = str(e)
        else:
            logs['current_screenshot_pil_original_size'] = "N/A"
            logs['foreground_window_pil_preview'] = "N/A"

        history_str = self.format_history(self.history)
        logs['previous_actions_formatted_str'] = history_str

        # --- Path 1: Single Model generates actions directly ---
        if self.planner_model is None:
            raw_model_response, pyautogui_actions, agent_logs = self._run_single_model_flow(
                instruction, history_str, current_screenshot_bytes
            )
            logs.update(agent_logs)
            return raw_model_response, pyautogui_actions, logs, None

        # --- Path 2: Planner-Executor Model Flow ---
        else:
            raw_model_response, pyautogui_actions, planner_logs = self._run_planner_executor_flow(
                instruction, obs, current_screenshot_bytes
            )
            logs.update(planner_logs)
            return raw_model_response, pyautogui_actions, logs, None

    def _run_single_model_flow(self, instruction, history_str, screenshot_bytes):
        """Handles the logic for the single-model approach."""
        logs = {}
        # Determine the system prompt based on whether 'thinking' is enabled
        system_prompt = SCALECUA_SYSTEM_PROMPT if self.enable_thinking else SCALECUA_NAVIGATION_SYSTEM_PROMPT
        
        user_prompt = SCALECUA_USER_PROMPT.format(
            instruction=instruction, previous_actions=history_str
        )

        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encode_image(screenshot_bytes)}"
                        }
                    },
                    {
                        "type": "text",
                        "text": user_prompt
                    }
                ]
            }
        ]
        
        if screenshot_bytes:
            messages[1]["content"].append()

        logs['agent_input_messages_summary'] = [(m['role'], [c['type'] for c in m['content']]) for m in messages]

        # Call the language model
        agent_response = self.call_llm({
            "model": self.executor_model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "temperature": self.temperature
        }, self.executor_model)
        
        logger.info(f"Agent Output: {agent_response}")
        logs['agent_raw_response'] = agent_response

        # Parse the response
        try:
            think, operation, actions = self.parse_response(agent_response)
            pyautogui_actions = self.parse_action(actions or [])
            logs.update({
                'agent_parsed_think': think,
                'agent_parsed_low_level_instruction': operation,
                'agent_parsed_pyautogui_actions': pyautogui_actions
            })
        except Exception as e:
            logger.error(f"Error parsing Agent response: {e}")
            logs['agent_parsing_error'] = str(e)
            operation = f"# Error parsing: {agent_response}"
            pyautogui_actions = ["# PARSE_ERROR"]
        
        # Update history with the operation for the next step
        if operation:
            self.history.append(operation)
            
        logs['final_pyautogui_actions_generated'] = pyautogui_actions
        return agent_response, pyautogui_actions, logs

    def _run_planner_executor_flow(self, instruction, obs, screenshot_bytes):
        """Handles the logic for the planner-executor approach."""
        logs = {}
        
        # --- Step 1: Call Planner ---
        planner_messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": AGUVIS_PLANNER_SYS_PROMPT
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encode_image(screenshot_bytes)}",
                            "detail": "high"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"You are asked to complete the following task: {instruction}"
                    }
                ]
            }
        ]
        
        logs['planner_input_messages_summary'] = [(m['role'], [c['type'] for c in m['content']]) for m in planner_messages]

        planner_response = self.call_llm({
            "model": self.planner_model,
            "messages": planner_messages,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "temperature": self.temperature
        }, self.planner_model)
        
        logger.info(f"Planner Output: {planner_response}")
        logs['planner_raw_response'] = planner_response

        try:
            code_lines = parse_code_from_planner_response(planner_response)
            logs['planner_parsed_code_lines'] = code_lines
        except Exception as e:
            logger.error(f"Error parsing planner response: {e}")
            logs['planner_parsing_error'] = str(e)
            code_lines = [f"# Error parsing planner response: {planner_response}"]

        # --- Step 2: Convert planned actions using Grounding Model ---
        pyautogui_actions = []
        conversion_logs = []
        for line in code_lines:
            try:
                # This function will call the grounding model if needed
                converted_code = self.convert_action_to_grounding_model_instruction(line, obs)
                pyautogui_actions.append(converted_code)
                conversion_logs.append({"line": line, "converted_code": converted_code, "status": "success"})
            except Exception as e:
                logger.error(f"Error converting planner action line '{line}': {e}")
                pyautogui_actions.append(f"# Error converting: {line}")
                conversion_logs.append({"line": line, "error": str(e), "status": "error"})
        
        logs['planner_action_conversion_details'] = conversion_logs
        logs['final_pyautogui_actions_generated'] = pyautogui_actions
        return planner_response, pyautogui_actions, logs

    def convert_action_to_grounding_model_instruction(self, line: str, obs: Dict) -> str:
        """
        Refines a planned action by using a grounding model to get precise coordinates.
        It looks for a comment above a pyautogui action and uses it as a prompt.
        
        Example Input Line:
        # Click on the File menu
        pyautogui.moveTo(x=50, y=25)

        Args:
            line: A line or block of code from the planner.
            obs: The observation dictionary containing the screenshot.

        Returns:
            The action with updated coordinates from the grounding model, or the original line.
        """
        # Pattern to find a comment followed by a pyautogui action with coordinates
        pattern = r'(#.*?)\n(pyautogui\.(?:moveTo|click|rightClick|doubleClick)\((?:x=)?\d+,\s*(?:y=)?\d+.*?\))'
        matches = re.findall(pattern, line, re.DOTALL)
        
        if not matches:
            return line

        new_instruction = line
        for match in matches:
            comment, original_action = match[0], match[1]
            instruction_from_comment = comment.replace("#", "").strip()

            if not obs.get('screenshot'):
                logger.warning("No screenshot available for grounding model, skipping conversion.")
                continue

            # Prepare messages for the grounding model
            grounder_messages = [
                {"role": "system", "content": [{"type": "text", "text": SCALECUA_GROUNDING_SYSTEM_PROMPT}]},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(obs['screenshot'])}", "detail": "high"}},
                    {"type": "text", "text": f"\n{instruction_from_comment}"}
                ]}
            ]

            grounding_response = self.call_llm({
                "model": self.executor_model,
                "messages": grounder_messages,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "temperature": self.temperature
            }, self.executor_model)

            coordinates = extract_coordinates(grounding_response, self.screen_height, self.screen_width)
            if coordinates:
                # Reconstruct the action with the new coordinates
                action_parts = original_action.split('(')
                new_action = f"{action_parts[0]}(x={coordinates[0]}, y={coordinates[1]}"
                
                # Preserve other arguments like duration or button
                if 'duration' in original_action:
                    duration_part = re.search(r'duration=[\d.]+', original_action).group(0)
                    new_action += f", {duration_part}"
                if 'button' in original_action:
                     button_part = re.search(r'button=.*?\)', original_action).group(0)
                     new_action += f", {button_part[:-1]}" # remove closing parenthesis
                
                new_action += ")"
                logger.info(f"Replacing '{original_action}' with '{new_action}'")
                new_instruction = new_instruction.replace(original_action, new_action)
            else:
                 logger.warning(f"Could not extract coordinates from grounding response: {grounding_response}")

        return new_instruction

    @backoff.on_exception(
        backoff.constant,
        (SSLError, openai.RateLimitError, openai.BadRequestError, openai.InternalServerError,
         InvalidArgument, ResourceExhausted, InternalServerError, BadRequest),
        interval=30,
        max_tries=10
    )
    def call_llm(self, payload: Dict, model: str) -> str:
        """
        Makes a call to the specified Large Language Model.

        Args:
            payload: The request payload for the API call.
            model: The name of the model to call.

        Returns:
            The content of the model's response message.
        """
        if model.startswith("gpt"):
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ.get('OPENAI_KEY', 'your_default_token')}"
            }
            # Proxies should also be configured externally
            proxies = {
                "http": os.environ.get('http_proxy', 'your_proxy'),
                "https": os.environ.get('https_proxy', 'your_proxy')
            }
            logger.info("Generating content with GPT model: %s", model)
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers, json=payload, proxies=proxies
            )
            response.raise_for_status() # Will raise an HTTPError for bad responses
            return response.json()['choices'][0]['message']['content']

        elif 'scalecua' in model.lower():
            client = OpenAI(
                base_url=self.api_url, # This should be configurable
                api_key="empty"
            )
            response = client.chat.completions.create(
                model=client.models.list().data[0].id,
                messages=payload['messages'],
                max_tokens=payload['max_tokens'],
                temperature=payload.get('temperature', 1.0),
                top_p=payload.get('top_p', 1.0),
                frequency_penalty=1,
                stream=False,
                extra_body={
                    "skip_special_tokens": False,
                    "spaces_between_special_tokens": False,
                    "top_k": payload.get('top_k', 1),
                },
            )
            return response.choices[0].message.content
        
        else:
            raise ValueError(f"Unknown model type for call_llm: {model}")

    def parse_response(self, response: str) -> Tuple[Optional[str], Optional[str], Optional[List[str]]]:
        """
        Parses the XML-like response from the agent model.

        Args:
            response: The raw string response from the LLM.

        Returns:
            A tuple containing the content of <think>, <operation>, and <action> tags.
        """
        # Extract content from <think> tag
        think_match = re.search(r'<think>\s*(.*?)\s*</think>', response, re.DOTALL)
        think = think_match.group(1).strip() if think_match else None

        # Extract content from <operation> tag
        operation_match = re.search(r'<operation>\s*(.*?)\s*</operation>', response, re.DOTALL)
        operation = operation_match.group(1).strip() if operation_match else None
        
        # Extract content from all <action> tags
        action_matches = re.findall(r'<action>\s*(.*?)\s*</action>', response, re.DOTALL)
        actions = []
        if action_matches:
            for match in action_matches:
                # Split each match by newline and add non-empty lines
                lines = [line.strip() for line in match.split('\n') if line.strip()]
                actions.extend(lines)

        return think, operation, actions if actions else None

    def format_history(self, history: List[str]) -> str:
        """
        Formats the action history into a numbered string for the prompt.

        Args:
            history: A list of past operations.

        Returns:
            A formatted string of historical actions or "None." if history is empty.
        """
        if not history:
            return "None."
        
        return "\n".join([f"Step {i+1}: {low_level}" for i, low_level in enumerate(history)])

    def parse_action(self, actions: List[str]) -> List[str]:
        """
        Parses raw action strings from the model into structured dictionaries,
        then transforms them into executable pyautogui commands.

        Args:
            actions: A list of action strings, e.g., ["click(x=100, y=200)"].

        Returns:
            A list of executable pyautogui command strings.
        """
        parsed_actions = []
        for action_str in actions:
            match = re.match(r"(\w+)\((.*)\)", action_str)
            if not match:
                logger.warning(f"Could not parse action string: {action_str}")
                continue

            func_name, args_str = match.groups()
            
            # This is a simplified parser. For robustness, a more advanced
            # parsing strategy might be needed, but this handles common cases.
            try:
                # Attempt to parse arguments as a dictionary
                # This is safer than complex regex for varied inputs
                parsed_args = ast.literal_eval(f"dict({args_str})")
            except (ValueError, SyntaxError):
                # Fallback for non-dict formats like hotkey('ctrl', 'c')
                # It creates a special 'args' key for positional arguments
                args_list = [arg.strip() for arg in split_args(args_str)]
                parsed_args = {'args': args_list}

            parsed_actions.append({'name': func_name, 'parameters': parsed_args})
        
        # Transform the structured actions into pyautogui strings
        pyautogui_actions = [self.transform_action(pa) for pa in parsed_actions]
        return pyautogui_actions

    def _parse_kwargs(self, arg_str: str) -> Dict[str, Any]:
        """Safely parses a string of keyword arguments into a dictionary."""
        try:
            # Use ast.literal_eval to safely evaluate the string as a Python literal
            return ast.literal_eval(arg_str)
        except (ValueError, SyntaxError, TypeError) as e:
            logger.error(f"Failed to parse argument string: {arg_str}, error: {e}")
            return {}

    def transform_action(self, action: Dict) -> str:
        """

        Converts a parsed action dictionary into an executable pyautogui command string.
        Args:
            action: A dictionary with 'name' and 'parameters' keys.
        Returns:
            An executable pyautogui command as a string.
        """
        func = action.get("name")
        kwargs = action.get("parameters", {})

        # --- Click Actions ---
        if func in ["click", "doubleClick", "rightClick"]:
            x = kwargs.get("x")
            y = kwargs.get("y")
            if x is None or y is None:
                return f"# Error: Missing coordinates for {func}"
            
            # Scale coordinates from relative (0-1) to absolute screen pixels
            resize_h, resize_w = smart_resize(self.screen_height, self.screen_width)
            abs_x = f"{float(x) / resize_w * self.screen_width:.4f}"
            abs_y = f"{float(y) / resize_h * self.screen_height:.4f}"
            
            clicks = 2 if func == "doubleClick" else kwargs.get("clicks", 1)
            button = "right" if func == "rightClick" else kwargs.get("button", "left")
            return f'pyautogui.click(x={abs_x}, y={abs_y}, clicks={clicks}, button="{button}")'

        # --- Scroll Action ---
        if func == "scroll":
            # Get parameters from kwargs, use default values if they don't exist.
            clicks = kwargs.get("clicks", 0)
            x = kwargs.get("x")
            y = kwargs.get("y")
            
            # If both x and y coordinates are provided, scroll at the specified position.
            if x is not None and y is not None:
                return f"pyautogui.scroll(clicks={clicks}, x={x}, y={y})"
            # Otherwise, scroll at the current mouse position.
            else:
                return f"pyautogui.scroll(clicks={clicks})"
             
        # --- Mouse Movement ---
        if func == "moveTo" or func == "dragTo":
            x = kwargs.get("x")
            y = kwargs.get("y")
            if x is None or y is None:
                return f"# Error: Missing coordinates for {func}"

            # Scale coordinates from relative (0-1) to absolute screen pixels
            resize_h, resize_w = smart_resize(self.screen_height, self.screen_width)
            abs_x = f"{float(x) / resize_w * self.screen_width:.4f}"
            abs_y = f"{float(y) / resize_h * self.screen_height:.4f}"

            if func == "moveTo":
                return f"pyautogui.moveTo({abs_x}, {abs_y})"
            else: # dragTo
                button = kwargs.get("button", "left")
                return f'pyautogui.dragTo({abs_x}, {abs_y}, button="{button}")'
        
        # --- Keyboard Actions ---
        if func == "press":
            keys = kwargs.get("keys", [])
            presses = int(kwargs.get("presses", 1))
            if isinstance(keys, str): keys = [keys] # Ensure keys is a list
            
            commands = [f"pyautogui.press('{key}')" for key in keys for _ in range(presses)]
            return "; ".join(commands)

        if func == "hotkey":
            # 兼容 args 和 keys
            keys = kwargs.get("keys", kwargs.get("args", []))
            key_str = ", ".join([f'"{k}"' for k in keys])
            return f"pyautogui.hotkey({key_str})"

        if func == "keyDown" or func == "keyUp":
            key = kwargs.get("key")
            return f'pyautogui.{func}("{key}")'

        if func == "write":
            msg = kwargs.get("message", kwargs.get("msg", ""))
            # Escape double quotes in the message to prevent breaking the command string
            escaped_msg = msg.replace('"', '\\"')
            return f'pyautogui.write("{escaped_msg}")'

        # --- Control Flow ---
        if func == "wait":
            seconds = kwargs.get("seconds", 1)
            return f"time.sleep({seconds})"

        if func == "terminate":
            return "DONE"
        
        # --- Fallback for unhandled actions ---
        return f"# Unhandled action: {func}({kwargs})"