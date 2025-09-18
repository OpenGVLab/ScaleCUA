import logging
import os
import time
from typing import Callable, Any, Optional, Tuple
from typing import List, Dict, Union
import requests
import json
import random
import base64
import subprocess
import datetime

from envs.base_env import BaseEnv
from envs.base_env import agent_action
from envs.ubuntu.vm.actions import KEYBOARD_KEYS
from envs.ubuntu.accessibility_tree_wrap.heuristic_retrieve import get_clickable_elements
from envs.ubuntu.env_api.env_api_manager import find_free_port

logger = logging.getLogger("env.ubuntu")

def b64_to_byte(data):
    return base64.b64decode(data)

def get_app_init_config(app: str) -> Dict[str, Any]:
    config_path = f'config/envs/ubuntu_init/{app}.json'
    if not os.path.exists(config_path):
        raise ValueError(f"No init config for {app}, check {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)

def request_api_wrapper(url, data=None, method="POST", try_max_times=5, timeout=60000):
    """Synchronous request API wrapper"""
    headers = {
        "Content-Type": "application/json",
    }
    for _ in range(try_max_times):
        try:
            response = requests.request(method=method, url=url, json=data, headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            response = response.json()
            is_success = response.get("success")
            if not is_success:
                message = response.get("message", None)
                logger.error(f"API execution error: {message}")
            else:
                return response
        except requests.RequestException as e:
            logger.error(f"Request error, please check: {e}")
        except Exception as e:
            logger.error(f"Unexpected error, please check: {e}")
        time.sleep(1)

    raise Exception(f"Request error for {try_max_times} times, returning None. Please check the API server.")

MANAGER_LAUNCH_SCRIPT = "mkdir -p log_env_api/env_manager;" \
                        "python envs/ubuntu/env_api/env_api_manager.py --host 0.0.0.0 --port {port} " \
                        "2>&1 | tee log_env_api/env_manager/{port}_{time}.log"

class UbuntuEnv(BaseEnv):
    def __init__(
        self, 
        server_path: str = None,
        **kwargs,
    ):
        """
            Args:
            server_path: The path to the server, if None, will create a local env manager.
            kwargs: Additional parameters for the environment
        """
        super().__init__(server_path=server_path, platform="ubuntu")
        
        self.env_port = kwargs.get("env_port", None)
        self.manager_port = kwargs.get("manager_port", None)
        self.connect_max_try = kwargs.get("connect_max_try", 5)
        self.action_pause = kwargs.get("action_pause", 5)

        if self.server_path is None:
            if self.manager_port is None:
                self.manager_port = find_free_port()
            script = MANAGER_LAUNCH_SCRIPT.format(port=self.manager_port, time=datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
            self.localhost_manager_process = subprocess.Popen(script, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(5)
            if self.localhost_manager_process.poll() is not None:
                raise Exception(f"create env manager failed: {self.localhost_manager_process.poll()}")
            self.server_path = "http://0.0.0.0"
            self.localhost_as_manager = True
            logger.info(f"create env manager locally success at port: {self.manager_port}, pid: {self.localhost_manager_process.pid}")
        else:
            self.localhost_as_manager = False
            self.localhost_manager_process = None
        
        # create env api by manager
        if self.env_port is None:
            assert self.manager_port is not None, "use manager to assign an api"
            self.use_api_manager = True
            create_url = f"{self.server_path}:{self.manager_port}/create_env_api"
            response = self._request_handler(create_url, try_max_times=self.connect_max_try)
            self.env_id = response["env_id"]
            self.env_port = response["port"]
            time.sleep(5)
            logger.info("creating env api done")
        else:
            self.use_api_manager = False
            
        # create env
        data = {
            "vm_path": kwargs.get("vm_path", '/path/to/docker_vm_data/Ubuntu.qcow2'),
            "action_space": kwargs.get("action_space", 'pyautogui'),
            "screen_width": kwargs.get("screen_size", (1920, 1080))[0],
            "screen_height": kwargs.get("screen_size", (1920, 1080))[1],
            "headless": kwargs.get("headless", True),
            "require_a11y_tree": kwargs.get("require_a11y_tree", True),
            "os_type": "Ubuntu"
        }
        
        start_url = f"{self.server_path}:{self.env_port}/start"
        response = self._request_handler(start_url, data, try_max_times=self.connect_max_try)
        logger.info("create env done") 
        self.screen_size = [data["screen_width"], data["screen_height"]]   
          
    def _request_handler(self, url, data=None, method="POST", try_max_times=5, timeout=60000):
        """
        Handle the exception raised during the request to the env api. Kill the env, and env manager if necessary.
        """
        try:
            return request_api_wrapper(url, data, method, try_max_times, timeout)
        except Exception as e:
            logger.error(f"{e}")
            # try to close the env
            try:
                close_url = f"{self.server_path}:{self.env_port}/close"
                _ = request_api_wrapper(close_url, try_max_times=self.connect_max_try)
            except:
                pass
            # terminate the env manager if it is running locally
            if self.localhost_as_manager:
                self.localhost_manager_process.terminate()
                self.localhost_manager_process.wait()
                logger.info(f"terminate localhost env manager done, freed port: {self.manager_port}")
            self.close()

    def save_screenshot(self, image_path):
        screenshot = self.get_screenshot()
        with open(image_path, "wb") as image_save:
            image_save.write(screenshot)
            
    def reset(self, **kwargs) -> Dict[str, Any]:
        self.action_history = []
        logger.info("resetting env...")
        reset_url = f"{self.server_path}:{self.env_port}/reset"
        self.task_config = kwargs.get("task_config", None)
        if self.task_config is None:
            if "application" in kwargs and kwargs["application"] is not None:
                self.task_config = get_app_init_config(kwargs["application"])
            else:
                self.task_config = get_app_init_config("desktop") 
        response = self._request_handler(reset_url, {"task_config": self.task_config}, try_max_times=self.connect_max_try)
        obs = response["obs"] # screenshot:screenshot_b64
        obs["screenshot"] = b64_to_byte(obs["screenshot"])
        logger.info("resetting env done.")
        return obs
    
    def exit(self):
        # terminate env api
        self.close()
        if self.use_api_manager:
            terminate_url = f"{self.server_path}:{self.manager_port}/terminate_env_api"
            data = {"env_id": self.env_id}
            _ = self._request_handler(terminate_url, data, try_max_times=self.connect_max_try)
            return "[remote_env_manager]: Close manager"
        if self.localhost_as_manager:
            self.localhost_manager_process.terminate()
            self.localhost_manager_process.wait()
            logger.info(f"terminate localhost env manager done, freed port: {self.manager_port}")
            return "[localhost_env_manager]: Close manager"

    def close(self):
        close_url = f"{self.server_path}:{self.env_port}/close"
        _ = self._request_handler(close_url, try_max_times=self.connect_max_try)


    def get_screen_size(self) -> tuple[int, int]:
        return self.screen_size
    
    def get_screenshot(self):
        """
        Gets a screenshot(in binary form) from the server. With the cursor.
        """
        screenshot_url = f"{self.server_path}:{self.env_port}/screenshot"
        response = self._request_handler(screenshot_url, method="GET", try_max_times=self.connect_max_try)
        screenshot = b64_to_byte(response["screenshot"])
        return screenshot

    def get_a11tree(self):
        """
        Gets the accessibility tree from the server. None -> no accessibility tree or unexpected error.
        """
        a11tree_url = f"{self.server_path}:{self.env_port}/accessibility"
        response = self._request_handler(a11tree_url, method="GET", try_max_times=self.connect_max_try)
        a11tree = response["accessibility"]
        return a11tree

    def evaluate(self, **kwargs) -> Dict[str, Any]:
        """
        Evaluate the environment.
        """
        # [{"name": "terminate", "parameters": {"status": "success", "answer": null}}]
        if 'evaluator' in self.task_config:
            if self.task_config['evaluator']['func'] == "infeasible":
                last_action = self.action_history[-1][-1]
                if len(self.action_history) > 0 and last_action['name'] == 'terminate':
                    if "status" in last_action["parameters"] and last_action["parameters"]["status"] == "failure":
                        return 1
                    else:
                        return 0
                else:
                    return 0
            else:
                evaluate_url = f"{self.server_path}:{self.env_port}/evaluate"
                response = self._request_handler(evaluate_url, method="GET", try_max_times=self.connect_max_try)
                return response["metric"]
        else:
            return None

    def execute_single_action(self, action: dict):
        """
        Execute a single action, call the corresponding handler function based on the action type

        Args:
            action: {name: str, parameters: dict}
        """
        try:
            action_type = action["name"]
            parameters = action.get("parameters", {})
            if 'x' in parameters or 'y' in parameters:
                parameters['x'], parameters['y'] = round(parameters['x'] * self.screen_size[0]), round(parameters['y'] * self.screen_size[1])

            # action type mapping table
            action_handlers = {
                "moveTo": self._execute_move_to,
                "click": self._execute_click,
                "write": self._execute_write,
                "dragTo": self._execute_drag_to,
                "press": self._execute_press,
                "callUser": self._execute_call_user,
                "wait": self._execute_wait,
                "response": self._execute_response,
                "terminate": self._execute_terminate,
                "doubleClick": self._execute_double_click,
                "rightClick": self._execute_right_click,
                "hotkey": self._execute_hotkey,
                "scroll": self._execute_scroll,
                "keyUp":self._execute_keyup,
                "keyDown":self._execute_keydown,
            }

            # get the corresponding handler function and execute
            handler = action_handlers.get(action_type, None)
            if handler is None:
                logger.warning(f"Unknown action type: {action_type}")
                return False
                
            success = handler(parameters)
            logger.debug(f'{action_type} done {success}')
            return success

        except Exception as e:
            logger.warning(f"exception in parsing {action}: {e}  ")
            return False

    def _execute_single_action(self, command: str):
        """
        Executes a python command on the server.
        It can be used to execute the pyautogui commands
        """

        exec_url = f"{self.server_path}:{self.env_port}/execute"
        _ = self._request_handler(exec_url, {"command": command}, try_max_times=self.connect_max_try)
        time.sleep(self.action_pause)

    def _execute_move_to(self, parameters: dict) -> bool:
        try:
            if 'x' not in parameters or 'y' not in parameters:
                raise KeyError(f"moveTo requires 'x' and 'y' as parameter, current params: {parameters}")
            x = parameters["x"]
            y = parameters["y"]
            move_mode = random.choice([
                "pyautogui.easeInQuad", "pyautogui.easeOutQuad", 
                "pyautogui.easeInOutQuad", "pyautogui.easeInBounce",
                "pyautogui.easeInElastic"
            ])
            default_duration = random.uniform(0.5, 1)
            command = f"pyautogui.moveTo({x}, {y}, {default_duration}, {move_mode})"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing moveTo: {e}")
            return False
    
    def _execute_click(self, parameters: dict) -> bool:
        try:
            x = parameters.get("x", None)
            y = parameters.get("y", None)
            button = parameters.get("button", 'left')
            clicks = int(parameters.get("clicks", "1"))                    
            
            if button not in ['left', 'right', 'middle']:
                raise Exception(f"the button argument {button} is not one of 'left', 'middle', 'right'")
            
            command = f"pyautogui.click(button='{button}', x={x}, y={y}, clicks={clicks})"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing click: {e}")
            return False

    def _execute_drag_to(self, parameters: dict) -> bool:
        try:
            x = parameters.get("x", None)
            y = parameters.get("y", None)
            button = parameters.get("button", "left")
            default_duration = random.uniform(0.5, 1)
            command = f"pyautogui.dragTo({x}, {y}, duration={default_duration}, button='{button}', mouseDownUp=True)"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing dragTo: {e}")
            return False
    
    def _execute_write(self, parameters: dict) -> bool:
        try:
            if 'message' not in parameters:
                raise KeyError(f"write requires 'message' as parameter, current params: {parameters}")
            message = parameters["message"]
            command = "pyautogui.typewrite({:})".format(repr(message))
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing write: {e}")
            return False
    
    def _execute_press(self, parameters: dict) -> bool:
        try:
            if 'keys' not in parameters:
                raise KeyError(f"press requires 'keys' as parameter, current params: {parameters}")
            keys = parameters["keys"]
            presses = parameters.get("presses", 1)
            
            commands = []
            if isinstance(keys, str):
                keys = keys.lower()
                if keys not in KEYBOARD_KEYS:
                    logger.warning(f"Key must be one of {KEYBOARD_KEYS}. Skip current key: {keys}")
                    return False
                for _ in range(presses):
                    commands.append(f"pyautogui.press('{keys}')")
            elif isinstance(keys, list):
                for key in keys:
                    key = key.lower()
                    if key not in KEYBOARD_KEYS:
                        logger.warning(f"Key must be one of {KEYBOARD_KEYS}. Skip current key: {key}")
                        continue
                    for _ in range(presses):
                        commands.append(f"pyautogui.press('{key}')")
            else:
                raise Exception(f"'keys' for press must be type str or list, current keys are: {keys}")
            
            for command in commands:
                self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing press: {e}")
            return False
    
    def _execute_call_user(self, parameters: dict) -> bool:
        logger.info(f"Wait for manual operation")
        return True
    
    def _execute_wait(self, parameters: dict) -> bool:
        try:
            seconds = parameters.get("seconds", 3)
            command = f"time.sleep({seconds})"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing wait: {e}")
            return False
    
    def _execute_keyup(self, parameters: dict) -> bool:
        try:
            key = parameters.get("key", None)          
            command = f"pyautogui.keyUp('{key}')"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing click: {e}")
            return False
        
    def _execute_keydown(self, parameters: dict) -> bool:
        try:
            key = parameters.get("key", None)          
            command = f"pyautogui.keyDown('{key}')"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing click: {e}")
            return False

    def _execute_response(self, parameters: dict) -> bool:
        try:
            if 'answer' not in parameters:
                raise KeyError(f"response requires 'answer', current params: {parameters}")
            answer = parameters["answer"]
            logger.info(f"Answer to the question: {answer}")
            return True
        except Exception as e:
            logger.warning(f"Error executing response: {e}")
            return False
    
    def _execute_terminate(self, parameters: dict) -> bool:
        try:
            if 'status' not in parameters:
                raise KeyError(f"terminate requires 'status', current params: {parameters}")
            status = parameters["status"]
            logger.info(f"Terminate options. Final status: {status}")
            return True
        except Exception as e:
            logger.warning(f"Error executing terminate: {e}")
            return False
    
    def _execute_double_click(self, parameters: dict) -> bool:
        try:
            x = parameters.get("x", None)
            y = parameters.get("y", None)
            button = parameters.get("button", 'left')
            clicks = parameters.get("clicks", "2")
            if clicks != 2:
                logger.warning(f"doubleClick suggests 'clicks' set to 2, current is: {clicks}, ignored")                    
            
            if button not in ['left', 'right', 'middle']:
                raise Exception(f"the button argument {button} is not one of 'left', 'middle', 'right'")
            
            command = f"pyautogui.doubleClick(button='{button}', x={x}, y={y})"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing doubleClick: {e}")
            return False
    
    def _execute_right_click(self, parameters: dict) -> bool:
        try:
            x = parameters.get("x", None)
            y = parameters.get("y", None)
            command = f'pyautogui.rightClick(x={x}, y={y})'
            self._execute_single_action(command)
            return True
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.warning(f"Error executing rightClick: {e}")
            return False
    
    def _execute_hotkey(self, parameters: dict) -> bool:
        try:
            if 'args' not in parameters:
                raise KeyError(f"hotkey requires 'args', current params: {parameters}")
            args = parameters["args"]
            for i, key in enumerate(args):
                key = key.lower()
                if key not in KEYBOARD_KEYS:
                    raise Exception(f"Key must be one of {KEYBOARD_KEYS}")
                args[i] = key
            
            keys_para_rep = "', '".join(args)
            command = f"pyautogui.hotkey('{keys_para_rep}')"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing hotkey: {e}")
            return False
    
    def _execute_scroll(self, parameters: dict) -> bool:
        try:
            if 'clicks' not in parameters:
                raise KeyError(f"scroll requires 'clicks', current params: {parameters}")
            clicks = int(float(parameters['clicks']))
            x = parameters.get("x", None)
            y = parameters.get("y", None)
            if isinstance(x, Tuple):
                x, y = x
            command = f"pyautogui.scroll({clicks}, x={x}, y={y})"
            self._execute_single_action(command)
            return True
        except Exception as e:
            logger.warning(f"Error executing scroll: {e}")
            return False

    def find_all_clickable_elements(self) -> List[Dict[str, Any]]:
        """
        Find all clickable elements on the screen.
        Return: [{id: int, bbox: [lt_w, lt_h, rb_w, rb_h], text: str, name: str}]
        """
        response = self.get_a11tree()
        clickable_elements = get_clickable_elements(response)
        return clickable_elements

    def start_recording(self):
        """
        Start recording the screen.
        """
        start_recording_url = f"{self.server_path}:{self.env_port}/start_recording"
        _ = self._request_handler(start_recording_url, method="GET", try_max_times=self.connect_max_try)

    def end_recording(self, save_path: str):
        """
        End recording the screen.
        """
        end_recording_url = f"{self.server_path}:{self.env_port}/end_recording"
        _ = self._request_handler(end_recording_url, method="POST", data={"save_path": save_path}, try_max_times=self.connect_max_try)   




if __name__ == "__main__":
    action_1 =[{"name": "write", "parameters": {"message": "cd large_files && ls -R"}}, {"name": "press", "parameters": {"keys": "enter", "presses": 1}}]
    action_2 = [{"name": "terminate", "parameters": {"status": "success", "answer": None}}]
    action_history = [action_1, action_2]
    last_action = action_history[-1][-1]
    if len(action_history) > 0 and last_action["parameters"]["status"] == "failure":
            print("1")
    else:
        print("0")
