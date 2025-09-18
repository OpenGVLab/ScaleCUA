import json
import logging
import re
from typing import Dict, List, Tuple
from agents.ui_agent import UIAgent
from utils.misc import call_llm_safe, smart_resize, IMAGE_FACTOR
import ast

logger = logging.getLogger("desktopenv.agent")

class OpenCUANativeAgent(UIAgent):
    def __init__(self,
                 engine_params: Dict,
                 platform: str = "web",
                 width: int = 1600,
                 height: int = 2560):
        """
        Initialize the Native OpenCUA worker agent.

        Args:
            engine_params: Configuration parameters for the vision-language model
            platform: Target platform (e.g., "web", "desktop")
            width: Screen width for coordinate normalization
            height: Screen height for coordinate normalization
        """
        super().__init__(engine_params=engine_params,
                         platform=platform)

        self.width = width
        self.height = height

        with open(self.engine_params["prompt_template"], "r", encoding="utf-8") as f:
            self.prompt_template = json.load(f)

        self.user_instruction_template = self.prompt_template["user_prompt_planning"]
        if self.engine_params["enable_thinking"]:
            self.sys_prompt = self.prompt_template["sys_prompt_planning_cot"]
        else:
            self.sys_prompt = self.prompt_template["sys_prompt_planning_withoutcot"]

        self.grounding_coord = self.engine_params.get("grounding_coord", 1)
        self.smart_resize = self.engine_params.get("smart_resize", False)
        self.max_pixels = self.engine_params.get("max_pixel", 2007040)
        self.min_pixels = self.engine_params.get("min_pixel", 3136)

        self.messages = None
        self.native_agent = None
        self.previous_operations_list = None
        self.reset()

    def reset(self):
        """
        Reset the agent's state to prepare for a new conversation.
        """
        self.messages = [
            {
                "role": "system",
                "content": self.sys_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "waiting to fill",
                            "detail": "high"
                        }
                    },
                    {
                        "type": "text",
                        "text": "waiting to fill"
                    }
                ],
            }
        ]
        self.native_agent = self._create_agent("")
        self.previous_operations_list = []

    def parse_plan(self, plan: str) -> tuple[str, str, str]:
        """
        Parse the plan string to extract thinking, operation and action parts using regex.

        Args:
            plan: A string containing structured sections in specified format.

        Returns:
            A tuple of (thought, operation, action) strings.
        """
        # Extract thinking section
        think_pattern = r'<think>(.*?)</think>'
        think_match = re.search(think_pattern, plan, re.DOTALL)
        thought = think_match.group(1).strip() if think_match else ""

        # Extract operation section
        operation_pattern = r'<operation>(.*?)</operation>'
        operation_match = re.search(operation_pattern, plan, re.DOTALL)
        operation = operation_match.group(1).strip() if operation_match else ""

        # Extract action section
        action_pattern = r'<operation>.*?</operation>.*?<action>(.*?)</action>'
        action_match = re.search(action_pattern, plan, re.DOTALL)
        action = action_match.group(1).strip() if action_match else ""

        return thought, operation, action

    def parse_exec_action_list(self, action):
        """
        Parse multiple action calls that may contain multiple commands.

        Args:
            action: String containing one or more action function calls

        Returns:
            List of parsed action dictionaries
        """
        lines = action.strip().split("\n")
        cleaned_lines = []
        exec_action = []
        for line in lines:
            # Skip empty lines, comments, function definitions, etc.
            if (not line.strip() or
                    line.strip().startswith('#') or
                    line.strip().startswith('def ') or
                    line.strip().startswith('"""') or
                    line.strip().startswith("'''") or
                    line.strip() == 'pass'):
                continue
            cleaned_lines.append(line.strip())

        for line in cleaned_lines:
            exec_action.append(self.parse_exec_action(line))
        if len(exec_action) > 0:
            return exec_action
        else:
            return [{
                "name": "wait",
                "parameters": {
                    "seconds": 3
                }
            }]

    def parse_exec_action(self, action):
        """
        Parse a single action call to extract method name and parameters.

        Args:
            action: String representing a function call

        Returns:
            Dictionary containing parsed method name and parameters
        """
        # Initialize result variables
        args = []
        kwargs = {}

        # Auto-complete missing closing parenthesis
        if action[-1] != ")":
            action += ")"

        # Parse using AST
        try:
            tree = ast.parse(action.strip(), mode='eval')

            # Ensure it's a function call
            if not isinstance(tree.body, ast.Call):
                raise ValueError("Invalid call format. Must represent a function call.")

            # Extract method name
            method_name = tree.body.func.id

            # Extract positional and keyword arguments
            args, kwargs = [], {}

            # Process positional arguments (for hotkey)
            for arg in tree.body.args:
                try:
                    args.append(ast.literal_eval(arg))
                except (ValueError, SyntaxError):
                    raise ValueError(f"Unable to parse argument: {arg}")

            # Process keyword arguments
            for kw in tree.body.keywords:
                try:
                    kwargs[kw.arg] = ast.literal_eval(kw.value)
                except (ValueError, SyntaxError):
                    raise ValueError(f"Unable to parse keyword argument: {kw}")

        except (SyntaxError, ValueError):
            # Fallback to regex parsing if AST fails
            func_match = re.match(r'(\w+)\((.*)\)$', action.strip())
            if not func_match:
                raise ValueError(f"Invalid function call format: {action}")

            method_name = func_match.group(1)
            params_str = func_match.group(2)

            # Special handling for write function
            if method_name == "write":
                write_match = re.match(r'message=[\'\"](.+)[\'\"]', params_str)
                if write_match:
                    message = write_match.group(1)
                    kwargs = {"message": message}

            # Special handling for response function
            elif method_name == "response":
                response_match = re.match(r'answer=[\'\"](.+)[\'\"]', params_str)
                if response_match:
                    answer = response_match.group(1)
                    kwargs = {"answer": answer}
            else:
                # For unsupported functions, raise an exception
                raise ValueError(f"Unable to parse function call: {action}")

        # Apply smart resize if enabled
        if self.smart_resize:
            smart_resize_height, smart_resize_width = smart_resize(self.height, self.width, factor=IMAGE_FACTOR,
                                                                   min_pixels=self.min_pixels,
                                                                   max_pixels=self.max_pixels)
            # Adjust coordinates to 0-1 scale
            kwargs['x'] = kwargs.get("x") / smart_resize_width if kwargs.get("x") is not None else None
            kwargs['y'] = kwargs.get("y") / smart_resize_height if kwargs.get("y") is not None else None
            kwargs['from_coord'] = (kwargs.get("from_coord")[0] / smart_resize_width,
                                    kwargs.get("from_coord")[1] / smart_resize_height) if kwargs.get(
                "from_coord") is not None and isinstance(kwargs.get("from_coord"), list) else None
            kwargs['to_coord'] = (kwargs.get("to_coord")[0] / smart_resize_width,
                                  kwargs.get("to_coord")[1] / smart_resize_height) if kwargs.get(
                "to_coord") is not None and isinstance(kwargs.get("to_coord"), list) else None

        # Convert to standardized action format based on method name
        if method_name == "click":
            return {
                "name": "click",
                "parameters": {
                    "x": kwargs.get("x") * self.width if kwargs.get("x") is not None else None,
                    "y": kwargs.get("y") * self.height if kwargs.get("y") is not None else None,
                    "clicks": kwargs.get("clicks", 1),
                    "button": kwargs.get("button", "left")
                }
            }

        elif method_name == "doubleClick":
            return {
                "name": "click",
                "parameters": {
                    "x": kwargs.get("x") * self.width if kwargs.get("x") is not None else None,
                    "y": kwargs.get("y") * self.height if kwargs.get("y") is not None else None,
                    "clicks": 2,
                    "button": kwargs.get("button", "left")
                }
            }

        elif method_name == "rightClick":
            return {
                "name": "click",
                "parameters": {
                    "x": kwargs.get("x") * self.width if kwargs.get("x") is not None else None,
                    "y": kwargs.get("y") * self.height if kwargs.get("y") is not None else None,
                    "clicks": 1,
                    "button": "right"
                }
            }

        elif method_name == "moveTo":
            return {
                "name": "moveTo",
                "parameters": {
                    "x": kwargs.get("x") * self.width if kwargs.get("x") is not None else None,
                    "y": kwargs.get("y") * self.height if kwargs.get("y") is not None else None,
                }
            }

        elif method_name == "dragTo":
            return {
                "name": "dragTo",
                "parameters": {
                    "x": kwargs.get("x") * self.width if kwargs.get("x") is not None else None,
                    "y": kwargs.get("y") * self.height if kwargs.get("y") is not None else None,
                    "button": kwargs.get("button", "left")
                }
            }

        elif method_name == "swipe":
            return {
                "name": "swipe",
                "parameters": {
                    "from_coord": (kwargs.get("from_coord")[0] * self.width,
                                   kwargs.get("from_coord")[1] * self.height)
                    if kwargs.get("from_coord") is not None and isinstance(kwargs.get("from_coord"), list) else (
                    None, None),
                    "to_coord": (kwargs.get("to_coord")[0] * self.width,
                                 kwargs.get("to_coord")[1] * self.height)
                    if kwargs.get("to_coord") is not None and isinstance(kwargs.get("to_coord"), list) else (
                    None, None),
                    "direction": kwargs.get("direction", "up"),
                    "amount": kwargs.get("amount", 0.5)
                }
            }

        elif method_name == "write":
            return {
                "name": "write",
                "parameters": {
                    "message": kwargs.get("message", "")
                }
            }

        elif method_name == "press":
            return {
                "name": "press",
                "parameters": {
                    "keys": kwargs.get("keys", None)
                }
            }

        elif method_name == "hotkey":
            return {
                "name": "hotkey",
                "parameters": {
                    "args": args if len(args) > 0 else []
                }
            }

        elif method_name == "callUser":
            return {
                "name": "callUser",
                "parameters": {}
            }

        elif method_name == "wait":
            return {
                "name": "wait",
                "parameters": {
                    "seconds": kwargs.get("seconds", 3)
                }
            }

        elif method_name == "response":
            return {
                "name": "response",
                "parameters": {
                    "answer": kwargs.get("answer", "")
                }
            }
        elif method_name == "terminate":
            return {
                "name": "terminate",
                "parameters": {
                    "status": kwargs.get("status", "success"),
                    "info": kwargs.get("info", "")
                }
            }

        else:
            return {
                "name": "wait",
                "parameters": {
                    "seconds": 1
                }
            }

    def generate_next_action(
            self,
            instruction: str,
            obs: Dict
    ) -> Tuple[Dict, List]:
        """
        Generate the next action based on the current observation and instruction.

        Args:
            instruction: User's task instruction
            obs: Current observation from the environment

        Returns:
            Tuple containing execution info and action list
        """
        # Build history of previous operations (limited to last 15)
        previous_operations = ""
        for i, operation in enumerate(self.previous_operations_list[-15:]):
            previous_operations += f"Step {i + 1}: {operation}\n"

        # Format user prompt
        user_prompt = self.user_instruction_template.format(
            instruction=instruction,
            actions=previous_operations
        )

        self.messages[1]["content"][1]["text"] = user_prompt

        # Encode screenshot
        image_content = obs["screenshot"]
        base64_image = self.native_agent.encode_image(image_content)
        self.messages[1]["content"][0]["image_url"]["url"] = f"data:image/png;base64,{base64_image}"

        # Send message to language model
        self.native_agent.replace_messages(self.messages)
        plan = call_llm_safe(self.native_agent)
        print(plan)

        # Parse response according to expected format:
        # <think>[reasoning]</think>
        # <operation>[operation description]</operation>
        # <action>[executable commands]</action>
        thought, operation, actions = self.parse_plan(plan)
        self.previous_operations_list.append(operation)

        # Parse action code into executable actions
        try:
            exec_actions = self.parse_exec_action_list(actions)

        except Exception as e:
            logger.error("Error in parsing plan code: %s", e)
            exec_actions = [{
                "name": "wait",
                "parameters": {
                    "seconds": 1
                }
            }]

        # Prepare execution info
        exec_info = {
            "thought": thought,
            "operation": operation,
            "actions": actions
        }

        return exec_info, exec_actions

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """
        Main prediction method called by external code.

        Args:
            instruction: User's task instruction
            observation: Current observation from environment

        Returns:
            Tuple containing execution info and action list
        """
        exec_info, exec_action = self.generate_next_action(instruction, observation)
        return exec_info, exec_action
