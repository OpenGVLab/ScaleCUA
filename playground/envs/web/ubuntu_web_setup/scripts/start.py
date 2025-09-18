"""
Ubuntu-Web Environment Server: Runs on Ubuntu VM to execute browser automation
"""

import base64
import signal
import subprocess
import tempfile
import traceback

import pyautogui
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
from PIL import ImageGrab, Image
import io
import Xlib.display
from Xlib.xobject.drawable import Window
import ewmh
from util import *

# Create FastAPI application
app = FastAPI(title="Ubuntu Web Environment Server")

# Global variables to store browser state
browser = None
context = None
page = None
playwright = None
screen_size = (1920, 1080)
dpr = 1.0
css_width, css_height = 1920, 1080
timeout = 30000
browser_window = None
browser_window_id = None
browser_offset_x, browser_offset_y = 0, 0
task_config = {}

# Initialize X display and EWMH
display = Xlib.display.Display()
ewmh_instance = ewmh.EWMH()

# Video recording globals
recording_process = None
recording_output_file = None
recording_temp_dir = None


# Define API request and response models
class InitParams(BaseModel):
    width: int = 2560
    height: int = 1600
    dpr: float = 1.5
    timeout: int = 30
    explicitly_allowed_ports: List[int]
    web_proxy: str = None


class ResetParams(BaseModel):
    kwargs: Dict
    task_config: Dict


class ActionParams(BaseModel):
    action: Dict


class EvaluateParams(BaseModel):
    benchmark: str
    actions: Optional[List] = None
    trajectory_dir: Optional[str] = None


class EndRecordingResponse(BaseModel):
    video: str  # base64 encoded video


# API route definitions
@app.post("/init")
def initialize_browser(params: InitParams):
    """Initialize browser instance"""
    global browser, context, playwright, screen_size, dpr, css_width, css_height, timeout
    _exit()
    try:
        # Store configuration
        screen_size = (params.width, params.height)
        dpr = params.dpr
        css_width, css_height = int(params.width // params.dpr), int(
            params.height // params.dpr
        )
        timeout = params.timeout * 1000
        explicitly_allowed_ports = params.explicitly_allowed_ports

        # Start Playwright
        playwright = sync_playwright().start()
        browser_type = playwright.chromium

        proxy = params.web_proxy
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

        # Launch browser
        browser = browser_type.launch(
            headless=False, proxy=proxy_settings, args=browser_args
        )

        # Create context
        _initialize_context("about:blank")

        # Update browser window information
        _update_browser_window_info()

        return {"status": "success", "message": "Browser initialization successful"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Browser initialization failed: {str(e)}"
        )


@app.post("/reset")
def reset_environment(params: ResetParams):
    """Reset environment, create new context and navigate to specified URL"""
    global task_config

    try:
        # Save task configuration
        task_config = params.task_config
        kwargs = params.kwargs

        # Process task configuration file
        if "benchmark" in kwargs and kwargs["benchmark"] in [
            "webarena_multi_app",
            "vab_webarena_lite",
        ]:
            # Automatically login
            if task_config["storage_state"]:
                cookie_file_name = os.path.basename(task_config["storage_state"])
                comb = get_site_comb_from_filepath(cookie_file_name)
                temp_dir = tempfile.mkdtemp()
                # subprocess to renew the cookie
                python_path = os.getenv("PYTHON")
                if python_path is None:
                    python_path = "python3"
                subprocess.run(
                    [
                        python_path,
                        "/app/scripts/auto_login.py",
                        "--auth_folder",
                        temp_dir,
                        "--site_list",
                        *comb,
                    ]
                )
                task_config["storage_state"] = f"{temp_dir}/{cookie_file_name}"
                assert os.path.exists(task_config["storage_state"])

        start_url = (
            kwargs.get("url", None) or task_config.get("start_url", None) or None
        )

        # Set up browser environment
        _initialize_context(start_url)

        # Retrieve browser window information again
        _update_browser_window_info()

        return {"status": "success", "message": "Environment reset successful"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Environment reset failed: {str(e)}"
        )


@app.post("/execute")
def execute(params: ActionParams):
    """Execute a series of operations"""
    try:
        action = params.action
        success = execute_single_action(action)
        if not success:
            raise HTTPException(
                status_code=400, detail=f"Failed to execute action: {action['name']}"
            )
        return {"status": "success", "message": "Operations executed successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to execute operations: {str(e)}"
        )


