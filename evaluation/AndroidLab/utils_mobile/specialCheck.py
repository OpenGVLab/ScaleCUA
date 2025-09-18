import math
import re
from collections import deque


def bounds_to_coords(bounds_string):
    pattern = r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"
    matches = re.findall(pattern, bounds_string)
    return list(map(int, matches[0]))


def coords_to_bounds(bounds):
    return f"[{bounds[0]},{bounds[1]}][{bounds[2]},{bounds[3]}]"


def check_valid_bounds(bounds):
    bounds = bounds_to_coords(bounds)

    return bounds[0] >= 0 and bounds[1] >= 0 and \
        bounds[0] < bounds[2] and bounds[1] < bounds[3]


def check_point_containing(bounds, x, y, window, threshold=0):
    bounds = bounds_to_coords(bounds)

    screen_threshold_x = threshold * window[0]
    screen_threshold_y = threshold * window[1]

    return bounds[0] - screen_threshold_x <= x <= bounds[2] + screen_threshold_x and \
        bounds[1] - screen_threshold_y <= y <= bounds[3] + screen_threshold_y


def check_bounds_containing(bounds_contained, bounds_containing):
    bounds_contained = bounds_to_coords(bounds_contained)
    bounds_containing = bounds_to_coords(bounds_containing)

    return bounds_contained[0] >= bounds_containing[0] and \
        bounds_contained[1] >= bounds_containing[1] and \
        bounds_contained[2] <= bounds_containing[2] and \
        bounds_contained[3] <= bounds_containing[3]


def check_bounds_intersection(bounds1, bounds2):
    bounds1 = bounds_to_coords(bounds1)
    bounds2 = bounds_to_coords(bounds2)

    return bounds1[0] < bounds2[2] and bounds1[2] > bounds2[0] and \
        bounds1[1] < bounds2[3] and bounds1[3] > bounds2[1]


def get_bounds_area(bounds):
    bounds = bounds_to_coords(bounds)
    return (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])


