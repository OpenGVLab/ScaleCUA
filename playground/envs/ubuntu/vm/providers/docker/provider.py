"""Script to download original file .
Utils and basic architecture credit to https://github.com/xlang-ai/OSWorld/blob/main/desktop_env/providers/docker/provider.py
"""

import logging
import os
import platform
import time
import docker
import psutil
import requests
from filelock import FileLock
from pathlib import Path

from envs.ubuntu.vm.providers.base import Provider

from ipdb import set_trace as st

logger = logging.getLogger("vm.providers.docker.DockerProvider")
logger.setLevel(logging.INFO)

WAIT_TIME = 3
RETRY_INTERVAL = 1
LOCK_TIMEOUT = 10


class PortAllocationError(Exception):
    pass


class DockerProvider(Provider):
    def __init__(
        self,
        region: str,
        image: str = "happysixd/osworld-docker",
        mount_mode: str = "ro",
    ):
        self.client = docker.from_env()
        self.server_port = None
        self.vnc_port = None
        self.chromium_port = None
        self.vlc_port = None
        self.container = None
        self.environment = {
            "DISK_SIZE": "32G",
            "RAM_SIZE": "8G",
            "CPU_CORES": "8",
        }  # Modify if needed
        self.image = image
        self.mount_mode = mount_mode

        temp_dir = Path(os.getenv("TEMP") if platform.system() == "Windows" else "/tmp")
        self.lock_file = (
            temp_dir / "docker_port_allocation.lck"
        )  # DEBUG: use this to avoid multi-user conflict
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

    def _get_used_ports(self):
        """Get all currently used ports (both system and Docker)."""
        # Get system ports
        system_ports = set(conn.laddr.port for conn in psutil.net_connections())

        # Get Docker container ports
        docker_ports = set()
        for container in self.client.containers.list():
            ports = container.attrs["NetworkSettings"]["Ports"]
            if ports:
                for port_mappings in ports.values():
                    if port_mappings:
                        docker_ports.update(int(p["HostPort"]) for p in port_mappings)

        return system_ports | docker_ports

    def _get_available_port(self, start_port: int) -> int:
        """Find next available port starting from start_port."""
        used_ports = self._get_used_ports()
        port = start_port
        while port < 65354:
            if port not in used_ports:
                return port
            port += 1
        raise PortAllocationError(
            f"No available ports found starting from {start_port}"
        )

    def _wait_for_vm_ready(self, timeout: int = 300):
        """Wait for VM to be ready by checking screenshot endpoint."""
        start_time = time.time()

        def check_screenshot():
            try:
                time.sleep(0.01)
                response = requests.get(
                    f"http://0.0.0.0:{self.server_port}/screenshot", timeout=(10, 10)
                )
                logger.info(f"response status code: {response.status_code}")
                return response.status_code == 200
            except Exception:
                # import traceback
                # traceback.print_exc()
                return False

        while time.time() - start_time < timeout:
            if check_screenshot():
                return True
            logger.info("Checking if virtual machine is ready...")
            time.sleep(RETRY_INTERVAL)

        raise TimeoutError("VM failed to become ready within timeout period")

    def start_emulator(self, path_to_vm: str, headless: bool, os_type: str):
        lock = FileLock(str(self.lock_file), timeout=LOCK_TIMEOUT)

        try:
            with lock:
                # Allocate all required ports
                self.vnc_port = self._get_available_port(5900)  # 8006 / 10010
                self.server_port = self._get_available_port(5000)  # 5000 / 10011
                self.chromium_port = self._get_available_port(9222)  # 9222 / 10012
                self.vlc_port = self._get_available_port(8080)  # 8080 / 10013
                self.fastapi_port = self._get_available_port(10050)

                logger.info(
                    f"trying to start container with ports - VNC: {self.vnc_port}, "
                    f"Server: {self.server_port}, Chrome: {self.chromium_port}, VLC: {self.vlc_port}, FastAPI: {self.fastapi_port}"
                )
                # Start container while still holding the lock

                # osworld-editable: This image is used to motify virtual machine file
                # happysixd/osworld-docker: This is the original osworld image, changes in virtual machine won't be kept
                self.container = self.client.containers.run(
                    self.image,
                    read_only=False,
                    environment=self.environment,
                    cap_add=["NET_ADMIN"],
                    devices=["/dev/kvm"],
                    volumes={
                        os.path.abspath(path_to_vm): {
                            "bind": "/System.qcow2",
                            "mode": self.mount_mode,
                        }
                    },
                    ports={
                        5900: self.vnc_port,  # 8006 / 10010
                        5000: self.server_port,  # 5000 / 10011
                        9222: self.chromium_port,  # 9222 / 10012
                        8080: self.vlc_port,  # 8080 / 10013
                        10050: self.fastapi_port,
                        # 5901: 5901, # only for debug
                        # 5902: 5902,
                        # 5900: 5900,
                        # 5700: 5700,
                    },
                    detach=True,
                    use_config_proxy=True,
                )

            logger.info(
                f"Started container with ports - VNC: {self.vnc_port}, "
                f"Server: {self.server_port}, Chrome: {self.chromium_port}, VLC: {self.vlc_port}"
            )

            # Wait for VM to be ready
            time.sleep(5.0)
            self._wait_for_vm_ready()

        except Exception as e:
            # Clean up if anything goes wrong
            if self.container:
                try:
                    self.container.stop()
                    self.container.remove()
                except:
                    pass
            raise e

    def get_ip_address(self, path_to_vm: str) -> str:
        if not all(
            [self.server_port, self.chromium_port, self.vnc_port, self.vlc_port]
        ):
            raise RuntimeError("VM not started - ports not allocated")
        return f"0.0.0.0:{self.server_port}:{self.chromium_port}:{self.vnc_port}:{self.vlc_port}"

    def save_state(self, path_to_vm: str, snapshot_name: str):
        raise NotImplementedError("Snapshots not available for Docker provider")

    def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str):
        self.stop_emulator(path_to_vm)

    def stop_emulator(self, path_to_vm: str):
        if self.container:
            logger.info("Stopping VM...")
            try:
                self.container.stop()
                self.container.remove()
                time.sleep(WAIT_TIME)
            except Exception as e:
                logger.error(f"Error stopping container: {e}")
            finally:
                self.container = None
                self.server_port = None
                self.vnc_port = None
                self.chromium_port = None
                self.vlc_port = None
