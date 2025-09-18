import json
import logging
import re
from typing import Dict, List, Tuple
from utils.misc import call_llm_safe
from agents.ui_agent import UIAgent
from agents.agentic_workflow.scalecua_grounder import OpenCUAGrounder

logger = logging.getLogger("desktopenv.agent")


class OpenCUAAgenticWorkflow(UIAgent):
    """Agent that uses hierarchical planning and directed acyclic graph modeling for UI automation"""

    def __init__(
        self,
        planner_engine_params: Dict,
        grounder_engine_params: Dict,
        platform: str = "web",
    ):
        super().__init__(engine_params={}, platform=platform)

        self.planner_engine_params = planner_engine_params
        self.grounder_engine_params = grounder_engine_params

        with open(planner_engine_params["prompt_template"], "r") as f:
            self.planner_prompt_template = json.load(f)

        with open(grounder_engine_params["prompt_template"], "r") as f:
            self.grounder_prompt_template = json.load(f)

        self.step_count = 0
        self.turn_count = 0

        # Create Planner
        self.planner = self._create_agent(
            self.planner_prompt_template["sys_prompt_planning_cot"],
            self.planner_engine_params,
        )
        self.grounder = OpenCUAGrounder(self.grounder_engine_params, self.platform)

        self.reset()

    def reset(self) -> None:
        """Reset the agent state by clearing step count, turn count and resetting planner and grounder"""
        self.step_count: int = 0
        self.turn_count: int = 0
        self.planner.reset()
        self.grounder.reset()

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """
        Generate UI actions based on instruction and observation

        Args:
            instruction: Task instruction from user
            observation: Dictionary containing UI state with screenshot

        Returns:
            Tuple of info dictionary and list of actions
        """
        # Set up planner with task instruction on first step
        if self.step_count == 0:
            for msg in self.planner.messages:
                if msg["role"] == "system":
                    msg["content"][0]["text"] = msg["content"][0]["text"].format(
                        task_instruction=instruction
                    )
                    break

        # Add current UI state to planner
        self.planner.add_message(
            text_content=self.format_history(),
            image_content=observation["screenshot"],
            role="user",
            put_text_last=True,
        )

        response = call_llm_safe(self.planner)
        logger.info(f"RAW Response: {response}")
        thought, operation, action = self.parse_response(response)
        logger.info(
            f"Thoughts: {thought}\nLow-level instructions: {operation}\nActions: {action}",
        )

        # Generate concrete coordinates from high-level operation
        coords = self.grounder.generate_coords(operation, observation)
        action = self.parse_action(action, coords)
        info, actions = {
            "thought": thought,
            "operation": operation,
            "actions": [action],
        }, [action]
        self.step_count += 1
        return info, actions

    def parse_response(self, output: str) -> Tuple[str, str, str]:
        """
        Parses the model's output to extract thought, operation and action.

        Args:
            output: Raw response string from planner

        Returns:
            Tuple of (thought, operation, action)

        Raises:
            ValueError: If output format is invalid
        """
        # Extract code block if wrapped in markdown
        code_block_match = re.search(r"```python(.*?)```", output, re.DOTALL)
        if code_block_match:
            code_content = code_block_match.group(1).strip()
        else:
            code_content = output.strip()

        lines = [line.strip() for line in code_content.split("\n") if line.strip()]

        if len(lines) != 2:
            raise ValueError(
                "Output must contain exactly 2 lines (instruction + action)."
            )

        instruction_line, action_line = lines

        # Validate instruction line starts with #
        if not instruction_line.startswith("#"):
            raise ValueError("First line must be an instruction (starting with #).")

        instruction = instruction_line[1:].strip()
        return "", instruction, action_line.strip()

    def parse_action(self, action_line, coord):
        """
        Parses an action line and replaces coordinates if needed

        For click and double-click actions, replaces x,y coordinates with those
        provided by the grounder. For hotkey actions, organizes parameters as args list.

        Args:
            action_line: Action string (e.g., 'click(x=100, y=200)' or 'hotkey(key1, key2)')
            coord: Coordinates tuple (x, y) from grounder

        Returns:
            Dict with action name and parameters

        Raises:
            ValueError: If action format is invalid
        """
        # Extract function name and arguments
        match = re.match(r"^(\w+)\((.*)\)$", action_line.strip())
        if not match:
            raise ValueError(f"Invalid action format: '{action_line}'")

        action_type = match.group(1)
        args_str = match.group(2).strip()

        # Handle hotkey with positional arguments
        if action_type == "hotkey":
            # 简单地用逗号分割参数
            args = [arg.strip() for arg in args_str.split(",") if arg.strip()]
            # 去掉可能存在的引号
            args = [
                (
                    arg[1:-1]
                    if (arg.startswith('"') and arg.endswith('"'))
                    or (arg.startswith("'") and arg.endswith("'"))
                    else arg
                )
                for arg in args
            ]

            return {"name": action_type, "parameters": {"args": args}}

        # 处理普通的key=value参数
        params = {}
        if args_str:
            # 简单地按逗号分割
            arg_pairs = [p.strip() for p in args_str.split(",") if p.strip()]

            for pair in arg_pairs:
                if "=" not in pair:
                    raise ValueError(f"Parameter '{pair}' must be in key=value format.")

                key, value = pair.split("=", 1)
                key = key.strip()
                value = value.strip()

                # 简单的值类型转换
                try:
                    # 尝试处理列表
                    if value.startswith("[") and value.endswith("]"):
                        value = eval(value)  # 使用eval解析列表
                    # 处理引号包围的字符串
                    elif (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    # 处理数字
                    elif value.replace(".", "", 1).isdigit():
                        value = float(value) if "." in value else int(value)
                    # 处理布尔值和None
                    elif value in ("None", "True", "False"):
                        value = eval(value)
                except:
                    # 如果转换失败，保持原样
                    pass

                params[key] = value

        # 替换坐标（如果需要）
        if "x" in params and "y" in params:
            params["x"], params["y"] = coord[0], coord[1]

        return {"name": action_type, "parameters": params}

    def format_history(self, observation=None, instruction=None):
        """Format history for planner prompt"""
        user_prompt = self.planner_prompt_template["user_prompt_planning"]
        return user_prompt
