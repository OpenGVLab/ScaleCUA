import re
from abc import ABC, abstractmethod
import timeout_decorator
from core.mllm import VLMEngine
from utils.common_utils import call_llm_safe
import json
import ast
from typing import List
from agents.utils import parse_point_from_string
from agents.utils import smart_resize, encoded_img_to_pil_img
class Base(ABC):
    """
    Base class for all environments.
    """

    def __init__(self, engine_params, **kwargs):
        self.engine_params = engine_params

    @timeout_decorator.timeout(10)
    @abstractmethod
    def generate_coords(self, ref_expr: str, obs: dict) -> list[int]:
        pass
    
class UIGroundingAgent(Base):
    """
    Grounding agent using LLM.
    """
    
    def __init__(self, engine_params):
        print(engine_params)
        
        self.sys_prompt = None
        self.user_prompt = "Query:{ref_expr}\nOutput only the coordinate of one point in your response.\n"
       
        self.prompt_template_dict = json.load(
            open(engine_params.pop("prompt_template"), 'r')
            )
        self.resize_corrds = engine_params.pop("resize_corrds", True)


        if "sys_prompt_grounding" in self.prompt_template_dict:
            self.grounding_model = VLMEngine(engine_params, self.prompt_template_dict["sys_prompt_grounding"])
        else:
            self.grounding_model = VLMEngine(engine_params)
        
        self.user_prompt = self.prompt_template_dict["user_prompt_grounding"]
            
    def reset(self):
        self.grounding_model.reset()

    def generate_coords(self, ref_expr: str, obs: dict) -> list[int]:
        """
        Generate coordinates for the reference expression.
        """
        self.reset()
        
    
        prompt = self.user_prompt.format(ref_expr=ref_expr)
        self.grounding_model.add_message(
            text_content=prompt, image_content=obs["screenshot"], put_text_last=True
        )

        # Generate and parse coordinates
        # import pdb;pdb.set_trace()
        response = call_llm_safe(self.grounding_model)
        numericals = parse_point_from_string(response)
        assert len(numericals) >= 2
        numericals = self.resize_coordinates(numericals, obs)
        return numericals
    
    
    # Resize from grounding model dim into OSWorld dim (1920 * 1080)
    def resize_coordinates(self, coordinates: List[int], observation: dict) -> List[int]:
        # User explicitly passes the grounding model dimensions
        if self.resize_corrds:
            image = encoded_img_to_pil_img(observation["screenshot"])
            width, height = image.size
            grounding_height, grounding_width = smart_resize(height, width)
        else:

            if {"grounding_width", "grounding_height"}.issubset(
                self.engine_params
            ):
                grounding_width = self.engine_params["grounding_width"]
                grounding_height = self.engine_params["grounding_height"]
            else:
                grounding_width = 1000
                grounding_height = 1000

        return [
            coordinates[0] / grounding_width,
            coordinates[1] / grounding_height,
        ]