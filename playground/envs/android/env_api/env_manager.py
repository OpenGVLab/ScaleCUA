# env_manager.py
import os
import json
from typing import Dict, Optional
import uuid
from dataclasses import dataclass
import time
from env_tools.docker import Docker_Instance
from env_tools.config import Config
from utils_mobile.and_controller import AndroidController
from env_tools.env_executor import EnvAPIExecutor


class EnvManager:
    def __init__(self):
        self.environments = {}

    def start_emulator(self, instance, config):
        device = instance.initialize_single_task(config)

        instance.controller = AndroidController(device, "docker", instance)
        instance.controller.run_command("adb root")
        instance.controller.run_command("adb emu geo fix -122.156 37.438")

    def create_env(self, config_dict):
        env_id = str(uuid.uuid4())
        config = Config(config_dict, env_id)
        # print(config)
        if config.docker:
            instance = Docker_Instance(config)
            self.start_emulator(instance, config)
            page_executor = self.get_executor(instance.controller, config)
            self.environments[env_id] = {
                "config": config,
                "instance": instance,
                "controller": instance.controller,
                "page_executor": page_executor,
                "step": 0,
                "type": "docker",
                "status": "initialized"
            }
            return env_id
        else:
            controller = AndroidController(config.avd_name, "cmd", None)
            page_executor = self.get_executor(controller, config)
            self.environments[env_id] = {
                "config": config,
                "instance": None,
                "controller": controller,
                "page_executor": page_executor,
                "step": 0,
                "type": "physical_device",
                "status": "initialized"
            }
            return env_id
            

    def get_screenshot(self, env_id: str, prefix: Optional[str] = None, suffix: Optional[str] = "before"):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        page_executor = env["page_executor"]
        if prefix != None:
            page_executor.update_screenshot(prefix = str(env.get("step")) + "_" + prefix, suffix = suffix)
        else:
            page_executor.update_screenshot(prefix = str(env.get("step")), suffix = suffix)
        return page_executor.current_screenshot

    def get_screen_size(self, env_id: str):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        page_executor = env["page_executor"]
        return page_executor.get_screen_size()

    def step(self, env_id, action=None, element=None, **kwargs):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        page_executor = env["page_executor"]
        page_executor.do(action, element, **kwargs)
        env["step"] += 1

    def stop(self, env_id: str):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        instance = env["instance"]
        if instance:
            instance.stop_single_task()
    
    def get_executor(self, controller, config):
        return EnvAPIExecutor(controller, config)
    
    def get_xml(self, env_id: str):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        controller = env["controller"]
        config = env["config"]
        if env['type'] == "docker":
            ac_status = controller.check_ac_survive()
        else:
            ac_status = False
        if not ac_status:
            xml_status = controller.get_xml(prefix=str(env.get("step")), save_dir=config.xml_dir)
            print(xml_status)
            if "ERROR" in xml_status:
                xml_status = controller.get_ac_xml(prefix=str(env.get("step")), save_dir=config.xml_dir)
                if "ERROR" in xml_status:
                    xml_path = "ERROR"
                else:
                    xml_path = os.path.join(config.xml_dir, str(env.get("step")) + '.xml')
            else:
                xml_path = os.path.join(config.xml_dir, str(env.get("step")) + '.xml')
            return xml_path
        else:
            print("AC mode")
            xml_status = controller.get_ac_xml(prefix=str(env.get("step")), save_dir=config.xml_dir)
            if "ERROR" in xml_status:
                xml_status = controller.get_xml(prefix=str(env.get("step")), save_dir=config.xml_dir)
                if "ERROR" in xml_status:
                    ac_xml_path = "ERROR"
                else:
                    ac_xml_path = os.path.join(config.xml_dir, str(env.get("step")) + '.xml')
            else:
                ac_xml_path = os.path.join(config.xml_dir, str(env.get("step")) + '.xml')
            return ac_xml_path
        
    def start_record(self, env_id: str):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        page_executor = env["page_executor"]
        page_executor.start_record()
    
    def end_record(self, env_id: str):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        page_executor = env["page_executor"]
        
        return page_executor.end_record()
    
    def reset(self, env_id: str, app_name: Optional[str] = None):
        env = self.environments.get(env_id)
        if env is None:
            raise ValueError(f"Environment {env_id} not found")
        page_executor = env["page_executor"]
        page_executor.reset(app_name)
        

    

if __name__ == "__main__":
    manager = EnvManager()
#     server_path: http://127.0.0.1
# platform: android
# manager_port: 8000
# avd_name: f44cdae5
# docker: False
# docker_args:
#   image_name: android_eval:latest
#   port: 6060
    env_id = manager.create_env({
        "server_path": "http://127.0.0.1",
        "platform": "android",
        "manager_port": 8000,
        "avd_name": "Pixel_7_Pro_API_33",
        "docker": True,
        "docker_args": {
            "image_name": "android_eval:latest",
            "port": 6060
        },
    })
    # manager.get_screenshot(env_id)
    # print(manager.get_xml(env_id))
    manager.start_record(env_id)
    time.sleep(5)
    manager.end_record(env_id)
    manager.reset(env_id, "settings")