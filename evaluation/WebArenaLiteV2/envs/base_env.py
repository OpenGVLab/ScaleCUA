from abc import ABC, abstractmethod
import timeout_decorator
from typing import Any, Dict, List, Optional, Tuple, Union


# Agent action decorator
def agent_action(func):
    func.is_agent_action = True
    return func


class BaseEnv(ABC):
    """
    Base class for all environments.
    """

    def __init__(self, server_path, platform, **kwargs):
        self.server_path = server_path
        self.platform = platform
        self.action_history = []

    @abstractmethod
    def reset(self, **kwargs):
        pass

    @abstractmethod
    def get_screen_size(self) -> tuple[int, int]:
        pass

    def onScreen(self, x, y):
        screen_width, screen_height = self.get_screen_size()
        if isinstance(x, float) and isinstance(y, float):
            assert 0 <= x <= 1 and 0 <= y <= 1
            x = round(x * screen_width)
            y = round(y * screen_height)

        return 0 <= x < screen_width and 0 <= y < screen_height

    @abstractmethod
    def get_screenshot(self):
        pass

    @abstractmethod
    def get_a11tree(self):
        pass

    @abstractmethod
    def start_recording(self):
        pass

    @abstractmethod
    def end_recording(self):
        pass

    def get_obs(self, return_screenshot=True, return_a11tree=False):
        assert (
            return_screenshot or return_a11tree
        ), "At least one of return_screenshot and return_a11tree should be True."
        ret = {}
        if return_screenshot:
            ret["screenshot"] = self.get_screenshot()
        if return_a11tree:
            ret["a11tree"] = self.get_a11tree()
        return ret

    def step(self, action_list):
        self.action_history.append(action_list)
        try:
            # action_list = self.parse_action(prediction)
            self.execute(action_list)
        except Exception as e:
            from traceback import print_stack

            print_stack()
            return False

        return True

    @abstractmethod
    @timeout_decorator.timeout(10)
    def execute_single_action(self, action: dict):
        pass

    def execute(self, action_list: list[dict]):
        for action in action_list:
            self.execute_single_action(action)

    def parse_action(self, prediction):
        pass
