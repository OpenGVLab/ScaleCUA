import os
import inspect
import re
from mm_agents.navi.gpt import (
    gpt4v_azure,
    gpt4v_oai,
    claude4v_oai,
    system_messages,
    planner_messages,
)
from mm_agents.navi.prompts import SYS_PROMPT_IN_SCREENSHOT_OUT_CODE
import tiktoken
import time
import json
import re


class GPT4V_Planner:
    def __init__(self, server="azure", model="gpt-4o", temperature=1.0):
        self.server = server
        self.model = model
        self.temperature = temperature

        if self.server == "azure":
            self.gpt4v = gpt4v_azure.GPT4VisionAzure()
        elif self.server == "oai":
            if model.startswith("claude"):
                self.gpt4v = claude4v_oai.ClaudeVisionOAI(self.model)
            else:
                self.gpt4v = gpt4v_oai.GPT4VisionOAI(self.model)
        else:
            raise ValueError(f"Server {server} not supported")

        # set the initial system message
        # self.system_prompt =  planner_messages.planning_system_message
        self.system_prompt = SYS_PROMPT_IN_SCREENSHOT_OUT_CODE

    def plan(self, images, user_query):
        response = self.gpt4v.process_images(
            self.system_prompt,
            user_query,
            images,
            max_tokens=4096,
            temperature=self.temperature,
            only_text=True,
        )
        return response

    def describe_elements(self, screenshot, crops, descriptions=None) -> str:
        n = len(crops)
        system_prompt = f"you will be presented with crops of interactive element in the screen and a screenshot marked with red bounding-boxes. Your task is to describe each element and infer its function. A single crop may contain multiple elements, if so, describe them all in a single paragraph. You must provide one description for each of the {n} elements provided."

        user_query = f"Given the element and screenshot. what could be the purpose of these {n} elements? The last image is the screenshot with the elements marked with red bounding boxes."

        print(system_prompt)
        print(user_query)

        r = self.gpt4v.process_images(
            system_prompt,
            user_query,
            crops + [screenshot],
            max_tokens=4096,
            temperature=0.0,
            only_text=True,
        )

        # display(Image.open(screenshot_tagged))
        print(r)

        structuring_prompt = "Given descriptions of the elements/images, format into a json with the element index as key and values as summarized descriptions. if a single description references to multiple elements, break it down into the appropriate items. Make sure to remove from the descriptons any references to the element index. e.g input \n'Here's a description of the elements\n 1. The first icon looks liek a bell indicating... \n2. The second and third elements represent a magnifying glass...\n3. it appears to be a ball' output: ```json\n{'1':'A bell indicating...', '2':'A magnifying glass...','3':'A magnifying glass...', '4':'ball' ...}```."
        user_query = (
            f"Structure the following text into a json with descriprions of the {n} elements/images. \n'"
            + r
            + "\n'"
        )
        formatted = self.gpt4v.process_images(
            structuring_prompt,
            user_query,
            [],
            max_tokens=4096,
            temperature=0.0,
            only_text=True,
        )
        print(formatted)
        try:
            # extract code block
            formatted = re.search(r"```json\n(.*)```", formatted, re.DOTALL).group(1)
            result = json.loads(formatted)
        except Exception as e:
            print(f"{formatted}\n\n\nFailed to extract json from response: {e}")
            result = {}
        print(result)
        return result