def get_bounds_center(bounds):
    bounds = bounds_to_coords(bounds)
    return (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2


def calculate_point_distance(x1, y1, x2, y2):
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return distance


def compare_bounds_area(bounds1, bounds2):
    """
    :return:
        if bounds1 is smaller than bounds2, return true
        else return false
    """
    return get_bounds_area(bounds1) < get_bounds_area(bounds2)


def compare_y_in_bounds(bounds1, bounds2):
    """
    :return:
        if y in bounds1 is smaller than that in bounds2, return true
        else return false
    """
    bounds1 = bounds_to_coords(bounds1)
    bounds2 = bounds_to_coords(bounds2)

    return bounds1[1] < bounds2[1] and bounds1[3] < bounds2[3]


class MiniMapSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()

        self.base_node = None
        self.retrieve_times = 0
        if page == "filter":
            self.recycler_node = None
            self.recycler_bounds = "[0,0][0,0]"
            self.check_filter(page_type)
        elif page == "route":
            self.check_route(page_type)
        elif page == "search-result":
            self.check_search_result(page_type)

    def check_page(self):
        page_map = {
            "filter": [
                (["距离优先", "推荐排序", "好评优先"], "推荐排序"),
                (["距离", "km内"], "位置距离"),
                (["烤肉", "烧烤", "螺蛳粉"], "全部分类"),
                (["烤肉", "烧烤", "蛋糕店"], "全部分类"),
                (["水产海鲜", "火锅", "熟食"], "全部分类"),
                (["水产海鲜", "火锅", "早餐"], "全部分类"),
                (["星级(可多选)", "价格"], "星级酒店"),
                (["品牌", "宾客类型", "特色主题"], "更多筛选"),
                (["92#", "95#", "98#", "0#"], "油类型"),
                (["全部品牌", "中国石化", "中国石油", "壳牌"], "全部品牌")
            ],
            "route": [
                (["驾车", "火车", "步行", "收起"], "出行方式"),
                (["选择日期", "日", "一", "二", "三", "四", "五", "六"], "选择日期"),
                (["选择出发时间弹窗", "现在出发"], "选择出发时间"),
                (["选择出发时间", "确定"], "选择出发时间_taxi")
            ],
            "search-result": [
                (["周边", "收藏", "分享", "打车"], "周边收藏")
            ]
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None

    def get_filter_base_node(self, node, page_type):
        page_criteria = {
            "推荐排序": [("距离优先", 14)],
            "位置距离": [("km内", 8)],
            "全部分类": [("烤肉", 14), ("火锅", 14)],
            "星级酒店": [("星级(可多选)", 10)],
            "更多筛选": [("品牌", 9)],
            "全部品牌": [("全部品牌", 14)],
            "油类型": [("95#", 14)]
        }

        pattern_need_fuzzy = ["km内"]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                        (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        # Find a node that can scroll in a loop.
        if 'RecyclerView' in node.attrib.get('class', '') and 'true' in node.attrib.get('scrollable', ''):
            # If the node is not unique, find the one that is larger.
            if compare_bounds_area(self.recycler_bounds, node.attrib['bounds']):
                self.recycler_node = node
                self.recycler_bounds = node.attrib['bounds']

        for child in list(node):
            self.get_filter_base_node(child, page_type)

    def check_filter(self, page_type):
        self.get_filter_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            try:
                parent.remove(list(parent)[delete_ind])
                parent.remove(list(parent)[delete_ind])
            except Exception:
                pass

        if self.recycler_node.getparent() is not None:
            self.recycler_node.getparent().remove(self.recycler_node)

    def get_route_base_node(self, node, page_type):
        page_criteria = {
            "出行方式": [("收起", 2)],
            "选择日期": [("选择日期", 5)],
            "选择出发时间": [("选择出发时间", 5)],
            "选择出发时间_taxi": [("选择出发时间", 3)]
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_route_base_node(child, page_type)

    def check_route(self, page_type):
        self.get_route_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node:
                parent.remove(child)

    def get_search_result_base_node(self, node, page_type):
        page_criteria = {
            "周边收藏": [("收藏按钮", 3)],
        }

        pattern_need_fuzzy = ["收藏按钮"]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                        (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_search_result_base_node(child, page_type)

    def check_search_result(self, page_type):
        self.get_search_result_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node and check_bounds_intersection(child.attrib['bounds'], node.attrib['bounds']):
                for ch in child.iter():
                    if check_bounds_containing(ch.attrib['bounds'], node.attrib['bounds']):
                        ch_parent = ch.getparent()
                        ch_parent.remove(ch)


class WeiXinSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()
        if page == "search":
            self.base_node = None
            self.retrieve_times = 0
            self.check_search(page_type)
        elif page == "moments":
            self.check_moments_icons(page_type)
        elif page == "menu":
            self.base_node = {}
            self.retrieve_times = 0
            self.check_menu(page_type)

    def check_page(self):
        page_map = {
            "search": [
                (["排序", "类型", "时间", "范围"], "搜索-全部")
            ],
            "moments": [
                (["朋友圈", "拍照分享"], "朋友圈-全部"),
                (["轻触更换封面", "拍照分享"], "朋友圈-全部")
            ],
            "menu": [
                (["微信", "通讯录", "发现", "我"], "首页"),
            ]
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None

    def check_moments_icons(self, page_type):
        page_criteria = {
            "朋友圈-全部": {"ImageView": "选项：点赞/评论", "RelativeLayout": "选项：广告屏蔽"}
        }

        nodes_with_attribute = self.root.xpath('//*[@NAF="true"]')
        for node in nodes_with_attribute:
            if node.attrib['class'] in page_criteria[page_type]:
                node.attrib['func-desc'] = page_criteria[page_type][node.attrib['class']]
                del node.attrib['NAF']

    def get_search_base_node(self, node, page_type):
        page_criteria = {
            "搜索-全部": [("清空", 1)]
        }

        pattern_need_fuzzy = []

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                        (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_search_base_node(child, page_type)

    def check_search(self, page_type):
        self.get_search_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            del parent[delete_ind:]

    def get_menu_base_node(self, node, page_type):
        page_criteria = {
            "首页": ["微信", "通讯录", "发现", "我"]
        }
        retrieve_times = 1

        if 'content-desc' in node.attrib:
            content_desc = node.attrib['content-desc']
            text = node.attrib['text']
            if text in page_criteria.get(page_type, []) or content_desc in page_criteria.get(page_type, []):
                if text not in self.base_node or compare_y_in_bounds(self.base_node[text].attrib['bounds'],
                                                                     node.attrib['bounds']):
                    self.base_node[text] = node
                    self.retrieve_times = retrieve_times

        for child in list(node):
            self.get_menu_base_node(child, page_type)

    def check_menu(self, page_type):
        self.get_menu_base_node(self.root, page_type)
        self.base_node = list(self.base_node.values())
        if len(self.base_node) == 0:
            return

        cur = None
        for node in self.base_node:
            if node.get("selected", "false") == "false":
                cur = node
                break

        while self.retrieve_times > 0:
            if cur.getparent() is not None:
                cur = cur.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = cur.getparent()
        view_node = None
        for node in list(parent)[0].iter():
            if "ListView" in node.attrib["class"] or "RecyclerView" in node.attrib["class"]:
                view_node = node
                break

        for node in list(view_node):
            intersect = False
            for check_node in self.base_node:
                if check_bounds_intersection(node.attrib['bounds'], check_node.attrib['bounds']):
                    intersect = True
                    break
            if intersect:
                view_node.remove(node)


class MeituanSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()

        self.base_node = None
        self.retrieve_times = 0
        if page == "home":
            self.check_home(page_type)
        elif page == "favourite":
            self.check_favourite(page_type)
        elif page == "search":
            self.check_search(page_type)
        # else:
        #     self.remove_overlap()

    def child_index(self, parent, node):
        # find the index of a given node in its sibling nodes
        for i, v in enumerate(list(parent)):
            if v == node:
                return i
        return -1

    def remove_children_overlap_with_bounds(self, node, overlap_bounds, current):
        for child in node:
            child_bounds = child.attrib['bounds']
            if check_bounds_intersection(child_bounds, overlap_bounds) and "EditText" not in child.attrib['class']:
                self.remove_children_overlap_with_bounds(child, overlap_bounds, current)
            else:
                child.getparent().remove(child)
                cur_parent = current.getparent()
                cur_parent.insert(self.child_index(cur_parent, current), child)
                self.queue.append(child)

    def remove_overlap(self):
        self.queue = deque([self.root])

        while self.queue:
            current = self.queue.popleft()
            # print(current.get('text', ""), current.get('content-desc', ''), current.get('bounds', ''))
            # for nodes without bounds, just go ahead
            if 'bounds' not in current.attrib:
                self.queue.extend(current.getchildren())
                continue

            current_bounds = current.attrib['bounds']
            # get siblings
            subsequent_siblings = []
            temp = current.getnext()
            while temp is not None:
                subsequent_siblings.append(temp)
                temp = temp.getnext()

            # Check overlaps with each subsequent sibling
            overlap_bounds = None
            for sibling in subsequent_siblings:
                sibling_bounds = sibling.attrib['bounds']
                if check_bounds_intersection(current_bounds, sibling_bounds):
                    overlap_bounds = sibling_bounds
                    break

            if overlap_bounds is not None:
                # Traverse children and handle overlaps
                if "EditText" not in current.attrib['class']:
                    self.remove_children_overlap_with_bounds(current, overlap_bounds, current)
                    current.getparent().remove(current)
            else:
                # No overlap, enqueue all children
                self.queue.extend(current.getchildren())

    def check_page(self):
        page_map = {
            "home": [
                (["我的", "消息", "购物车", "扫一扫"], "首页"),
            ],
            "favourite": [
                (["全部服务", "全部服务"], "全部服务"),
                (["全部地区", "全部地区"], "全部地区"),
            ],
            "search": [
                (["综合排序", "综合排序"], "综合排序"),
                (["商家品质", "价格", "营业状态"], "筛选"),
            ],
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                xml_string = self.xml_string
                check = []
                for k in keywords:
                    check.append(k in xml_string)
                    xml_string = xml_string.replace(k, "", 1)
                if all(check):
                    return key, page_type
        return None, None

    def get_home_base_node(self, node, page_type):
        page_criteria = {
            "首页": [("搜索框", 1)]
        }

        pattern_need_fuzzy = ["搜索框"]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                        (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_home_base_node(child, page_type)

    def check_home(self, page_type):
        self.get_home_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node and check_bounds_intersection(child.attrib['bounds'], node.attrib['bounds']):
                parent.remove(child)

    def get_favourite_base_node(self, node, page_type):
        page_criteria = {
            "全部服务": [("全部服务", 3)],
            "全部地区": [("全部地区", 3)],
        }

        pattern_need_fuzzy = [""]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                        (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_favourite_base_node(child, page_type)

    def check_favourite(self, page_type):
        self.get_favourite_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            try:
                parent.remove(list(parent)[delete_ind])
            except Exception:
                pass

    def get_search_base_node(self, node, page_type):
        page_criteria = {
            "综合排序": [("综合排序", 3)],
            "筛选": [("综合排序", 3)],
        }

        pattern_need_fuzzy = [""]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                        (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(node.attrib['bounds'],
                                                                     self.base_node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_search_base_node(child, page_type)

    def check_search(self, page_type):
        self.get_search_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            try:
                for child in list(parent)[delete_ind:]:
                    parent.remove(child)
            except Exception:
                pass


SpecialCheck = {
    "com.autonavi.minimap": MiniMapSpecialCheck,
    "com.tencent.mm": WeiXinSpecialCheck,
    "com.sankuai.meituan": MeituanSpecialCheck,
}
