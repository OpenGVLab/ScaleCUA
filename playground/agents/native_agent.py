import json
import logging
import os
import shutil
from typing import Dict, List, Optional, Tuple
import re
import logging

from utils.common_utils import Node
from core.module import BaseModule
from agents.utils import smart_resize, encoded_img_to_pil_img
from utils.common_utils import call_llm_safe
logger = logging.getLogger("native-agent")
working_dir = os.path.dirname(os.path.abspath(__file__))

class NativeAgent(BaseModule):
    """Agent for UI automation"""

    def __init__(
        self,
        engine_params: Dict,
        grounding_width,
        grounding_height,
        prompt_template: str = None,
        platform: str = "macos",
        observation_type: str = "vision",
        resize_corrds: Optional[bool] = True,
    ):
        """Initialize SingleAgent

        Args:
            engine_params: Configuration parameters for the model engine
            grounding_width: Width of the grounding box
            grounding_height: Height of the grounding box
            prompt_template: Path to the prompt template file
            platform: Platform type (e.g., macos, ubuntu)
            observation_type: Type of observation (e.g., vision)        
        """
        self.engine_params = engine_params
        self.platform = platform
        self.observation_type = observation_type

        if prompt_template is not None:
            with open(prompt_template, "r") as f:
                self.prompt_template = json.load(f)
        if engine_params['enable_thinking']:
            self.planner = self._create_vlm_api(self.prompt_template['sys_prompt_planning_cot'], self.engine_params)
        else:
            self.planner = self._create_vlm_api(self.prompt_template['sys_prompt_planning_withoutcot'], self.engine_params)
        self.user_instruction = self.prompt_template['user_prompt_planning']
        self.history = []
        self.grounding_width = grounding_width
        self.grounding_height = grounding_height
        self.resize_corrds = resize_corrds


    def reset(self) -> None:
        """Reset agent state and initialize components"""

        # Reset state variables
        self.history = []
        self.planner.reset()

    def predict(self, instruction: str, observation: Dict, env = None) -> Tuple[Dict, List[str]]:
        if len(self.planner.messages) > 1:
            self.planner.messages = [self.planner.messages[0]]
        self.planner.add_message(
            text_content= self.format_history(instruction, self.history),
            image_content=observation["screenshot"],
            role='user'
        )
        
        response = call_llm_safe(self.planner)
        logger.info(f"RAW Response: {response}")
        thought, low_level_instruction, actions = self.parse_response(response)
        logger.info(
            f"Thoughts: {thought}\nLow-level instructions: {low_level_instruction}\nActions: {actions}",
        )
        self.history.append(low_level_instruction)
        actions = self.parse_action(actions)
        if self.resize_corrds:
            image = encoded_img_to_pil_img(observation["screenshot"])
            width, height = image.size
            grounding_height, grounding_width = smart_resize(height, width)
        else:
            grounding_height, grounding_width = self.grounding_height, self.grounding_width
        for i, action in enumerate(actions):
            for key, value in action['parameters'].items():
                if key in ["x", "y"]:
                    if key == 'x': actions[i]["parameters"]["x"] /= grounding_width
                    else: actions[i]["parameters"]["y"] /= grounding_height

        # Return agent info and actions
        return {"agent_info": thought}, actions



    def parse_response(self, response: str) -> Dict:
        action_matches = re.findall(r'<action>\s*(.*?)\s*</action>', response, re.DOTALL)
        actions = []
        if action_matches:
            for match in action_matches:
                # Split each match by newline and strip whitespace from each line
                lines = [line.strip() for line in match.split('\n') if line.strip()]
                actions.extend(lines)
                
        operation_match = re.search(r'<operation>\s*(.*?)\s*</operation>', response, re.DOTALL)
        operation = operation_match.group(1).strip() if operation_match else None
    
        think_match = re.search(r'<think>\s*(.*?)\s*</think>', response, re.DOTALL)
        think = think_match.group(1).strip() if think_match else None
        
        return (think, operation, actions)
    


    def format_history(self, instruction, history):
        if len(history) > 0:
            actions_history = [f"Step {i+1}: {low_level}" for i, low_level in enumerate(history)]
        else:
            actions_history = None
        return self.user_instruction.format(
            instruction=instruction,
            actions= "\n".join(actions_history) if actions_history is not None else None
        )
    

    
    def parse_action(self, actions):
        parsed_action = []
        for action in actions:
            match = re.match(r"(\w+)\((.*)\)", action)
            if not match:
                return None

            func_name = match.group(1)
            args_str = match.group(2)
            args = {}
            if "=" in args_str:
                for arg in re.finditer(r"(\w+)=\[([^\]]+)\]", args_str):
                    param = arg.group(1)
                    list_str = arg.group(2)
                    
                    list_items = []
                    for item in re.finditer(r"'([^']*)'|\"([^\"]*)\"|([^,\]]+)", list_str):
                        val = (item.group(1) or item.group(2) or item.group(3)).strip()
                        if val:
                            list_items.append(val.strip('"\'')) 
                    
                    args[param] = list_items

                for arg in re.finditer(r"(\w+)=([^,)]+)", args_str):
                    param = arg.group(1)
                    if param in args:
                        continue
                    
                    value_str = arg.group(2).strip()
                    
                    if value_str.isdigit():
                        value = int(value_str)
                    elif value_str.replace(".", "", 1).isdigit():
                        value = float(value_str)
                    elif value_str.lower() in ("true", "false"):
                        value = value_str.lower() == "true"
                    else:
                        value = value_str.strip('"\'')
                    
                    args[param] = value

            else:
                args_list = []
                for arg in re.finditer(r"'([^']*)'|\"([^\"]*)\"|([^,]+)", args_str):
                    val = (arg.group(1) or arg.group(2) or arg.group(3)).strip()
                    if val:
                        args_list.append(val.strip('"\''))  
                
                if args_list:
                    args["args"] = args_list


            parsed_action.append({
                'name': func_name,
                'parameters': args
            })
        return parsed_action


