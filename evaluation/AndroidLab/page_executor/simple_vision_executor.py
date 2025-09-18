import time
import xml.etree.ElementTree as ET

from page_executor.text_executor import TextOnlyExecutor


class AndroidElement:
    def __init__(self, uid, bbox, attrib):
        self.uid = uid
        self.bbox = bbox
        self.attrib = attrib


def get_id_from_element(elem):
    bounds = elem.attrib["bounds"][1:-1].split("][")
    x1, y1 = map(int, bounds[0].split(","))
    x2, y2 = map(int, bounds[1].split(","))
    elem_w, elem_h = x2 - x1, y2 - y1
    if "resource-id" in elem.attrib and elem.attrib["resource-id"]:
        elem_id = elem.attrib["resource-id"].replace(":", ".").replace("/", "_")
    else:
        elem_id = f"{elem.attrib['class']}_{elem_w}_{elem_h}"
    if "content-desc" in elem.attrib and elem.attrib["content-desc"] and len(elem.attrib["content-desc"]) < 20:
        content_desc = elem.attrib['content-desc'].replace("/", "_").replace(" ", "").replace(":", "_")
        elem_id += f"_{content_desc}"
    return elem_id


def traverse_tree(xml_path, elem_list, attrib, add_index=False):
    path = []
    for event, elem in ET.iterparse(xml_path, ['start', 'end']):
        if event == 'start':
            path.append(elem)
            if attrib in elem.attrib:
                if elem.attrib[attrib] != "true":
                    if elem.attrib["text"].strip() == "" and elem.attrib["content-desc"].strip() == "":
                        continue
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
                    center_ = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
                    dist = (abs(center[0] - center_[0]) ** 2 + abs(center[1] - center_[1]) ** 2) ** 0.5
                    if dist <= 5:
                        close = True
                        break
                if not close:
                    elem_list.append(AndroidElement(elem_id, ((x1, y1), (x2, y2)), attrib))

        if event == 'end':
            path.pop()


class VisionExecutor(TextOnlyExecutor):
    def __init__(self, controller, config):
        self.controller = controller
        self.device = controller.device
        self.screenshot_dir = config.screenshot_dir
        self.task_id = int(time.time())

        self.new_page_captured = False
        self.current_screenshot = None
        self.current_return = None

        self.last_turn_element = None
        self.last_turn_element_tagname = None
        self.is_finish = False
        self.device_pixel_ratio = None
        self.latest_xml = None
        # self.glm4_key = config.glm4_key

        # self.device_pixel_ratio = self.page.evaluate("window.devicePixelRatio")

    def set_elem_list(self, xml_path):
        clickable_list = []
        focusable_list = []
        traverse_tree(xml_path, clickable_list, "clickable", True)
        traverse_tree(xml_path, focusable_list, "focusable", True)
        elem_list = []
        for elem in clickable_list:
            elem_list.append(elem)
        for elem in focusable_list:
            bbox = elem.bbox
            center = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
            close = False
            for e in clickable_list:
                bbox = e.bbox
                center_ = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
                dist = (abs(center[0] - center_[0]) ** 2 + abs(center[1] - center_[1]) ** 2) ** 0.5
                if dist <= 10:  # configs["MIN_DIST"]
                    close = True
                    break
            if not close:
                elem_list.append(elem)
        self.elem_list = elem_list

    def tap(self, index):
        assert 0 < index <= len(self.elem_list), f"Tap Index {index} out of range"
        tl, br = self.elem_list[index - 1].bbox
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        ret = self.controller.tap(x, y)
        self.current_return = {"operation": "do", "action": 'Tap', "kwargs": {"element": (x, y)}}

    def text(self, input_str):
        self.controller.text(input_str)
        self.current_return = {"operation": "do", "action": 'Type', "kwargs": {"text": input_str}}

    def type(self, input_str):
        self.controller.text(input_str)
        self.current_return = {"operation": "do", "action": 'Type', "kwargs": {"text": input_str}}

    def long_press(self, index):
        tl, br = self.elem_list[index - 1].bbox
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        ret = self.controller.long_press(x, y)
        self.current_return = {"operation": "do", "action": 'Long Press', "kwargs": {"element": (x, y)}}

    def swipe(self, index, direction, dist):
        tl, br = self.elem_list[index - 1].bbox
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        ret = self.controller.swipe(x, y, direction, dist)
        self.current_return = {"operation": "do", "action": 'Swipe',
                               "kwargs": {"element": (x, y), "direction": direction, "dist": dist}}

    def back(self):
        self.controller.back()
        self.current_return = {"operation": "do", "action": 'Back', "kwargs": {}}

    def home(self):
        self.controller.home()
        self.current_return = {"operation": "do", "action": 'Home', "kwargs": {}}

    def wait(self, interval=5):
        if interval < 0 or interval > 10:
            interval = 5
        time.sleep(interval)
        self.current_return = {"operation": "do", "action": 'Wait', "kwargs": {"interval": interval}}

    def enter(self):
        self.controller.enter()
        self.current_return = {"operation": "do", "action": 'Enter', "kwargs": {}}

    def launch(self, app_name):
        self.controller.launch(app_name)
        self.current_return = {"operation": "do", "action": 'Launch', "kwargs": {"app_name": app_name}}

    def finish(self, message=None):
        self.is_finish = True
        self.current_return = {"operation": "finish", "action": 'finish', "kwargs": {"message": message}}
