from envs.base_env import BaseEnv
from envs.base_env import agent_action
from typing import Tuple, List, Union, Dict
import requests
import yaml
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import time
from abc import ABC, abstractmethod
import timeout_decorator
from io import BytesIO
from PIL import Image
import os
import base64


def b64_to_byte(data):
    return base64.b64decode(data)


def request_api_wrapper(url, files=None, json=None, try_max_times=5, timeout=360):
    """Synchronous request API wrapper"""
    for _ in range(try_max_times):
        try:
            # response = requests.post(url=url, json=data, headers=headers)
            response = requests.post(url=url, files=files, json=json, timeout=timeout)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            response = response.json()
            is_success = response.get("success")
            if not is_success:
                message = response.get("message", None)
                print(f"API execution error: {message}")
            else:
                return response
        except requests.RequestException as e:
            print(f"Request error, please check: {e}")
        except Exception as e:
            print(f"Unexpected error, please check: {e}")
        time.sleep(1)


class AndroidEnv(BaseEnv):
    def __init__(self, server_path, platform="Android", **kwargs):
        super().__init__(server_path, platform)
        self.manager_port = kwargs.get("manager_port", None)
        self.avd_name = kwargs.get("avd_name", "Pixel_7_Pro_API_33")
        self.docker = kwargs.get("docker", True)
        self.docker_args = kwargs.get(
            "docker_args", {"image_name": "android_eval:latest", "port": 6060}
        )
        self.config = {
            "avd_name": self.avd_name,
            "docker": self.docker,
            "docker_args": self.docker_args,
        }
        # print(self.config)
        Base_url = f"{self.server_path}:{self.manager_port}/"
        self.Base_url = Base_url

        config_json = json.dumps(self.config)
        files = {"file": ("config.json", config_json, "application/json")}
        response = request_api_wrapper(f"{Base_url}create_env", files=files)
        self.env_id = response["env_id"]
        print(response)

        self.get_a11tree()

        get_screen_size_payload = {"env_id": self.env_id}
        response = request_api_wrapper(
            f"{self.Base_url}get_screen_size", json=get_screen_size_payload
        )
        self.width, self.height = response["screen_size"]
        self.screen_size = (self.width, self.height)
        print(f"Screen size: {self.width}x{self.height}")

        self.is_recording = False

    def _execute_click(self, parameters):
        try:
            click_payload = {
                "env_id": self.env_id,
                "action": "Tap",
                "element": [parameters["x"], parameters["y"]],
            }
            response = request_api_wrapper(f"{self.Base_url}step", json=click_payload)
            if response["success"]:
                return True
        except Exception as e:
            print(f"Click failed: {e}")
            return False

    def _execute_write(self, parameters):
        try:
            write_payload = {
                "env_id": self.env_id,
                "action": "Type",
                "kwargs": {"text": parameters["message"]},
            }
            response = request_api_wrapper(f"{self.Base_url}step", json=write_payload)
            if response["success"]:
                return True
        except Exception as e:
            print(f"Write failed: {e}")
            return False

    def _execute_swipe(self, parameters):
        try:
            swipe_payload = {
                "env_id": self.env_id,
                "action": "Swipe Precise",
                "kwargs": {
                    "start": parameters["from_coord"],
                    "end": parameters["to_coord"],
                },
            }
            response = request_api_wrapper(f"{self.Base_url}step", json=swipe_payload)
            if response["success"]:
                return True
        except Exception as e:
            print(f"Swipe failed: {e}")
            return False

    def _execute_long_press(self, parameters):
        try:
            long_press_payload = {
                "env_id": self.env_id,
                "action": "Long Press",
                "element": [parameters["x"], parameters["y"]],
            }
            response = request_api_wrapper(
                f"{self.Base_url}step", json=long_press_payload
            )
            if response["success"]:
                return True
        except Exception as e:
            print(f"Long press failed: {e}")
            return False

    def _execute_home(self, parameters):
        try:
            home_payload = {
                "env_id": self.env_id,
                "action": "Home",
            }
            response = request_api_wrapper(f"{self.Base_url}step", json=home_payload)
            if response["success"]:
                return True
        except Exception as e:
            print(f"Home failed: {e}")
            return False

    def _execute_back(self, parameters):
        try:
            back_payload = {
                "env_id": self.env_id,
                "action": "Back",
            }
            response = request_api_wrapper(f"{self.Base_url}step", json=back_payload)
            if response["success"]:
                return True
        except Exception as e:
            print(f"Back failed: {e}")
            return False

    def _execute_open_app(self, parameters):
        try:
            open_app_payload = {
                "env_id": self.env_id,
                "action": "Launch",
                "kwargs": {"app": parameters["app_name"]},
            }
            response = request_api_wrapper(
                f"{self.Base_url}step", json=open_app_payload
            )
            if response["success"]:
                return True
        except Exception as e:
            print(f"Open app failed: {e}")
            return False

    def _execute_wait(self, parameters):
        try:
            seconds = parameters.get("seconds", 5)
            time.sleep(seconds)
            return True
        except Exception as e:
            print(f"Wait failed: {e}")
            return False

    def _execute_terminate(self, parameters):
        try:
            status = parameters.get("status", None)
            if status is None:
                raise Exception("Status not specified.")
            print(f"Task terminated with status: {status}")
            return True
        except Exception as e:
            print(f"Terminate failed: {e}")
            return False

    def _execute_callUser(self, parameters):
        print("Calling user...")
        return True

    def _execute_response(self, parameters):
        print(f"Response: {parameters['answer']}")
        return True

    # def _execute_terminate(self, parameters):

    def resart(self, **kwargs):
        stop_payload = {"env_id": self.env_id}
        response = request_api_wrapper(f"{self.Base_url}stop_env", json=stop_payload)

        config_json = json.dumps(self.config)
        files = {"file": ("config.json", config_json, "application/json")}
        response = request_api_wrapper(f"{self.Base_url}create_env", files=files)
        self.env_id = response["env_id"]

    def resart(self, **kwargs):
        stop_payload = {"env_id": self.env_id}
        response = request_api_wrapper(f"{self.Base_url}stop_env", json=stop_payload)

        config_json = json.dumps(self.config)
        files = {"file": ("config.json", config_json, "application/json")}
        response = request_api_wrapper(f"{self.Base_url}create_env", files=files)
        self.env_id = response["env_id"]

    def reset(self, **kwargs):
        app = None
        if "application" in kwargs:
            app = kwargs["application"]
        reset_payload = {"env_id": self.env_id, "app_name": app}
        response = request_api_wrapper(f"{self.Base_url}reset", json=reset_payload)
        if response["success"]:
            return True
        else:
            print(f"Reset failed: {response.get('message', 'Unknown error')}")
            return False

    def get_screen_size(self) -> tuple[int, int]:
        return self.width, self.height

    def onScreen(self, x, y):
        screen_width, screen_height = self.get_screen_size()
        if isinstance(x, float) and isinstance(y, float):
            assert 0 <= x <= 1 and 0 <= y <= 1
            x = round(x * screen_width)
            y = round(y * screen_height)

        return 0 <= x < screen_width and 0 <= y < screen_height

    def get_screenshot(self, prefix=None, suffix=None):
        screenshot_payload = {"env_id": self.env_id, "prefix": None, "suffix": None}
        response = request_api_wrapper(
            f"{self.Base_url}screenshot", json=screenshot_payload
        )
        screenshot = b64_to_byte(response["screenshot"])

        # image = Image.open(BytesIO(screenshot))
        # image.show()
        return screenshot

    def get_a11tree(self):
        get_xml_payload = {"env_id": self.env_id}
        response = request_api_wrapper(f"{self.Base_url}get_xml", json=get_xml_payload)
        xml = response["xml"]
        return xml

    def step(self, action_list):
        try:
            # action_list = self.parse_action(prediction)
            self.execute(action_list)
        except Exception as e:
            from traceback import print_stack

            print_stack()
            return False

        return True

    def parse_action(self, prediction):
        pass

    @timeout_decorator.timeout(60)
    def execute_single_action(self, action: dict):
        action_name = action["name"]
        parameters = action["parameters"]
        action_dict = {
            "click": self._execute_click,
            "write": self._execute_write,
            "swipe": self._execute_swipe,
            "long_press": self._execute_long_press,
            "navigate_home": self._execute_home,
            "navigate_back": self._execute_back,
            "open_app": self._execute_open_app,
            "wait": self._execute_wait,
            "terminate": self._execute_terminate,
            "callUser": self._execute_callUser,
            "response": self._execute_response,
        }
        if action_name not in action_dict:
            raise Exception(f"Action {action_name} not supported.")
        action_stauts = action_dict[action_name](parameters)
        time.sleep(5)
        if action_stauts:
            print(f"Action Status: \n {action} executed successfully.")
        else:
            print(f"Action Status: \n {action} failed.")

    def execute(self, action_list: list[dict]):
        for action in action_list:
            self.execute_single_action(action)

    def exit(self):
        stop_payload = {"env_id": self.env_id}
        response = request_api_wrapper(f"{self.Base_url}stop_env", json=stop_payload)
        print(response)

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
        actions = [
            {
                "name": "click",
                "parameters": {"x": None, "y": None, "clicks": 1, "button": "left"},
            },
            {"name": "write", "parameters": {"message": text}},
        ]
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
        return_value: Optional[Union[Dict, str, List, Tuple, int, float, bool]] = None,
    ):
        """End the current task with a success and the required return value"""
        self.returned_info = return_value
        actions = [
            {
                "name": "terminate",
                "parameters": {
                    "status": "success",
                },
            }
        ]
        return actions

    @agent_action
    def fail(self):
        """End the current task with a failure, and replan the whole task."""
        actions = [
            {
                "name": "terminate",
                "parameters": {
                    "status": "failure",
                },
            }
        ]
        return actions

    @agent_action
    def callUser():
        """Call the user
        Args:
            None
        """
        actions = [{"name": "callUser", "parameters": {}}]
        return actions

    @agent_action
    def swipe(self, starting_description: str, ending_description: str):
        """Drag from the starting description to the ending description
        Args:
            starting_description:str, a very detailed description of where to start the swipe action. This description should be at least a full sentence.
            ending_description:str, a very detailed description of where to end the swipe action. This description should be at least a full sentence.
        """
        actions = [
            {
                "name": "swipe",
                "parameters": {
                    "from": None,
                    "to": None,
                },
            }
        ]
        return actions

    @agent_action
    def home(self):
        """Press the home button on the device"""
        actions = [{"name": "home", "parameters": {}}]
        return actions

    @agent_action
    def back(self):
        """Press the back button on the device"""
        actions = [{"name": "back", "parameters": {}}]
        return actions

    @agent_action
    def long_press(self, element_description: str):
        """Long press on a specified element
        Args:
            element_description:str, a detailed descriptions of which element to click on. This description should be at least a full sentence.
        """
        actions = [
            {
                "name": "long_press",
                "parameters": {
                    "x": None,
                    "y": None,
                },
            }
        ]
        return actions

    @agent_action
    def open_app(self, app_name: str):
        """Open an app on the device
        Args:
            app_name (str): The name of the app to open.
        """
        actions = [
            {
                "name": "open_app",
                "parameters": {
                    "app_name": app_name,
                },
            }
        ]
        return actions

    def start_recording(self, save_path: str = None):
        if self.is_recording:
            print("Recording is already in progress.")
            return False
        self.is_recording = True
        try:
            start_record_payload = {"env_id": self.env_id}
            response = request_api_wrapper(
                f"{self.Base_url}start_record", json=start_record_payload
            )
            if response["success"]:
                return True
        except Exception as e:
            print(f"record failed: {e}")
            return False

    def end_recording(self, save_path):
        if not self.is_recording:
            print("Recording is not in progress.")
            return False
        self.is_recording = False
        url = f"{self.Base_url}/end_record"
        payload = {"env_id": self.env_id}

        try:
            resp = requests.post(url, json=payload, stream=True, timeout=120)
            resp.raise_for_status()
            dirpath = os.path.dirname(save_path)
            if dirpath and not os.path.exists(dirpath):
                os.makedirs(dirpath, exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"Saved recording to {save_path}")
            return True

        except requests.HTTPError as e:
            print("HTTP error:", e, resp.text)
        except Exception as e:
            print(f"record failed: {e}")

        return False


if __name__ == "__main__":

    with open("config/env/android.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    env = AndroidEnv(
        config["server_path"],
        platform=config.get("platform", "Android"),
        manager_port=config.get("manager_port", None),
        avd_name=config.get("avd_name", None),
        docker=config.get("docker", None),
        docker_args=config.get("docker_args", None),
    )
