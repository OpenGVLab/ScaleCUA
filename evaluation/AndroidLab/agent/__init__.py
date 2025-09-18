try:
    from .mllm.claude_model import *
except:
    print("Claude LLM is not available.")
try:
    from .mllm.internvl_model import *
except:
    print("InternVL is not available.")
try:
    from .mllm.aguvis_model import *
except:
    print("Aguvis is not available.")
try:
    from .llm.glm4 import *
except:
    print("GLM4 is not available.")
try:
    from .llm.qwen_llm_model import *
    from .mllm.qwen_model import *
except:
    print("Qwen LLM is not available.")

from .model import *



def get_agent(agent_module: str, **kwargs) -> Agent:
    class_ = globals().get(agent_module)

    if class_ is None:
        raise AttributeError(f"Not found class {agent_module}")

    if not issubclass(class_, Agent):
        raise TypeError(f"{agent_module} is not Agent")

    return class_(**kwargs)
