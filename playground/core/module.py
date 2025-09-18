from typing import Dict, Optional
from core.mllm import VLMEngine


class BaseModule:
    def __init__(self, engine_params: Dict, platform: str):
        self.engine_params = engine_params
        self.platform = platform

    def _create_vlm_api(
        self, system_prompt: str = None, engine_params: Optional[Dict] = None
    ) -> VLMEngine:
        """Create a new LMMAgent instance"""
        model = VLMEngine(engine_params or self.engine_params)
        if system_prompt:
            model.add_system_prompt(system_prompt)
        return model

    @staticmethod
    def format_history(
        self,
        instruction: Optional[str] = None,
        observation: Optional[Dict] = None,
        history: Optional[list] = None,
    ) -> str:
        pass
