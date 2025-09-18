import datetime
import time
from evaluation.configs import TaskConfig
from evaluation.docker_utils import (
    create_docker_container,
    execute_command_in_container,
    remove_docker_container,
    start_avd,
    stop_avd,
)
from evaluation.evaluation import *
from evaluation.utils import *
from page_executor import TextOnlyExecutor, PixelLevelExecutor
from page_executor.simple_vision_executor import VisionExecutor
from recorder import JSONRecorder
from templates import *
from templates.packages import find_package


class Instance:
    def __init__(self, config, idx=0):
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
        self.tar_avd_dir, self.tar_ini_file = clone_avd(
            src_avd_name, self.avd_name, sdk_path
        )

    def initialize_single_task(self, config=None):
        avd_name = self.avd_name
        print_with_color(f"Starting Android Emulator with AVD name: {avd_name}", "blue")
        if not os.path.exists(self.config.avd_log_dir):
            os.makedirs(self.config.avd_log_dir, exist_ok=True)
        out_file = open(
            os.path.join(self.config.avd_log_dir, f"emulator_output_{self.idx}.txt"),
            "a",
        )

        if self.config.show_avd:
            emulator_process = subprocess.Popen(
                ["emulator", "-avd", avd_name, "-no-snapshot-save"],
                stdout=out_file,
                stderr=out_file,
            )
        else:
            emulator_process = subprocess.Popen(
                [
                    "emulator",
                    "-avd",
                    avd_name,
                    "-no-snapshot-save",
                    "-no-window",
                    "-no-audio",
                ],
                stdout=out_file,
                stderr=out_file,
            )
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
            if boot_complete == "stopped":
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
        if os.path.exists(
            os.path.join(self.config.avd_log_dir, f"emulator_output_{self.idx}.txt")
        ):
            os.remove(
                os.path.join(self.config.avd_log_dir, f"emulator_output_{self.idx}.txt")
            )

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
    def __init__(self, config, idx=0):
        self.idx = idx
        self.config = config
        self.container_id = None
        self.docker_port_local = None
        self.initialize_worker(config)

    def initialize_worker(self, config):
        self.config = config
        print_with_color(
            f"Starting Android Emulator in docker with AVD name: {config.avd_name}",
            "blue",
        )
        docker_port_local = find_free_ports(start_port=6060 + self.idx)
        self.docker_port_local = docker_port_local
        print(f"Local port: {docker_port_local}")

    def initialize_single_task(self, config):
        docker_image_name = config.docker_args.get("image_name")
        docker_port = config.docker_args.get("port")
        container_id = create_docker_container(
            docker_image_name, docker_port, self.docker_port_local
        )

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

        execute_command_in_container(self.container_id, f"mkdir -p {config.task_dir}")
        execute_command_in_container(self.container_id, f"mkdir -p {config.trace_dir}")
        execute_command_in_container(
            self.container_id, f"mkdir -p {config.screenshot_dir}"
        )
        execute_command_in_container(self.container_id, f"mkdir -p {config.xml_dir}")
        time.sleep(10)
        return device

    def stop_single_task(self):
        print_with_color("Stopping Android Emulator in docker...", "blue")
        remove_docker_container(self.container_id)
        # stop_avd(self.docker_port_local, self.config.avd_name)
        print_with_color("Emulator stopped successfully", "blue")

    def __del__(self):
        try:
            if self.container_id is not None:
                remove_docker_container(self.container_id)
        except:
            pass


