import os
import json
import re
from mm_agents.navi.gpt.phi3_azure import Phi3VisionAzure
from mm_agents.navi.gpt import system_messages, planner_messages
import ssl


class Phi3_Planner:
    def __init__(
        self,
        server="azure",
        model="phi3-v",
        temperature=1.0,
        api_key=None,
        endpoint_url=None,
    ):

        if api_key is None:
            api_key = os.getenv("AZURE_API_KEY")
        if endpoint_url is None:
            endpoint_url = os.getenv("AZURE_ENDPOINT")

        self.server = server
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.endpoint_url = endpoint_url

        if self.server != "azure":
            raise ValueError(f"Server {server} not supported")

        self.phi3v = Phi3VisionAzure(azure_key_path=None, endpoint=self.endpoint_url)
        self.system_prompt = planner_messages.planning_system_message

    def plan(self, images, user_query):
        if len(images) > 3:

            response0 = self.phi3v.process_images(
                self.system_prompt,
                "This is the first image of two images, please remeber this, this image will be ref later on"
                + user_query,
                images[0],
                max_tokens=4096,
                temperature=self.temperature,
            )
            response = self.phi3v.process_images(
                "the last iamge are " + response0 + self.system_prompt,
                user_query,
                images[1],
                max_tokens=4096,
                temperature=self.temperature,
            )
        else:
            response = self.phi3v.process_images(
                self.system_prompt,
                user_query,
                images[-1],
                max_tokens=4096,
                temperature=self.temperature,
            )
        return response

    def describe_elements(self, screenshot, crops, descriptions=None) -> str:
        n = len(crops)
        system_prompt = f"you will be presented with crops of interactive element in the screen and a screenshot marked with red bounding-boxes. Your task is to describe each element and infer its function. A single crop may contain multiple elements, if so, describe them all in a single paragraph. You must provide one description for each of the {n} elements provided."

        user_query = f"Given the element and screenshot. what could be the purpose of these {n} elements? The last image is the screenshot with the elements marked with red bounding boxes."

        r = self.phi3v.process_images(
            system_prompt,
            user_query,
            crops + [screenshot],
            max_tokens=4096,
            temperature=0.0,
        )

        structuring_prompt = "Given descriptions of the elements/images, format into a json with the element index as key and values as summarized descriptions. if a single description references to multiple elements, break it down into the appropriate items. Make sure to remove from the descriptions any references to the element index. e.g input \n'Here's a description of the elements\n 1. The first icon looks like a bell indicating... \n2. The second and third elements represent a magnifying glass...\n3. it appears to be a ball' output: ```json\n{'1':'A bell indicating...', '2':'A magnifying glass...','3':'A magnifying glass...', '4':'ball' ...}```."
        user_query = (
            f"Structure the following text into a json with descriptions of the {n} elements/images. \n'"
            + r
            + "\n'"
        )
        formatted = self.phi3v.process_images(
            structuring_prompt, user_query, [], max_tokens=4096, temperature=0.0
        )
        try:
            formatted = re.search(r"```json\n(.*)```", formatted, re.DOTALL).group(1)
            result = json.loads(formatted)
        except Exception as e:
            print(f"{formatted}\n\n\nFailed to extract json from response: {e}")
            result = {}
        return result


def allowSelfSignedHttps(allowed):
    if (
        allowed
        and not os.environ.get("PYTHONHTTPSVERIFY", "")
        and getattr(ssl, "_create_unverified_context", None)
    ):
        ssl._create_default_https_context = ssl._create_unverified_context
