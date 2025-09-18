import json
import shutil
import subprocess
import tempfile
from playwright.sync_api import sync_playwright
from typing import Tuple, List, Union, Dict, Optional, ByteString, Any
import os
import time
import traceback
from env.base_env import BaseEnv
from env.web.utils.js import find_clickable_elements_js_code
from env.web.utils.keyword import KEYBOARD_KEYS, key_mapping
from env.web.webarena.evaluation.vab_evaluators import webarena_evaluator_router
from env.web.webarena.utils.auto_login import get_site_comb_from_filepath


class WebEnv(BaseEnv):
    """
    Web environment for browser interaction using Playwright.
    Provides a interface for web automation tasks.
    """

    def __init__(self, server_path: Optional[str] = None, **kwargs) -> None:
        """
        Initialize the web environment.

        Args:
            server_path: Path to the server, if any
            **kwargs: Additional web configuration parameters
        """
        super().__init__(server_path=None, platform="web")

        self.playwright = sync_playwright().start()
        self.browser_type = self.playwright.chromium
        self.should_record = False
        self.temp_video_dir = None
        self.task_config = {}

        explicitly_allowed_ports = kwargs.get("explicitly_allowed_ports", [])
        browser_args = [
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-logging",
            "--ignore-certificate-errors",
            "--disable-dev-shm-usage",
            "--disable-application-cache",
            "--media-cache-size=0",
            "--disk-cache-size=0",
            "--log-level=3",
            "--silent",
            "--allow-running-insecure-content",
            "--disable-web-security",
            f"--explicitly-allowed-ports={','.join(str(p) for p in explicitly_allowed_ports)}",
        ]

        # Proxy configuration
        proxy = kwargs.get("web_proxy", None)
        if isinstance(proxy, str):
            proxy_username = proxy.split("//")[1].split(":")[0]
            proxy_password = proxy.split("//")[1].split(":")[1].split("@")[0]
            proxy_server = "http://" + proxy.split("//")[1].split("@")[1]

            # Create proxy settings
            proxy_settings = {
                "server": proxy_server,
                "username": proxy_username,
                "password": proxy_password,
            }
        else:
            proxy_settings = None

        self.browser = self.browser_type.launch(
            headless=True, args=browser_args, proxy=proxy_settings
        )

        # Create context, set viewport size
        self.screen_size = (kwargs.get("width", 1280), kwargs.get("height", 720))
        self.dpr = kwargs.get("dpr", 1)
        self.css_width, self.css_height = int(self.screen_size[0] // self.dpr), int(
            self.screen_size[1] // self.dpr
        )
        self.context = None
        self.timeout = kwargs.get("wait_timeout", 5) * 1000
        self._initialize_context(enable_recording=False, start_url="about:blank")
        print(
            f"Initializing WebEnv, browser type: {self.browser_type.name}, proxy settings: {proxy_settings}, viewport size: {self.screen_size}, DPR: {self.dpr}, timeout: {self.timeout}s"
        )
        print(f"WebEnv initialization successful!")

    def start_recording(self) -> None:
        """
        Mark that video recording should begin (actual recording starts on next reset)
        """
        self.should_record = True
        print("Recording flag set, recording will start on next reset")

    def end_recording(self, path: str) -> None:
        """
        End video recording, save file, and remove current window context

        Args:
            path: Path where to save the recording
        """
        if not self.should_record:
            print("No active recording in progress")
            return None

        try:
            # Close context
            self.context.close()
            self.context = None
            self.should_record = False

            # Wait for video file to complete writing
            max_wait = 10  # Maximum 10 seconds wait
            start_time = time.time()

            # Wait for video file to appear
            latest_video_path = None
            while time.time() - start_time < max_wait:
                video_files = [
                    f
                    for f in os.listdir(self.temp_video_dir.name)
                    if f.endswith(".webm")
                ]
                if video_files:
                    # Sort by modification time, get most recent video file
                    video_files.sort(
                        key=lambda f: os.path.getmtime(
                            os.path.join(self.temp_video_dir.name, f)
                        ),
                        reverse=True,
                    )
                    latest_video_path = os.path.join(
                        self.temp_video_dir.name, video_files[0]
                    )
                    if os.path.getsize(latest_video_path) > 0:
                        break
                time.sleep(0.5)

            # Ensure destination path's directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)

            # Move the video to final destination
            shutil.move(latest_video_path, path)
            print(f"Video moved to {path}")

        except Exception as e:
            print(f"Error ending video recording: {str(e)}")

    def reset(self, **kwargs) -> None:
        """
        Reset environment, create new context and navigate to specified URL.

        Args:
            **kwargs: Keyword arguments containing:
                      url: The url web environment to reset
                      task_config: Info to set up the task, includes the instruction, storage, start_url and the evaluation function
                      benchmark: The benchmark name, default is 'vab_webarena_lite'
        """
        if "task_config" in kwargs and kwargs["benchmark"] in ["vab_webarena_lite"]:
            with open(kwargs["task_config"]["file_path"], "r", encoding="utf-8") as f:
                self.task_config = json.load(f)

            # Automatically login
            if self.task_config["storage_state"]:
                cookie_file_name = os.path.basename(self.task_config["storage_state"])
                comb = get_site_comb_from_filepath(cookie_file_name)
                temp_dir = tempfile.mkdtemp()
                # subprocess to renew the cookie
                python_path = os.getenv("PYTHON")
                if python_path is None:
                    python_path = "python"

                try:
                    subprocess.run(
                        [
                            python_path,
                            "env/web/webarena/utils/auto_login.py",
                            "--auth_folder",
                            temp_dir,
                            "--site_list",
                            *comb,
                        ],
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"Error during auto login: {e}")
                    print(f"Return code: {e.returncode}")
                    if e.stdout:
                        print(f"Standard output: {e.stdout.decode()}")
                    if e.stderr:
                        print(f"Standard error: {e.stderr.decode()}")

                self.task_config["storage_state"] = f"{temp_dir}/{cookie_file_name}"
                assert os.path.exists(self.task_config["storage_state"])

        start_url = (
            kwargs.get("url", None)
            or self.task_config.get("start_url", None)
            or "http://bing.com"
        )

        # Set up browser env
        self._initialize_context(
            enable_recording=self.should_record, start_url=start_url
        )

    def evaluate_webarena(self, **kwargs) -> float:
        """
        Evaluate WebArena tasks using the appropriate evaluator.

        Args:
            **kwargs: Keyword arguments containing:
                actions: List of actions performed by the agent

        Returns:
            float: Evaluation score between 0 and 1
        """
        action_list = kwargs["actions"]
        evaluator = webarena_evaluator_router(self.task_config)
        score = evaluator(
            action_list=action_list, task_config=self.task_config, page=self.page
        )
        return score

    def evaluate_demo(self, **kwargs) -> float:
        """
        Simple demonstration evaluator that always returns a perfect score.

        Args:
            **kwargs: Keyword arguments (not used in this evaluator)

        Returns:
            float: Always returns 1.0 (perfect score)
        """
        return 1.0

    def evaluate(self, **kwargs) -> float:
        """
        Evaluate the current trajectory and return a score based on the specified benchmark.

        Args:
            **kwargs: Keyword arguments containing:
                benchmark: The benchmark name, default is 'vab_webarena_lite', can also be 'demo'
                actions: The list of actions performed by the agent

        Returns:
            float: Evaluation score between 0 and 1
        """
        evaluate_dict = {
            "vab_webarena_lite": self.evaluate_webarena,
            "demo": self.evaluate_demo,
        }
        score = evaluate_dict[kwargs["benchmark"]](**kwargs)
        return score

    def _initialize_context(
        self, enable_recording: bool = False, start_url: Optional[str] = None
    ) -> None:
        """
        Initialize or reinitialize browser context and page.

        Args:
            enable_recording: Whether to enable video recording
            start_url: URL to navigate to after initialization
        """
        # If context already exists, close it first
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                print(f"Error closing old context: {str(e)}")

        storage_state = self.task_config.get("storage_state", None)
        # Basic context configuration
        context_options = {
            "viewport": {"width": self.css_width, "height": self.css_height},
            "device_scale_factor": self.dpr,
            "is_mobile": False,
            "storage_state": storage_state,
        }

        # Add video recording configuration if needed
        if enable_recording:
            self.temp_video_dir = tempfile.TemporaryDirectory()
            context_options["record_video_dir"] = self.temp_video_dir.name
            context_options["record_video_size"] = {
                "width": self.css_width,
                "height": self.css_height,
            }

        # Create new context and page
        self.context = self.browser.new_context(**context_options)
        self.context.set_default_timeout(self.timeout)

        # If initial page exists, there might be multiple initial pages for complex tasks
        assert start_url
        start_urls = start_url.split(" |AND| ")
        for url in start_urls:
            page = self.context.new_page()
            page.goto(url, timeout=self.timeout)
            page.wait_for_load_state("domcontentloaded")

        # Set first page as current starting page
        self.page = self.context.pages[0]
        self.page.bring_to_front()

        # Register listeners last - this listener is used to automatically switch Page handles
        self.setup_global_page_listener()

        # Dialog listener
        self.setup_dialog_interceptor()
        time.sleep(2)

    def exit(self) -> None:
        """
        Close all Playwright resources and exit.
        """
        if self.page and not self.page.is_closed():
            self.page.close()

        if self.context:
            self.context.close()

        if self.browser:
            self.browser.close()

        if self.playwright:
            self.playwright.stop()

    def find_all_clickable_elements(self) -> List[Dict[str, Any]]:
        """
        Get all clickable elements on the page.

        Returns:
            List of dictionaries containing information about clickable elements
        """
        try:
            all_clickable_elements_info = self.page.evaluate(
                find_clickable_elements_js_code
            )

            # Normalize returned coordinates[0~1]
            return [
                {
                    **ele,
                    "bbox": [
                        (
                            coord / self.css_width
                            if i % 2 == 0
                            else coord / self.css_height
                        )
                        for i, coord in enumerate(ele["bbox"])
                    ],
                }
                for ele in all_clickable_elements_info
            ]

        except Exception as e:
            print(str(e))
            return []

    def get_a11tree(self) -> List[Dict[str, Any]]:
        """
        Get accessibility tree of clickable elements.

        Returns:
            List of dictionaries containing information about clickable elements
        """
        return self.find_all_clickable_elements()

    def get_screen_size(self) -> Tuple[int, int]:
        """
        Get current screen size.

        Returns:
            Tuple of (width, height) in pixels
        """
        viewport = self.page.viewport_size
        return int(viewport["width"] * self.dpr), int(viewport["height"] * self.dpr)

    def get_screenshot(self) -> ByteString:
        """
        Take a screenshot of the current page.

        Returns:
            Screenshot as bytes
        """
        screenshot_bytes = self.page.screenshot()
        return screenshot_bytes

    def setup_global_page_listener(self) -> None:
        """
        Set up global page listener to automatically switch to new pages and close old ones.
        Critical: Ensures each operation occurs on the current page.
        """

        def _handle_new_page(page):
            print(f"New page detected: {page.url}")
            old_page = self.page
            self.page = page
            self.page.wait_for_load_state("domcontentloaded")
            self.setup_dialog_interceptor()
            print(f"Switched to new page: {self.page.url}")

        # Add page listener
        self.context.on("page", _handle_new_page)

    def setup_dialog_interceptor(self) -> None:
        """
        Set up dialog interceptor to replace native popups with DOM popups.
        """
        if not self.page:
            return

        # Create a new dialog intercept handler
        def intercept_dialog(dialog):
            try:
                # Immediately handle native dialog - accept all dialogs by default
                dialog_type = dialog.type
                dialog_message = dialog.message
                dialog_default_value = (
                    dialog.default_value if dialog_type == "prompt" else ""
                )

                # Immediately handle the native dialog
                if dialog_type == "prompt":
                    dialog.accept(dialog_default_value)
                else:
                    dialog.accept()

                # Record dialog information
                dialog_id = f"mock-dialog-{int(time.time() * 1000)}"

                # Inject mock dialog into DOM
                self.page.evaluate(
                    """
                    ({ type, message, defaultValue, dialogId }) => {
                        // Clean up existing mock popups
                        const existingMock = document.getElementById('mock-dialog-container');
                        if (existingMock) existingMock.remove();

                        // Create container
                        const container = document.createElement('div');
                        container.id = 'mock-dialog-container';
                        container.style = `
                            position: fixed;
                            top: 0;
                            left: 0;
                            right: 0;
                            bottom: 0;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            z-index: 99999;
                            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        `;

                        // Create overlay
                        const overlay = document.createElement('div');
                        overlay.style = `
                            position: absolute;
                            top: 0;
                            left: 0;
                            right: 0;
                            bottom: 0;
                            background: rgba(0, 0, 0, 0.5);
                            z-index: 1;
                        `;

                        // Create dialog
                        const dialog = document.createElement('div');
                        dialog.id = dialogId;
                        dialog.style = `
                            background: white;
                            border-radius: 8px;
                            box-shadow: 0 4px 23px 0 rgba(0, 0, 0, 0.2);
                            padding: 20px;
                            min-width: 320px;
                            max-width: 90vw;
                            position: relative;
                            z-index: 2;
                            overflow: hidden;
                        `;

                        // Message text
                        const messageElement = document.createElement('div');
                        messageElement.style = `
                            margin-bottom: 20px;
                            font-size: 14px;
                            color: #333;
                            line-height: 1.5;
                            word-break: break-word;
                        `;
                        messageElement.textContent = message;

                        // Button container
                        const buttonsContainer = document.createElement('div');
                        buttonsContainer.style = `
                            display: flex;
                            justify-content: flex-end;
                            gap: 10px;
                        `;

                        let inputElement = null;
                        if (type === 'prompt') {
                            // Add input field
                            inputElement = document.createElement('input');
                            inputElement.type = 'text';
                            inputElement.value = defaultValue || '';
                            inputElement.style = `
                                width: 100%;
                                padding: 10px;
                                border: 1px solid #ddd;
                                border-radius: 4px;
                                margin-bottom: 15px;
                                font-size: 14px;
                            `;
                        }

                        // OK button
                        const okButton = document.createElement('button');
                        okButton.className = 'ok-button';
                        okButton.textContent = 'OK';
                        okButton.style = `
                            padding: 8px 16px;
                            background: #0d6efd;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 14px;
                            color: white;
                        `;
                        okButton.addEventListener('mouseover', () => {
                            okButton.style.background = '#0b5ed7';
                        });
                        okButton.addEventListener('mouseout', () => {
                            okButton.style.background = '#0d6efd';
                        });
                        okButton.addEventListener('click', () => {
                            // Close mock dialog
                            container.remove();
                        });
                        buttonsContainer.appendChild(okButton);

                        // Add elements to dialog
                        dialog.appendChild(messageElement);
                        if (inputElement) {
                            dialog.appendChild(inputElement);
                        }
                        dialog.appendChild(buttonsContainer);

                        // Add all elements to container
                        container.appendChild(overlay);
                        container.appendChild(dialog);

                        // Add to document
                        document.body.appendChild(container);

                        // Support ESC key and background click to close
                        const handleKeyDown = (e) => {
                            if (e.key === 'Escape') {
                                container.remove();
                                document.removeEventListener('keydown', handleKeyDown);
                            }
                        };
                        document.addEventListener('keydown', handleKeyDown);

                        // Close on background click
                        overlay.addEventListener('click', () => {
                            container.remove();
                        });
                    }
                """,
                    {
                        "type": dialog_type,
                        "message": dialog_message,
                        "defaultValue": dialog_default_value,
                        "dialogId": dialog_id,
                    },
                )

                # Log dialog information
                print(
                    f"Dialog intercepted and handled: {dialog_type} - {dialog_message}"
                )

            except Exception as e:
                print(f"Error handling dialog: {str(e)}")
                # If error during handling, try to dismiss dialog
                try:
                    dialog.dismiss()
                except:
                    pass

        self.page.on("dialog", intercept_dialog)

    def parse_action(self, prediction):
        pass

    def get_element_type(self, parameters: Dict[str, Any]) -> str:
        """
        Get the type of element at specified coordinates.

        Args:
            parameters: Dictionary containing x, y coordinates

        Returns:
            str: Element type (tag name)
        """
        if "x" in parameters and "y" in parameters:
            return self.page.evaluate(
                """
                ({x, y}) => {
                    const element = document.elementFromPoint(x, y);
                    if (!element) return 'none';

                    // Check if select element
                    if (element.tagName.toLowerCase() === 'select') {
                        return 'select';
                    }

                    // Check if option element
                    if (element.tagName.toLowerCase() === 'option') {
                        return 'option';
                    }

                    return element.tagName.toLowerCase();
                }
                """,
                {"x": parameters["x"], "y": parameters["y"]},
            )
        else:
            return "unknown"

    def _execute_click_select(self, parameters: Dict[str, Any]) -> None:
        """
        Execute special handling for clicking on select elements.

        Args:
            parameters: Dictionary containing action parameters
        """
        element_type = self.get_element_type(parameters)
        if element_type == "select":
            self.page.evaluate(
                """
                ({x, y}) => {
                    const select = document.elementFromPoint(x, y);
                    if (select && select.tagName.toLowerCase() === 'select') {
                        // Save all original states and styles
                        const originalState = {
                            size: select.size,
                            style: {
                                position: select.style.position,
                                zIndex: select.style.zIndex,
                                height: select.style.height,
                                maxHeight: select.style.maxHeight,
                                overflow: select.style.overflow,
                                display: select.style.display,
                                visibility: select.style.visibility,
                                width: select.style.width,
                                minWidth: select.style.minWidth,
                                maxWidth: select.style.maxWidth,
                                boxSizing: select.style.boxSizing
                            }
                        };

                        // Save original width for setting expanded width
                        const originalWidth = select.offsetWidth + 'px';

                        // Save original styles of options
                        const optionsOriginalStyle = [];
                        const options = select.querySelectorAll('option');
                        for (let i = 0; i < options.length; i++) {
                            optionsOriginalStyle.push({
                                width: options[i].style.width,
                                boxSizing: options[i].style.boxSizing,
                                whiteSpace: options[i].style.whiteSpace,
                                overflow: options[i].style.overflow,
                                textOverflow: options[i].style.textOverflow
                            });
                        }

                        // Calculate total number of options
                        let totalOptions = select.options.length;

                        // Set size equal to number of options to make all options visible
                        select.size = Math.min(totalOptions, 30); // Limit max rows to 30

                        // Force display styles
                        select.style.position = 'absolute';
                        select.style.zIndex = '9999';
                        select.style.height = 'auto';
                        select.style.maxHeight = '500px';
                        select.style.overflow = 'auto';
                        select.style.display = 'block';
                        select.style.visibility = 'visible';

                        // Ensure width doesn't change
                        select.style.width = originalWidth;
                        select.style.minWidth = originalWidth;
                        select.style.maxWidth = originalWidth;
                        select.style.boxSizing = 'border-box';

                        // Handle option width to prevent them from expanding dropdown
                        for (let i = 0; i < options.length; i++) {
                            options[i].style.width = '100%';
                            options[i].style.boxSizing = 'border-box';
                            options[i].style.whiteSpace = 'nowrap';
                            options[i].style.overflow = 'hidden';
                            options[i].style.textOverflow = 'ellipsis';
                        }

                        // Add event listeners to restore after selection
                        const restoreSelect = () => {
                            // Restore select element's original state
                            select.size = originalState.size;

                            // Restore select element's original styles
                            for (const prop in originalState.style) {
                                select.style[prop] = originalState.style[prop];
                            }

                            // Restore options' original styles
                            for (let i = 0; i < options.length; i++) {
                                options[i].style.width = optionsOriginalStyle[i].width;
                                options[i].style.boxSizing = optionsOriginalStyle[i].boxSizing;
                                options[i].style.whiteSpace = optionsOriginalStyle[i].whiteSpace;
                                options[i].style.overflow = optionsOriginalStyle[i].overflow;
                                options[i].style.textOverflow = optionsOriginalStyle[i].textOverflow;
                            }

                            document.removeEventListener('click', closeHandler);
                            select.removeEventListener('change', changeHandler);
                        };

                        const changeHandler = function() {
                            restoreSelect();
                        };

                        const closeHandler = function(e) {
                            if (e.target !== select && !select.contains(e.target)) {
                                restoreSelect();
                            }
                        };

                        select.addEventListener('change', changeHandler);

                        // Restore when clicking outside
                        setTimeout(() => {
                            document.addEventListener('click', closeHandler);
                        }, 0);
                    }
                }
            """,
                {"x": parameters["x"], "y": parameters["y"]},
            )

    def execute_single_action(self, action: Dict[str, Any]) -> bool:
        """
        Execute a single action based on action type.

        Args:
            action: Dictionary containing action type and parameters

        Returns:
            bool: Whether the action was executed successfully
        """
        try:
            action_type = action["name"]
            parameters = action.get("parameters", {})

            # 0,1 coordinates -> CSS Viewport coordinates
            # if "x" in parameters and parameters["x"] is not None:
            #     parameters["x"] = max(0, min(1, parameters["x"])) * self.css_width
            # if "y" in parameters and parameters["y"] is not None:
            #     parameters["y"] = max(0, min(1, parameters["y"])) * self.css_height
            # if "from_coord" in parameters and isinstance(parameters["from_coord"], tuple):
            #     parameters["from_coord"][0] = max(0, min(1, parameters["from_coord"][0])) * self.css_width
            #     parameters["from_coord"][1] = max(0, min(1, parameters["from_coord"][1])) * self.css_height
            # if "to_coord" in parameters and isinstance(parameters["to_coord"], tuple):
            #     parameters["to_coord"][0] = max(0, min(1, parameters["to_coord"][0])) * self.css_width
            #     parameters["to_coord"][1] = max(0, min(1, parameters["to_coord"][1])) * self.css_height

            # Convert absolute coordinates -> CSS Viewport coordinates
            if "x" in parameters and parameters["x"] is not None:
                parameters["x"] = parameters["x"] / self.dpr
            if "y" in parameters and parameters["y"] is not None:
                parameters["y"] = parameters["y"] / self.dpr
            if (
                "from_coord" in parameters
                and parameters["from_coord"][0] is not None
                and parameters["from_coord"][1] is not None
            ):
                parameters["from_coord"][0] = parameters["from_coord"][0] / self.dpr
                parameters["from_coord"][1] = parameters["from_coord"][1] / self.dpr
            if (
                "to_coord" in parameters
                and parameters["to_coord"][0] is not None
                and parameters["to_coord"][1] is not None
            ):
                parameters["to_coord"][0] = parameters["to_coord"][0] / self.dpr
                parameters["to_coord"][1] = parameters["to_coord"][1] / self.dpr

            # Action type mapping table
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
                "swipe": self._execute_swipe,
                "keyup": self._execute_keyup,
                "keydown": self._execute_keydown,
            }

            # Get corresponding handler and execute
            handler = action_handlers.get(action_type)
            if handler:
                success = handler(parameters)
                print(f"{action_type} is done")
                return success
            else:
                return False

        except Exception:
            return False

    def _execute_move_to(self, parameters: Dict[str, Any]) -> bool:
        """
        Move mouse to specified position.

        Args:
            parameters: Dictionary containing x and y coordinates

        Returns:
            bool: Whether the action was executed successfully
        """
        x = parameters.get("x", 0)
        y = parameters.get("y", 0)
        self.page.mouse.move(x, y)
        self.page.wait_for_timeout(2000)
        return True

    def _execute_click(self, parameters: Dict[str, Any]) -> bool:
        """
        Click at specified position.

        Args:
            parameters: Dictionary containing click parameters (x, y, clicks, button)

        Returns:
            bool: Whether the action was executed successfully
        """
        x = parameters.get("x", 0)
        y = parameters.get("y", 0)
        clicks = parameters.get("clicks", 1)
        button = parameters.get("button", "left")

        self.page.mouse.click(x, y, button=button, click_count=clicks)
        self.page.wait_for_timeout(4000)
        # Special handling for clicking on select elements
        self._execute_click_select(parameters)

        return True

    def _execute_write(self, parameters: Dict[str, Any]) -> bool:
        """
        Simulate keyboard typing text.

        Args:
            parameters: Dictionary containing message to type

        Returns:
            bool: Whether the action was executed successfully
        """
        message = parameters.get("message", "")
        self.page.keyboard.type(message)
        self.page.wait_for_timeout(1000)
        return True

    def _execute_drag_to(self, parameters: Dict[str, Any]) -> bool:
        """
        Execute drag operation. Note: x and y attributes must both be present
        because JS cannot get real-time mouse position.

        Args:
            parameters: Dictionary containing drag parameters (x, y, button)

        Returns:
            bool: Whether the action was executed successfully
        """
        end_x = parameters.get("x", 0)
        end_y = parameters.get("y", 0)
        button = parameters.get("button", "left")

        self.page.mouse.down(button=button)
        self.page.mouse.move(end_x, end_y)
        self.page.mouse.up(button=button)
        self.page.wait_for_timeout(2000)
        return True

    def _execute_press(self, parameters: Dict[str, Any]) -> bool:
        """
        Press and release specified key or key sequence.

        Args:
            parameters: Dictionary containing keys to press and number of presses

        Returns:
            bool: Whether the action was executed successfully
        """
        keys = parameters.get("keys", [])
        presses = parameters.get("presses", 1)

        # Support single key or key list
        if isinstance(keys, str):
            if keys not in KEYBOARD_KEYS:
                return False

            keys = key_mapping.get(keys, keys)
            # Single key, press specified number of times
            for _ in range(presses):
                self.page.keyboard.press(keys)
        else:
            # Key sequence, press each key in order
            for key in keys:
                if key not in KEYBOARD_KEYS:
                    continue
                key = key_mapping.get(key, key)
                for _ in range(presses):
                    self.page.keyboard.press(key)

        self.page.wait_for_timeout(2000)
        return True

    def _execute_call_user(self, parameters: Dict[str, Any]) -> bool:
        """
        Call the user, might be a notification or callback in actual operation.

        Args:
            parameters: Action parameters (unused)

        Returns:
            bool: Always returns True
        """
        return True

    def _execute_wait(self, parameters: Dict[str, Any]) -> bool:
        """
        Wait for specified number of seconds.

        Args:
            parameters: Dictionary containing seconds to wait

        Returns:
            bool: Whether the action was executed successfully
        """
        seconds = parameters.get("seconds", 3)
        self.page.wait_for_timeout(seconds * 1000)
        return True

    def _execute_response(self, parameters: Dict[str, Any]) -> bool:
        """
        Send response or feedback.

        Args:
            parameters: Dictionary containing answer text

        Returns:
            bool: Always returns True
        """
        return True

    def _execute_terminate(self, parameters: Dict[str, Any]) -> bool:
        """
        Terminate operation sequence, could be success or failure.

        Args:
            parameters: Dictionary containing status

        Returns:
            bool: Always returns True
        """
        return True

    def _execute_double_click(self, parameters: Dict[str, Any]) -> bool:
        """
        Execute double-click operation.

        Args:
            parameters: Dictionary containing click parameters

        Returns:
            bool: Whether the action was executed successfully
        """
        parameters["clicks"] = 2
        self._execute_click(parameters)
        return True

    def _execute_right_click(self, parameters: Dict[str, Any]) -> bool:
        """
        Execute right-click operation.

        Args:
            parameters: Dictionary containing click parameters

        Returns:
            bool: Whether the action was executed successfully
        """
        parameters["button"] = "right"
        self._execute_click(parameters)
        return True

    def _execute_hotkey(self, parameters: Dict[str, Any]) -> bool:
        """
        Execute combination key operation.

        Args:
            parameters: Dictionary containing key arguments

        Returns:
            bool: Whether the action was executed successfully
        """
        args = parameters.get("args", [])

        # Press all keys first
        for key in args:
            if key not in KEYBOARD_KEYS:
                continue
            key = key_mapping.get(key, key)
            self.page.keyboard.down(key)

        # Release all keys in reverse order
        for key in reversed(args):
            if key not in KEYBOARD_KEYS:
                continue

            key = key_mapping.get(key, key)
            self.page.keyboard.up(key)

        self.page.wait_for_timeout(2000)
        return True

    def _execute_keyup(self, parameters):
        """
        Execute keyup operation.

        Args:
            parameters: Dictionary containing key to press up

        Returns:
            bool: Whether the action was executed successfully
        """
        key = parameters.get("key")
        key = key_mapping.get(key, key)
        self.page.keyboard.up(key)

        self.page.wait_for_timeout(2000)
        return True

    def _execute_keydown(self, parameters):
        """
        Execute keydown operation.

        Args:
            parameters: Dictionary containing key to press down

        Returns:
            bool: Whether the action was executed successfully
        """
        key = parameters.get("key")
        key = key_mapping.get(key, key)
        self.page.keyboard.down(key)

        self.page.wait_for_timeout(2000)
        return True

    def _execute_swipe(self, parameters: Dict[str, Any]) -> bool:
        """
        Execute swipe operation.

        Args:
            parameters: Dictionary containing swipe parameters

        Returns:
            bool: Whether the action was executed successfully
        """
        x1, y1 = parameters.get("from_coord", (None, None))
        x2, y2 = parameters.get("to_coord", (None, None))
        direction = parameters.get("direction", "up")
        amount = parameters.get("amount", 0.5)
        amount = max(0.0, min(1.0, amount))
        # If to_coord exists, use vector as delta_x, delta_y
        # delta_y > 0 means scroll down, delta_y < 0 means scroll up
        if x2 is not None and y2 is not None and x1 is not None and y1 is not None:
            delta_x = x1 - x2
            delta_y = y1 - y2
        else:
            # Keep custom logic here
            if direction in ["up", "down"]:
                distance = (
                    self.css_height * amount
                    if direction == "up"
                    else -self.css_height * amount
                )
                delta_x, delta_y = 0, distance
            else:  # direction in ["left", "right"]
                distance = (
                    self.css_width * amount
                    if direction == "left"
                    else -self.css_width * amount
                )
                delta_x, delta_y = distance, 0

        # If from_coord coordinates provided, move mouse to specified position, otherwise move global page
        if x1 is not None and y1 is not None:
            self.page.mouse.move(x1, y1)
            self.page.mouse.wheel(delta_x, delta_y)
        else:
            # If x1, y1 don't exist, use JavaScript to scroll page
            if direction in ["up", "down"]:
                js_scroll = f"window.scrollBy(0, {delta_y});"
            else:  # direction in ["left", "right"]
                js_scroll = f"window.scrollBy({delta_x}, 0);"
            self.page.evaluate(js_scroll)
        self.page.wait_for_timeout(2000)
        return True
