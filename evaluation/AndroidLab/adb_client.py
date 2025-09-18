import os
import shutil
import subprocess
import time
from flask import Flask, request, jsonify


def list_all_devices():
    adb_command = "adb devices"
    device_list = []
    result = EmulatorController.execute_adb(adb_command)
    if result != "ERROR":
        devices = result.split("\n")[1:]
        for d in devices:
            device_list.append(d.split()[0])

    return device_list


def get_adb_device_name(avd_name=None):
    device_list = list_all_devices()
    for device in device_list:
        command = f"adb -s {device} emu avd name"
        ret = EmulatorController.execute_adb(command)
        ret = ret.split("\n")[0]
        if ret == avd_name:
            return device
    return None


app = Flask(__name__)


class Config:
    avd_log_dir = "/logs" 


class EmulatorController:
    def __init__(self):
        self.avd_log_dir = "logs"
        self.emulator_process = None
        self.out_file = None

    @classmethod
    def execute_adb(self, adb_command):
        print(f"Executing command: {adb_command}")
        assert adb_command.startswith("adb"), "Command must start with 'adb'"
        adb_command = "/root/.android/platform-tools/adb" + adb_command[3:]

        result = subprocess.run(adb_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Return code: {result}")
        if result.returncode == 0:
            return result.stdout.strip()
        print(f"Command execution failed: {adb_command}")
        print(result.stderr)
        return "ERROR"

    def start_emulator(self, avd_name):
        print(f"Starting Android Emulator with AVD name: {avd_name}")

        if not os.path.exists(self.avd_log_dir):
            os.makedirs(self.avd_log_dir, exist_ok=True)

        self.out_file = open(os.path.join(self.avd_log_dir, 'emulator_output.txt'), 'a')
        self.emulator_process = subprocess.Popen(
            ["/root/.android/emulator/emulator", "-avd", avd_name, "-no-snapshot-save", "-no-window", "-no-audio"],
            stdout=self.out_file,
            stderr=self.out_file
        )

        print("Waiting for the emulator to start...")

        while True:
            time.sleep(1)
            try:
                device = get_adb_device_name(avd_name)
            except:
                import traceback
                traceback.print_exc()
                continue
            if device is not None:
                break

        print("Device name: ", device)
        print("AVD name: ", avd_name)

        while True:
            boot_complete = f"adb -s {device} shell getprop init.svc.bootanim"
            boot_complete = self.execute_adb(boot_complete)
            if boot_complete == 'stopped':
                print("Emulator started successfully")
                break
            time.sleep(1)

        time.sleep(1)

        device_list = list_all_devices()
        if len(device_list) == 1:
            device = device_list[0]
            print(f"Device selected: {device}")

        return device

    def stop_emulator(self, avd_name):
        print("Stopping Android Emulator...")
        if self.emulator_process:
            self.emulator_process.terminate()

        while True:
            try:
                device = get_adb_device_name(avd_name)
                command = f"adb -s {device} reboot -p"
                ret = self.execute_adb(command)
                self.emulator_process.terminate()
            except:
                device = None
            if device is None:
                print("Emulator stopped successfully")
                break
            time.sleep(1)

        if self.out_file:
            self.out_file.close()


emulator_controller = EmulatorController()


@app.route('/start', methods=['POST'])
def start():
    avd_name = request.json.get('avd_name')
    if not avd_name:
        return jsonify({"error": "No AVD name provided"}), 400

    device = emulator_controller.start_emulator(avd_name)
    return jsonify({"result": "Emulator started", "device": device})


@app.route('/stop', methods=['POST'])
def stop():
    avd_name = request.json.get('avd_name')
    if not avd_name:
        return jsonify({"error": "No AVD name provided"}), 400

    emulator_controller.stop_emulator(avd_name)
    return jsonify({"result": "Emulator stopped"})


@app.route('/execute', methods=['POST'])
def execute():
    adb_command = request.json.get('command')
    if not adb_command:
        return jsonify({"error": "No command provided"}), 400

    result = emulator_controller.execute_adb(adb_command)
    return jsonify({"result": result})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6060)
