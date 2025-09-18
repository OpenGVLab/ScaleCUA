import yaml
import paramiko

import time
import subprocess
from pathlib import Path
import json
from typing import Optional
import importlib
import uuid
import tempfile
from utils.logger import ProjectLogger
from utils.basic import reset_applications, transform_pyautogui_line
from launcher.docker.restart_docker import docker_reset_container, docker_start_container, container_exists, docker_remove_container, docker_run_container, DOCKER_RUN_SCRIPT_PATH

import shlex

logger = ProjectLogger()

class MacOSEnv:
    def __init__(self, config_file='config/default_config.yaml'):
        """
        Initialize the MacOSEnv class. Reads configurations from the provided YAML file.
        """
        self.config = self._load_config(config_file)
        self.mode = self.config.get('mode', 'docker')
        self.platform = self.config.get('platform', 'wsl')
        self.docker_name = self.config.get('docker_name', 'evalkit_macos')
        self.host_ip = self.config.get('host_ip', 'localhost')
        self.port = self.config.get('port', 50922)
        self.password = self.config.get('password', '1234')
        self.username = self.config.get('username', 'pipiwu')
        self.action_space = self.config.get('action_space', 'pyautogui')
        
        self.ssh_client = None
        self.sftp_client = None
        self.task = None

    def _load_config(self, config_file):
        """
        Load the YAML configuration file.
        """
        try:
            with open(config_file, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            raise

    def connect_ssh(self):
        """
        Connects to the MacOS docker container via SSH.
        """
        transport = self.ssh_client.get_transport() if self.ssh_client else None
        if self.ssh_client is None or not transport or not transport.is_active():
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                self.ssh_client.connect(self.host_ip, port=self.port, username=self.username, password=self.password)
                logger.info(f"Connected to {self.host_ip} on port {self.port}")
            except Exception as e:
                logger.error(f"SSH connection failed: {e}")
                raise e
        else:
            # logger.info("Already connected to the container.")
            pass
        
    def _reset_env(self):
        self.close_connection()
        if self.mode == "docker":
            docker_remove_container(self.docker_name)
            retry_time = 0
            while container_exists(self.docker_name) and retry_time < 10:
                time.sleep(3)
                retry_time += 1
            if container_exists(self.docker_name):
                 raise TimeoutError(f"Remove Container {self.docker_name} Timeout")
            docker_run_container(self.docker_name, platform=self.platform, docker_name=self.docker_name, port=self.port)
            # if not container_exists(self.docker_name):
            #     logger.info(f"Launching container: {self.docker_name}")
            #     proc = subprocess.Popen(["bash", str(DOCKER_RUN_SCRIPT_PATH)])

            #     for _ in range(100):
            #         try:
            #             self.connect_ssh() 
            #             logger.info("SSH connection established.")
            #             break
            #         except Exception:
            #             time.sleep(2)
            #     else:
            #         logger.error("Failed to SSH into the container after timeout.")
            # docker_reset_container(self.docker_name)
            # # docker_start_container(self.docker_name)
        else:
            raise ValueError(f"Unspported mode: {self.mode}")
                
    def run_command(self, command: str, decode: bool = True):
        if not self.ssh_client:
            self.connect_ssh()
            # raise ValueError("SSH client not connected.")

        stdin, stdout, stderr = self.ssh_client.exec_command(command)

        if decode:
            # logger.info(stdout)
            # logger.info(command)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            return out, err
        else:
            return stdout, stderr  # raw paramiko ChannelFile
        
    def _get_obs(self):
        return {
            "screenshot": self.get_screenshot(),
            "accessibility_tree": None,
            "terminal": None,
            "instruction": None
        }
        
    def step(self, action, pause=2):
        if self.task is None:
            logger.info("Task is None, load a task before taking actions.")
            return None, None, None, None
        self.task.step_no += 1
        self.task.action_history.append(action)

        reward = 0  # always 0, keep the same as OSworld do, maybe insert a PRM later
        done = False 
        info = {}

        # handle the special actions
        if action in ['WAIT', 'FAIL', 'DONE'] or (type(action) == dict and action['action_type'] in ['WAIT', 'FAIL', 'DONE']):
            if action == 'WAIT':
                time.sleep(pause)
            elif action == 'FAIL':
                done = True
                info = {"fail": True}
            elif action == 'DONE':
                done = True
                info = {"done": True}

        if self.action_space == "computer_13":
            # the set of all possible actions defined in the action representation
            self.execute_action(action)
        elif self.action_space == "pyautogui":
            if action in ['WAIT', 'FAIL', 'DONE']:
                pass
            else:
                self.execute_python_command(action)

        time.sleep(pause)
        observation = self._get_obs()

        return observation, reward, done, info
    
    def execute_action(self, action):
        # TODO
        pass
    
    def execute_python_command(self, action: str):
        """
        Upload a temporary Python script to the remote macOS and execute it safely.
        """
 
        remote_tmp_path = f"/tmp/task_script_{uuid.uuid4().hex}.py"

        if self.task is None:
            lines = []
            lines.append("import pyautogui")
            lines.append("import time")
            lines.append("import pynput")
            lines.append("import keyboard")
            lines.append("pyautogui.FAILSAFE = False")
            for line in action.strip().splitlines():
                if line.strip():
                    lines.append(line)
            python_code = "\n".join(lines)

        else:
            lines = []
            for line in action.strip().splitlines():
                stripped = line.strip()
                # current_line = line
                if not stripped or stripped.startswith("#"):
                    continue
                # if "pyautogui.write" in stripped or "pyautogui.typewrite" in stripped:
                #     indent = line[:len(line) - len(line.lstrip())]
                #     line = f"{indent}pyautogui.keyUp('shift'); {line.lstrip()}"
                transformed_line = transform_pyautogui_line(line)
                lines.append(transformed_line)
            command_block = "\n".join(lines)
            python_code = self.task.pkgs_prefix.format(command=command_block)

        try:
            self.connect_sftp()
            with self.sftp_client.open(remote_tmp_path, "w") as remote_script:
                remote_script.write(python_code)

            logger.info(f"Uploaded script to: {remote_tmp_path}")

            full_cmd = f"sudo python3 {remote_tmp_path}"
            stdout, stderr = self.run_command(full_cmd)
            logger.info(f"[exec code] {python_code}")
            logger.info(f"[exec output] {stdout}")
            logger.info(f"[exec error] {stderr}")

            self.run_command(f"rm -f {remote_tmp_path}")

        except Exception as e:
            logger.error(f"execute_python_command failed: {e}")
        
    def get_screenshot(self, remote_tmp_path: str = "/tmp/fullscreen_dock.png") -> bytes:
        """
        Capture a fullscreen screenshot on the remote macOS system and return it as raw image bytes.

        :param remote_tmp_path: Remote temporary path to store screenshot
        :return: Screenshot image content as bytes (e.g., PNG format); returns b'' on failure
        """
        capture_cmd = f"sudo screencapture -C {remote_tmp_path}"

        try:
            self.connect_ssh()
            logger.info("Executing screencapture command in macOS...")
            stdout, stderr = self.run_command(capture_cmd, decode=False)

            out = stdout.read().decode().strip() if hasattr(stdout, "read") else ""
            err = stderr.read().decode().strip() if hasattr(stderr, "read") else ""
            logger.debug(f"[stdout] {out}")
            logger.debug(f"[stderr] {err}")

            self.connect_sftp()
            with self.sftp_client.open(remote_tmp_path, "rb") as remote_file:
                image_data = remote_file.read()

            logger.info("Screenshot successfully captured and returned.")
            return image_data

        except Exception as e:
            logger.error(f"get_screenshot failed: {e}")
            return b""
        
    def start_recording(self, remote_path="/tmp/screen_recording_test.mp4", resolution="1920x1080", fps=30):
        """
        Starts screen recording on macOS using ffmpeg.
        """
        cmd = f'sudo /usr/local/bin/ffmpeg -y -f avfoundation -framerate {fps} -i "0:none" "{remote_path}" > /dev/null 2>&1 & echo $! > /tmp/ffmpeg_pid'
        # cmd = f'sudo /usr/local/bin/ffmpeg -y -f avfoundation -framerate {fps} -i "0:none" "{remote_path}" &'

        out, err = self.run_command(cmd)
        logger.info(out)
        self.recording_path = remote_path
        self._recording_start_time = time.time()
        logger.info(f"Screen recording started at {remote_path}.")

    def end_recording(self, local_save_path: str):
        """
        Stops screen recording and fetches the file to local path.
        """
        # Find and kill ffmpeg process
        out, err = self.run_command('sudo kill $(cat /tmp/ffmpeg_pid)')
        # logger.info(err)
        logger.info("Stopped screen recording.")

        # Wait briefly to ensure file write is finished
        time.sleep(2)

        # Fetch the file
        remote_path = getattr(self, "recording_path", "/tmp/screen_recording_test.mp4")
        local_path = Path(local_save_path)
        self.connect_sftp()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.sftp_client.get(remote_path, str(local_path))
        logger.info(f"Recording saved to {local_save_path}")
        
    def connect_sftp(self):
        self.connect_ssh()
        if self.sftp_client is None:
            self.sftp_client = self.ssh_client.open_sftp()

    def close_connection(self):
        """
        Close all the connection.
        """
        if self.sftp_client:
            self.sftp_client.close()
            self.sftp_client = None
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            
    def init_task_info(self, task_json_path: str):
        path = Path(task_json_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Task JSON file not found at: {path}")
        self.task: Optional[TaskController] = TaskController(path)
        
    def init_task(self, task_json_path: str):
        
        def disable_caps_lock():
            jxa_script = '''
            ObjC.import("IOKit");

            (() => {
                var ioConnect = Ref();
                var state = Ref();

                $.IOServiceOpen(
                    $.IOServiceGetMatchingService(
                        $.kIOMasterPortDefault,
                        $.IOServiceMatching($.kIOHIDSystemClass)
                    ),
                    $.mach_task_self_,
                    $.kIOHIDParamConnectType,
                    ioConnect
                );

                $.IOHIDGetModifierLockState(ioConnect, $.kIOHIDCapsLockState, state);
                if (state[0]) {
                    $.IOHIDSetModifierLockState(ioConnect, $.kIOHIDCapsLockState, 0);
                }

                $.IOServiceClose(ioConnect);
            })();
            '''.strip()

            stdout, _ = self.run_command(f"osascript -l JavaScript -e {shlex.quote(jxa_script)}")
            logger.info("====Close Caps Lock====")
            logger.info(stdout)
            logger.info(_)

        disable_caps_lock()
        
        self.init_task_info(task_json_path)
        if self.task is None:
            raise ValueError("TaskController was not initialized.")

        if (not self.task.config) or len(self.task.config) == 0:
            return
        
        for step in self.task.config:
            step_type = step.get("type")
            parameters = step.get("parameters", {})

            if step_type == "cmd":
                commands = parameters.get("command", [])
                for cmd in commands:
                    stdout, _ = self.run_command(cmd)
                    # logger.info(stdout)
                    # logger.info(_)
            else:
                try:
                    basic_utils = importlib.import_module("utils.basic")
                    if hasattr(basic_utils, step_type):
                        func = getattr(basic_utils, step_type)
                        logger.info(f"Executing: {step_type} with {parameters}")
                        func(self, **parameters)
                    else:
                        logger.warning(f"Function '{step_type}' not found in utils.basic")
                except Exception as e:
                    logger.error(f"Error executing step '{step_type}': {e}")


    def evaluate_task(self):
        """
        Evaluate the task using the evaluation spec provided in `self.task.evaluator`.

        This function executes a list of getter functions and evaluates their outputs
        using metric functions, as specified in the evaluator config.

        Returns:
            bool: True if all/any evaluations pass based on the configured logical conjunction.
        """
        if not self.task or not self.task.evaluator:
            logger.warning("No evaluator found in task.")
            return False

        evaluator = self.task.evaluator
        func_list = evaluator.get("func", [])
        expected_list = evaluator.get("expected", [])
        param_list = evaluator.get("parameters", [{}] * len(func_list))
        conj = evaluator.get("conj", "and")

        if not (len(func_list) == len(expected_list) == len(param_list)):
            raise ValueError("Evaluator 'func', 'parameters', and 'expected' lists must be the same length.")

        results = []
        
        # Reset the applications
        reset_applications(self, self.task.related_apps)

        for func_name, params, expected in zip(func_list, param_list, expected_list):
            # Load the getter function from evaluators.getter (already imported in __init__.py)
            try:
                evaluators_getter = importlib.import_module("evaluators.getter")
                getter_func = getattr(evaluators_getter, func_name)
                # logger.info(getter_func)
            except AttributeError as e:
                logger.error(f"Getter function '{func_name}' not found in 'evaluators': {e}")
                results.append(False)
                continue

            # Execute the getter function
            try:
                output = getter_func(self, **params)
            except Exception as e:
                logger.error(f"Error calling getter '{func_name}': {e}")
                results.append(False)
                continue

            # Evaluate the result using the metric function
            try:
                metric_type = expected.get("type")
                metric_func_name = expected["rules"]["func"]
                metric_params = expected["rules"]["parameters"]

                metric_module = importlib.import_module(f"evaluators.metrics.{metric_type}")
                metric_func = getattr(metric_module, metric_func_name)

                # Call the metric function with correct parameter format
                if isinstance(metric_params, list):
                    match = metric_func(output, *metric_params)
                elif isinstance(metric_params, dict):
                    match = metric_func(output, **metric_params)
                else:
                    match = metric_func(output, metric_params)

                results.append(match)
                logger.info(f"[Evaluation] {func_name} => {output} vs {metric_func_name}({metric_params}) => {match}")

            except Exception as e:
                logger.error(f"Evaluation failed for '{func_name}': {e}")
                results.append(False)

        # Combine results based on conjunction type: 'and' or 'or'
        return all(results) if conj == "and" else any(results)

class TaskController:
    def __init__(self, json_path: Path, pkgs_prefix: str = "from AppKit import NSBundle; app_info = NSBundle.mainBundle().infoDictionary(); app_info[\"LSBackgroundOnly\"] = \"1\"; import pyautogui; import time; import pynput; import keyboard; pyautogui.FAILSAFE = False; {command}"):
        self.json_path = Path(json_path)
        self.task = self._load_task()

        self.task_id = self.task.get("id")
        self.system_img = self.task.get("system_img", "default")
        self.instruction = self.task.get("instruction", "")
        self.config = self.task.get("config", [])
        self.related_apps = self.task.get("related_apps", [])
        self.evaluator = self.task.get("evaluator", {})
        
        self.step_no = 0
        self.action_history = []
        self.pkgs_prefix = pkgs_prefix
        

    def _load_task(self):
        if not self.json_path.exists():
            logger.error(f"Task JSON file not found: {self.json_path}")
            raise FileNotFoundError(f"Missing task definition file: {self.json_path}")

        with open(self.json_path, 'r', encoding='utf-8') as f:
            task_data = json.load(f)
            logger.info(f"Loaded task from {self.json_path}")
            return task_data

    def get_config_steps(self):
        return self.config

    def get_evaluator_spec(self):
        return self.evaluator

    def get_instruction(self):
        return self.instruction

    def get_related_apps(self):
        return self.related_apps
    