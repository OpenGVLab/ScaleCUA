import datetime
import time
from env_tools.docker_utils import create_docker_container, execute_command_in_container, remove_docker_container, \
    start_avd, stop_avd
import os
from utils_mobile.utils import *

class Instance():
    def __init__(self, config, idx = 0):
        self.idx = str(idx)
        self.type = "cmd"
        self.config = config
        self.container_id = None
        self.docker_port_local = None
        self.avd_name = None
        self.tar_avd_dir = None
        self.tar_ini_file = None
        self.initialize_worker()

    def initialize_worker(self):
        sdk_path = self.config.avd_base
        src_avd_name = self.config.avd_name
        self.avd_name = f"{src_avd_name}_{self.idx}"
        self.tar_avd_dir, self.tar_ini_file = clone_avd(src_avd_name, self.avd_name, sdk_path)

    def initialize_single_task(self, config = None):
        avd_name = self.avd_name
        print_with_color(f"Starting Android Emulator with AVD name: {avd_name}", "blue")
        if not os.path.exists(self.config.avd_log_dir):
            os.makedirs(self.config.avd_log_dir, exist_ok=True)
        out_file = open(os.path.join(self.config.avd_log_dir, f'emulator_output_{self.idx}.txt'), 'a')

        if self.config.show_avd:
            emulator_process = subprocess.Popen(["emulator", "-avd", avd_name, "-no-snapshot-save"], stdout=out_file,
                                                stderr=out_file)
        else:
            emulator_process = subprocess.Popen(
                ["emulator", "-avd", avd_name, "-no-snapshot-save", "-no-window", "-no-audio"], stdout=out_file,
                stderr=out_file)
        print_with_color(f"Waiting for the emulator to start...", "blue")
        while True:
            try:
                device = get_adb_device_name(avd_name)
            except:
                continue
            if device is not None:
                break

        print("Device name: ", device)
        print("AVD name: ", avd_name)

        while True:
            boot_complete = f"adb -s {device} shell getprop init.svc.bootanim"
            boot_complete = execute_adb(boot_complete, output=False)
            if boot_complete == 'stopped':
                print_with_color("Emulator started successfully", "blue")
                break
            time.sleep(1)
        time.sleep(1)
        self.emulator_process = emulator_process
        self.out_file = out_file
        device_list = list_all_devices()
        if len(device_list) == 1:
            device = device_list[0]
            print_with_color(f"Device selected: {device}", "yellow")
        else:
            device = get_avd_serial_number(avd_name)
        return device

    def stop_single_task(self):
        print_with_color("Stopping Android Emulator...", "blue")
        self.emulator_process.terminate()

        while True:
            try:
                device = get_adb_device_name(self.config.avd_name)
                command = f"adb -s {device} reboot -p"
                ret = execute_adb(command, output=False)
                self.emulator_process.terminate()
            except:
                device = None
            if device is None:
                print_with_color("Emulator stopped successfully", "blue")
                break
            time.sleep(1)
        self.out_file.close()
        if os.path.exists(os.path.join(self.config.avd_log_dir, f'emulator_output_{self.idx}.txt')):
            os.remove(os.path.join(self.config.avd_log_dir, f'emulator_output_{self.idx}.txt'))

    def __del__(self):
        if self.tar_avd_dir is not None:
            shutil.rmtree(self.tar_avd_dir)
        if self.tar_ini_file is not None:
            os.remove(self.tar_ini_file)
        try:
            self.emulator_process.terminate()
        except:
            pass
        try:
            self.out_file.close()
        except:
            pass

class Docker_Instance(Instance):
    def __init__(self, config, idx = 0):
        self.controller = None
        self.idx = idx
        self.config = config
        self.container_id = None
        self.docker_port_local = None
        self.initialize_worker(config)
        self.screenshot_dir = config.screenshot_dir
        self.record_dir = config.record_dir
        self.xml_dir = config.xml_dir
        
    def initialize_worker(self, config):
        self.config = config
        print_with_color(f"Starting Android Emulator in docker with AVD name: {config.avd_name}", "blue")
        docker_port_local = find_free_ports(start_port=6060 + self.idx)
        self.docker_port_local = docker_port_local
        print(f"Local port: {docker_port_local}")

    def initialize_single_task(self,config):
        docker_image_name = config.docker_args.get("image_name")
        docker_port = config.docker_args.get("port")
        container_id = create_docker_container(docker_image_name, docker_port, self.docker_port_local)

        # TODO: python location should be configurable
        command = "/usr/local/bin/python adb_client.py > server.txt 2>&1"
        execute_command_in_container(container_id, command)
        execute_command_in_container(container_id, command)
        self.container_id = container_id
        time.sleep(3)

        avd_name = config.avd_name
        result = start_avd(self.docker_port_local, avd_name)
        device = result.get("device")

        print("Device name: ", device)
        print("AVD name: ", avd_name)

        self.make_dirs()
        # execute_command_in_container(self.container_id, f"mkdir -p {config.rsp_dir}")
        time.sleep(10)
        return device
    
    def make_dirs(self):
        execute_command_in_container(self.container_id, f"mkdir -p {self.screenshot_dir}")
        execute_command_in_container(self.container_id, f"mkdir -p {self.xml_dir}")
        execute_command_in_container(self.container_id, f"mkdir -p {self.record_dir}")

    def stop_single_task(self):
        print_with_color("Stopping Android Emulator in docker...", "blue")
        remove_docker_container(self.container_id)
        #stop_avd(self.docker_port_local, self.config.avd_name)
        print_with_color("Emulator stopped successfully", "blue")

    def __del__(self):
        try:
            if self.container_id is not None:
                remove_docker_container(self.container_id)
        except:
            pass