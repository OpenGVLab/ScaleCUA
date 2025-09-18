from evaluation.task import *


class SingleTask_Zoom_1(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Join with a personal link name"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "123 456 7890")
        if len(outs) > 0:
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Zoom_2(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Join with a personal link name"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        judge_key1 = False
        judge_key2 = False
        outs1 = find_subtrees_of_parents_with_key(xml_compressed_tree, "098 765 4321")
        outs2 = find_subtrees_of_parents_with_key(xml_compressed_tree, "Alice")
        if len(outs1) > 0:
            judge_key1 = True
        if len(outs2) > 0:
            judge_key2 = True
        outcome = {"judge_page": True, "1": judge_key1, "2": judge_key2, "complete": judge_key1 and judge_key2}
        return outcome


class SingleTask_Zoom_3(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Join with a personal link name"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        judge_key1 = False
        judge_key2 = False
        judge_key3 = False
        outs1 = find_subtrees_of_parents_with_key(xml_compressed_tree, "123 456 7890")
        outs2_tree = find_subtrees_of_parents_with_key(xml_compressed_tree, "Don't Connect To Audio")
        outs2 = find_subtrees_of_parents_with_key(outs2_tree[0], "On, switch")
        outs3_tree = find_subtrees_of_parents_with_key(xml_compressed_tree, "Turn Off My Video")
        outs3 = find_subtrees_of_parents_with_key(outs3_tree[0], "On, switch")
        if len(outs1) > 0:
            judge_key1 = True
        if len(outs2) > 0:
            judge_key2 = True
        if len(outs3) > 0:
            judge_key3 = True
        outcome = {"judge_page": True, "1": judge_key1, "2": judge_key2, "3": judge_key3,
                   "complete": judge_key1 and judge_key2 and judge_key3}
        return outcome


class SingleTask_Zoom_4(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Auto-connect to audio"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        judge_key = False
        outs_tree = find_subtrees_of_parents_with_key(xml_compressed_tree, "Auto-connect to audio")
        outs = find_subtrees_of_parents_with_key(outs_tree[0], "WiFi or cellular data")
        if len(outs) > 0:
            judge_key = True
        outcome = {"judge_page": True, "1": judge_key, "complete": judge_key}
        return outcome


class SingleTask_Zoom_5(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if (not find_subtrees_of_parents_with_key(xml_compressed_tree, "Reaction skin tone")
                or not find_subtrees_of_parents_with_key(xml_compressed_tree, "Medium-light")):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        judge_key = False
        outs_tree = find_subtrees_of_parents_with_key(xml_compressed_tree, "Medium-light")
        outs = find_subtrees_of_parents_with_key(outs_tree[0], "Selected")
        if len(outs) > 0:
            judge_key = True
        outcome = {"judge_page": True, "1": judge_key, "complete": judge_key}
        return outcome
