import inspect
import json
import re
import time
from functools import partial
import xml.etree.ElementTree as ET

from utils_mobile.packages import find_package
import inspect
import json
import re
import time
from functools import partial
import xml.etree.ElementTree as ET
import os
from utils_mobile.packages import find_package


class AndroidElement:
    def __init__(self, uid, bbox, attrib, attrs):
        self.uid = uid
        self.bbox = bbox
        self.attrib = attrib
        self.attrs = attrs


def get_id_from_element(elem):
    bounds = elem.attrib["bounds"][1:-1].split("][")
    x1, y1 = map(int, bounds[0].split(","))
    x2, y2 = map(int, bounds[1].split(","))
    elem_w, elem_h = x2 - x1, y2 - y1
    if "resource-id" in elem.attrib and elem.attrib["resource-id"]:
        elem_id = elem.attrib["resource-id"].replace(":", ".").replace("/", "_")
    else:
        elem_id = f"{elem.attrib['class']}_{elem_w}_{elem_h}"
    if (
        "content-desc" in elem.attrib
        and elem.attrib["content-desc"]
        and len(elem.attrib["content-desc"]) < 20
    ):
        content_desc = (
            elem.attrib["content-desc"]
            .replace("/", "_")
            .replace(" ", "")
            .replace(":", "_")
        )
        elem_id += f"_{content_desc}"
    return elem_id


def remove_leading_zeros_in_string(s):

    return re.sub(r"(?<!\.)(?<![\d])\b0+(\d+)", r"\1", s)


def traverse_tree(xml_path, elem_list, attrib, add_index=False):
    path = []
    for event, elem in ET.iterparse(xml_path, ["start", "end"]):
        if event == "start":
            path.append(elem)
            if attrib in elem.attrib:
                if elem.attrib[attrib] != "true":
                    continue
                # if elem.attrib["text"].strip() == "" and elem.attrib["content-desc"].strip() == "":
                #     continue
                elem_attrs = {
                    "text": elem.attrib.get("text", "").strip(),
                    "content-desc": elem.attrib.get("content-desc", "").strip(),
                    "class": elem.attrib.get("class", ""),
                    "clickable": elem.attrib.get("clickable", "false"),
                    "focusable": elem.attrib.get("focusable", "false"),
                    "scrollable": elem.attrib.get("scrollable", "false"),
                }

                parent_prefix = ""
                if len(path) > 1:
                    parent_prefix = get_id_from_element(path[-2])
                bounds = elem.attrib["bounds"][1:-1].split("][")
                x1, y1 = map(int, bounds[0].split(","))
                x2, y2 = map(int, bounds[1].split(","))
                center = (x1 + x2) // 2, (y1 + y2) // 2
                elem_id = get_id_from_element(elem)
                if parent_prefix:
                    elem_id = parent_prefix + "_" + elem_id
                if add_index:
                    elem_id += f"_{elem.attrib['index']}"
                close = False
                for e in elem_list:
                    bbox = e.bbox
                    center_ = (bbox[0][0] + bbox[1][0]) // 2, (
                        bbox[0][1] + bbox[1][1]
                    ) // 2
                    dist = (
                        abs(center[0] - center_[0]) ** 2
                        + abs(center[1] - center_[1]) ** 2
                    ) ** 0.5
                    if dist <= 5:
                        close = True
                        break
                if not close:
                    elem_list.append(
                        AndroidElement(
                            elem_id, ((x1, y1), (x2, y2)), attrib, elem_attrs
                        )
                    )

        if event == "end":
            path.pop()


def is_intersecting(bbox1, bbox2):
    if bbox1[1][0] < bbox2[0][0] or bbox1[0][0] > bbox2[1][0]:
        return False
    if bbox1[1][1] < bbox2[0][1] or bbox1[0][1] > bbox2[1][1]:
        return False
    return True