@app.get("/screenshot")
def get_screenshot():
    """Get current screen screenshot"""
    try:
        screenshot_bytes = _get_screenshot()
        base64_screenshot = base64.b64encode(screenshot_bytes).decode("utf-8")
        return {"screenshot": base64_screenshot}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get screenshot: {str(e)}"
        )


@app.get("/elements")
def get_elements():
    """Get clickable element information"""
    try:
        # elements = find_all_clickable_elements()
        return {"elements": []}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get element information: {str(e)}"
        )


@app.post("/evaluate")
def evaluate_trajectory(params: EvaluateParams):
    """Evaluate current trajectory"""
    try:
        benchmark = params.benchmark

        evaluate_dict = {"vab_webarena_lite": evaluate_webarena, "demo": evaluate_demo}

        if benchmark not in evaluate_dict:
            raise HTTPException(
                status_code=400, detail=f"Unsupported evaluation benchmark: {benchmark}"
            )

        score = evaluate_dict[benchmark](params)
        return {"score": score}

    except Exception as e:
        print(traceback.print_exc())
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.post("/exit")
def exit_browser():
    """Close all Playwright resources and exit"""
    success = _exit()
    if success:
        return {"success": "Playwright resources exited successfully"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to close resources")


@app.get("/start_recording")
def start_recording():
    """
    Start screen recording using ffmpeg

    Args:
        params: Recording parameters including save location and quality

    Returns:
        Dict with status and message
    """
    global recording_process, recording_output_file, recording_temp_dir

    try:
        # Stop any existing recording
        if recording_process:
            _stop_recording_process()

        # Create temp directory if needed
        if not recording_temp_dir:
            recording_temp_dir = tempfile.mkdtemp()

        # Use specified save folder or temp directory
        save_folder = recording_temp_dir
        os.makedirs(save_folder, exist_ok=True)

        recording_output_file = os.path.join(
            save_folder, f"recording_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        # Set ffmpeg quality presets based on parameter
        # quality_presets = {
        #     "low": "-c:v libx264 -preset ultrafast -crf 28",
        #     "medium": "-c:v libx264 -preset medium -crf 23",
        #     "high": "-c:v libx264 -preset slow -crf 18"
        # }
        # quality_params = quality_presets.get(quality_presets["medium"])

        # Start ffmpeg process to record screen
        command = [
            "ffmpeg",
            "-f",
            "x11grab",
            "-framerate",
            "24",
            "-video_size",
            "1920x1080",
            "-i",
            ":1",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            recording_output_file,
        ]

        recording_process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Wait a moment to ensure recording starts
        time.sleep(1)

        # Check if process is still running
        if recording_process.poll() is not None:
            stdout, stderr = recording_process.communicate()
            raise Exception(f"Recording failed to start: {stderr.decode('utf-8')}")

    except Exception as e:
        print(traceback.print_exc())
        raise HTTPException(
            status_code=500, detail=f"Failed to start recording: {str(e)}"
        )


@app.post("/end_recording", response_model=EndRecordingResponse)
def end_recording():
    """
    End screen recording and return video file

    Returns:
        Dict with status, message and base64 encoded video
    """
    global recording_process, recording_output_file

    try:
        if not recording_process:
            raise HTTPException(status_code=400, detail="No active recording found")

        # Stop the recording process
        _stop_recording_process()

        # Check if file exists
        if not os.path.exists(recording_output_file):
            raise Exception(f"Recording file not found: {recording_output_file}")

        # Read the file
        with open(recording_output_file, "rb") as f:
            video_bytes = f.read()

        print(f"Video bytes: {len(video_bytes)}")
        # Encode to base64
        base64_video = base64.b64encode(video_bytes).decode("utf-8")

        return EndRecordingResponse(video=base64_video)

    except Exception as e:
        print(traceback.print_exc())
        raise HTTPException(
            status_code=500, detail=f"Failed to end recording: {str(e)}"
        )


def _stop_recording_process():
    """
    Properly stop the ffmpeg recording process
    """
    global recording_process, recording_output_file

    if recording_process:
        # Send SIGINT (Ctrl+C) signal to ffmpeg, which allows it to properly finish writing the video
        recording_process.send_signal(signal.SIGINT)

        try:
            recording_process.wait(timeout=10)  # Give ffmpeg more time to complete
        except subprocess.TimeoutExpired:
            # If it hasn't finished after 10 seconds, try to forcefully terminate
            recording_process.terminate()
            try:
                recording_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                recording_process.kill()
                recording_process.wait()

        recording_process = None

    # Validate file integrity before reading
    try:
        # Use ffprobe to check file integrity
        check_cmd = f"ffprobe -v error {recording_output_file}"
        result = subprocess.run(check_cmd, shell=True, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise Exception(
                f"Recording file is corrupted: {result.stderr.decode('utf-8')}"
            )
    except Exception as e:
        print(f"File validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Recording file is corrupted")


# Helper functions
def _exit():
    global page, context, browser, playwright

    try:
        if page and not page.is_closed():
            page.close()
            page = None

        if context:
            context.close()
            context = None

        if browser:
            browser.close()
            browser = None

        if playwright:
            playwright.stop()
            playwright = None

        return True

    except Exception as e:
        print(f"Error during exit: {str(e)}")
        return False


def _update_browser_window_info():
    """Update browser window information using X11/EWMH"""
    global browser_window, browser_window_id, browser_offset_x, browser_offset_y

    time.sleep(1)
    try:
        # Get all client windows
        client_list = ewmh_instance.getClientList()
        ewmh_instance.display.flush()

        # Look for Chrome/Chromium window
        for window in client_list:
            try:
                window_name = ewmh_instance.getWmName(window)
                if not isinstance(window_name, str):
                    window_name = window_name.decode("utf-8", errors="ignore")

                print(f"window name: {window_name}")

                if "Chromium" in window_name or "Chrome" in window_name:
                    # Get window geometry
                    geometry = window.get_geometry()

                    # Get absolute position
                    x, y = 0, 0
                    parent = window
                    while parent:
                        try:
                            parent_geom = parent.get_geometry()
                            tree = parent.query_tree()
                            new_parent = tree.parent

                            # Translate coordinates relative to direct parent
                            translation = parent.translate_coords(new_parent, 0, 0)
                            if translation:
                                x += translation.x
                                y += translation.y

                            # If reached root window, stop
                            if new_parent.id == display.screen().root.id:
                                break

                            parent = new_parent
                        except Exception as e:
                            print(f"Error walking parent tree: {e}")
                            break

                    browser_window = window
                    browser_window_id = window.id
                    browser_offset_x = x
                    browser_offset_y = y

                    print(
                        f"Detected browser window position: x={browser_offset_x}, y={browser_offset_y}, "
                        f"width={geometry.width}, height={geometry.height}"
                    )
                    break

            except Exception as window_error:
                print(f"Error processing window: {str(window_error)}")
                continue

        if not browser_window:
            print("Chrome/Chromium window not found")

    except Exception as e:
        print(f"Failed to get browser window info: {str(e)}")


def _initialize_context(start_url):
    """Initialize or reinitialize browser context and page"""
    global context, page

    # If context already exists, close it first
    if context:
        try:
            context.close()
        except Exception as e:
            print(f"Error closing old context: {str(e)}")

    storage_state = task_config.get("storage_state", None)
    geolocation = task_config.get("geolocation", None)

    # Basic context configuration
    context_options = {
        "viewport": {"width": css_width, "height": css_height},
        "device_scale_factor": dpr,
        "is_mobile": False,
        "storage_state": storage_state,
        "geolocation": geolocation,
    }

    # Create new context and page
    context = browser.new_context(**context_options)
    context.set_default_timeout(timeout)

    # If there is an initial interface, may have multiple initial interfaces to complete complex tasks
    if start_url:
        start_urls = start_url.split(" |AND| ")
        for url in start_urls:
            new_page = context.new_page()
            new_page.goto(url, timeout=60000)
            new_page.wait_for_load_state("domcontentloaded")

        # Set the first page as the current start page
        page = context.pages[0]
        page.bring_to_front()

        # Finally register the listener
        setup_global_page_listener()
        time.sleep(2)


def _get_screenshot():
    """Get OS level screenshot and crop browser area using scrot and PIL"""
    try:
        # Make sure browser window info is available
        if not browser_window:
            _update_browser_window_info()
            if not browser_window:
                print(
                    "Warning: Unable to get browser window info, using Playwright screenshot"
                )
                return page.screenshot()

        # Create temp file path without pre-creating the file
        temp_dir = tempfile.mkdtemp()

        temp_file_path = os.path.join(temp_dir, f"{time.strftime('%Y%m%d_%H%M%S')}.png")

        # Capture screenshot using scrot
        subprocess.run(["scrot", temp_file_path], check=True)
        time.sleep(2)

        # Open the screenshot with PIL
        screenshot = Image.open(temp_file_path).convert("RGB")

        # Get browser window geometry
        try:
            geometry = browser_window.get_geometry()

            # Crop to browser window area
            left = browser_offset_x
            top = browser_offset_y
            right = left + geometry.width
            bottom = top + geometry.height

            browser_screenshot = screenshot.crop((left, top, right, bottom))

            # Convert to bytes
            buffer = io.BytesIO()
            browser_screenshot.save(buffer, format="PNG")

            # Clean up
            os.unlink(temp_file_path)

            return buffer.getvalue()

        except Exception as crop_error:
            print(f"Error cropping screenshot: {str(crop_error)}")
            # Fall back to full screenshot
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            os.unlink(temp_file_path)
            return buffer.getvalue()

    except Exception as e:
        print(f"Screenshot failed: {str(e)} {traceback.print_exc()}")
        # Fall back to Playwright screenshot
        return page.screenshot()


def setup_global_page_listener():
    """Set up global page listener to automatically switch to new pages"""

    def _handle_new_page(new_page):
        global page
        print(f"New page detected: {new_page.url}")
        old_page = page
        page = new_page
        page.wait_for_load_state("domcontentloaded")
        print(f"Switched to new page: {page.url}")

    # Add page listener
    context.on("page", _handle_new_page)


def _convert_to_os_coordinates(x, y):
    """Convert browser coordinates to OS coordinates"""
    if x is None or y is None:
        return None, None

    # Add browser window offset
    x_os = browser_offset_x + x
    y_os = browser_offset_y + y

    return x_os, y_os


def execute_single_action(action):
    """Execute a single action based on action type"""
    global page
    try:
        action_type = action["name"]
        parameters = action.get("parameters", {})

        # Action type mapping table
        action_handlers = {
            "moveTo": _execute_move_to,
            "click": _execute_click,
            "write": _execute_write,
            "dragTo": _execute_drag_to,
            "press": _execute_press,
            "callUser": _execute_call_user,
            "wait": _execute_wait,
            "response": _execute_response,
            "terminate": _execute_terminate,
            "doubleClick": _execute_double_click,
            "rightClick": _execute_right_click,
            "hotkey": _execute_hotkey,
            "swipe": _execute_swipe,
        }

        # Get the corresponding handler and execute
        handler = action_handlers.get(action_type)
        if handler:
            success = handler(parameters)
            print(f"{action_type} is done~")
            time.sleep(2)
            # Desktop special operation, listen for URL changes after each step
            current_url = page.evaluate("window.location.href")
            print(current_url)
            if current_url != page.url:
                print(f"URL has changed: {page.url} -> {current_url}")
                # Use goto instead of reload to preserve new state
                page.goto(current_url, wait_until="domcontentloaded")
            return success
        else:
            return False

    except Exception as e:
        print(f"Failed to execute action: {str(e)}")
        traceback.print_exc()
        return False


# Various operation execution functions
def _execute_move_to(parameters):
    """Move mouse to specified position"""
    x = parameters.get("x", 0)
    y = parameters.get("y", 0)

    # Convert to OS coordinates
    x_os, y_os = _convert_to_os_coordinates(x, y)
    if x_os is not None and y_os is not None:
        pyautogui.moveTo(x_os, y_os)
    return True


def _execute_click(parameters):
    """Click at specified position"""
    global page
    x = parameters.get("x", 0)
    y = parameters.get("y", 0)
    clicks = parameters.get("clicks", 1)
    button = parameters.get("button", "left")

    # Convert to OS coordinates
    x_os, y_os = _convert_to_os_coordinates(x, y)
    if x_os is not None and y_os is not None:
        # Map button names
        button_map = {"left": "left", "middle": "middle", "right": "right"}
        pyautogui.click(
            x_os, y_os, clicks=clicks, button=button_map.get(button, "left")
        )
    return True


def _execute_write(parameters):
    """Simulate keyboard typing text"""
    message = parameters.get("message", "")
    pyautogui.write(message)
    return True


def _execute_drag_to(parameters):
    """Perform drag operation"""
    end_x = parameters.get("x", 0)
    end_y = parameters.get("y", 0)
    button = parameters.get("button", "left")

    # Get current mouse position as starting point
    start_x, start_y = pyautogui.position()

    # Convert target coordinates to OS coordinates
    end_x_os, end_y_os = _convert_to_os_coordinates(end_x, end_y)
    if end_x_os is not None and end_y_os is not None:
        # Perform drag
        pyautogui.mouseDown(start_x, start_y, button=button)
        pyautogui.moveTo(end_x_os, end_y_os, duration=0.5)
        pyautogui.mouseUp(end_x_os, end_y_os, button=button)
    return True


def _execute_press(parameters):
    """Press and release specified key or key sequence"""
    keys = parameters.get("keys", [])
    presses = parameters.get("presses", 1)

    # Support single key or key list
    if isinstance(keys, str):
        if keys not in KEYBOARD_KEYS:
            return False

        key = key_mapping.get(keys, keys)
        # Single key, press specified number of times
        for _ in range(presses):
            pyautogui.press(key)
    else:
        # Key sequence, press each key in order
        for key in keys:
            if key not in KEYBOARD_KEYS:
                continue
            key = key_mapping.get(key, key)
            for _ in range(presses):
                pyautogui.press(key)
    return True


def _execute_call_user(parameters):
    """Call user, in actual operation might be a notification or callback"""
    return True


def _execute_wait(parameters):
    """Wait for specified number of seconds"""
    seconds = parameters.get("seconds", 3)
    time.sleep(seconds)
    return True


def _execute_response(parameters):
    """Send response or feedback"""
    return True


def _execute_terminate(parameters):
    """Terminate operation sequence"""
    return True


def _execute_double_click(parameters):
    """Perform double click operation"""
    x = parameters.get("x", 0)
    y = parameters.get("y", 0)

    # Convert to OS coordinates
    x_os, y_os = _convert_to_os_coordinates(x, y)
    if x_os is not None and y_os is not None:
        pyautogui.doubleClick(x_os, y_os)
    return True


def _execute_right_click(parameters):
    """Perform right-click"""
    x = parameters.get("x", 0)
    y = parameters.get("y", 0)

    # Convert to OS coordinates
    x_os, y_os = _convert_to_os_coordinates(x, y)
    if x_os is not None and y_os is not None:
        pyautogui.rightClick(x_os, y_os)
    return True


def _execute_hotkey(parameters):
    """Perform key combination operation"""
    args = parameters.get("args", [])

    # Map key names to pyautogui compatible key names
    mapped_args = [key_mapping.get(key, key) for key in args if key in KEYBOARD_KEYS]

    if mapped_args:
        pyautogui.hotkey(*mapped_args)
    return True


def _execute_swipe(parameters):
    """Perform scroll operation"""
    x1, y1 = parameters.get("from_coord", (None, None))
    x2, y2 = parameters.get("to_coord", (None, None))
    direction = parameters.get("direction", "up")
    amount = parameters.get("amount", 0.5)
    amount = max(0, min(1, amount))
    if x2 is not None and y2 is not None and x1 is not None and y1 is not None:
        delta_x = x1 - x2
        delta_y = y1 - y2
    else:
        # Keep custom logic here
        if direction in ["up", "down"]:
            distance = (
                css_height * amount if direction == "up" else -css_height * amount
            )
            delta_x, delta_y = 0, distance
        else:  # direction in ["left", "right"]
            distance = (
                css_width * amount if direction == "left" else -css_width * amount
            )
            delta_x, delta_y = distance, 0

    # If from_coord coordinates are provided, move mouse to specified location, otherwise move global page
    # If starting coordinates x1, y1 exist, use mouse move and scroll
    if x1 is not None and y1 is not None:
        page.mouse.move(x1, y1)
        page.mouse.wheel(delta_x, delta_y)
    else:
        # If x1, y1 don't exist, use JavaScript to scroll the page
        if direction in ["up", "down"]:
            js_scroll = f"window.scrollBy(0, {delta_y});"
        else:  # direction in ["left", "right"]
            js_scroll = f"window.scrollBy({delta_x}, 0);"
        page.evaluate(js_scroll)
    page.wait_for_timeout(2000)
    return True


# Evaluation functions
def evaluate_webarena(params):
    action_list = params.actions
    try:
        evaluator = webarena_evaluator_router(task_config)
        score = evaluator(action_list=action_list, task_config=task_config, page=page)
        return score

    except Exception as e:
        raise e


def evaluate_demo(**kwargs):
    return 1


# Start server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
