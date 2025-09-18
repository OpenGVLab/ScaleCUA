import logging
import json
from agents.ui_agent import UIAgent
from typing import List
from utils.misc import smart_resize, encoded_img_to_pil_img, parse_point_from_string, call_llm_safe

logger = logging.getLogger("desktopenv.agent")

class OpenCUAGrounder(UIAgent):
    """
    Grounding agent using LLM.
    """
    def __init__(self, 
                 engine_params,
                 platform):
        super().__init__(engine_params=engine_params, platform=platform)

        with open(self.engine_params["prompt_template"], "r", encoding="utf-8") as f:
            self.prompt_template = json.load(f)
        
        self.smart_resize = engine_params.get("smart_resize", True)
        self.max_pixels = self.engine_params.get("max_pixel", 2007040)
        self.min_pixels = self.engine_params.get("min_pixel", 3136)

        self.grounding_coord = engine_params.get("grounding_coord", 1)
        self.grounder = self._create_agent(self.prompt_template["sys_prompt_grounding"], engine_params)
        self.user_prompt = self.prompt_template["user_prompt_grounding"]

    def reset(self):
        self.grounder.reset()

    def generate_coords(self, ref_expr: str, obs: dict) -> list[float]:
        """
        Generate coordinates for the reference expression.
        """
        # Flush user message
        self.reset()

        prompt = self.user_prompt.format(ref_expr=ref_expr)
        self.grounder.add_message(
            text_content=prompt, image_content=obs["screenshot"], put_text_last=True
        )

        # Generate and parse coordinates
        # import pdb;pdb.set_trace()
        response = call_llm_safe(self.grounder)
        numericals = parse_point_from_string(response)
        assert len(numericals) >= 2
        numericals = self.resize_coordinates(numericals, obs)
        return numericals

    def resize_coordinates(self, coordinates: List[int], observation: dict) -> List[float]:
        """
        Resize coordinates to 0-1 scaled coordinates
        """
        # User explicitly passes the grounding model dimensions
        if self.smart_resize:
            image = encoded_img_to_pil_img(observation["screenshot"])
            width, height = image.size
            grounding_height, grounding_width = smart_resize(height, width, min_pixels=self.min_pixels, max_pixels=self.max_pixels)
        else:
            grounding_width = self.grounding_coord
            grounding_height = self.grounding_coord

        return [
            coordinates[0] / grounding_width,
            coordinates[1] / grounding_height,
        ]