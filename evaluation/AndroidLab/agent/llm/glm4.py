from zhipuai import ZhipuAI

from agent.model import *


class GLM4Agent(OpenAIAgent):
    def __init__(
            self,
            model_name: str,
            model_key: str,
            max_new_tokens: int = 16384,
            temperature: float = 0,
            top_p: float = 0.7,
            **kwargs
    ) -> None:
        self.model_name = model_name
        self.glm4_key = model_key
        self.client = ZhipuAI(api_key=self.glm4_key)
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.kwargs = kwargs
        self.name = "GLM4Agent"

    @backoff.on_exception(
        backoff.expo, Exception,
        on_backoff=handle_backoff,
        on_giveup=handle_giveup,
        max_tries=10
    )
    def act(self, messages: List[Dict[str, Any]]) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name, 
            messages=messages,
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    agent = GLM4Agent()

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Please response concisely."
        },
        {
            "role": "user",
            "content": "Tell me a story."
        }
    ]
    print(agent.act(messages))
