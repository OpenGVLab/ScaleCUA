from __future__ import annotations

import logging
import os
import subprocess
import time
import json
from typing import Callable, Any, Optional, Tuple
from typing import List, Dict, Union

import gymnasium as gym

from desktop_env.controllers.python import PythonController
from desktop_env.controllers.setup import SetupController
from desktop_env.controllers.vm import VMController
from desktop_env.evaluators import metrics, getters

logger = logging.getLogger("desktopenv.env")

Metric = Callable[[Any, Any], float]
Getter = Callable[[gym.Env, Dict[str, Any]], Any]


def _execute_command(command: List[str]) -> None:
    def _is_contained_in(a, b):
        for v in set(a):
            if a.count(v) > b.count(v):
                return False
        return True

    # Specially handled for the `vmrun` command in Windows
    # if _is_contained_in(["vmrun", "-T", "ws", "start"], command):
    #     p = subprocess.Popen(command)
    #     p.wait()
    # else:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise Exception("\033[91m" + result.stdout + result.stderr + "\033[0m")
    return result.stdout


class DesktopEnv(gym.Env):
    """
    DesktopEnv with OpenAI Gym interface. It provides a desktop environment for setting and evaluating desktop automation tasks.
    """

    def __init__(
        self,
        snapshot_name: str = "init_state",
        action_space: str = "computer_13",
        cache_dir: str = "cache",
        screen_size: Tuple[int] = (1920, 1080),
        headless: bool = False,
        a11y_backend: str = "uia",
        require_a11y_tree: bool = True,
        require_terminal: bool = False,
        emulator_ip: str = None,
    ):
        """
        Args:
            snapshot_name (str): snapshot name to revert to, default to "init_state"
            action_space (str): "computer_13" | "pyautogui"
            cache_dir (str): cache directory to cache task-related stuffs like
              reference file for evaluation
            screen_size (Tuple[int]): screen size of the VM
            headless (bool): whether to run the VM in headless mode
            require_a11y_tree (bool): whether to require accessibility tree
            require_terminal (bool): whether to require terminal output
        """

        # Initialize environment variables
        self.snapshot_name = snapshot_name
        self.cache_dir_base: str = cache_dir
        # todo: add the logic to get the screen size from the VM
        self.headless = headless
        self.a11y_backend = a11y_backend
        self.require_a11y_tree = require_a11y_tree
        self.require_terminal = require_terminal

        # Initialize emulator and controller
        logger.info("Initializing...")
        if emulator_ip is None:
            self.remote_vm = False
            self._start_emulator()
            self.vm_ip = self._get_vm_ip()
        else:
            self.remote_vm = True
            logger.info("Using external emulator...")
            self.vm_ip = emulator_ip
            # self._wait_emulator()

        self.controller = PythonController(vm_ip=self.vm_ip)
        self.setup_controller = SetupController(
            vm_ip=self.vm_ip, cache_dir=self.cache_dir_base
        )
        self.vm_controller = VMController(cache_dir=self.cache_dir_base)

        logger.info(
            "(QEMU) get_status: %s",
            json.dumps(self.vm_controller.get_status(), indent=2),
        )

        # mode: human or machine
        self.instruction = None
        assert action_space in ["computer_13", "pyautogui", "code_block"]
        self.action_space = action_space

        # episodic stuffs, like counters, will be updated or reset
        # when calling self.reset()
        self._traj_no: int = -1
        self._step_no: int = 0
        self.action_history: List[Dict[str, any]] = []

    @property
    def vm_platform(self):
        return self.controller.get_vm_platform()

    @property
    def vm_screen_size(self):
        return self.controller.get_vm_screen_size()

    def _wait_emulator(self):
        """
        Continuously calls `get_probe` until it returns True, indicating the VM is ready.
        Polls every 5 seconds up to a specified maximum retry limit.
        """
        max_attempts = 20
        attempt = 0

        while attempt < max_attempts:
            if self.controller.get_probe():  # Check if VM is ready
                logger.info("VM is up and ready.")
                return True

            logger.info("VM not ready yet. Retrying in 5 seconds...")
            time.sleep(5)  # Wait for 5 seconds before retrying
            attempt += 1

        logger.error("VM did not become ready after %d attempts.", max_attempts)
        return False

    def _get_vm_ip(self):
        return self.vm_ip

    def _save_state(self):
        # TODO: test this
        # self.vm_controller.take_snapshot(self.snapshot_name)
        logger.error("Not implemented! Saving state is not supported for remote VMs!")

    def _get_screenshot(self):
        screenshot = None
        # Get the screenshot and save to the image_path
        max_retries = 20
        for _ in range(max_retries):
            screenshot = self.vm_controller.take_screenshot()
            if screenshot is not None:
                break
            print("Retrying to get screenshot...")
            time.sleep(1)

        if screenshot is None:
            logger.error("Failed to get screenshot!")

        return screenshot

    def _get_obs(self):
        screenshot = self._get_screenshot()
        # screenshot = None
        # print("screenshot done")
        accessibility_tree = (
            self.controller.get_accessibility_tree(backend=self.a11y_backend)
            if self.require_a11y_tree
            else None
        )
        # accessibility_tree = "test"
        # accessibility_tree = None
        # print("accessibility_tree done")
        terminal = (
            self.controller.get_terminal_output() if self.require_terminal else None
        )
        # terminal = None
        obs = self.controller.get_obs_winagent()
        if obs is not None:
            (
                window_image,
                window_title,
                window_rect,
                window_names_str,
                computer_clipboard,
                human_input,
            ) = obs
            return {
                "screenshot": screenshot,
                "accessibility_tree": accessibility_tree,
                "terminal": terminal,
                "instruction": self.instruction,
                "window_title": window_title,
                "window_rect": window_rect,
                "window_image": window_image,
                "window_names_str": window_names_str,
                "computer_clipboard": computer_clipboard,
                "human_input": human_input,
            }
        else:
            return None
        # print("terminal done")
        # print("LOG: Observation collected")

    def _set_task_info(self, task_config: Dict[str, Any]):
        self.task_id: str = task_config["id"]
        self.cache_dir: str = os.path.join(self.cache_dir_base, self.task_id)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.instruction = task_config["instruction"]
        self.config = task_config["config"] if "config" in task_config else []

        # evaluator dict
        # func -> metric function string, or list of metric function strings
        # conj -> conjunction of multiple metrics if func is a list with length > 1, "and"/"or"
        # result -> result getter config, or list of result getter configs
        # expected (optional) -> expected getter config, or list of expected getter configs
        # options (optional) -> metric options, or list of metric options
        # if func is a str list, then result, expected (if exists), options (if exists) should also be lists of the same length
        # even if one of the metrics does not need expected or options field, it should be included in the list with None
        self.evaluator = task_config["evaluator"]
        self.metric: Metric = (
            [getattr(metrics, func) for func in self.evaluator["func"]]
            if isinstance(self.evaluator["func"], list)
            else getattr(metrics, self.evaluator["func"])
        )
        self.metric_conj: str = self.evaluator.get(
            "conj", "and"
        )  # take conjunction of multiple metrics
        if "result" in self.evaluator and len(self.evaluator["result"]) > 0:
            self.result_getter: Getter = (
                [
                    getattr(getters, "get_{:}".format(res["type"]))
                    for res in self.evaluator["result"]
                ]
                if isinstance(self.evaluator["result"], list)
                else getattr(
                    getters, "get_{:}".format(self.evaluator["result"]["type"])
                )
            )
        else:
            self.result_getter = (
                [None] * len(self.metric) if isinstance(self.metric, list) else None
            )

        if "expected" in self.evaluator and len(self.evaluator["expected"]) > 0:
            self.expected_getter: Getter = (
                [
                    getattr(getters, "get_{:}".format(exp["type"])) if exp else None
                    for exp in self.evaluator["expected"]
                ]
                if isinstance(self.evaluator["expected"], list)
                else getattr(
                    getters, "get_{:}".format(self.evaluator["expected"]["type"])
                )
            )
        else:
            self.expected_getter = (
                [None] * len(self.metric) if isinstance(self.metric, list) else None
            )
        self.metric_options: Union[List[Dict[str, Any]], Dict[str, Any]] = (
            [opt if opt else {} for opt in self.evaluator["options"]]
            if isinstance(self.evaluator.get("options", {}), list)
            else (
                self.evaluator["options"]
                if "options" in self.evaluator
                else [{}] * len(self.metric) if isinstance(self.metric, list) else {}
            )
        )

        assert not isinstance(self.evaluator["func"], list) or (
            len(self.metric)
            == len(self.result_getter)
            == len(self.expected_getter)
            == len(self.metric_options)
        )

    def reset(
        self, task_config: Optional[Dict[str, Any]] = None, seed=None, options=None
    ) -> Dict[str, Any]:
        logger.info("Resetting environment...")

        logger.info("Switching task...")

        logger.info("Setting counters...")
        self._traj_no += 1
        self._step_no = 0
        self.action_history.clear()

        logger.info("Reverting to snapshot to {}...".format(self.snapshot_name))

        if self.remote_vm:
            # TODO: Implement this
            # self.controller.revert_to_snapshot(self.snapshot_name)

            logger.error(
                "Not implemented! Reverting to snapshot is not supported for remote VMs! Closing all applications instead"
            )
            self.setup_controller._close_all_setup()

        time.sleep(5)

        logger.info("Starting emulator...")
        if self.remote_vm:
            self._wait_emulator()
        # else:
        #     self._start_emulator() # already started
        logger.info("Emulator started.")

        if task_config is not None:
            logger.info("Cleaning up existing task files...")
            self.setup_controller._clean_up_files()

            logger.info("Setting task info...")
            self._set_task_info(task_config)

            # logger.info(f"TASK RESULT GETTER: {self.result_getter}")
            # logger.info(f"EXPECTED RESULT GETTER: {self.expected_getter}")
            # logger.info(f"TASK METRIC: {self.metric}")
            # logger.info(f"TASK EVALUATOR: {self.evaluator}")

            self.setup_controller.reset_cache_dir(self.cache_dir)
            logger.info("Setting up environment...")
            self.setup_controller.setup(self.config)
            time.sleep(5)
            logger.info("Environment setup complete.")

        observation = self._get_obs()
        return observation

    def step(self, action, pause=0.5):
        self._step_no += 1
        self.action_history.append(action)

        reward = 0  # todo: Define reward calculation for each example
        done = False  # todo: Define episode termination condition for each example
        info = {}
        # handle the special actions
        if action in ["WAIT", "FAIL", "DONE"]:
            if action == "WAIT":
                time.sleep(pause)
            elif action == "FAIL":
                done = True
                info = {"fail": True}
            elif action == "DONE":
                done = True
                info = {"done": True}
        else:
            if self.action_space == "computer_13":
                # the set of all possible actions defined in the action representation
                self.controller.execute_action(action)
            elif self.action_space == "pyautogui":
                print(
                    "\n******************************** <Executing action> ********************************\n",
                    action,
                )
                print(
                    "\n******************************** </Executing action> ********************************\n"
                )
                if action in ["WAIT", "FAIL", "DONE"]:
                    self.controller.execute_action(action)
                else:
                    # the set of all possible python commands insides `pyautogui`
                    self.controller.execute_python_command(action)
            elif self.action_space == "code_block":
                self.controller.execute_python_windows_command(action)
            else:
                raise ValueError("Unknown action space: {}".format(self.action_space))
        # wait a little before taking the next observation
        time.sleep(pause)
        observation = self._get_obs()

        return observation, reward, done, info

    def evaluate(self):
        """
        Evaluate whether the task is successfully completed.
        """

        self.setup_controller.setup(self.evaluator.get("postconfig", []))

        # logger.info(f"ACTION HISTORY: {self.action_history}")

        if self.evaluator["func"] == "infeasible":
            if len(self.action_history) > 0 and self.action_history[-1] == "FAIL":
                # logger.info("Infeasible task and last agent action = FAIL")
                return 1
            else:
                # logger.info("Infeasible task but last agent action != FAIL")
                return 0
        else:
            if len(self.action_history) > 0 and self.action_history[-1] == "FAIL":
                # logger.info("Feasible task but last agent = FAIL")
                return 0

        if type(self.metric) == list:
            results = []
            for idx, metric in enumerate(self.metric):
                try:
                    config = self.evaluator["result"][idx]
                    result_state = self.result_getter[idx](self, config)
                except FileNotFoundError:
                    logger.error("File not found!")
                    if self.metric_conj == "and":
                        return 0

                expected = self.evaluator["expected"][idx]
                expected_state = (
                    self.expected_getter[idx](self, expected) if expected else None
                )

                metric: int = (
                    metric(result_state, expected_state, **self.metric_options[idx])
                    if expected_state is not None
                    else metric(result_state, **self.metric_options[idx])
                )

                if self.metric_conj == "and" and float(metric) == 0.0:
                    return 0
                elif self.metric_conj == "or" and float(metric) == 1.0:
                    return 1
                else:
                    results.append(metric)
            return (
                sum(results) / len(results)
                if self.metric_conj == "and"
                else max(results)
            )
        else:
            try:
                result_state = self.result_getter(self, self.evaluator["result"])
            except FileNotFoundError:
                logger.error("File not found!")
                return 0
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                return 0
            expected_state = (
                self.expected_getter(self, self.evaluator["expected"])
                if "expected" in self.evaluator
                else None
            )

            # logger.info(f"RESULT STATE: {result_state}")
            # logger.info(f"EXPECTED STATE: {expected_state}")

            metric: float = (
                self.metric(result_state, expected_state, **self.metric_options)
                if expected_state is not None
                else self.metric(result_state, **self.metric_options)
            )

        if isinstance(metric, (float, int, bool)):
            return metric
        else:
            logger.error(
                "Task metric value produced is neither numeric nor boolean: returning 0 instead"
            )
            return 0

        return metric

    def render(self, mode="rgb_array"):
        if mode == "rgb_array":
            return self._get_screenshot()
        else:
            raise ValueError("Unsupported render mode: {}".format(mode))

    def close(self):
        logger.info("Stopping emulator...")
        if self.remote_vm:
            # TODO: Implement this
            logger.error(
                "Not implemented! Stopping emulator is not supported for remote VMs!"
            )
        # else:
        #     _execute_command(["vmrun", "stop", self.path_to_vm])
