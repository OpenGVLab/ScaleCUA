import requests
import json
import backoff
from typing import List, Dict, Any
from base64 import b64encode
from agent.model import *

# from your_agent_module import Agent

class InternVL(OpenAIAgent):
    def __init__(
            self,
            api_key: str = '',  
            api_base: str = 'http://10.140.60.11:23333/v1',
            model_name: str = 'internvl3_dynamic',
            max_new_tokens: int = 16384,
            temperature: float = 0.0,
            top_p: float = 0.7,
            **kwargs
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            **kwargs
        )
        self.api_base = api_base
        self.api_base = api_base
        self.name = "InternVL"
        self.headers = {
            "Content-Type": "application/json"
            # "Authorization": "Bearer your_token"
        }

    @backoff.on_exception(
        backoff.expo, Exception,
        on_backoff=lambda details: print(f"Backing off {details['wait']} seconds after {details['tries']} tries."),
        on_giveup=lambda details: print("Gave up after several retries."),
        max_tries=10
    )
    def act(self, messages: List[Dict[str, Any]]) -> str:
        url = f"{self.api_base}/chat/completions"
        # print(self.model_name)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            **self.kwargs
        }
        # print(f"message: {messages}")
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(payload))
            response.raise_for_status()  
            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                reply = result['choices'][0]['message']['content']
                print(f"Response: {reply}")
                return reply
            else:
                print("No valid response found in the API result.")
                return ""

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error: {http_err}")
            print(f"Response content: {response.text}")
            raise
        except Exception as err:
            print(f"Other error: {err}")
            raise

    def prompt_to_message(self, prompt: str, images: List[str]) -> Dict[str, Any]:
        # content = [
        #     {
        #         "type": "text",
        #         "text": prompt
        #     }
        # ]
        content = []
        for img in images:
            base64_img = self.image_to_base64(img)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_img}"
                }
            })
        content.append({
            "type": "text",
            "text": prompt
        })
        message = {
            "role": "user",
            "content": content
        }
        return message

    def image_to_base64(self, image_path: str) -> str:
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = b64encode(image_file.read()).decode('utf-8')
            return encoded_string
        except FileNotFoundError:
            print(f"Image file not found: {image_path}")
            return ""
        except Exception as e:
            print(f"Error encoding image {image_path}: {e}")
            return ""

    def system_prompt(self, instruction: str) -> str:
        return SYSTEM_PROMPT_ANDROID_InternVL_Pixellevel
