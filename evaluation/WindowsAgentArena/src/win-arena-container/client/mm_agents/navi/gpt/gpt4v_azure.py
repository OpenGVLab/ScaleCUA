import os
import base64
import requests
from PIL import Image, ImageDraw
import io
from typing import Union, List
import time
from mimetypes import guess_type 
from io import BytesIO  
import inspect

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff

class GPT4VWrapperError(Exception):
    pass


class GPT4VisionAzure:

    def __init__(self, azure_key_path=None, endpoint=None):

        if azure_key_path is None:
            self.api_key = os.getenv("AZURE_API_KEY")
        else:
            with open(azure_key_path, "r") as key_file:
                self.api_key = key_file.read().strip()

        self.headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        if endpoint is None:
            self.endpoint = os.environ.get("AZURE_ENDPOINT")
        else:
            self.endpoint = endpoint
        
    def encode_image(self, image: Union[str, Image.Image], format) -> str:
        if isinstance(image, str):
            with open(image, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        elif isinstance(image, Image.Image):
            image = image.convert("RGB")
            buffer = io.BytesIO()
            if format=="JPEG":
                image.save(buffer, format="JPEG")
            elif format=="PNG":
                image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def get_url_payload(self, url: str) -> dict:
        return {
            "type": "image_url",
            "image_url": {
                "url": url
            }
        }

    def get_base64_payload(self, base64_image: str, format) -> dict:
        if format=="JPEG":
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                }
            }
        elif format=="PNG":
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                }
            }

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(10))
    def process_images(self, system_prompt: str, question: str, images: Union[str, Image.Image, List[Union[str, Image.Image]]], max_tokens=300, temperature=0, only_text=True, format="JPEG") -> str:

        if system_prompt==None:
            system_prompt = "You are a helpful assistant."

        if not isinstance(images, list):
            images = [images]

        content = []

        for image in images:
            if isinstance(image, str) and image.startswith("http"):
                content.append(self.get_url_payload(image))
            else:
                base64_image = self.encode_image(image, format=format)
                content.append(self.get_base64_payload(base64_image, format=format))
        
        content.append({"type": "text", "text": question})

        payload = {
            "messages": [
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
                    "content": content
                }
            ],
            "frequency_penalty": 0.0,
            "max_tokens": max_tokens,
            "n": 1,
            "presence_penalty": 0.0,
            "temperature": temperature,
            "top_p": 1.0,
        }

        # print("Sending request...")
        try:
            response = requests.post(self.endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
        except requests.RequestException as e:
            # raise SystemExit(f"Failed to make the request. Error: {e}")
            raise GPT4VWrapperError(f"Failed to make the request. Error: {e}")

        # return response.json()
        if only_text:
            return response.json()['choices'][0]['message']['content']
        else:
            return response
    

# Main function
def main():

    system_prompt = "You are a helpful assistant."

    # SINGLE RESOURCE
    gpt4v_wrapper = GPT4VisionAzure()

    # process a single image
    start_time = time.time()
    prompt = "What's in this image?"  
    image0 = Image.open("test_fig.jpg")
    response = gpt4v_wrapper.process_images(system_prompt, prompt, image0, max_tokens=300, temperature=0.0, only_text=True)
    print(response) 
    print(f"Single image elapsed time: {time.time() - start_time}")

    # processing URLs
    start = time.time()
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"  
    response = gpt4v_wrapper.process_images(system_prompt, prompt, url, max_tokens=300, temperature=0.0, only_text=True)
    print(response) 
    print("URL elapsed time: ", time.time() - start)

    # process multiple images
    start_time = time.time()
    prompt = "What's the difference between both images?"
    image0 = Image.open("test_fig.jpg")
    image1 = Image.open("test_fig.jpg")
    list_of_images = [image0, image1]
    response = gpt4v_wrapper.process_images(system_prompt, prompt, list_of_images, max_tokens=300, temperature=0.0, only_text=True)
    print(response) 
    print(f"Multi image elapsed time: {time.time() - start_time}")


# Call main function
if __name__ == "__main__":
    main()
