import os
from typing import Dict, List, Tuple

from core.module import BaseModule

working_dir = os.path.dirname(os.path.abspath(__file__))


class UIAgent(BaseModule):
    """Base class for UI automation agents"""

    def __init__(self, engine_params: Dict, platform: str = "web"):
        """Initialize UIAgent

        Args:
            engine_params: Configuration parameters for the LLM engine
            platform: Operating system platform (macos, linux, windows)
        """
        super().__init__(engine_params=engine_params, platform=platform)

    def reset(self) -> None:
        """Reset agent state"""
        pass

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """Generate next action prediction

        Args:
            instruction: Natural language instruction
            observation: Current UI state observation

        Returns:
            Tuple containing agent info dictionary and list of actions
        """
        pass
