import base64
import getpass
import os
import subprocess
import time
from typing import Union
import uiautomator2 as u2
from env_tools.docker_utils import execute_adb_command, cp_docker
from utils_mobile.packages import *

# from config import load_config
from utils_mobile.utils import print_with_color
from utils_mobile.utils import time_within_ten_secs
import threading


class AndroidController:
    def __init__(self, device, type="cmd", instance=None):
        self.is_physical_device = True if type == "cmd" else False
        self.device = device
        self.type = type
        if instance is not None:
            self.port = instance.docker_port_local
            self.container_id = instance.container_id
        else:
            self.port = None
            self.container_id = None
        self.screenshot_dir = "/sdcard"
        self.xml_dir = "/sdcard"
        self.record_dir = "/sdcard"
        self.ac_xml_dir = "/sdcard/Android/data/com.example.android.xml_parser/files"
        self.width, self.height = self.get_device_size()
        self.viewport_size = (self.width, self.height)
        self.backslash = "\\"
        if self.is_physical_device:
            self.xml_device = u2.connect(device)
        else:
            power_cmd = f"adb -s {self.device} shell input keyevent KEYCODE_POWER"
            self.execute_adb(power_cmd, self.type)
            time.sleep(2)
            power_cmd = f"adb -s {self.device} shell input keyevent KEYCODE_POWER"
            self.execute_adb(power_cmd, self.type)
            self.home()
            time.sleep(3)

    def execute_adb(self, adb_command, type="cmd", output=True):
        if type == "cmd":
            # env = os.environ.copy()
            # env["PATH"] = f"/Users/{getpass.getuser()}/Library/Android/sdk/platform-tools:" + env["PATH"]
            # env["PATH"] = f"/Users/{getpass.getuser()}/Library/Android/sdk/tools:" + env["PATH"]
            # result = subprocess.run(adb_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            #                         executable='/bin/zsh', env=env)
            # if result.returncode == 0:
            #     return result.stdout.strip()
            # if output:
            #     print_with_color(f"Command execution failed: {adb_command}", "red")
            #     print_with_color(result.stderr, "red")
            # return "ERROR"
            result = subprocess.run(
                adb_command, shell=True, capture_output=True, text=True
            )
            return result.stdout
        elif type == "docker":
            port = self.port
            assert port is not None, "Port must be provided for docker type"
            result = execute_adb_command(port, adb_command)
            assert "result" in result, "Error in executing adb command"
            return result["result"]

    def get_device_size(self):
        test_time = 0
        while test_time < 10:
            try:
                command = f"adb -s {self.device} shell wm size"
                output = self.execute_adb(command, self.type)
                resolution = output.split(":")[1].strip()
                print(resolution)
                width, height = resolution.split("x")
                return int(width), int(height)
            except Exception as e:
                test_time += 1
                time.sleep(2)
        assert False, "Error in getting device size"

    def get_screenshot(self, prefix, save_dir):
        cap_command = (
            f"adb -s {self.device} shell screencap -p "
            f"{os.path.join(self.screenshot_dir, prefix + '.png').replace(self.backslash, '/')}"
        )
        pull_command = (
            f"adb -s {self.device} pull "
            f"{os.path.join(self.screenshot_dir, prefix + '.png').replace(self.backslash, '/')} "
            f"{os.path.join(save_dir, prefix + '.png')}"
        )
        result = self.execute_adb(cap_command, self.type)
        if result != "ERROR":
            result = self.execute_adb(pull_command, self.type)
            if result != "ERROR":
                return os.path.join(save_dir, prefix + ".png")
            return result
        return result

    def save_screenshot(self, save_path):
        prefix = os.path.basename(save_path).replace(".png", "")
        remote_path = f"{os.path.join(self.screenshot_dir, prefix + '.png').replace(self.backslash, '/')}"
        # print(f"remote_path: {remote_path}")
        # print(f"save_path: {save_path}")
        cap_command = f"adb -s {self.device} shell screencap -p {remote_path}"
        # check_command = f"adb -s {self.device} shell ls {remote_path}"
        pull_command = f"adb -s {self.device} pull {remote_path} {save_path}"
        result = self.execute_adb(cap_command, self.type)
        # print(f"cap_command result: {result}")
        # if result != "ERROR":
        #     result = self.execute_adb(check_command, self.type)
        #     print(f"check_command result: {result}")
        #     if result == "ERROR":
        #         return "ERROR"
        result = self.execute_adb(pull_command, self.type)
        # print(f"pull_command result: {result}")
        if result != "ERROR":
            if self.type == "docker":
                cp_docker(
                    save_path, save_path, self.container_id, local_to_docker=False
                )
            return save_path
        return result

    def get_xml(self, prefix, save_dir):
        if not self.is_physical_device:
            remote_path = os.path.join(self.xml_dir, prefix + ".xml").replace(
                self.backslash, "/"
            )
            local_path = os.path.join(save_dir, prefix + ".xml")
            dump_command = f"adb -s {self.device} shell uiautomator dump {remote_path}"
            pull_command = f"adb -s {self.device} pull {remote_path} {local_path}"

            def is_file_empty(file_path):
                return os.path.exists(file_path) and os.path.getsize(file_path) == 0

            # print("Begin to try get xml")
            for attempt in range(5):
                result = self.execute_adb(dump_command, self.type)
                # print(f"dump_command result: {result}")
                if result == "ERROR":
                    time.sleep(2)
                    continue

                result = self.execute_adb(pull_command, self.type)
                # print(f"pull_command result: {result}")
                if result == "ERROR" or is_file_empty(local_path):
                    time.sleep(2)
                    continue
                if self.type == "docker":
                    cp_docker(
                        local_path, local_path, self.container_id, local_to_docker=False
                    )
                return local_path

            # Final attempt after 3 retries
            result = self.execute_adb(dump_command, self.type)
            result = self.execute_adb(pull_command, self.type)
            if result != "ERROR" and not is_file_empty(local_path):
                if self.type == "docker":
                    cp_docker(
                        local_path, local_path, self.container_id, local_to_docker=False
                    )
                return local_path

            return result
        else:
            local_path = os.path.join(save_dir, prefix + ".xml")
            xml = self.xml_device.dump_hierarchy()
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(xml)
            return local_path

    def get_ac_xml(self, prefix, save_dir):
        remote_path = (
            f"{os.path.join(self.ac_xml_dir, 'ui.xml').replace(self.backslash, '/')}"
        )
        local_path = os.path.join(save_dir, prefix + ".xml")
        pull_command = f"adb -s {self.device} pull {remote_path} {local_path}"

        def is_file_empty(file_path):
            return os.path.exists(file_path) and os.path.getsize(file_path) == 0

        for attempt in range(5):
            result = self.execute_adb(pull_command, self.type)
            if result != "ERROR" and not is_file_empty(local_path):
                if self.type == "docker":
                    cp_docker(
                        local_path, local_path, self.container_id, local_to_docker=False
                    )
                return local_path
            time.sleep(2)

        # Final attempt after 3 retries
        result = self.execute_adb(pull_command, self.type)
        if result != "ERROR" and not is_file_empty(local_path):
            if self.type == "docker":
                cp_docker(
                    local_path, local_path, self.container_id, local_to_docker=False
                )
            return local_path

        return result

    def get_current_activity(self):
        adb_command = "adb -s {device} shell dumpsys window | grep mCurrentFocus | awk -F '/' '{print $1}' | awk '{print $NF}'"
        adb_command = adb_command.replace("{device}", self.device)
        result = self.execute_adb(adb_command, self.type)
        if result != "ERROR":
            return result
        return 0

    def get_current_app(self):
        activity = self.get_current_activity()
        app = find_app(activity)
        return app

    def back(self):
        adb_command = f"adb -s {self.device} shell input keyevent KEYCODE_BACK"
        ret = self.execute_adb(adb_command, self.type)
        return ret

    def enter(self):
        adb_command = f"adb -s {self.device} shell input keyevent KEYCODE_ENTER"
        ret = self.execute_adb(adb_command, self.type)
        return ret

    def home(self):
        adb_command = f"adb -s {self.device} shell input keyevent KEYCODE_HOME"
        ret = self.execute_adb(adb_command, self.type)
        return ret

    def restart(self):
        power_cmd = f"adb -s {self.device} shell input keyevent KEYCODE_POWER"
        self.execute_adb(power_cmd, self.type)
        print("Press power key to wake up the device")
        time.sleep(2)
        power_cmd = f"adb -s {self.device} shell input keyevent KEYCODE_POWER"
        self.execute_adb(power_cmd, self.type)
        self.home()
        print("Press home key to return to home screen")
        time.sleep(3)

    def safe_tap(self, x, y, duration=100):
        print(f"before check ime active: {self.check_ime_active()}")
        if self.check_ime_active():
            back_command = f"adb -s {self.device} shell input keyevent KEYCODE_BACK"
            self.execute_adb(back_command, self.type)
            time.sleep(0.3)
        print(f"after check ime active: {self.check_ime_active()}")
        return self.tap(x, y, duration)

    def tap(self, x, y, duration=100):
        """
        Tap action
        Args:
            x: x coordinate of tap position
            y: y coordinate of tap position
            duration: tap duration in ms, default 100ms
        """
        command = f"adb -s {self.device} shell input touchscreen tap {x} {y}"
        # print(f"ime active: {self.check_ime_active()}")
        return self.execute_adb(command, self.type)

    def text(self, input_str):
        # adb_command = f'adb -s {self.device} input keyevent KEYCODE_MOVE_END'
        # ret = self.execute_adb(adb_command, self.type)
        adb_command = f'adb -s {self.device} shell input keyevent --press $(for i in {{1..100}}; do echo -n "67 "; done)'
        ret = self.execute_adb(adb_command, self.type)
        chars = input_str
        charsb64 = str(base64.b64encode(chars.encode("utf-8")))[1:]
        # adb_command = f"adb -s {self.device} shell am broadcast -a ADB_INPUT_B64 --es msg {charsb64}"
        adb_command = f"adb -s {self.device} shell input text {chars}"
        ret = self.execute_adb(adb_command, self.type)
        return ret

    def long_press(self, x, y, duration=1000):
        adb_command = (
            f"adb -s {self.device} shell input swipe {x} {y} {x} {y} {duration}"
        )
        ret = self.execute_adb(adb_command, self.type)
        return ret

    def kill_app(self, package_name):
        command = f"adb -s {self.device} shell am force-stop {package_name}"
        self.execute_adb(command, self.type)

    def swipe(self, x, y, direction, dist: Union[str, int] = "medium", quick=False):
        if x == None:
            x = self.width // 2
        if y == None:
            y = self.height // 2
        if isinstance(dist, str):
            unit_dist = int(self.width / 10)
            if dist == "long":
                unit_dist *= 10
            elif dist == "medium":
                unit_dist *= 2
        elif isinstance(dist, int):
            unit_dist = dist
        if direction == "up":
            offset = 0, -2 * unit_dist
        elif direction == "down":
            offset = 0, 2 * unit_dist
        elif direction == "left":
            offset = -1 * unit_dist, 0
        elif direction == "right":
            offset = unit_dist, 0
        else:
            return "ERROR"
        duration = 100 if quick else 400
        adb_command = f"adb -s {self.device} shell input swipe {x} {y} {x + offset[0]} {y + offset[1]} {duration}"
        ret = self.execute_adb(adb_command, self.type)
        return ret

    def swipe_precise(self, start, end, duration=400):
        start_x, start_y = start
        end_x, end_y = end
        adb_command = f"adb -s {self.device} shell input swipe {start_x} {start_y} {end_x} {end_y} {duration}"
        ret = self.execute_adb(adb_command, self.type)
        return ret

    def check_ime_active(self):
        """
        Check whether the input method (keyboard) is active
        Returns:
            bool: True means IME is in use, False means not active
        """
        command = (
            f"adb -s {self.device} shell dumpsys input_method | grep mShowRequested"
        )
        result = self.execute_adb(command, self.type)
        return "true" in result.lower() if result else False

    def toggle_keyboard(self, enable=True):
        """
        Toggle keyboard state
        Args:
            enable: True to enable, False to disable
        """
        value = "1" if enable else "0"
        command = f"adb -s {self.device} shell settings put secure show_ime_with_hard_keyboard {value}"
        return self.execute_adb(command, self.type)

    def launch_app(self, package_name):
        command = f"adb -s {self.device} shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        ret = self.execute_adb(command, self.type)
        return ret

    def start_screen_record(self, prefix):
        print("Starting screen record")
        command = f"adb -s {self.device} shell screenrecord /sdcard/{prefix}.mp4"
        return subprocess.Popen(command, shell=True)

    def launch(self, package_name):
        command = f"adb -s {self.device} shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        self.execute_adb(command, self.type)

    def run_command(self, command):
        command = command.replace("adb", f"adb -s {self.device} ")
        return self.execute_adb(command, self.type)

    def check_ac_survive(self):
        try:
            time_command = f"adb -s {self.device} shell stat -c %y /sdcard/Android/data/com.example.android.xml_parser/files/ui.xml"
            time_phone_command = f'adb -s {self.device} shell date +"%H:%M:%S"'
            time_command_output = self.execute_adb(time_command, self.type)
            time_phone_command_output = self.execute_adb(time_phone_command, self.type)
            if time_command_output == "ERROR" or time_phone_command_output == "ERROR":
                return False
            print("time_command output:", self.execute_adb(time_command, self.type))
            print(
                "time_phone_command output:",
                self.execute_adb(time_phone_command, self.type),
            )
            result = time_within_ten_secs(
                time_command_output, time_phone_command_output
            )
        except Exception as e:
            print(e)
            return False
        return result

    def start_screen_record_segmented(
        self, prefix: str, save_dir, segment_time: int = 180
    ):
        """
        Segmented recording: continuously start screenrecord in a background thread, each segment up to segment_time seconds, until manually stopped.
        """
        self._record_stop_flag = False
        self._record_prefix = prefix
        self._record_save_dir = save_dir
        self._record_segments = []

        # Start background thread
        self._record_thread = threading.Thread(
            target=self._record_loop, args=(segment_time,), daemon=True
        )
        self._record_thread.start()
        print(
            f"[start_screen_record_segmented] Segmented recording thread started, each segment max {segment_time} seconds."
        )

    def stop_screen_record_segmented(self, merge=True):
        """
        Stop segmented recording thread, optionally merge all recorded segments.
        """
        if not self._record_thread or not self._record_thread.is_alive():
            print("[stop_screen_record_segmented] No ongoing segmented recording.")
            return "ERROR"

        print(
            "[stop_screen_record_segmented] Requesting to stop segmented recording thread..."
        )
        self._record_stop_flag = True
        self._record_thread.join()  # Wait for recording thread to fully end

        if merge:
            if len(self._record_segments) > 1:
                print("[stop_screen_record_segmented] Start merging all segments...")
                merged_path = self._merge_segments(self._record_segments)
                print(
                    f"[stop_screen_record_segmented] All segments merged => {merged_path}"
                )
                return merged_path
            elif len(self._record_segments) == 1:
                print(
                    f"[stop_screen_record_segmented] Only one segment, path: {self._record_segments[0]}"
                )
                return self._record_segments[0] if self._record_segments else "ERROR"
            else:
                print("[stop_screen_record_segmented] No segments to merge.")
                return "ERROR"
        else:
            print("[stop_screen_record_segmented] Segmented recording stopped.")
            if self._record_segments:
                print("[stop_screen_record_segmented] All segments:")
                for seg in self._record_segments:
                    print("   ", seg)
            return "STOPPED"

    def _record_loop(self, segment_time: int = 180):
        """
        Background thread: continuously start single segment recording until stop.
        """
        segment_index = 1
        while not self._record_stop_flag:
            remote_path = f"/sdcard/{self._record_prefix}_{segment_index}.mp4"
            local_path = os.path.join(
                self._record_save_dir, f"{self._record_prefix}_{segment_index}.mp4"
            )

            print(f"[record_loop] => Start recording segment {segment_index} ...")
            # Different start methods based on type
            if self.type == "cmd":
                # Local use Popen
                proc = subprocess.Popen(
                    f"adb -s {self.device} shell screenrecord --time-limit {segment_time} {remote_path}",
                    shell=True,
                )

                start_t = time.time()
                while proc.poll() is None:
                    if self._record_stop_flag:
                        print(
                            f"[record_loop] Stop requested, forcibly end segment {segment_index} recording (local) ..."
                        )
                        self._docker_force_stop_screenrecord()
                        break
                    time.sleep(0.5)

                # Wait process exit
                retcode = proc.wait(timeout=5) if proc.poll() is None else proc.poll()
                print(
                    f"[record_loop] Segment {segment_index} recording ended, returncode={retcode}"
                )

            else:
                # Docker mode: use thread + pkill
                # 1) Execute in child thread with execute_adb()
                # 2) When stop detected, pkill to terminate
                record_thread = threading.Thread(
                    target=self._docker_blocking_record,
                    args=(segment_time, remote_path),
                    daemon=True,
                )
                record_thread.start()

                # Poll wait
                while record_thread.is_alive():
                    if self._record_stop_flag:
                        print(
                            f"[record_loop] Stop requested, forcibly end segment {segment_index} recording (docker) ..."
                        )
                        self._docker_force_stop_screenrecord()
                        break
                    time.sleep(0.5)

                record_thread.join(timeout=5)
                print(
                    f"[record_loop] Segment {segment_index} (docker) recording ended."
                )
            check_cmd = f'adb shell \'[ -e {remote_path} ] && echo "exists" || echo "not_exists"\''
            check_res = self.execute_adb(check_cmd, self.type)
            print(
                f"[record_loop] Segment {segment_index} video file exists?: {check_res}"
            )
            size_cmd = f"adb -s {self.device} shell ls -l {remote_path}"
            size_res = self.execute_adb(size_cmd, self.type)
            print("remote_path file info:", size_res)
            # Pull video
            pull_cmd = f"adb -s {self.device} pull {remote_path} {local_path}"
            pull_res = self.execute_adb(pull_cmd, self.type)
            print(f"pull_res: {pull_res}")
            if pull_res != "ERROR":
                print(f"local path{local_path}")
                if self.type == "docker":
                    cp_docker(
                        local_path, local_path, self.container_id, local_to_docker=False
                    )
                print(
                    f"os.path.exists(record_save_dir):{os.path.exists(self._record_save_dir)}"
                )
                print(f"os.path.exists(local_path):{os.path.exists(local_path)}")
                print(f"os.path.getsize(local_path):{os.path.getsize(local_path)}")
                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    print(
                        f"[record_loop] Segment {segment_index} video saved locally: {local_path}"
                    )
                    self._record_segments.append(local_path)
                else:
                    self._record_segments.append(local_path)
                    print(
                        f"[record_loop] Segment {segment_index} video file is empty after pull! Possibly too short or forcibly stopped."
                    )
            else:
                print(f"[record_loop] Segment {segment_index} video file pull failed.")

            if pull_res != "ERROR":
                if self.type == "docker":
                    cp_docker(
                        local_path, local_path, self.container_id, local_to_docker=False
                    )

            # Delete residue on device
            rm_cmd = f"adb -s {self.device} shell rm {remote_path}"
            self.execute_adb(rm_cmd, self.type)

            if self._record_stop_flag:
                break
            segment_index += 1

    # ---------------------------
    # Recording/stopping methods in Docker mode
    # ---------------------------
    def _docker_blocking_record(self, segment_time: int, remote_path: str):
        """
        In docker mode, call self.execute_adb(...) to run screenrecord (blocking) until
        1) time reaches --time-limit
        2) or externally killed via self._docker_force_stop_screenrecord()
        whichever occurs first.
        """
        cmd = f"adb -s {self.device} shell screenrecord --size 720x1280 --time-limit {segment_time} {remote_path}"
        # Ensure not to remove "adb -s ..." because self.execute_adb does not auto prepend here
        print(f"[docker_blocking_record] => {cmd}")
        result = self.execute_adb(
            cmd, self.type
        )  # This blocks until screenrecord exits
        print("[docker_blocking_record] => screenrecord exited.")

    def _docker_force_stop_screenrecord(self):
        """
        In docker mode, use pkill to kill running screenrecord.
        Note: Requires pkill in Android shell; otherwise replace with ps+grep+kill.
        """
        kill_cmd = "adb shell pkill -2 screenrecord"
        # Or: kill -9 $(pidof screenrecord)
        # Or: ps | grep screenrecord | awk '{print $2}' | xargs kill -9
        print(f"[docker_force_stop_screenrecord] => {kill_cmd}")
        self.execute_adb(kill_cmd, self.type)

    # ---------------------------
    # Merge all segments
    # ---------------------------
    def _merge_segments(self, segments: list[str]) -> str:
        """Use ffmpeg to merge all segments. Requires ffmpeg installed in host or Docker container."""
        # Build a segment list file using absolute paths to ensure ffmpeg can locate segments
        txt_path = os.path.join(
            self._record_save_dir, f"{self._record_prefix}_segments.txt"
        )
        with open(txt_path, "w", encoding="utf-8") as f:
            for seg in segments:
                # Write absolute path or path relative to current working directory
                abs_path = os.path.abspath(seg)
                f.write(f"file '{abs_path}'\n")

        merged_path = os.path.join(
            self._record_save_dir, f"{self._record_prefix}_merged.mp4"
        )
        ffmpeg_cmd = (
            f"ffmpeg -y -f concat -safe 0 -i '{txt_path}' -c copy '{merged_path}'"
        )
        print(f"[merge_segments] => {ffmpeg_cmd}")

        # Use execute_adb to execute merge command to support Docker environment
        self.execute_adb(ffmpeg_cmd, "cmd")

        # Check merge result
        if os.path.exists(merged_path) and os.path.getsize(merged_path) > 0:
            print(f"[merge_segments] Merge success => {merged_path}")
            return merged_path
        else:
            print("[merge_segments] Merge failed, list file or paths may be wrong.")
            return "ERROR"


if __name__ == "__main__":
    And = AndroidController("emulator-5554")
