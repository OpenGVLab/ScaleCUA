import os
import base64
import json
import ssl
import urllib.request
from PIL import Image
import io
import time
from typing import Union, List
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff

class Phi3WrapperError(Exception):
    pass

class Phi3VisionAzure:

    def __init__(self, azure_key_path=None, endpoint=None):
        if azure_key_path is None:
            self.api_key = os.getenv("AZURE_API_KEY")
        else:
            with open(azure_key_path, "r") as key_file:
                self.api_key = key_file.read().strip()

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "azureml-model-deployment": "phi-3-vision-128k-instruct-2"
        }

        if endpoint is None:
            self.endpoint = os.environ.get("AZURE_ENDPOINT")
        else:
            self.endpoint = endpoint

    def encode_image(self, image: Union[str, Image.Image], format="JPEG") -> str:
        if isinstance(image, str):
            with open(image, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        elif isinstance(image, Image.Image):
            image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format=format)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def get_base64_payload(self, base64_image: str, format="JPEG") -> dict:
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{format.lower()};base64,{base64_image}",
            }
        }
    
    def get_url_payload(self, url: str) -> dict:
        return {
            "type": "image_url",
            "image_url": {
                "url": url
            }
        }
    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(10))
    def process_images(self, system_prompt: str, question: str, images: Union[str, Image.Image, List[Union[str, Image.Image]]], max_tokens=2048, temperature=0.0, only_text=True, format="JPEG") -> str:
        allowSelfSignedHttps(True)  # this line is needed if you use self-signed certificate in your scoring service.

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

        data = {
            "input_data": {
                "input_string": [
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "parameters": {"temperature": temperature, "max_new_tokens": max_tokens}
            }
        }

        body = str.encode(json.dumps(data))
        
        req = urllib.request.Request(self.endpoint, body, self.headers)

        try:
            response = json.load(urllib.request.urlopen(req))
            return response["output"]
        except urllib.error.HTTPError as error:
            print("The request failed with status code: " + str(error.code))
            print(error.info())
            print(error.read().decode("utf8", 'ignore'))
            raise Phi3WrapperError(f"Failed to make the request. Error: {error}")

def allowSelfSignedHttps(allowed):
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):
        ssl._create_default_https_context = ssl._create_unverified_context

# Main function
def main():

    system_prompt = "You are a helpful assistant."

    # SINGLE RESOURCE
    phi3_wrapper = Phi3VisionAzure()

    # process a single image
    start_time = time.time()
    prompt = "What's in this image?"  
    image0 = Image.open("test_fig.jpg")
    response = phi3_wrapper.process_images(system_prompt, prompt, image0, max_tokens=300, temperature=0.0, only_text=True, format="JPEG")
    print(response) 
    print(f"Single image elapsed time: {time.time() - start_time}")

    # processing URLs
    start = time.time()
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"  
    response = phi3_wrapper.process_images(system_prompt, prompt, url, max_tokens=300, temperature=0.0, only_text=True, format="JPEG")
    print(response) 
    print("URL elapsed time: ", time.time() - start)

    # process multiple images
    start_time = time.time()
    prompt = "what in those two image?"
    image0 = Image.open("test_fig.jpg")
    image1 = Image.open("OIP.jpg")
    list_of_images = [image0, image1]

    response = phi3_wrapper.process_images(system_prompt, prompt, image0, max_tokens=300, temperature=0.0, only_text=True, format="JPEG")
    response = phi3_wrapper.process_images(system_prompt, prompt+"talk about last image", image1, max_tokens=300, temperature=0.0, only_text=True, format="JPEG")
    print(response) 
    print(f"Multi image elapsed time: {time.time() - start_time}")

# Call main function
if __name__ == "__main__":
    main()
