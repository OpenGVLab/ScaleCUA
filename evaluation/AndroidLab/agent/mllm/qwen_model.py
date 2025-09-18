from http import HTTPStatus

import dashscope

from agent.model import *


class QwenAgent(OpenAIAgent):
    def __init__(
            self,
            api_key: str,
            model_name: str = "qwen-vl-max",
            seed: int = 42,
            top_k: float = 1.0,
            sleep: int = 2
    ):
        dashscope.api_key = api_key
        self.name = "QwenAgent"
        self.model = model_name
        self.seed = seed
        self.top_k = top_k
        self.sleep = sleep

    @backoff.on_exception(
        backoff.expo, Exception,
        on_backoff=handle_backoff,
        on_giveup=handle_giveup,
        max_tries=10
    )
    def act(self, messages: List[Dict[str, Any]]) -> str:
        messages = self.format_message(messages)
        print(messages)
        response = dashscope.MultiModalConversation.call(model=self.model, messages=messages, seed=self.seed,
                                                         top_k=self.top_k)

        if response.status_code == HTTPStatus.OK:
            print(f"Prompt Tokens: {response.usage.input_tokens}\nCompletion Tokens: {response.usage.output_tokens}\n")
            return response.output.choices[0].message.content[0]['text']
        else:
            print(response.code, response.message)
            for message in messages:
                print(message)
            return response.code, response.message  # The error code & message

    def format_message(self, message):
        if message[0]["role"] == "system":
            message[-1]["content"][0]["text"] = message[0]["content"]
        return [message[-1]]

    def prompt_to_message(self, prompt, images):
        content = [{
            "text": prompt
        }]
        for img in images:
            img_path = f"file://{img}"
            content.append({
                "image": img_path
            })
        message = {
            "role": "user",
            "content": content
        }
        return message
