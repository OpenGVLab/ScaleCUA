import yaml
import os


class Config:
    def __init__(self, config_data, env_id):
        # with open(config_file, 'r', encoding='utf-8') as f:
        #     config_data = yaml.safe_load(f)
        self.avd_name = config_data.get("avd_name")
        self.docker = config_data.get("docker")
        self.docker_args = config_data.get("docker_args")
        self.is_relative_bbox = False
        self.screenshot_dir = f"./env_data/screenshot/screenshot_{env_id}"
        self.xml_dir = f"./env_data/xml/xml_{env_id}"
        self.record_dir = f"./env_data/record/record_{env_id}"
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
        if not os.path.exists(self.xml_dir):
            os.makedirs(self.xml_dir)
        if not os.path.exists(self.record_dir):
            os.makedirs(self.record_dir)

    def __str__(self):
        return f"AVD Name: {self.avd_name}, Docker: {self.docker}, Docker Args: {self.docker_args}"
