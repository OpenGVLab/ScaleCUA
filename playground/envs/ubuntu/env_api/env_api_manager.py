import os
import argparse
import time
import datetime
import subprocess
import asyncio
import socket
import requests
import psutil
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

MAX_NUM_ENV = 32
START_PORT = 10150
END_PORT = 10199
# LAUNCH_SCRIPT = "PORT={} FLAG={} bash env_api_launch.sh"
LAUNCH_SCRIPT = "export PYTHONPATH=./:$PYTHONPATH;" \
                "fastapi run envs/ubuntu/env_api/env_api_launch.py --host 0.0.0.0 --port {} " \
                "2>&1 | tee log_env_api/env_api_{}.log"


process_dict = {}
port_dict = {}

def get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_json_data(request: Request):
    return asyncio.run(request.json())

def _is_free_port(port):
    ips = socket.gethostbyname_ex(socket.gethostname())[-1]
    ips.append('localhost')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return all(s.connect_ex((ip, port)) != 0 for ip in ips)

def find_free_port():
    existing_port = list(port_dict.values())
    for port in range(START_PORT, END_PORT):
        if port not in existing_port and _is_free_port(port):
            return port
    return None

def recursive_terminate(p):
    parent = psutil.Process(p.pid)
    for child in parent.children(recursive=True):  
        child.terminate()
    parent.terminate()

def request_api_wrapper(url, data=None, try_max_times=5, method="POST", timeout=60000):
    """Synchronous request API wrapper"""
    headers = {
        "Content-Type": "application/json",
    }
    for _ in range(try_max_times):
        try:
            # response = requests.post(url=url, json=data, headers=headers)
            response = requests.request(method=method, url=url, json=data, headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            response = response.json()
            is_success = response.get("success")
            if not is_success:
                message = response.get("message", None)
                print(f"API excecution error: {message}")
            else:
                return response
        except requests.RequestException as e:
            print(f"Request error, please check: {e}")
        except Exception as e:
            print(f"Unexpected error, please check: {e}")
        time.sleep(1)

    raise Exception(f"Request error for {try_max_times} times, returning None. Please check the API server.")


app = FastAPI()

@app.get("/")
def read_root():
    return {"info": "OSWorld env manager"}


@app.get("/get_pid")
def get_pid():
    return {"pid": [p.pid for p in process_dict.values()]}


@app.post("/create_env_api")
def create_env_api():
    if len(list(process_dict.keys())) >= MAX_NUM_ENV:
        print(f"[{get_time()}] [env manager] exceed maximum number of env")
        return {"success": False, "message": "exceed maximum number of env"}
    port = find_free_port()
    if port is None:
        print(f"[{get_time()}] [env manager] no free port, existing ports: {list(port_dict.values())}")
        return {"success": False, "message": "no free port"}
    
    try:
        env_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # import ipdb;ipdb.set_trace()
        script = LAUNCH_SCRIPT.format(port, env_id)
        p = subprocess.Popen(script, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            # preexec_fn=os.setpgrp)
        process_dict[env_id] = p
        port_dict[env_id] = port
        time.sleep(3)
        if p.poll() is not None:
            print(f"[{get_time()}] [env manager] create env failed. env_id: {env_id}, port: {port}")
            return {"success": False, "message": f"create env failed: {p.poll()}"}

        print(f"[{get_time()}] [env manager] create env success. env_id: {env_id}, port: {port}")
        print(f"[{get_time()}] [env manager] existing env: {len(list(process_dict.keys()))}, used ports: {list(port_dict.values())}")
        return {"success": True, "env_id": env_id, "port": port}

    except Exception as e:
        print(f"[{get_time()}] [env manager] create env failed:", e)
        return {"success": False, "message": f"create env failed: {e}"}


@app.post("/terminate_env_api")
def terminate_env_api(request: Request):
    data = get_json_data(request)
    env_id = data.get("env_id")
    p = process_dict.get(env_id, None)
    is_terminated = False
    if p:
        try:
            # p.terminate()
            # os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            port = port_dict[env_id]
            close_url = f"http://0.0.0.0:{port}/close"
            request_api_wrapper(close_url)
            recursive_terminate(p)
            is_terminated = True
            message = f"[{get_time()}] [env manager] terminate env_id: {env_id} done."
        except Exception as e:
            message = f"[{get_time()}] [env manager] terminate env_id: {env_id} failed, " + str(e)
    else:
        message = f"[{get_time()}] [env manager] env_id: {env_id} not found."
    if is_terminated:
        process_dict.pop(env_id, None)
        port_dict.pop(env_id, None)
    print(message)
    print(f"[{get_time()}] [env manager] existing env: {len(list(process_dict.keys()))}, used ports: {list(port_dict.values())}")
    return {"success": is_terminated, "message": message}


@app.post("/clean")
def clean():
    is_success = True
    message = ""
    terminated_id = []
    for env_id, p in process_dict.items():
        is_terminated = False
        try:
            port = port_dict[env_id]
            close_url = f"http://0.0.0.0:{port}/close"
            request_api_wrapper(close_url)
            recursive_terminate(p)
            is_terminated = True
        except Exception as e:
            is_success = False
            message += f"[{get_time()}] [env manager] terminate env_id: {env_id} failed, " + str(e) + "\n"
        if is_terminated:
            terminated_id.append(env_id)
    for env_id in terminated_id:
        process_dict.pop(env_id, None)
        port_dict.pop(env_id, None)
    print(f"[{get_time()}] [env manager] existing env: {len(list(process_dict.keys()))}, used ports: {list(port_dict.values())}")
    return {"success": is_success, "message": message}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=10040)
    args = parser.parse_args()
    os.makedirs('log_env_api', exist_ok=True)
    uvicorn.run(app, host=args.host, port=args.port)