class EnvAPIExecutor:
    def __init__(self, controller, config):
        self.controller = controller
        self.device = controller.device
        self.viewport_width, self.viewport_height = self.controller.get_device_size()
        self.image_width, self.image_height = 1, 1
        self.before_image = None
        self.previous_image = None
        self.is_record = False
        self.config = config
        self.screenshot_dir = config.screenshot_dir
        self.xml_dir = config.xml_dir
        self.record_dir = config.record_dir

    def __get_current_status__(self):
        page_position = None
        scroll_height = None
        status = {
            "Current URL": self.controller.get_current_activity(),
        }
        return json.dumps(status, ensure_ascii=False)

    def __call__(self, code_snippet):
        """
        self.new_page_captured = False
        self.controller.on("page", self.__capture_new_page__)
        self.current_return = None"""

        local_context = self.__get_class_methods__()
        local_context.update(**{"self": self})
        print(code_snippet.strip())
        if len(code_snippet.split("\n")) > 1:
            for code in code_snippet.split("\n"):
                if "Action: " in code:
                    code_snippet = code
                    break

        code = remove_leading_zeros_in_string(code_snippet.strip())
        exec(code, {}, local_context)
        return self.current_return

    def __get_class_methods__(self, include_dunder=False, exclude_inherited=True):
        """
        Returns a dictionary of {method_name: method_object} for all methods in the given class.

        Parameters:
        - cls: The class object to inspect.
        - include_dunder (bool): Whether to include dunder (double underscore) methods.
        - exclude_inherited (bool): Whether to exclude methods inherited from parent classes.
        """
        methods_dict = {}
        cls = self.__class__
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if exclude_inherited and method.__qualname__.split(".")[0] != cls.__name__:
                continue
            if not include_dunder and name.startswith("__"):
                continue
            methods_dict[name] = partial(method, self)
        return methods_dict

    def update_screenshot_dir(self, screenshot_dir):
        self.screenshot_dir = screenshot_dir
        self.previous_image = None
        self.before_image = None

    def update_screenshot(self, prefix=None, suffix=None):
        # time.sleep(2)
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
        if prefix is None and suffix is None:
            self.current_screenshot = (
                f"{self.screenshot_dir}/screenshot-{time.time()}.png"
            )
        elif prefix is not None and suffix is None:
            self.current_screenshot = (
                f"{self.screenshot_dir}/screenshot-{prefix}-{time.time()}.png"
            )
        elif prefix is None and suffix is not None:
            self.current_screenshot = (
                f"{self.screenshot_dir}/screenshot-{time.time()}-{suffix}.png"
            )
        else:
            self.current_screenshot = (
                f"{self.screenshot_dir}/screenshot-{prefix}-{time.time()}-{suffix}.png"
            )

        self.controller.save_screenshot(self.current_screenshot)
        if suffix == "before":
            self.previous_image = self.before_image
            self.before_image = self.current_screenshot

    def get_screen_size(self):
        return self.viewport_width, self.viewport_height

    def do(self, action=None, element=None, **kwargs):
        # assert action in ["Tap", "Type", "Swipe", "Enter", "Home", "Back", "Long Press", "Wait", "Launch", "Call_API", "Swipe Precise"], "Unsupported Action"
        if self.config.is_relative_bbox:
            if element is not None:
                element = self.modify_relative_bbox(element)
        if action == "Tap":
            # print(f"element: {element}")
            self.tap(element)
        elif action == "Type":
            print(f"element: {element}")
            self.type(element, **kwargs)
        elif action == "Swipe":
            self.swipe(element, **kwargs)
        elif action == "Enter":
            self.press_enter()
        elif action == "Home":
            self.press_home()
        elif action == "Back":
            self.press_back()
        elif action == "Long Press":
            self.long_press(element)
        elif action == "Wait":
            self.wait()
        elif action == "Swipe Precise":
            self.swipe_precise(**kwargs)
        elif action == "Launch":
            self.launch(**kwargs)
        elif action == "Call_API":
            self.call_api(**kwargs)
        else:
            return
        # self.__update_screenshot__()

    def tap(self, element):
        # print(f"element: {element}")
        print(
            f"self.viewport_width: {self.viewport_width}, self.viewport_height: {self.viewport_height}"
        )
        if isinstance(element, list) and len(element) == 4:
            center_x = (
                (element[0] + element[2]) / 2 * self.viewport_width / self.image_width
            )
            center_y = (
                (element[1] + element[3]) / 2 * self.viewport_height / self.image_height
            )
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = (
                element[0] * self.viewport_width / self.image_width,
                element[1] * self.viewport_height / self.image_height,
            )
        else:
            raise ValueError("Invalid element format")
        print(f"Tap at {center_x}, {center_y}")
        self.controller.tap(center_x, center_y)
        self.current_return = {
            "operation": "do",
            "action": "Tap",
            "kwargs": {"element": element},
        }

    def long_press(self, element):

        if isinstance(element, list) and len(element) == 4:
            center_x = (
                (element[0] + element[2]) / 2 * self.viewport_width / self.image_width
            )
            center_y = (
                (element[1] + element[3]) / 2 * self.viewport_height / self.image_height
            )
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = (
                element[0] * self.viewport_width / self.image_width,
                element[1] * self.viewport_height / self.image_height,
            )
        else:
            raise ValueError("Invalid element format")
        self.controller.long_press(center_x, center_y)
        self.current_return = {
            "operation": "do",
            "action": "Long Press",
            "kwargs": {"element": element},
        }

    def swipe(self, element=None, **kwargs):
        if element is None:
            center_x, center_y = self.controller.width // 2, self.controller.height // 2
        elif element is not None:
            if isinstance(element, list) and len(element) == 4:
                center_x = (
                    (element[0] + element[2])
                    / 2
                    * self.viewport_width
                    / self.image_width
                )
                center_y = (
                    (element[1] + element[3])
                    / 2
                    * self.viewport_height
                    / self.image_height
                )
            elif isinstance(element, list) and len(element) == 2:
                center_x, center_y = (
                    element[0] * self.viewport_width / self.image_width,
                    element[1] * self.viewport_height / self.image_height,
                )
            else:
                raise ValueError("Invalid element format")
        assert "direction" in kwargs, "direction is required for swipe"
        direction = kwargs.get("direction")
        dist = kwargs.get("dist", "medium")
        self.controller.swipe(center_x, center_y, direction, dist)
        self.current_return = {
            "operation": "do",
            "action": "Swipe",
            "kwargs": {"element": element, "direction": direction, "dist": dist},
        }
        time.sleep(1)

    def swipe_precise(self, **kwargs):
        assert "start" in kwargs, "start is required for swipe_precise"
        assert "end" in kwargs, "end is required for swipe_precise"
        start = kwargs.get("start")
        end = kwargs.get("end")
        start_x = float(start[0]) * self.viewport_width / self.image_width
        start_y = float(start[1]) * self.viewport_height / self.image_height
        end_x = float(end[0]) * self.viewport_width / self.image_width
        end_y = float(end[1]) * self.viewport_height / self.image_height
        self.controller.swipe_precise(start=[start_x, start_y], end=[end_x, end_y])
        self.current_return = {
            "operation": "do",
            "action": "Swipe Precise",
            "kwargs": {"start": start, "end": end},
        }

    def type(self, element=None, **kwargs):
        assert "text" in kwargs, "text is required for type"
        instruction = kwargs.get("text")
        if element:
            print(f"Tap at {element}")
            self.tap(element)
            time.sleep(1)
        else:
            print(f"Tap at center")

        self.controller.text(instruction)
        self.controller.enter()

        self.current_return = {
            "operation": "do",
            "action": "Type",
            "kwargs": {"text": instruction, "element": element},
        }

    def press_enter(self):
        self.controller.enter()
        self.current_return = {"operation": "do", "action": "Press Enter"}

    def press_back(self):
        self.controller.back()
        self.current_return = {"operation": "do", "action": "Press Back"}

    def press_home(self):
        self.controller.home()
        self.current_return = {"operation": "do", "action": "Press Home"}

    def finish(self, message=None):
        self.is_finish = True
        self.current_return = {
            "operation": "finish",
            "action": "finish",
            "kwargs": {"message": message},
        }

    def wait(self):
        time.sleep(5)
        self.current_return = {"operation": "do", "action": "Wait"}

    def launch(self, **kwargs):
        assert "app" in kwargs, "app is required for launch"
        app = kwargs.get("app")
        if app is None:
            return
        package = None
        try:
            package = find_package(app)
        except:
            import traceback

            traceback.print_exc()
        if package:
            self.controller.launch_app(package)
        self.current_return = {
            "operation": "do",
            "action": "Launch",
            "kwargs": {"package": package},
        }

    def kill(self, **kwargs):
        assert "app" in kwargs, "app is required for launch"
        app = kwargs.get("app")
        if app is None:
            return
        package = None
        try:
            package = find_package(app)
        except:
            import traceback

            traceback.print_exc()
        if package:
            self.controller.kill_app(package)
        self.current_return = {
            "operation": "do",
            "action": "Launch",
            "kwargs": {"package": package},
        }

    def remove_before_screenshot(self):
        try:
            if hasattr(self, "before_image") and os.path.exists(self.before_image):
                os.remove(self.before_image)
                print(f"Already delete file: {self.before_image}")
                self.before_image = None
        except Exception as e:
            print(f"Error while deleting: {str(e)}")

    def start_record(self, prefix=None, suffix=None):
        if self.is_record:
            return
        self.is_record = True
        self.controller.start_screen_record_segmented(
            prefix="test_record", save_dir=self.record_dir, segment_time=180
        )

        self.current_return = {"operation": "start_record", "action": "start_record"}

    def end_record(self):
        if not self.is_record:
            return
        self.is_record = False
        merged_video = self.controller.stop_screen_record_segmented(merge=True)
        print("Merged video address:", merged_video)

        self.current_return = {"operation": "stop_record", "action": "stop_record"}
        return merged_video if merged_video else None

    def reset(self, app_name):
        self.before_image = None
        self.previous_image = None
        self.elem_list = []
        if self.is_record:
            self.end_record()
        self.is_record = False
        self.press_home()
        if app_name:
            self.kill(app=app_name)
            self.launch(app=app_name)
        self.current_return = {"operation": "reset", "action": "reset"}
