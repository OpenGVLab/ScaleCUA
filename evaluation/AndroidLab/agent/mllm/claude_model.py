import http.client

import anthropic

from agent.model import *

class Claude_official(OpenAIAgent):
    def __init__(
            self,
            model_name: str,
            model_key: str,
            max_new_tokens: int = 512,
            temperature: float = 0.0,
            **kwargs
    ) -> None:
        self.key = model_key
        self.temperature = temperature
        self.model_name = model_name
        self.max_tokens = max_new_tokens
        self.name = "ClaudeAgent"
        self.sleep = 3

    @backoff.on_exception(
        backoff.expo, Exception,
        on_backoff=handle_backoff,
        on_giveup=handle_giveup,
        max_tries=10
    )
    def act(self, messages: List[Dict[str, Any]]) -> str:
        client = anthropic.Anthropic(
            api_key=self.key,
        )
        messages = self.format_message(messages)
        try:
            if messages[0]["role"] == "system":
                system_prompt = messages[0]["content"]
                messages = messages[1:]
                res = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=512,
                    messages=messages,
                    stream=False,
                    temperature=0.0,
                    system=system_prompt
                )
            else:
                res = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=512,
                    messages=messages,
                    stream=False,
                    temperature=0.0
                )
        except Exception as e:
            return False, str(e)

        return res.content[0].text

    def format_message(self, messages: List[Dict[str, Any]]):
        messages = replace_image_url(messages, throw_details=True, keep_path=False)
        new_messages = []
        for message in messages:
            if message["role"] == "system" or message["role"] == "assistant":
                new_messages.append(message)
            else:
                new_message = {"role": "user", "content": []}
                if isinstance(message["content"], str):
                    new_message["content"].append({
                        "type": "text",
                        "text": message["content"]
                    })
                else:
                    for content in message["content"]:
                        if content["type"] == "text":
                            new_message["content"].append(content)
                        elif content["type"] == "image_url":
                            new_message["content"].append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": content["image_url"]["url"].split(";base64,")[0].split("data:")[1],
                                    "data": content["image_url"]["url"].split(";base64,")[1]
                                }
                            })
                        else:
                            return False, "Invalid content type."
                new_messages.append(new_message)
        return new_messages


if __name__ == "__main__":
    agent = Claude_official()
    path_to_image = ""
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Please response concisely."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What can you see?"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{path_to_image}",
                        "detail": "high"
                    }
                }
            ]
        }
    ]
    print(agent.act(messages))
