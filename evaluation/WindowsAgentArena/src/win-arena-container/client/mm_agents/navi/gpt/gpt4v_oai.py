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
import openai

os.environ["OPENAI_API_KEY"] = "your_api_key"

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff


class GPT4VisionOAI:

    def __init__(self, model="gpt-4o"):
        self.model = model
        # oad key from environment variable
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key is None:
            print("API key not found in environment variable.")
        self.client = openai.OpenAI(
            api_key=self.api_key, base_url="https://api.openai.com/v1"
        )

    def encode_image(self, image: Union[str, Image.Image]) -> str:
        if isinstance(image, str):
            with open(image, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        elif isinstance(image, Image.Image):
            buffer = io.BytesIO()
            # convert to rgb if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffer, format="JPEG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def get_url_payload(self, url: str) -> dict:
        return {"type": "image_url", "image_url": {"url": url}}

    def get_base64_payload(self, base64_image: str, detail="auto") -> dict:
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}",
                "detail": "auto",
            },
        }

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(30))
    def process_images(
        self,
        system_prompt: str,
        question: str,
        images: Union[str, Image.Image, List[Union[str, Image.Image]]],
        detail="auto",
        max_tokens=300,
        temperature=1.0,
        only_text=True,
        format="JPEG",
    ) -> str:

        if system_prompt == None:
            system_prompt = "You are a helpful assistant."

        if not isinstance(images, list):
            images = [images]

        content = [{"type": "text", "text": question}]

        for image in images:
            if isinstance(image, str) and image.startswith("http"):
                content.append(self.get_url_payload(image))
            else:
                base64_image = self.encode_image(image)
                content.append(self.get_base64_payload(base64_image, detail=detail))

        response = self.client.chat.completions.create(
            # model="gpt-4-vision-preview",
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # return response.choices[0].message.content
        if only_text:
            return response.choices[0].message.content
        else:
            return response


# Main function
def main():

    system_prompt = "You are a helpful assistant."

    # SINGLE RESOURCE
    gpt4v_wrapper = GPT4VisionOAI(model="gpt-4o-2024-11-20")

    # process a single image
    start_time = time.time()
    prompt = "What's in this image?"
    image0 = Image.open("test_fig.jpg")
    response = gpt4v_wrapper.process_images(
        system_prompt, prompt, image0, max_tokens=300, temperature=0.0, only_text=True
    )
    print(response)
    print(f"Single image elapsed time: {time.time() - start_time}")

    # process multiple images
    start_time = time.time()
    prompt = "What's the difference between both images?"
    image0 = Image.open("test_fig.jpg")
    image1 = Image.open("test_fig.jpg")
    list_of_images = [image0, image1]
    response = gpt4v_wrapper.process_images(
        system_prompt, prompt, list_of_images, max_tokens=300, temperature=0.0
    )
    print(response)
    print(f"Multi image elapsed time: {time.time() - start_time}")

    # processing URLs
    start = time.time()
    prompt = "What's in this image?"
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    response = gpt4v_wrapper.process_images(
        system_prompt, prompt, url, max_tokens=300, temperature=0.0
    )
    print(response)
    print("URL elapsed time: ", time.time() - start)


# Call main function
if __name__ == "__main__":
    main()
