import json
import logging
import random
from typing import Any, Dict, Optional

import requests

from desktop_env.envs.actions import KEYBOARD_KEYS

logger = logging.getLogger("desktopenv.pycontroller")

A11Y_TIMEOUT = 300 # max 5 minutes to fetch the uia tree


class PythonController:
    def __init__(self, vm_ip: str, pkgs_prefix: str = "import pyautogui; import time; pyautogui.FAILSAFE = False; {command}"):
        self.vm_ip = vm_ip
        self.http_server = f"http://{vm_ip}:5000"
        self.pkgs_prefix = pkgs_prefix  # fixme: this is a hacky way to execute python commands. fix it and combine it with installation of packages

    def get_probe(self):
        """
        Queries the server probe endpoint to check if the VM is running.
        """
        response = requests.get(self.http_server + "/probe")
        if response.status_code == 200:
            return True
        else:
            logger.error("Failed to get a successful response from the VM.")
            return False
     
    def update_computer(self, rects, window_rect, screenshot, scale, clipboard_content, swap_ctrl_alt=False):
        """
        Updates the computer object in the server
        """
        headers = {
            'Content-Type': 'application/json'
        }

        import base64  
        from PIL import Image  
        import io  
  
        def image_to_base64_str(image):  
            buffered = io.BytesIO()  
            image.save(buffered, format="PNG")  # you can change the format to your preferred format  
            img_str = base64.b64encode(buffered.getvalue()).decode()  
            return img_str  
        
        screenshot_str = image_to_base64_str(screenshot)  

        payload = {  
            'rects': rects,  
            'window_rect': window_rect,  
            'screenshot': screenshot_str,  
            'scale': scale,  
            'clipboard_content': clipboard_content,  
            'swap_ctrl_alt': swap_ctrl_alt  
        }  
        response = requests.post(self.http_server + "/update_computer", headers=headers, json=payload)
        if response.status_code == 200:
            logger.info("Updated computer successfully")
        else:
            logger.error("Failed to update computer. Status code: %d", response.status_code)


    def get_screenshot(self):
        """
        Gets a screenshot from the server. With the cursor.
        """
        response = requests.get(self.http_server + "/screenshot")
        if response.status_code == 200:
            return response.content
        else:
            logger.error("Failed to get screenshot. Status code: %d", response.status_code)
            return None

    def get_terminal_output(self):
        """ Gets the terminal output from the server. None -> no terminal output or unexpected error.
        """
        response = requests.get(self.http_server + "/terminal")
        if response.status_code == 200:
            return response.json()["output"]
        else:
            logger.error("Failed to get terminal output. Status code: %d", response.status_code)
            return None
        
    def get_obs_winagent(self):
        """ Gets the observations for the agent from the server. None -> no observations or unexpected error.
        """
        import base64
        import io
        from PIL import Image
        response = requests.get(self.http_server + "/obs_winagent")
        if response.status_code == 200:
            image_str = response.json()["image"]
            image = Image.open(io.BytesIO(base64.b64decode(image_str)))
            window_title = response.json()["window_title"]
            rect = response.json()["rect"]
            window_names_str = response.json()["window_names_str"]
            computer_clipboard = response.json()["computer_clipboard"]
            human_input = response.json()["human_input"]
            return image, window_title, rect, window_names_str, computer_clipboard, human_input
        else:
            logger.error("Failed to get the observations for the agent from the server. Status code: %d", response.status_code)
            return None 

    def get_accessibility_tree(self, backend: Optional[str] = None) -> Optional[str]:
        try:
            response: requests.Response = requests.get(self.http_server + (f"/accessibility?backend={backend}" if backend else "/accessibility"), timeout=A11Y_TIMEOUT)
            if response.status_code == 200:
                return response.json().get("AT")
            else:
                logger.error("Failed to get accessibility tree. Status code: %d", response.status_code)
                return None
        except requests.Timeout:
            logger.error("Request timed out while trying to get accessibility tree.")
            return None

    def get_file(self, file_path: str):
        """
        Gets a file from the server.
        """
        response = requests.post(self.http_server + "/file", data={"file_path": file_path})
        logger.info(f"GET_FILE, file_path: {file_path}")
        if response.status_code == 200:
            logger.info("File downloaded successfully")
            return response.content
        else:
            logger.error("Failed to get file. Status code: %d", response.status_code)
            return None

    def save_state(self, state: str):
        """
        Saves the state to the server.
        """
        payload = {"snapshot_name": state}
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/save_state", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("State saved successfully")
        else:
            logger.error("Failed to save state. Status code: %d", response.status_code)
            
    def revert_to_snapshot(self, state: str):
        """
        Reverts to a snapshot on the server.
        """
        payload = {"snapshot_name": state}
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/revert_to_snapshot", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("Reverted to snapshot successfully")
        else:
            logger.error("Failed to revert to snapshot. Status code: %d", response.status_code)
    
    def execute_python_windows_command(self, command: str) -> None:
        """
        Executes a python command on the server.
        It can be used to execute the pyautogui commands, or... any other python command. who knows?
        """

        if command in ['WAIT', 'FAIL', 'DONE']:
            return

        payload = {"command": command}

        headers = {
            'Content-Type': 'application/json'
        }


        try:
            response = requests.post(self.http_server + "/execute_windows", headers=headers, json=payload, timeout=90)
            if response.status_code == 200:
                logger.info("Command executed successfully: %s", response.text)
            else:
                logger.error("Failed to execute command. Status code: %d", response.status_code)
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("An error occurred while trying to execute the command: %s", e)

    def execute_python_command(self, command: str) -> None:
        """
        Executes a python command on the server.
        It can be used to execute the pyautogui commands, or... any other python command. who knows?
        """
        # command_list = ["python", "-c", self.pkgs_prefix.format(command=command)]
        command_list = ["python", "-c", self.pkgs_prefix.format(command=command)]
        payload = json.dumps({"command": command_list, "shell": False})
        headers = {
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(self.http_server + "/execute", headers=headers, data=payload, timeout=90)
            if response.status_code == 200:
                logger.info("Command executed successfully: %s", response.text)
            else:
                logger.error("Failed to execute command. Status code: %d", response.status_code)
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("An error occurred while trying to execute the command: %s", e)

    def execute_action(self, action: Dict[str, Any]):
        """
        Executes an action on the server computer.
        """
        if action in ['WAIT', 'FAIL', 'DONE']:
            return

        action_type = action["action_type"]
        parameters = action["parameters"] if "parameters" in action else {}
        move_mode = random.choice(
            ["pyautogui.easeInQuad", "pyautogui.easeOutQuad", "pyautogui.easeInOutQuad", "pyautogui.easeInBounce",
             "pyautogui.easeInElastic"])
        duration = random.uniform(0.5, 1)

        if action_type == "MOVE_TO":
            if parameters == {} or None:
                self.execute_python_command("pyautogui.moveTo()")
            elif "x" in parameters and "y" in parameters:
                x = parameters["x"]
                y = parameters["y"]
                self.execute_python_command(f"pyautogui.moveTo({x}, {y}, {duration}, {move_mode})")
            else:
                raise Exception(f"Unknown parameters: {parameters}")

        elif action_type == "CLICK":
            if parameters == {} or None:
                self.execute_python_command("pyautogui.click()")
            elif "button" in parameters and "x" in parameters and "y" in parameters:
                button = parameters["button"]
                x = parameters["x"]
                y = parameters["y"]
                if "num_clicks" in parameters:
                    num_clicks = parameters["num_clicks"]
                    self.execute_python_command(
                        f"pyautogui.click(button='{button}', x={x}, y={y}, clicks={num_clicks})")
                else:
                    self.execute_python_command(f"pyautogui.click(button='{button}', x={x}, y={y})")
            elif "button" in parameters and "x" not in parameters and "y" not in parameters:
                button = parameters["button"]
                if "num_clicks" in parameters:
                    num_clicks = parameters["num_clicks"]
                    self.execute_python_command(f"pyautogui.click(button='{button}', clicks={num_clicks})")
                else:
                    self.execute_python_command(f"pyautogui.click(button='{button}')")
            elif "button" not in parameters and "x" in parameters and "y" in parameters:
                x = parameters["x"]
                y = parameters["y"]
                if "num_clicks" in parameters:
                    num_clicks = parameters["num_clicks"]
                    self.execute_python_command(f"pyautogui.click(x={x}, y={y}, clicks={num_clicks})")
                else:
                    self.execute_python_command(f"pyautogui.click(x={x}, y={y})")
            else:
                raise Exception(f"Unknown parameters: {parameters}")

        elif action_type == "MOUSE_DOWN":
            if parameters == {} or None:
                self.execute_python_command("pyautogui.mouseDown()")
            elif "button" in parameters:
                button = parameters["button"]
                self.execute_python_command(f"pyautogui.mouseDown(button='{button}')")
            else:
                raise Exception(f"Unknown parameters: {parameters}")

        elif action_type == "MOUSE_UP":
            if parameters == {} or None:
                self.execute_python_command("pyautogui.mouseUp()")
            elif "button" in parameters:
                button = parameters["button"]
                self.execute_python_command(f"pyautogui.mouseUp(button='{button}')")
            else:
                raise Exception(f"Unknown parameters: {parameters}")

        elif action_type == "RIGHT_CLICK":
            if parameters == {} or None:
                self.execute_python_command("pyautogui.rightClick()")
            elif "x" in parameters and "y" in parameters:
                x = parameters["x"]
                y = parameters["y"]
                self.execute_python_command(f"pyautogui.rightClick(x={x}, y={y})")
            else:
                raise Exception(f"Unknown parameters: {parameters}")

        elif action_type == "DOUBLE_CLICK":
            if parameters == {} or None:
                self.execute_python_command("pyautogui.doubleClick()")
            elif "x" in parameters and "y" in parameters:
                x = parameters["x"]
                y = parameters["y"]
                self.execute_python_command(f"pyautogui.doubleClick(x={x}, y={y})")
            else:
                raise Exception(f"Unknown parameters: {parameters}")

        elif action_type == "DRAG_TO":
            if "x" in parameters and "y" in parameters:
                x = parameters["x"]
                y = parameters["y"]
                self.execute_python_command(
                    f"pyautogui.dragTo({x}, {y}, duration=1.0, button='left', mouseDownUp=True)")

        elif action_type == "SCROLL":
            # todo: check if it is related to the operating system, as https://github.com/TheDuckAI/DuckTrack/blob/main/ducktrack/playback.py pointed out
            if "dx" in parameters and "dy" in parameters:
                dx = parameters["dx"]
                dy = parameters["dy"]
                self.execute_python_command(f"pyautogui.hscroll({dx})")
                self.execute_python_command(f"pyautogui.vscroll({dy})")
            elif "dx" in parameters and "dy" not in parameters:
                dx = parameters["dx"]
                self.execute_python_command(f"pyautogui.hscroll({dx})")
            elif "dx" not in parameters and "dy" in parameters:
                dy = parameters["dy"]
                self.execute_python_command(f"pyautogui.vscroll({dy})")
            else:
                raise Exception(f"Unknown parameters: {parameters}")

        elif action_type == "TYPING":
            if "text" not in parameters:
                raise Exception(f"Unknown parameters: {parameters}")
            # deal with special ' and \ characters
            # text = parameters["text"].replace("\\", "\\\\").replace("'", "\\'")
            # self.execute_python_command(f"pyautogui.typewrite('{text}')")
            text = parameters["text"]
            self.execute_python_command("pyautogui.typewrite({:})".format(repr(text)))

        elif action_type == "PRESS":
            if "key" not in parameters:
                raise Exception(f"Unknown parameters: {parameters}")
            key = parameters["key"]
            if key.lower() not in KEYBOARD_KEYS:
                raise Exception(f"Key must be one of {KEYBOARD_KEYS}")
            self.execute_python_command(f"pyautogui.press('{key}')")

        elif action_type == "KEY_DOWN":
            if "key" not in parameters:
                raise Exception(f"Unknown parameters: {parameters}")
            key = parameters["key"]
            if key.lower() not in KEYBOARD_KEYS:
                raise Exception(f"Key must be one of {KEYBOARD_KEYS}")
            self.execute_python_command(f"pyautogui.keyDown('{key}')")

        elif action_type == "KEY_UP":
            if "key" not in parameters:
                raise Exception(f"Unknown parameters: {parameters}")
            key = parameters["key"]
            if key.lower() not in KEYBOARD_KEYS:
                raise Exception(f"Key must be one of {KEYBOARD_KEYS}")
            self.execute_python_command(f"pyautogui.keyUp('{key}')")

        elif action_type == "HOTKEY":
            if "keys" not in parameters:
                raise Exception(f"Unknown parameters: {parameters}")
            keys = parameters["keys"]
            if not isinstance(keys, list):
                raise Exception("Keys must be a list of keys")
            for key in keys:
                if key.lower() not in KEYBOARD_KEYS:
                    raise Exception(f"Key must be one of {KEYBOARD_KEYS}")

            keys_para_rep = "', '".join(keys)
            self.execute_python_command(f"pyautogui.hotkey('{keys_para_rep}')")

        elif action_type =="COMPUTER_CODE":
            if "code" not in parameters:
                raise Exception(f"Unknown parameters: {parameters}")
            code = parameters["code"]
            self.execute_python_command(code)

        elif action_type in ['WAIT', 'FAIL', 'DONE']:
            pass

        else:
            raise Exception(f"Unknown action type: {action_type}")

    # Record video
    def start_recording(self):
        """
        Starts recording the screen.
        """
        response = requests.post(self.http_server + "/start_recording")
        if response.status_code == 200:
            logger.info("Recording started successfully")
        else:
            logger.error("Failed to start recording. Status code: %d", response.status_code)

    def end_recording(self, dest: str):
        """
        Ends recording the screen.
        """
        try:
            response = requests.post(self.http_server + "/end_recording")
            if response.status_code == 200:
                logger.info("Recording stopped successfully")
                with open(dest, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            else:
                logger.error("Failed to stop recording. Status code: %d", response.status_code)
                return None
        except Exception as e:
            logger.error("An error occurred while trying to download the recording: %s", e)

    # Additional info
    def get_vm_platform(self):
        """
        Gets the size of the vm screen.
        """
        return self.execute_python_command("import platform; print(platform.system())")['output'].strip()

    def get_vm_screen_size(self):
        """
        Gets the size of the vm screen.
        """
        response = requests.post(self.http_server + "/screen_size")
        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Failed to get screen size. Status code: %d", response.status_code)
            return None

    def get_vm_window_size(self, app_class_name: str):
        """
        Gets the size of the vm app window.
        """
        response = requests.post(self.http_server + "/window_size", data={"app_class_name": app_class_name})
        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Failed to get window size. Status code: %d", response.status_code)
            return None

    def get_vm_wallpaper(self):
        """
        Gets the wallpaper of the vm.
        """
        response = requests.post(self.http_server + "/wallpaper")
        if response.status_code == 200:
            logger.info("Wallpaper downloaded successfully")
            return response.content
        else:
            logger.error("Failed to get wallpaper. Status code: %d", response.status_code)
            return None

    def get_vm_desktop_path(self):
        """
        Gets the desktop path of the vm.
        """
        response = requests.post(self.http_server + "/desktop_path")
        if response.status_code == 200:
            logger.info("Desktop path downloaded successfully")
            return response.json()["desktop_path"]
        else:
            logger.error("Failed to get desktop path. Status code: %d", response.status_code)
            return None

    def get_vm_documents_path(self):
        """
        Gets the documents path of the vm.
        """
        response = requests.post(self.http_server + "/documents_path")
        if response.status_code == 200:
            logger.info("Documents path downloaded successfully")
            return response.json()["documents_path"]
        else:
            logger.error("Failed to get documents path. Status code: %d", response.status_code)
            return None

    def get_vm_folder_exists_in_path(self, folder_name, path):
        """
        Checks if a folder exists in the path.
        """
        payload = json.dumps({"folder_name": folder_name, "path": path})
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/folder_exists", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("Folder exists")
            return True
        else:
            logger.error("Failed to get folder exists. Status code: %d", response.status_code)
            return False
        
    def get_vm_file_exists_in_path(self, file_name, path):
        """
        Checks if a file exists in the path.
        """
        payload = json.dumps({"file_name": file_name, "path": path})
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/file_exists", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("File exists")
            return True
        else:
            logger.error("Failed to get file exists. Status code: %d", response.status_code)
            return False

    def get_vm_are_files_sorted_by_modified_time(self, directory) -> bool:
        """
        Gets whether the files in the directory are sorted by modified time.
        """
        payload = json.dumps({"directory": directory})
        headers = {
            'Content-Type': 'application/json'
        }
        logger.info(f"Checking if files in {directory} are sorted by modified time")
        response = requests.post(self.http_server + "/are_files_sorted_by_modified_time", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("Files sorted by modified time")
            return True
        else:
            logger.error("Files are not sorted by modified time. Status text: %s", response.text)
            return False
        
    def get_file_hidden_status(self, file_path: str):
        """
        Gets the hidden status of the file. Check if file name starts with '.' or file hidden attribute is set in windows.
        """
        command = f"import os; print(1 if os.path.basename(r'{file_path}').startswith('.') or (os.name == 'nt' and bool(os.stat(r'{file_path}').st_file_attributes & 2)) else 0)"
        
        response = self.execute_python_command(command)
        
        if response['status'] == 'success' and response.get('returncode') == 0:
            try:
                return int(response['output'].strip())
            except ValueError:
                return 0
        else:
            return 0

    def get_vm_is_directory_read_only_for_user(self, directory, user) -> bool:
        """
        Gets whether the directory is read-only for user.
        """
        payload = json.dumps({"directory": directory, "user": user})
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/is_directory_read_only_for_user", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info(f"Directory {directory} is read-only for user {user}")
            return True
        else:
            logger.error(f"Directory {directory} is not read-only for user {user}. Status text: %s", response.text)
            return False

    def get_vm_are_all_images_tagged(self, directory, tag) -> bool:
        """
        Gets whether all images in the directory are tagged with the specific tag.
        """
        payload = json.dumps({"directory": directory, "tag": tag})
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/are_all_images_tagged", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info(f"All images in {directory} are tagged with {tag}")
            return True
        else:
            logger.error(f"Not all images in {directory} are tagged with {tag}. Status text: %s", response.text)
            return False

    def get_vm_directory_tree(self, path):
        """
        Gets the directory tree of the vm.
        """
        payload = json.dumps({"path": path})
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/list_directory", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("Directory tree downloaded successfully")
            return response.json()["directory_tree"]
        else:
            logger.error("Failed to get directory tree. Status code: %d", response.status_code)
            return None
            
    def get_vm_file_explorer_is_details_view(self, path):
        """
        Gets if the file explorer is in details view.
        """
        payload = json.dumps({"path": path})
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/is_details_view", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("File explorer is set to details view")
            return True
        else:
            logger.error("File explorer is not set to details view. Status code: %d", response.status_code)
            return False

    def get_file_as_text(self, file_path: str):
        """
        Gets a file from the server.
        """
        response = requests.post(self.http_server + "/file", data={"file_path": file_path})
        logger.info(f"GET_FILE, file_path: {file_path}")
        if response.status_code == 200:
            logger.info("File downloaded successfully")
            return response.text
        else:
            logger.error("Failed to get file. Status code: %d", response.status_code)
            return None

    def get_vm_library_folders(self, library_name):
        """
        Gets the library folders of the vm.
        """
        payload = json.dumps({"library_name": library_name})
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(self.http_server + "/library_folders", headers=headers, data=payload)
        if response.status_code == 200:
            library_folders = response.json()["output"]
            logger.info(f"Library folders {library_folders} downloaded successfully")
            return library_folders
        else:
            logger.error("Failed to get library folders. Status text: %s", response.text)
            return None
    
    # Clock, Timers, Alarms (Clock inbox app)
    def get_vm_check_if_timer_started(self, hours, minutes, seconds):
        """
        checks if a timer exists 
        """
        payload = json.dumps({"hours": hours, "minutes": minutes, "seconds": seconds})
        headers = {
            'Content-Type': 'application/json'
        }
        
        logger.info(f"Checking if timer exists: {hours} hours {minutes} minutes {seconds} seconds")

        response = requests.post(self.http_server + "/check_if_timer_started", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("Timer started in Clock app")
            return "True"
        else:
            logger.error("Timer is not start or does not exist in Clock app. Status text: %s", response.text)
            return "False"
        
    def get_vm_check_if_world_clock_exists(self, city, country):
        """
        checks if a world clock exists
        """
        payload = json.dumps({"city": city, "country": country})
        headers = {
            'Content-Type': 'application/json'
        }
        
        logger.info(f"Checking if world clock exists: {city}, {country}")

        response = requests.post(self.http_server + "/check_if_world_clock_exists", headers=headers, data=payload)
        if response.status_code == 200:
            logger.info("World clock exists in Clock app")
            return "True"
        else:
            logger.error("World clock does not exist in Clock app. Status text: %s", response.text)
            return "False"

    def get_all_installed_apps(self,):
        """
        Fetches the json of all installed apps
        """
        command_list = f"powershell -Command \"Get-AppxPackage | Select-Object Name,PackageFullName | ConvertTo-Json\""
        return self.execute_shell_command(command_list)
        
    def get_registry_key(self, path, value):
        """
        Fetches the value of a registry key from the VM
        """
        command_list = f"powershell -Command \"Get-ItemPropertyValue -Path '{path}' -Name '{value}'\""
        return self.execute_shell_command(command_list)

    def set_registry_key(self, path, name, value):  
        """  
        Sets the value of a registry key in the VM  
        """  
        command_list = f"powershell -Command \"Set-ItemProperty -Path '{path}' -Name '{name}' -Value '{value}'\""  
        return self.execute_shell_command(command_list)  

    def execute_shell_command(self, command):
        """
        Executes a command and returns the response.
        """
        payload = {"command": command}

        headers = {
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(self.http_server + "/execute", headers=headers, json=payload, timeout=90)
            if response.status_code == 200:
                logger.info("Command executed successfully: %s", response.text)
                return response.json()
            else:
                logger.error("Failed to execute command. Status code: %d", response.status_code)
                return None
        except requests.exceptions.RequestException as e:
            logger.error("An error occurred while trying to execute the command: %s", e)
            return None
