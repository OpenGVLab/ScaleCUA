import json
import os

import jsonlines

from utils_mobile.utils import draw_bbox_multi
from utils_mobile.xml_tool import UIXMLTree



def get_compressed_xml(xml_path, type="plain_text", version="v1"):
    xml_parser = UIXMLTree()
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_str = f.read()
    try:
        compressed_xml = xml_parser.process(xml_str, level=1, str_type=type)
        if isinstance(compressed_xml, tuple):
            compressed_xml = compressed_xml[0]

        if type == "plain_text":
            compressed_xml = compressed_xml.strip()
    except Exception as e:
        compressed_xml = None
        print(f"XML compressed failure: {e}")
    return compressed_xml


class JSONRecorder:
    def __init__(self, id, instruction, page_executor, config):
        self.id = id
        self.instruction = instruction
        self.page_executor = page_executor

        self.turn_number = 0
        trace_dir = os.path.join(config.task_dir, 'traces')
        xml_dir = os.path.join(config.task_dir, 'xml')
        log_dir = config.task_dir
        if not os.path.exists(trace_dir):
            os.makedirs(trace_dir)
        if not os.path.exists(xml_dir):
            os.makedirs(xml_dir)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.trace_file_path = os.path.join(trace_dir, 'trace.jsonl')
        self.xml_file_path = os.path.join(xml_dir)
        self.log_dir = log_dir
        self.contents = []
        self.xml_history = []
        self.history = []
        self.command_per_step = []
        if config.version is None or config.version == "v1":
            self.xml_compressed_version = "v1"
        elif config.version == "v2":
            self.xml_compressed_version = "v2"

    def update_response_deprecated(self, controller, response=None, prompt="** screenshot **", need_screenshot=False,
                                   ac_status=False):
        if need_screenshot:
            self.page_executor.update_screenshot(prefix=str(self.turn_number), suffix="before")
        xml_path = None
        ac_xml_path = None

        if not ac_status:
            xml_status = controller.get_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                xml_path = "ERROR"
            else:
                xml_path = os.path.join(self.xml_file_path, str(self.turn_number) + '.xml')
        else:
            xml_status = controller.get_ac_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                ac_xml_path = "ERROR"
            else:
                ac_xml_path = os.path.join(self.xml_file_path, 'ac_' + str(self.turn_number) + '.xml')
        step = {
            "trace_id": self.id,
            "index": self.turn_number,
            "prompt": prompt if self.turn_number > 0 else f"{self.instruction}",
            "image": self.page_executor.current_screenshot,
            "xml": xml_path,
            "ac_xml": ac_xml_path,
            "response": response,
            # "url": map_url_to_real(page.url),
            "window": controller.viewport_size,
            "target": self.instruction,
            "current_activity": controller.get_current_activity()
        }
        step = self.test_per_step(step, controller)
        self.contents.append(step)

        return xml_status

    def test_per_step(self, step, controller):
        if len(self.command_per_step) == 0 or self.command_per_step[0] is None:
            return step
        step["command"] = {}
        for command in self.command_per_step:
            if "adb" not in command:
                continue
            result = controller.run_command(command)
            step["command"][command] = result
        return step

    def update_before(self, controller, prompt="** XML **", need_screenshot=False, ac_status=False, need_labeled=False):
        if need_screenshot:
            self.page_executor.update_screenshot(prefix=str(self.turn_number), suffix="before")
        xml_path = None
        ac_xml_path = None

        if not ac_status:
            xml_status = controller.get_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                xml_path = "ERROR"
            else:
                xml_path = os.path.join(self.xml_file_path, str(self.turn_number) + '.xml')
        else:
            xml_status = controller.get_ac_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                ac_xml_path = "ERROR"
            else:
                ac_xml_path = os.path.join(self.xml_file_path, str(self.turn_number) + '.xml')

        step = {
            "trace_id": self.id,
            "index": self.turn_number,
            "prompt": prompt if self.turn_number > 0 else f"{self.instruction}",
            "image": self.page_executor.current_screenshot,
            "xml": xml_path,
            "ac_xml": ac_xml_path,
            "current_activity": controller.get_current_activity(),
            "window": controller.viewport_size,
            "target": self.instruction
        }
        step = self.test_per_step(step, controller)
        if need_labeled:
            try:
                if xml_path != "ERROR" and xml_path is not None:
                    self.page_executor.set_elem_list(xml_path)
                else:
                    self.page_executor.set_elem_list(ac_xml_path)
            except:
                print("xml_path:", xml_path)
                print("ac_xml_path:", ac_xml_path)
                import traceback
                print(traceback.print_exc())
            draw_bbox_multi(self.page_executor.current_screenshot,
                            self.page_executor.current_screenshot.replace(".png", "_labeled.png"),
                            self.page_executor.elem_list)
            self.labeled_current_screenshot_path = self.page_executor.current_screenshot.replace(".png", "_labeled.png")
            step["labeled_image"] = self.labeled_current_screenshot_path

        self.contents.append(step)

    def dectect_auto_stop(self):
        if len(self.contents) <= 5:
            return
        should_stop = True
        parsed_action = self.contents[-1]['parsed_action']
        for i in range(1, 6):
            if self.contents[-i]['parsed_action'] != parsed_action:
                should_stop = False
                break
        if should_stop:
            self.page_executor.is_finish = True

    def get_latest_xml(self):
        if len(self.contents) == 0:
            return None
        # print(self.contents[-1])
        if self.contents[-1]['xml'] == "ERROR" or self.contents[-1]['xml'] is None:
            xml_path = self.contents[-1]['ac_xml']
        else:
            xml_path = self.contents[-1]['xml']
        xml_compressed = get_compressed_xml(xml_path, version=self.xml_compressed_version)
        with open(os.path.join(self.xml_file_path, f"{self.turn_number}_compressed_xml.txt"), 'w',
                  encoding='utf-8') as f:
            f.write(xml_compressed)
        self.page_executor.latest_xml = xml_compressed
        return xml_compressed

    def get_latest_xml_tree(self):
        if len(self.contents) == 0:
            return None
        print(self.contents[-1])
        if self.contents[-1]['xml'] == "ERROR" or self.contents[-1]['xml'] is None:
            xml_path = self.contents[-1]['ac_xml']
        else:
            xml_path = self.contents[-1]['xml']
        xml_compressed = get_compressed_xml(xml_path, type="json")
        return json.loads(xml_compressed)

    def update_execution(self, exe_res):
        if len(self.contents) == 0:
            return
        self.contents[-1]['parsed_action'] = exe_res
        with jsonlines.open(self.trace_file_path, 'a') as f:
            f.write(self.contents[-1])

    def update_after(self, exe_res, rsp):
        if len(self.contents) == 0:
            return
        self.contents[-1]['parsed_action'] = exe_res
        self.history.append({"role": "user", "content": "** XML **"})
        if exe_res["action"] == "Call_API":
            call_instruction = exe_res["kwargs"]["instruction"]
            call_response = exe_res["kwargs"]["response"]
            rsp = rsp + f"\n\nQuery:{call_instruction}\nResponse:{call_response}"
        self.history.append({"role": "assistant", "content": rsp})
        self.contents[-1]["current_response"] = rsp
        with jsonlines.open(self.trace_file_path, 'a') as f:
            f.write(self.contents[-1])
        self.dectect_auto_stop()
