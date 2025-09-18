import paramiko
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
from pathlib import Path
import json
import time
from bs4 import BeautifulSoup
import shlex
import textwrap
import plistlib

script_dir = Path(__file__).resolve().parent.parent

logger = ProjectLogger(log_dir=script_dir / "logs")


def test_click_top_left(env) -> bool:
    """
    Directly executes a pyautogui script on the remote macOS or GUI-capable Docker environment
    to print the screen size and click at coordinate (20, 0).

    :param env: MacOSEnv or DockerEnv instance with run_command
    :return: True if screen size is printed and click attempted, False otherwise
    """
    env.connect_ssh()

    inline_py = (
        "import pyautogui; "
        "import time; "
        "import pynput; "
        "pyautogui.FAILSAFE = False; "
        "size = pyautogui.size(); "
        "print(f'Screen size: {size}'); "
        "time.sleep(0.1);"
        # "pyautogui.click(1008, 79, button='left'); "
        "pyautogui.write(message='https://calendar.google.com'); "
        "pyautogui.press('enter');"
        # "pynput.mouse.Controller().click(button=pynput.mouse.Button.left, count=2); "
    )

    try:
        cmd = f'python3 -c "{inline_py}"'
        stdout, stderr = env.run_command(cmd)

        out = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        err = (
            stderr.read().decode().strip()
            if hasattr(stderr, "read")
            else stderr.strip()
        )

        logger.info(f"[stdout]\n{out}")
        logger.info(f"[stderr]\n{err}")

        return "Screen size:" in out

    except Exception as e:
        logger.error(f"test_click_top_left failed: {e}")
        return False


if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()

    # Connect to Docker container
    macos_env.connect_ssh()

    value = test_click_top_left(macos_env)
    logger.info(value)

    import time

    time.sleep(3)
    macos_env.close_connection()
