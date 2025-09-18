import base64
import json
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import getpass
import os
import shutil
import socket
import subprocess

from env_tools.docker_utils import execute_adb_command
import backoff
import cv2
import jsonlines
import openai
import pyshine as ps
from colorama import Fore, Style


def handle_backoff(details):
    print(f"Retry {details['tries']} for Exception: {details['exception']}")


def handle_giveup(details):
    print(
        "Backing off {wait:0.1f} seconds afters {tries} tries calling fzunction {target} with args {args} and kwargs {kwargs}".format(
            **details
        )
    )


def time_within_ten_secs(time1, time2):
    def parse_time(t):
        if "+" in t:
            t = t.split()[1]
            t = t.split(".")[0] + "." + t.split(".")[1][:6]
            format = "%H:%M:%S.%f"
        else:
            format = "%H:%M:%S"
        return datetime.strptime(t, format)

    time1_parsed = parse_time(time1)
    time2_parsed = parse_time(time2)

    time_difference = abs(time1_parsed - time2_parsed)

    return time_difference <= timedelta(seconds=10)


def print_with_color(text: str, color=""):
    if color == "red":
        print(Fore.RED + text)
    elif color == "green":
        print(Fore.GREEN + text)
    elif color == "yellow":
        print(Fore.YELLOW + text)
    elif color == "blue":
        print(Fore.BLUE + text)
    elif color == "magenta":
        print(Fore.MAGENTA + text)
    elif color == "cyan":
        print(Fore.CYAN + text)
    elif color == "white":
        print(Fore.WHITE + text)
    elif color == "black":
        print(Fore.BLACK + text)
    else:
        print(text)
    print(Style.RESET_ALL)


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


import os


def write_jsonl(data: List[dict], path: str, append: bool = False):
    with jsonlines.open(path, mode="a" if append else "w") as writer:
        for item in data:
            writer.write(item)


def del_file(path):
    for elm in Path(path).glob("*"):
        elm.unlink() if elm.is_file() else shutil.rmtree(elm)
    if os.path.exists(path):
        os.rmdir(path)


def copy_directory(source_dir, target_dir):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        target_item = os.path.join(target_dir, item)

        if os.path.isdir(source_item):
            shutil.copytree(source_item, target_item)
        else:
            shutil.copy2(source_item, target_item)


def split_chunks(lst, num_chunks):
    avg = len(lst) // num_chunks
    remainder = len(lst) % num_chunks
    chunks = []
    i = 0
    for _ in range(num_chunks):
        chunk_size = avg + (1 if remainder > 0 else 0)
        chunks.append(lst[i : i + chunk_size])
        i += chunk_size
        remainder -= 1
    return chunks


def load_json(path, encoding="utf-8"):
    return json.load(open(path, encoding=encoding))


def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_jsonl(path, encoding="utf-8"):
    res = []
    with open(path, encoding=encoding) as f:
        for line in f:
            res.append(json.loads(line))
    return res


