import requests
import json
import backoff
from typing import List, Dict, Any
from base64 import b64encode
from agent.model import *

# from your_agent_module import Agent


class AguvisAgent(OpenAIAgent):
    def __init__(
        self,
        api_key: str = "",
        api_base: str = "",
        model_name: str = "",
        max_new_tokens: int = 16384,
        temperature: float = 0,
        top_p: float = 0.7,
        **kwargs,
    ) -> None:
        self.client = OpenAI(api_key=api_key, base_url=api_base)
        # openai.api_base = api_base
        # openai.api_key = api_key
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.kwargs = kwargs
        self.name = "OpenAIAgent"

    @backoff.on_exception(
        backoff.expo,
        Exception,
        on_backoff=handle_backoff,
        on_giveup=handle_giveup,
        max_tries=10,
    )
    def act(self, messages: List[Dict[str, Any]]) -> str:
        # print(f"Request: {messages}")
        r = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        # print(f"messages: {messages}")
        print(f"Response: {r.choices[0].message.content}")
        response = self.AguvisActionSpace_mapping(r.choices[0].message.content)
        print(f"Mapping Response: {response}")
        return response

    def prompt_to_message(self, prompt, images):
        content = [{"type": "text", "text": prompt}]
        for img in images:
            base64_img = image_to_base64(img)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_img}"},
                }
            )
        message = {"role": "user", "content": content}
        return message

    def system_prompt(self, instruction) -> str:
        return (
            SYSTEM_PROMPT_ANDROID_MLLM_DIRECT + f"\n\nTask Instruction: {instruction}"
        )

    def AguvisActionSpace_mapping(self, response):
        Action = None
        import re

        if "pyautogui" in response:
            match = re.search(r"pyautogui\.(\w+)\(", response)
            if match:
                action = match.group(1).lower()
                if action == "write":
                    write_match = re.search(
                        r"pyautogui\.write\(message=['\"](.+?)['\"]\)", response
                    )
                    if write_match:
                        message = write_match.group(1)
                        Action = f'do(action="Type", text="{message}")'
                elif action == "click":
                    click_match = re.search(
                        r"pyautogui\.click\(x=(\d*\.?\d*),\s*y=(\d*\.?\d*)\)", response
                    )
                    if click_match:
                        x = click_match.group(1)
                        y = click_match.group(2)
                        Action = f'do(action="Tap", element=[{x}, {y}])'
        elif "mobile" in response:
            match = re.search(r"mobile\.(\w+)\(", response)
            if match:
                action = match.group(1).lower()
                if action == "swipe":
                    swipe_match = re.search(
                        r"mobile\.swipe\(from_coord=\[(\d*\.?\d*),\s*(\d*\.?\d*)\],\s*to_coord=\[(\d*\.?\d*),\s*(\d*\.?\d*)\]\)",
                        response,
                    )
                    if swipe_match:
                        from_x = swipe_match.group(1)
                        from_y = swipe_match.group(2)
                        to_x = swipe_match.group(3)
                        to_y = swipe_match.group(4)
                        Action = f'do(acton="Swipe Precise", start=[{from_x}, {from_y}], end=[{to_x}, {to_y}])'
                elif action == "home":
                    Action = f'do(action="Home")'
                elif action == "back":
                    Action = f'do(action="Back")'
                elif action == "wait":
                    Action = f'do(action="Wait")'
                elif action == "long_press":
                    long_press_match = re.search(
                        r"mobile\.long_press\(x=(\d*\.?\d*),\s*y=(\d*\.?\d*)\)",
                        response,
                    )
                    if long_press_match:
                        x = long_press_match.group(1)
                        y = long_press_match.group(2)
                        Action = f'do(action="Long Press", element=[{x}, {y}])'
                elif action == "terminate":
                    terminate_match = re.search(
                        r"mobile\.terminate\(status=['\"](.+?)['\"]\)", response
                    )
                    if terminate_match:
                        status = terminate_match.group(1)
                        Action = f'finish(message="{status}")'
        elif "answer" in response:
            answer_match = re.search(r"answer\(text=['\"](.+?)['\"]\)", response)
            if answer_match:
                text = answer_match.group(1)
                Action = f'finish(message="{text}")'
        elif "terminate" in response:
            terminate_match = re.search(
                r"terminate\(status=['\"](.+?)['\"]\)", response
            )
            if terminate_match:
                status = terminate_match.group(1)
                Action = f'finish(message="{status}")'

        content = response
        try:
            start = response.find("assistantall\n") + len("assistantall\n")
            end = response.find("\nassistantos")
            if start == -1 or end == -1:
                return None
            content = response[start:end]
        except Exception as e:
            return f"Extract content failed: {e}"

        return (
            "* Analysis: "
            + content
            + "\n"
            + "* Operation:"
            + "\n"
            + "```"
            + "\n"
            + Action
            + "\n"
            + "```"
        )