class AutoTest:
    def __init__(self, config: TaskConfig) -> None:
        self.config = config

    def prepare_for_task(self):
        os.makedirs(self.config.save_dir, exist_ok=True)
        self.config.task_dir = os.path.join(self.config.save_dir, self.config.task_name)
        self.config.log_path = os.path.join(
            self.config.task_dir, f"log_explore_{self.config.task_name}.jsonl"
        )
        self.config.trace_dir = os.path.join(self.config.task_dir, "traces")
        self.config.screenshot_dir = os.path.join(self.config.task_dir, "Screen")
        self.config.xml_dir = os.path.join(self.config.task_dir, "xml")
        if not os.path.exists(self.config.task_dir):
            os.mkdir(self.config.task_dir)
        os.makedirs(self.config.trace_dir, exist_ok=True)
        os.makedirs(self.config.screenshot_dir, exist_ok=True)
        os.makedirs(self.config.xml_dir, exist_ok=True)

    def start_emulator(self, instance):
        if self.config.docker:
            type = "docker"
        else:
            type = "cmd"
        device = instance.initialize_single_task(self.config)

        self.controller = AndroidController(device, type, instance)
        self.controller.run_command("adb root")
        self.controller.run_command("adb emu geo fix -122.156 37.438")
        if "map.me" not in self.instruction:
            self.controller.run_command('adb shell date "2024-05-10 12:00:00"')
        # self.controller.run_command("adb install /raid/xuyifan/data/ADBKeyboard.apk")
        # time.sleep(5)
        # self.controller.run_command("adb shell ime set com.android.adbkeyboard/.AdbIME")

        if self.config.mode == "in_app":
            self.controller.launch_app(find_package(self.app))
            time.sleep(15)

    def run_serial(self, tasks):
        if self.config.docker:
            instance = Docker_Instance(self.config)
        else:
            instance = Instance(self.config)
        for task in tasks:
            self.run_task(task, instance)

    def run_task(self, task_dict, instance):
        task_id = task_dict["task_id"]
        demo_timestamp = int(time.time())
        self.config.task_name = (
            task_id
            + "_"
            + datetime.datetime.fromtimestamp(demo_timestamp).strftime(
                "%Y-%m-%d_%H-%M-%S"
            )
        )
        # print(f"{task_id} running in {instance.container_id}")

        self.instruction = task_dict["task_instruction"]
        self.app = task_dict["app"]
        if not self.config.sample:
            self.command_per_step = task_dict["command_per_step"]
        else:
            self.command_per_step = None
        self.prepare_for_task()
        self.start_emulator(instance)
        self.llm_agent = task_dict["agent"]

        print_with_color(self.instruction, "green")
        round_count = 0
        task_complete = False

        self.page_executor = self.get_executor()

        self.record = JSONRecorder(
            id=self.config.task_name,
            instruction=self.instruction,
            page_executor=self.page_executor,
            config=self.config,
        )
        task_agent = self.get_agent()
        while round_count < self.config.max_rounds:
            try:
                round_count += 1
                print_with_color(f"Round {round_count}", "yellow")
                task_agent.run_step(round_count)
                print_with_color(
                    "Thinking about what to do in the next step...", "yellow"
                )
                time.sleep(self.config.request_interval)

                if task_agent.page_executor.is_finish:
                    print_with_color(f"Completed successfully.", "yellow")
                    task_agent.page_executor.update_screenshot(prefix="end")
                    task_complete = True
                    break
            except Exception as e:
                import traceback

                print(traceback.print_exc())

                print_with_color(f"Error: {e}", "red")
                break

        instance.stop_single_task()
        if task_complete:
            print_with_color(
                f"Completed successfully. {round_count} rounds generated.", "green"
            )
        elif round_count == self.config.max_rounds:
            print_with_color(
                f"Finished due to reaching max rounds. {round_count} rounds generated.",
                "yellow",
            )
        else:
            print_with_color(
                f"Finished unexpectedly. {round_count} rounds generated.", "red"
            )

    def get_agent(self):
        return NotImplementedError

    def get_executor(self):
        return NotImplementedError


class TextOnlyMobileTask_AutoTest(AutoTest):
    def get_agent(self):
        task_agent = TextOnlyTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent

    def get_executor(self):
        return TextOnlyExecutor(self.controller, self.config)


class ScreenshotMobileTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = ScreenshotTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent

    def get_executor(self):
        return VisionExecutor(self.controller, self.config)


class PixellevelMobileTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = PixellevelTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent

    def get_executor(self):
        return PixelLevelExecutor(self.controller, self.config)


class ScreenshotMobileTask_AutoTest_for_show(ScreenshotMobileTask_AutoTest):
    def start_emulator_cmd(self, avd_name):
        print_with_color(f"Starting Android Emulator with AVD name: {avd_name}", "blue")
        while True:
            try:
                device = get_adb_device_name(avd_name)
            except:
                continue
            if device is not None:
                break
        # TODO: fix open emulator bug here
        print("Device name: ", device)
        print("AVD name: ", avd_name)

        self.emulator_process = None
        self.out_file = None
        device_list = list_all_devices()
        if len(device_list) == 1:
            device = device_list[0]
            print_with_color(f"Device selected: {device}", "yellow")
        else:
            device = get_avd_serial_number(avd_name)
        return device

    def stop_emulator(self, instance):
        print_with_color("Skip Stopping Android Emulator...", "blue")


class CogAgentTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = CogAgentTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent

    def get_executor(self):
        return VisionExecutor(self.controller, self.config)


class ScreenSeeActTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = ScreenSeeActTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent


class ScreenReactTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = ScreenshotReactTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent

    def get_executor(self):
        return VisionExecutor(self.controller, self.config)


class TextOnlyReactTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = TextOnlyReactTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent


class TextOnlyFineTuneTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = TextOnlyFineTuneTask(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent


class TextOnlyFineTuneTask_long_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = TextOnlyFineTuneTask_long(
            self.instruction,
            self.controller,
            self.page_executor,
            self.llm_agent,
            self.record,
            self.command_per_step,
        )
        return task_agent