def save_jsonl(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        for item in obj:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_jsonl(data: List[dict], path: str, append: bool = False):
    with jsonlines.open(path, mode="a" if append else "w") as writer:
        for item in data:
            writer.write(item)


def del_file(path):
    for elm in Path(path).glob("*"):
        elm.unlink() if elm.is_file() else shutil.rmtree(elm)
    if os.path.exists(path):
        os.rmdir(path)


def get_avd_serial_number(avd_name):
    try:
        result = subprocess.run(
            ["adb", "devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        devices_output = result.stdout

        devices = [
            line.split()[0]
            for line in devices_output.splitlines()
            if "device" in line and "List" not in line
        ]

        for device in devices:
            result = subprocess.run(
                ["adb", "-s", device, "emu", "avd", "name"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            avd_output = result.stdout.replace("OK", "").strip()
            # print(avd_output.replace("OK", "").strip())

            if avd_output == avd_name:
                return device

        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def execute_adb(adb_command, type="cmd", output=True, port=None):
    if type == "cmd":
        env = os.environ.copy()
        env["PATH"] = (
            f"/Users/{getpass.getuser()}/Library/Android/sdk/platform-tools:"
            + env["PATH"]
        )
        env["PATH"] = (
            f"/Users/{getpass.getuser()}/Library/Android/sdk/tools:" + env["PATH"]
        )
        result = subprocess.run(
            adb_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            executable="/bin/zsh",
            env=env,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        if output:
            print(f"Command execution failed: {adb_command}", "red")
            print(result.stderr, "red")
        return "ERROR"
    elif type == "docker":
        assert port is not None, "Port must be provided for docker type"
        result = execute_adb_command(port, adb_command)
        assert "result" in result, "Error in executing adb command"
        return result["result"]


def list_all_devices(type="cmd", port=None):
    adb_command = "adb devices"
    device_list = []
    result = execute_adb(adb_command, type, port)
    if result != "ERROR":
        devices = result.split("\n")[1:]
        for d in devices:
            device_list.append(d.split()[0])

    return device_list


def get_adb_device_name(avd_name=None):
    device_list = list_all_devices()
    for device in device_list:
        command = f"adb -s {device} emu avd name"
        ret = execute_adb(command, output=False)
        ret = ret.split("\n")[0]
        if ret == avd_name:
            return device
    return None


def find_free_ports(start_port=6060):
    def is_port_free(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) != 0

    port = start_port
    while True:
        if is_port_free(port):
            return port
        port += 1


def clone_avd(src_avd_name, tar_avd_name, android_avd_home):
    """
    Clone the source AVD to the target AVD.

    Parameters:
    - src_avd_name: The name of the source AVD folder.
    - tar_avd_name: The name of the target AVD folder.
    - android_avd_home: The path to the .android/avd directory.

    This function copies the source AVD folder and its .ini file to a new target AVD
    and updates the paths inside the .ini files accordingly.
    """

    # Paths for source and target AVD directories and .ini files
    src_avd_dir = os.path.join(android_avd_home, src_avd_name + ".avd")
    tar_avd_dir = os.path.join(android_avd_home, tar_avd_name + ".avd")
    src_ini_file = os.path.join(android_avd_home, src_avd_name + ".ini")
    tar_ini_file = os.path.join(android_avd_home, tar_avd_name + ".ini")

    # Copy the AVD folder
    print(f"====Copying the AVD folder from {src_avd_dir} to {tar_avd_dir}====")
    print("This may take a while...")
    if not os.path.exists(tar_avd_dir):
        shutil.copytree(src_avd_dir, tar_avd_dir)

    # Copy the .ini file and modify it for the new AVD
    with open(src_ini_file, "r") as src_ini, open(tar_ini_file, "w") as tar_ini:
        for line in src_ini:
            tar_ini.write(line.replace(src_avd_name, tar_avd_name))

    # Update paths inside the target AVD's .ini files
    for ini_name in ["config.ini", "hardware-qemu.ini"]:
        ini_path = os.path.join(tar_avd_dir, ini_name)
        if os.path.exists(ini_path):
            with open(ini_path, "r") as file:
                lines = file.readlines()
            with open(ini_path, "w") as file:
                for line in lines:
                    # Update paths and AVD name/ID
                    new_line = line.replace(src_avd_name, tar_avd_name)
                    file.write(new_line)

    # Update the snapshots' hardware.ini file if it exists
    snapshots_hw_ini = os.path.join(
        tar_avd_dir, "snapshots", "default_boot", "hardware.ini"
    )
    if os.path.exists(snapshots_hw_ini):
        with open(snapshots_hw_ini, "r") as file:
            lines = file.readlines()
        with open(snapshots_hw_ini, "w") as file:
            for line in lines:
                # Update AVD name/ID
                new_line = line.replace(src_avd_name, tar_avd_name)
                file.write(new_line)

    return tar_avd_dir, tar_ini_file
