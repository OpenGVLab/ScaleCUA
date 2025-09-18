import json
import logging
import os
from typing import Dict, List, Optional, Tuple
from utils.common_utils import call_llm_safe
from core.module import BaseModule
from agents.ui_grounding import UIGroundingAgent
import re

logger = logging.getLogger("desktopenv.agent")
working_dir = os.path.dirname(os.path.abspath(__file__))



class AgenticWorkflow(BaseModule):
    """Agent that uses different planning and grounding models for UI automation"""

    def __init__(
        self,
        planner_engine_params: Dict,
        grounder_engine_params: Dict,
        platform: str = "macos",
        observation_type: str = "vision",
    ):
        """
        Args:
            planner_engine_params: Configuration parameters for the planning model engine
            grounder_engine_params: Configuration parameters for the grounding model engine
            platform: Platform type (e.g., macos, ubuntu)
            observation_type: Type of observation (e.g., vision)
        """
        self.engine_params = planner_engine_params
        self.grounder_engine_params = grounder_engine_params
        self.platform = platform
        self.observation_type = observation_type

        with open(planner_engine_params['prompt_template'], "r") as f:
            self.planner_prompt_template = json.load(f)

        with open(grounder_engine_params['prompt_template'], "r") as f:
            self.grounder_prompt_template = json.load(f)

        self.planner = self._create_vlm_api(self.planner_prompt_template['sys_prompt_planning_cot'])
        self.grounder= UIGroundingAgent(self.grounder_engine_params)

        self.reset()

    def reset(self) -> None:
        self.step_count: int = 0
        self.turn_count: int = 0
        self.planner.reset()
        self.grounder.reset()

        self.planner_history = []

    def predict(self, instruction: str, observation: Dict, env) -> Tuple[Dict, List[str]]:
        if self.step_count == 0:
            for msg in self.planner.messages:
                if msg["role"] == "system":
                    msg["content"][0]["text"] = msg["content"][0]["text"].format(task_instruction = instruction)
                    break
        
        self.planner.add_message(
            text_content= self.format_history(),
            image_content=observation["screenshot"],
            role='user',
            put_text_last=True,
        )
        
        response = call_llm_safe(self.planner)
        logger.info(f"RAW Response: {response}")

        thought, low_level_instruction, action = self.parse_response(response)
        logger.info(
            f"Thoughts: {thought}\nLow-level instructions: {low_level_instruction}\nActions: {action}",
        )
        corrds = self.grounder.generate_coords(low_level_instruction, observation)
        action = self.parse_action(action, corrds)
        info, actions = {
            "thought": thought,
            "step_instruction": low_level_instruction,
            "action": action
        }, [action]
        self.step_count += 1
        return info, actions


    def parse_response(self, output: str) -> Tuple[str, str, str]:
        """
        Parses the model's output to extract the instruction and action.
        Returns (instruction, action) or raises an error if invalid.
        """
        # Extract code block if wrapped in markdown
        code_block_match = re.search(r'```python(.*?)```', output, re.DOTALL)
        if code_block_match:
            code_content = code_block_match.group(1).strip()
        else:
            code_content = output.strip()

        lines = [line.strip() for line in code_content.split('\n') if line.strip()]
        
        if len(lines) != 2:
            raise ValueError("Output must contain exactly 2 lines (instruction + action).")
        
        instruction_line, action_line = lines
        
        # Validate instruction line starts with #
        if not instruction_line.startswith("#"):
            raise ValueError("First line must be an instruction (starting with #).")
        
        instruction = instruction_line[1:].strip()
        return None, instruction, action_line.strip()
    
    def parse_action(self, action_line, coord):
        """
        Parses an action line (e.g., 'click(x=100, y=200)') into:
        - action_type (str): The function name (e.g., 'click').
        - params (dict): A dictionary of parameter names and values.
        """
        # Extract function name and arguments
        match = re.match(r'^(\w+)\((.*)\)$', action_line.strip())
        if not match:
            raise ValueError(f"Invalid action format: '{action_line}'")

        action_type = match.group(1)
        args_str = match.group(2)

        # Parse parameters
        params = {}
        if args_str:
            # Split into key=value pairs, handling commas and optional spaces
            arg_pairs = [p.strip() for p in args_str.split(',') if p.strip()]
            for pair in arg_pairs:
                if '=' not in pair:
                    raise ValueError(f"Parameter '{pair}' must be in key=value format.")
                key, value = pair.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Convert numeric values (int or float)
                if value.replace('.', '', 1).isdigit():  # Check if numeric
                    value = float(value) if '.' in value else int(value)
                elif value.startswith(('"', "'")) and value.endswith(('"', "'")):
                    value = value[1:-1]  # Remove quotes from strings
                elif value in ('None', 'True', 'False'):
                    value = eval(value)  # Convert Python literals (careful with security!)
                params[key] = value
        if 'x' in params or 'y' in params:
            params['x'], params['y'] = coord[0],coord[1]
    
        return {
            "name": action_type,
            "parameters": params
        }
    
    def format_history(self, observation = None, instruction = None):
        user_prompt = self.planner_prompt_template['user_prompt_planning']
        return user_prompt
    