import os
import sys
import json
import base64
import logging
import asyncio
import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from envs.ubuntu.vm.vm import VirtualMachine


#  Logger Configs {{{ #
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.addFilter(logging.Filter("vm"))
logger.addHandler(stdout_handler)


CONFIG_BASE_DIR = "/path/to/osworld-codebase/config/tasks/osworld"
VM_DIR = "/path/to/docker_vm_data"
env = None


def byte_to_b64(byte_data) -> str:
    img_b64 = base64.b64encode(byte_data).decode("utf-8")
    return img_b64

def get_json_data(request: Request):
    return asyncio.run(request.json())

def get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


app = FastAPI()

@app.get("/")
def read_root():
    return {"info": "OSWorld env api"}


@app.post("/start")
def start(request: Request):
    try:
        data = get_json_data(request)
        vm_name = data.get("vm_name", "Ubuntu.qcow2")
        action_space = data.get("action_space", "pyautogui")
        screen_width = data.get("screen_width", 1920)
        screen_height = data.get("screen_height", 1080)
        headless = data.get("headless", True)
        require_a11y_tree = data.get("require_a11y_tree", False)
        os_type = data.get("os_type", "Ubuntu")
        vm_path = data.get("vm_path", os.path.join(VM_DIR, vm_name))

        print(f"[{get_time()}] [env api] vitual machine starting...")
        global env
        env = VirtualMachine(
                path_to_vm=vm_path,
                action_space=action_space,
                screen_size=(screen_width, screen_height),
                headless=headless,
                require_a11y_tree=require_a11y_tree,
                os_type=os_type,
            )
        print(f"[{get_time()}] [env api] vitual machine done.")
        return JSONResponse({"success": True})

    except Exception as e:
        print(f"[{get_time()}] [env api] start failed:", e)
        return JSONResponse({"success": False, "message": str(e)})


@app.post("/get_task_config")
def get_task_config(request: Request):
    try:
        data = get_json_data(request)
        domain = data.get("domain")
        example_id = data.get("example_id")
        config_file = os.path.join(CONFIG_BASE_DIR, f"examples/{domain}/{example_id}.json")
        with open(config_file, "r", encoding="utf-8") as f:
            task_config = json.load(f)
        return JSONResponse({"task_config": task_config, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] get task_config failed:", e)
        return JSONResponse({"success": False, "message": str(e)})


@app.post("/reset")
# async def reset(request: Request):
#     data = await request.json()
def reset(request: Request):
    try:
        data = get_json_data(request)
        task_config = data.get("task_config", None)
        
        # import ipdb;ipdb.set_trace()
        if task_config is None:
            if 'domain' in data and 'example_id' in data:
                domain = data.get("domain")
                example_id = data.get("example_id")
                config_file = os.path.join(CONFIG_BASE_DIR, f"examples/{domain}/{example_id}.json")
                with open(config_file, "r", encoding="utf-8") as f:
                    task_config = json.load(f)
        
        print(f"[{get_time()}] [env api] task_config:{task_config}...")

        print(f"[{get_time()}] [env api] env reset starting...")
        obs = env.reset(task_config=task_config)
        print(f"[{get_time()}] [env api] env reset done...")
        screenshot = obs['screenshot']
        screenshot_b64 = byte_to_b64(screenshot)
        obs['screenshot'] = screenshot_b64
        return JSONResponse({"obs": obs, "success": True})

    except Exception as e:
        print(f"[{get_time()}] [env api] reset failed:", e)
        return JSONResponse({"success": False, "message": str(e)})

@app.get("/screenshot")
def screenshot():
    try:
        screenshot = env.controller.get_screenshot()
        screenshot_b64 = byte_to_b64(screenshot)
        return JSONResponse({"screenshot": screenshot_b64, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] get screenshot failed:", e)
        return JSONResponse({"success": False, "message": str(e)})

@app.get("/accessibility")
def accessibility():
    try:
        a11tree = env.controller.get_accessibility_tree()
        return JSONResponse({"accessibility": a11tree, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] get accessibility failed:", e)
        return JSONResponse({"success": False, "message": str(e)})        

@app.post("/step")
# async def step(request: Request):
#     data = await request.json()
def step(request: Request):
    try:
        data = get_json_data(request)
        action = data.get("action")
        pause = data.get("pause", 2)
        obs, reward, done, info = env.step(action, pause=pause)

        screenshot = obs['screenshot']
        screenshot_b64 = byte_to_b64(screenshot)
        obs['screenshot'] = screenshot_b64
        result = {
            "obs": obs,
            "reward": reward,
            "done": done,
            "info": info,
            "success": True
        }
        return JSONResponse(result)

    except Exception as e:
        print(f"[{get_time()}] [env api] step failed:", e)
        return JSONResponse({"success": False, "message": str(e)})

@app.post("/execute")
def execute(request: Request):
    try:
        data = get_json_data(request)
        command = data.get("command")
        print(f"[{get_time()}] [env api] execute command:", command)
        env.controller.execute_python_command(command)
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] execute failed:", e)
        return JSONResponse({"success": False, "message": str(e)})   

@app.get("/evaluate")
def evaluate():
    try:
        metric = env.evaluate()
        return JSONResponse({"metric": metric, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] evaluate failed:", e)
        import traceback; traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/vm_platform")
def vm_platform():
    try:
        vm_platform = env.vm_platform
        return JSONResponse({"vm_platform": vm_platform, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] get vm_platform failed:", e)
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/vm_screen_size")
def vm_screen_size():
    try:
        vm_screen_size = env.vm_screen_size
        return JSONResponse({"vm_screen_size": vm_screen_size, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] get vm_screen_size failed:", e)
        return JSONResponse({"success": False, "message": str(e)})


@app.post("/close")
def close():
    if env is None:
        print(f"[{get_time()}] [env api] No env to close.")
        return JSONResponse({"success": True})
    try:
        env.close()
        print(f"[{get_time()}] [env api] vitual machine close.")
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] closing vitual machine failed:", e)
        return JSONResponse({"success": False, "message": str(e)})

@app.get("/start_recording")
def start_recording():
    try:
        env.controller.start_recording()
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] start recording failed:", e)
        import traceback; traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)})

@app.post("/end_recording")
def end_recording(request: Request):
    try:
        data = get_json_data(request)
        save_path = data.get("save_path")
        env.controller.end_recording(save_path)
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] end recording failed:", e)
        import traceback; traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)})