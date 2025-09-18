from evaluation.task import *


class SingleTask_Setting_0(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        if command["adb shell settings get global airplane_mode_on"] == "0":
            return {"judge_page": True, "1": False, "complete": False}
        else:
            return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_1(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Turn on Wi‑Fi automatically")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Turn on Wi‑Fi automatically")
        for out in outs:
            for key, value in out.items():
                for judge_key, _ in value.items():
                    if "unchecked" in judge_key:
                        return {"judge_page": True, "1": True, "complete": True}
        return {"judge_page": True, "1": False, "complete": False}


class SingleTask_Setting_2(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Private DNS provider hostname")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "dns.google")
        if len(outs) == 0:
            return {"judge_page": True, "1": False, "complete": False}
        else:
            return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_3(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        if command["adb shell settings get global bluetooth_on"] == "1":
            return {"judge_page": True, "1": False, "complete": False}
        else:
            return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_4(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Pair new device")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "my AVD")
        if len(outs) == 0:
            return {"judge_page": True, "1": False, "complete": False}
        else:
            return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_5(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Battery percentage")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Battery percentage")
        for out in outs:
            for key, value in out.items():
                for judge_key, _ in value.items():
                    if "unchecked" in judge_key:
                        return {"judge_page": True, "1": False, "complete": False}
        return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_6(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Apps")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Apps")
        for out in outs:
            for key, value in out.items():
                for storage, _ in value.items():
                    if "MB" in storage or "GB" in storage:
                        if ";" in storage:
                            storage = storage.split(";")[-1]
                        return {"judge_page": True, "1": storage}
        return {"judge_page": False}


class SingleTask_Setting_7(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Display ")
        if len(outs) == 0:
            return False
        return True

    def setting_ch(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Dark theme ")
        found = False
        finish = False
        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "RecyclerView" in key:
                        found = True
                        item = find_subtrees_of_parents_with_key(xml_compressed_tree, "Use Dark theme ")
                        for it in item:
                            it = it.values()
                            for single_it_ in it:
                                for key_, value_ in single_it_.items():
                                    if not "unchecked" in key_:
                                        if "checked" in key_:
                                            finish = True
                                            break
                        break
        if found:
            return {"judge_page": True, "1": finish, "complete": finish}
        else:
            return {"judge_page": False}

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Display ")
        found = False
        finish = False
        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "RecyclerView" in key:
                        found = True
                        item = find_subtrees_of_parents_with_key(xml_compressed_tree, "Dark theme ")
                        for it in item:
                            it = it.values()
                            for single_it_ in it:
                                for key_, value_ in single_it_.items():
                                    if not "unchecked" in key_:
                                        if "checked" in key_ and "Dark theme" in key_:
                                            finish = True
                                            break
                        break
        if found:
            return {"judge_page": True, "1": finish, "complete": finish}
        else:
            return self.setting_ch(xml_compressed_tree)


class SingleTask_Setting_8(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Brightness level ")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Brightness level ")
        finish = False
        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "%" in key:
                        key = key.split(";")[-1].rstrip()
                        break
        if key == "0%":
            return {"judge_page": True, "1": True, "complete": True}
        else:
            return {"judge_page": True, "1": False, "complete": False}


class SingleTask_Setting_9(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        if "0" in command["adb shell settings list system | grep volume_ring_speaker"]:
            return {"judge_page": True, "1": True, "complete": True}
        else:
            return {"judge_page": True, "1": False, "complete": False}


class SingleTask_Setting_10(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        if "7" in command["adb shell settings list system | grep volume_alarm_speaker"]:
            return {"judge_page": True, "1": True, "complete": True}
        else:
            return {"judge_page": True, "1": False, "complete": False}


class SingleTask_Setting_11(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Text-to-speech output"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Chinese")
        if len(outs) > 0:
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Setting_12(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Set time automatically"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "May 1, 2024")
        if len(outs) > 0:
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Setting_13(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Ring vibration ")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        finish = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Ring vibration ")
        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "unchecked" in key:
                        finish = {"judge_page": True, "1": True, "complete": True}
                        break
        return finish


class SingleTask_Setting_14(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        timezone = command["adb shell 'getprop persist.sys.timezone'"]
        if line["parsed_action"]["action"] != "finish":
            return {"judge_page": False}
        try:
            self.final_ground_truth = timezone
            if self.check_answer(line):
                return {"judge_page": True, "1": True, "complete": True}
            else:
                return {"judge_page": True, "1": False, "complete": False}
        except:
            return {"judge_page": True, "1": False, "complete": False}


class SingleTask_Setting_15(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Add a language")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Español (Estados Unidos)")
        if len(outs) == 0:
            return {"judge_page": True, "1": False, "complete": False}
        for out in outs:
            for key, value in out.items():
                for idx, judge_key in enumerate(value.keys()):
                    if "Español (Estados Unidos)" in judge_key:
                        if "2" in list(value.keys())[idx + 1]:
                            return {"judge_page": True, "1": True, "2": True, "complete": True}
                        else:
                            return {"judge_page": True, "1": True, "2": False, "complete": False}


class SingleTask_Setting_16(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        if line["parsed_action"]["action"] != "finish":
            return {"judge_page": False}
        try:
            self.final_ground_truth = "English (United States)"
            if self.check_answer(line):
                return {"judge_page": True, "1": True, "complete": True}
            else:
                return {"judge_page": True, "1": False, "complete": False}
        except:
            return {"judge_page": True, "1": False, "complete": False}


class SingleTask_Setting_17(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        answer = command["adb shell getprop ro.build.version.release"]
        if line["parsed_action"]["action"] != "finish":
            return {"judge_page": False}
        try:
            self.final_ground_truth = answer
            if self.check_answer(line):
                return {"judge_page": True, "1": True, "complete": True}
            else:
                return {"judge_page": True, "1": False, "complete": False}
        except:
            return {"judge_page": True, "1": False, "complete": False}


class SingleTask_Setting_18(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Allowed")
        if len(outs) == 0:
            return False
        return True

    def setting_18_ch(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Allow notification access")
        found = 0
        finish = False
        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if found == 1:
                        if not ("unchecked" in key):
                            if "checked" in key:
                                finish = True
                                break
                    if found >= 1:
                        found += 1
                    if "Allow notification access" in key:
                        found += 1
        if found >= 1:
            if finish:
                return {"judge_page": True, "1": False, "complete": False}
            else:
                return {"judge_page": True, "1": True, "complete": True}
        else:
            return {"judge_page": False}

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return self.setting_18_ch(xml_compressed_tree)
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Allowed")
        found_item = False
        found = False
        finish = False
        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if found_item:
                        try:
                            for _key in value.keys():
                                if "Contacts" in _key:
                                    finish = True
                                    break
                        except AttributeError:
                            pass
                    if "Allowed" in key:
                        found_item = True
                    if "Not allowed" in key:
                        found_item = False
        if finish:
            return {"judge_page": True, "1": False, "complete": False}
        else:
            return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_19(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Default browser app")
        if len(outs) == 0:
            return False
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Firefox")
        if len(outs) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Default browser app")
        for out in outs:
            for key, value in out.items():
                for judge_key, _ in value.items():
                    if "unchecked" in judge_key:
                        return {"judge_page": True, "1": False, "complete": False}
        return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_20(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        if "booking" in command["adb shell pm list packages | grep 'com.booking'"]:
            return {"judge_page": True, "1": False, "complete": False}
        else:
            return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_21(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Settings ")
        outs1 = find_subtrees_of_parents_with_key(xml_compressed_tree, "Search settings")
        if len(outs) == 0 or len(outs1) == 0:
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Setting_22(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        if "command" not in line:
            return {"judge_page": False}
        command = line["command"]
        answer = command["adb shell settings get global airplane_mode_on"]
        if answer == "1":
            answer = "open"
        else:
            answer = "not open"
        if line["parsed_action"]["action"] != "finish":
            return {"judge_page": False}
        try:
            self.final_ground_truth = answer
            if self.check_answer(line):
                return {"judge_page": True, "1": True, "complete": True}
            else:
                return {"judge_page": True, "1": False, "complete": False}
        except:
            return {"judge_page": True, "1": False, "complete": False}
