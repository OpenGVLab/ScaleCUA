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
    def end_recording(self, path: str):
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

    @agent_action
    def click(
        self,
        element_description: str,
        num_clicks: int = 1,
        button_type: str = "left",
        hold_keys: List = [],
    ):
        """Click on the element
        Args:
            element_description:str, a detailed descriptions of which element to click on. This description should be at least a full sentence.
            num_clicks:int, number of times to click the element
            button_type:str, which mouse button to press can be "left", "middle", or "right"
            hold_keys:List, list of keys to hold while clicking
        """
        actions = [
            {
                "name": "click",
                "parameters": {
                    "x": None,
                    "y": None,
                    "clicks": num_clicks,
                    "button": button_type,
                },
            }
        ]
        return actions

    @agent_action
    def type(
        self,
        element_description: Optional[str] = None,
        text: str = "",
        overwrite: bool = False,
        enter: bool = False,
    ):
        """Type text into a specific element
        Args:
            element_description:str, a detailed description of which element to enter text in. This description should be at least a full sentence.
            text:str, the text to type
            overwrite:bool, Assign it to True if the text should overwrite the existing text, otherwise assign it to False. Using this argument clears all text in an element.
            enter:bool, Assign it to True if the enter key should be pressed after typing the text, otherwise assign it to False.
        """
        actions = []
        if element_description is not None:
            actions.append(
                {
                    "name": "click",
                    "parameters": {"x": None, "y": None, "clicks": 1, "button": "left"},
                }
            )
        actions.append({"name": "write", "parameters": {"message": text}})
        if enter:
            actions.append(
                {
                    "name": "press",
                    "parameters": {
                        "keys": "enter",
                        "presses": 1,
                    },
                }
            )
        return actions

    @agent_action
    def scroll(self, element_description: str, clicks: int, shift: bool = False):
        """Scroll the element in the specified direction
        Args:
            element_description:str, a very detailed description of which element to enter scroll in. This description should be at least a full sentence.
            clicks:int, the number of clicks to scroll can be positive (up) or negative (down).
            shift:bool, whether to use shift+scroll for horizontal scrolling
        """
        actions = [
            {"name": "scroll", "parameters": {"x": None, "y": None, "clicks": clicks}}
        ]
        return actions

    @agent_action
    def wait(self, time: float):
        """Wait for a specified amount of time
        Args:
            time:float the amount of time to wait in seconds
        """
        actions = [
            {
                "name": "wait",
                "parameters": {
                    "seconds": time,
                },
            }
        ]
        return actions

    @agent_action
    def done(
        self,
        answer: Optional[str] = None,
        return_value: Optional[Union[Dict, str, List, Tuple, int, float, bool]] = None,
    ):
        """End the current task with a success, output the final answer and the required return value
        Args:
            answer: the final answer to response the user's query
        """
        self.returned_info = return_value
        actions = [
            {"name": "terminate", "parameters": {"status": "success", "answer": answer}}
        ]
        return actions

    @agent_action
    def fail(self, rationale: Optional[str] = None):
        """End the current task with a failure, output the failure reason, and replan the whole task.
        Args:
            rationale: the failure reason of this task
        """
        actions = [
            {
                "name": "terminate",
                "parameters": {"status": "failure", "answer": rationale},
            }
        ]
        return actions

    @agent_action
    def callUser(self):
        """Call the user
        Args:
            None
        """
        actions = [{"name": "callUser", "parameters": {}}]
        return actions
