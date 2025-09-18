import os
import base64
import requests
from PIL import Image, ImageDraw
import io
from typing import Union, List, Tuple
import time
from mimetypes import guess_type
from io import BytesIO
import json # Added for payload display and error parsing

# tenacity is used for retrying requests, which is good practice
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

class ClaudeVisionOAI:

    def __init__(self, model="claude-3-7-sonnet-20250219", anthropic_api_key: str = "your_api_key", proxies: dict = {
"http": "your_proxy",
"https": "your_proxy"
}):
        self.model = model
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.api_key is None:
            print("Anthropic API key not found in environment variable or constructor.")
            # Depending on strictness, you might want to raise an error here
            # raise ValueError("Anthropic API key is required.")

        self.claude_api_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01" # Or a newer version if available/required
        }
        # Store proxies if provided, otherwise use None (no proxy)
        self.proxies = proxies
        if self.proxies:
            print(f"ClaudeVisionOAI initialized with proxies: {self.proxies}")
        else:
            print("ClaudeVisionOAI initialized without proxies.")


    def encode_image(self, image: Union[str, Image.Image]) -> str:
        """
        Encodes an image to a base64 string.
        If image is a PIL.Image, it's converted to JPEG format before encoding.
        The returned string is raw base64, without the "data:image/jpeg;base64," prefix.
        """
        if isinstance(image, str):
            # This path assumes the image file will be opened and read.
            # For Claude, we'll also need the media type. This function only returns base64.
            # The media type will be handled/assumed in get_base64_payload or process_images.
            with open(image, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        elif isinstance(image, Image.Image):
            buffer = io.BytesIO()
            # Convert to RGB if necessary (e.g., for RGBA or P mode images to be saved as JPEG)
            if image.mode not in ["RGB", "L"]: # L is grayscale, also ok for JPEG
                if image.mode == "RGBA" or (image.mode == "P" and 'transparency' in image.info):
                     # If has alpha, better to save as PNG or convert to RGB and lose alpha
                     # For simplicity matching original GPT4VisionOAI behavior, convert to RGB
                     image = image.convert("RGB")
                else: # For other palette images etc.
                     image = image.convert("RGB")

            image.save(buffer, format="JPEG") # Original code specifies JPEG
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        else:
            raise TypeError("Image must be a file path string or a PIL.Image object.")

    def _get_media_type_and_base64_from_image_input(self, image_input: Union[str, Image.Image]) -> Tuple[str, str]:
        """
        Internal helper to get media type and base64 data.
        This is needed because Claude requires media_type.
        """
        if isinstance(image_input, str) and image_input.startswith("http"): # URL
            try:
                response = requests.get(image_input, stream=True, proxies=self.proxies, timeout=20)
                response.raise_for_status()
                content_type = response.headers.get("Content-Type")
                if not content_type or not content_type.startswith("image/"):
                    # If server doesn't provide a proper content type, try to guess or default
                    # For simplicity, default to JPEG if unsure, or try to guess from URL extension
                    guessed_type, _ = guess_type(image_input)
                    if guessed_type and guessed_type.startswith("image/"):
                        media_type = guessed_type
                    else:
                        media_type = "image/jpeg" # Fallback
                else:
                    media_type = content_type

                image_data = base64.b64encode(response.content).decode("utf-8")
                return media_type, image_data
            except requests.RequestException as e:
                print(f"Error downloading image from URL {image_input}: {e}")
                raise
        elif isinstance(image_input, str): # Local file path
            media_type, _ = guess_type(image_input)
            if not media_type or not media_type.startswith("image/"):
                media_type = "image/jpeg" # Fallback if guess fails
            base64_image = self.encode_image(image_input) # encode_image handles file opening
            return media_type, base64_image
        elif isinstance(image_input, Image.Image):
            # encode_image for PIL.Image converts to JPEG.
            base64_image = self.encode_image(image_input)
            return "image/jpeg", base64_image # As encode_image converts to JPEG
        else:
            raise TypeError("Image input must be a URL string, file path string, or PIL.Image object.")


    def get_url_payload(self, url: str) -> dict:
        """
        Creates the Claude image payload part for an image URL.
        Downloads the image and base64 encodes it.
        """
        try:
            media_type, base64_image = self._get_media_type_and_base64_from_image_input(url)
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_image,
                },
            }
        except Exception as e:
            print(f"Failed to create payload for URL {url}: {e}")
            # Return a structure that indicates error or raise, depends on desired handling
            # For now, re-raise to be caught by the caller or retry mechanism
            raise


    def get_base64_payload(self, base64_image: str, detail="auto") -> dict:
        """
        Creates the Claude image payload part for a base64 encoded image string.
        The 'detail' parameter is ignored as it's specific to OpenAI.
        Assumes the base64_image is raw data without a "data:" prefix.
        Since the media type isn't passed, we have to assume one, or it should have been
        determined by the caller. Defaulting to "image/jpeg" as per encode_image behavior.
        """
        # If base64_image string might contain a data URI prefix, strip it.
        # Example: "data:image/png;base64,iVBORw0KGgo..."
        media_type = "image/jpeg" # Default assumption
        if base64_image.startswith('data:'):
            try:
                prefix = base64_image.split(',')[0]
                actual_base64_data = base64_image.split(',')[1]
                media_type = prefix.split(';')[0].split(':')[1]
                base64_image = actual_base64_data
            except IndexError:
                # Malformed data URI, proceed with raw data and default media type
                pass

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type, # Needs to be accurate.
                "data": base64_image,
            },
        }

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(5)) # Adjusted attempts
    def process_images(self, system_prompt: str, question: str, images: Union[str, Image.Image, List[Union[str, Image.Image]]], detail="auto", max_tokens=300, temperature=1.0, only_text=True, format="JPEG") -> str:
        """
        Processes images and a question with the Claude API.
        'detail' and 'format' parameters are part of the original signature but less relevant for Claude.
        'format' might be implicitly handled by encode_image if PIL Images are used.
        """
        if self.api_key is None:
            return "Error: Anthropic API key not configured."

        if system_prompt is None:
            system_prompt = "You are a helpful assistant." # Default system prompt

        if not isinstance(images, list):
            images = [images]

        # Claude API expects 'user' and 'assistant' messages in a list.
        # The 'content' for these messages is a list of blocks (text, image).
        user_content_blocks = []
        user_content_blocks.append({"type": "text", "text": question})

        for image_input in images:
            try:
                if isinstance(image_input, str) and image_input.startswith("http"):
                    # Use _get_media_type_and_base64_from_image_input to get necessary parts
                    media_type, base64_data = self._get_media_type_and_base64_from_image_input(image_input)
                    # Use the generic get_base64_payload to construct the image block, passing the raw base64
                    # We need to ensure get_base64_payload can use this media_type.
                    # Forcing our structure here as get_base64_payload has a fixed signature.
                    user_content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    })
                else: # Local file path or PIL.Image object
                    media_type, base64_data = self._get_media_type_and_base64_from_image_input(image_input)
                    user_content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    })
            except Exception as e:
                print(f"Error processing image {str(image_input)[:50]}...: {e}")
                # Optionally skip this image or return an error message
                return f"Error processing image: {e}"


        claude_messages = [{"role": "user", "content": user_content_blocks}]

        payload = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt: # Add system prompt if provided
            payload["system"] = system_prompt

        # For debugging:
        # print(f"Claude API URL: {self.claude_api_url}")
        # safe_headers = self.headers.copy()
        # if "x-api-key" in safe_headers: safe_headers["x-api-key"] = "****REDACTED****"
        # print(f"Claude Headers: {safe_headers}")
        # print(f"Claude Payload: {json.dumps(payload, indent=2)}")


        try:
            response = requests.post(
                self.claude_api_url,
                headers=self.headers,
                json=payload,
                proxies=self.proxies,
                timeout=90 # Increased timeout for potentially large images/responses
            )
            response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
            response_data = response.json()

            if only_text:
                if response_data and 'content' in response_data and len(response_data['content']) > 0:
                    # Assuming the first content block is the primary text response
                    text_content = ""
                    for block in response_data['content']:
                        if block['type'] == 'text':
                            text_content += block['text'] + "\n"
                    return text_content.strip() if text_content else "No text content found in response."
                elif 'error' in response_data:
                    return f"Claude API Error: {response_data['error'].get('message', 'Unknown error')}"
                else:
                    return "No content found in Claude response or unexpected format."
            else:
                return response_data # Return the full response object

        except requests.exceptions.Timeout as e:
            print(f"Request timed out: {e}")
            return "Error: Request to Claude API timed out."
        except requests.exceptions.RequestException as e:
            error_message = f"Request to Claude API failed: {e}"
            if e.response is not None:
                error_message += f"\nStatus Code: {e.response.status_code}"
                try:
                    error_details = e.response.json()
                    error_message += f"\nDetails: {json.dumps(error_details, indent=2)}"
                except json.JSONDecodeError:
                    error_message += f"\nResponse (not JSON): {e.response.text}"
            print(error_message)
            return error_message
        except Exception as e: # Catch any other unexpected errors
            print(f"An unexpected error occurred: {e}")
            return f"An unexpected error occurred: {e}"


# Main function
def main():

    system_prompt = "You are a helpful assistant."

    # SINGLE RESOURCE
    gpt4v_wrapper = ClaudeVisionOAI()

    # process a single image
    start_time = time.time()
    prompt = "What's in this image?"  
    image0 = Image.open("test_fig.jpg")
    response = gpt4v_wrapper.process_images(system_prompt, prompt, image0, max_tokens=300, temperature=0.0, only_text=True)
    print(response) 
    print(f"Single image elapsed time: {time.time() - start_time}")

    # process multiple images
    start_time = time.time()
    prompt = "What's the difference between both images?"
    image0 = Image.open("test_fig.jpg")
    image1 = Image.open("test_fig.jpg")
    list_of_images = [image0, image1]
    response = gpt4v_wrapper.process_images(system_prompt, prompt, list_of_images, max_tokens=300, temperature=0.0)
    print(response)
    print(f"Multi image elapsed time: {time.time() - start_time}")

    # processing URLs
    start = time.time()
    prompt = "What's in this image?"
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"  
    response = gpt4v_wrapper.process_images(system_prompt, prompt, url, max_tokens=300, temperature=0.0)
    print(response)
    print("URL elapsed time: ", time.time() - start)


# Call main function
if __name__ == "__main__":
    main()
