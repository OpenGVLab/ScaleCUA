"""
Ubuntu-Web Environment Client: Connect to a remote server to execute Web Tasks
"""

import base64
import json
import os
import requests
from typing import Tuple, List, Union, Dict, Optional, Any, ByteString
from envs.base_env import BaseEnv, agent_action


class UbuntuWebEnv(BaseEnv):
    """
    Client for interacting with a remote Ubuntu web environment.
    Provides methods to control a browser, capture screenshots, and execute actions.
    """

    def __init__(
        self,
        server_path: str,  # Server address, e.g.: "http://192.168.1.100:8000"
        **kwargs,
    ):
        """
        Initialize the Ubuntu Web Environment client.

        Args:
            server_path: URL of the remote server
            **kwargs: Additional configuration parameters
                - width: Screen width (default: 1280)
                - height: Screen height (default: 720)
                - dpr: Device pixel ratio (default: 1)
                - wait_timeout: Timeout in seconds (default: 5)
                - explicitly_allowed_ports: List of allowed ports for navigation
                - web_proxy: Internet proxy playwright uses
        """
        super().__init__(server_path=server_path, platform="web")

        self.server_path = server_path
        self.screen_size = (kwargs.get("width", 1280), kwargs.get("height", 720))
        self.dpr = kwargs.get("dpr", 1)
        self.css_width, self.css_height = int(self.screen_size[0] // self.dpr), int(
            self.screen_size[1] // self.dpr
        )
        self.wait_timeout = kwargs.get("wait_timeout", 5) * 1000
        self.task_config = {}

        # Initialize browser on the server
        init_params = {
            "width": self.screen_size[0],
            "height": self.screen_size[1],
            "dpr": self.dpr,
            "timeout": self.wait_timeout,
            "explicitly_allowed_ports": kwargs.get("explicitly_allowed_ports", []),
            "web_proxy": kwargs.get("web_proxy", None),
        }

        response = requests.post(f"{self.server_path}/init", json=init_params)
        if response.status_code != 200:
            raise Exception(f"Failed to initialize server: {response.text}")

        print(
            f"UbuntuWebEnvClient initialized successfully, connected to server: {server_path}"
        )

    def end_recording(self, path: str) -> None:
        """
        End recording and save the video to the specified path.

        Args:
            path: Path where the video file will be saved
        """
        try:
            # Send request to end recording
            response = requests.post(f"{self.server_path}/end_recording")

            # Check if request was successful
            if response.status_code != 200:
                raise Exception(f"Status code: {response.status_code}")

            # Parse JSON response
            response_data = response.json()

            # Decode base64 data, should be mp4 format
            video_bytes = base64.b64decode(response_data.get("video"))

            # Ensure target directory exists
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

            # Write video file
            with open(path, "wb") as f:
                f.write(video_bytes)

        except Exception as e:
            print(f"Error in end_recording: {str(e)}")

    def start_recording(self) -> None:
        """
        Start recording the screen.
        """
        response = requests.get(f"{self.server_path}/start_recording")

        if response.status_code != 200:
            print(f"Failed to start video recording: {response.text}")

    def parse_action(self, prediction):
        pass

    def reset(self, **kwargs) -> None:
        """
        Reset the environment, create a new context and navigate to the specified URL.

        Args:
            **kwargs: Configuration options for reset
                - url: URL to navigate to
        """
        if "task_config" in kwargs and "file_path" in kwargs["task_config"]:
            with open(kwargs["task_config"]["file_path"], "r", encoding="utf-8") as f:
                self.task_config = json.load(f)

        reset_params = {"kwargs": kwargs, "task_config": self.task_config}

        response = requests.post(f"{self.server_path}/reset", json=reset_params)
        if response.status_code != 200:
            print(f"Failed to reset environment: {response.text}")

    def get_screenshot(self) -> ByteString | None:
        """
        Get the current screenshot.

        Returns:
            bytes: Screenshot image data or None if failed
        """
        response = requests.get(f"{self.server_path}/screenshot")
        if response.status_code == 200:
            return base64.b64decode(response.json().get("screenshot", ""))
        return None

    def get_a11tree(self) -> List[Dict[str, Optional]]:
        """
        Get the accessibility tree of the current page.

        Returns:
            list: List of elements in the accessibility tree or empty list if failed
        """
        response = requests.get(f"{self.server_path}/elements")
        if response.status_code == 200:
            return response.json().get("elements", [])
        return []

    def get_screen_size(self) -> tuple[int, int]:
        """
        Get the screen size.

        Returns:
            tuple: (width, height) of the screen
        """
        return self.screen_size

    def exit(self) -> None:
        """
        Close all resources and exit.
        """
        requests.post(f"{self.server_path}/exit")

    def execute_single_action(self, action: Dict[str, Any]) -> bool:
        """
        Execute a single action.

        Args:
            action: Dictionary containing action details

        Returns:
            bool: Whether the action executed successfully
        """
        response = requests.post(f"{self.server_path}/execute", json={"action": action})
        return response.status_code == 200

    def evaluate(self, **kwargs):
        pass
