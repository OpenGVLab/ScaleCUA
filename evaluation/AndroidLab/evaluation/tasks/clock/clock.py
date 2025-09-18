from evaluation.task import *


def extract_alarms(data):
    def clock_end(key, Collapse=False):
        if not Collapse:
            if "Switch" in key and "checked" in key:
                return True
            return False
        else:
            if "Delete" in key or "Add alarm" in key:
                return True
            return False

    def split_string(str, splitter):
        str = str.split(";")
        for substr in str:
            if splitter in substr:
                return substr.split(splitter)[0].rstrip()

    elements = list(data.values())[0]
    alarms = []
    for k, v in elements.items():
        if "CardView" not in k:
            continue

        alarm = {}
        alarm["days"] = []
        Collapse = False
        for key, element in v.items():
            if isinstance(element, str):
                continue
            if "Collapse" in key:
                Collapse = True
                alarm["Expand"] = True
            if "Switch" in key:
                if "unchecked" in key:
                    alarm["status"] = "unchecked"
                else:
                    alarm["status"] = "checked"
            if "AM" in key or "PM" in key:
                alarm["time"] = key
            if "Label" in key:
                alarm["label"] = key

            days = [
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
                "Sun",
                "Not scheduled",
                "Today",
                "Tomorrow",
                "Every day",
            ]
            for day in days:
                if day in key and "TextView" in key:
                    alarm["days"].append(day)
            if "Ringtone" in key:
                alarm["ringtone"] = key
            if "Vibrate" in key:
                if "unchecked" in key:
                    alarm["vibrate"] = "unchecked"
                else:
                    alarm["vibrate"] = "checked"

        alarms.append(alarm)
    print(alarms)
    return alarms


class SingleTask_Clock_General(SingleTask):
    def __init__(self, args):
        super().__init__(args)
        self.time_flag = False
        self.vibrate_flag = False
        self.ringtone_flag = False
        self.status_flag = False
        self.days_flag = False
        self.label_flag = False

    def split_string(self, str, splitter):
        str = str.split(";")
        for substr in str:
            if splitter in substr:
                return substr.split(splitter)[0].rstrip()


class SingleTask_Clock_1(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")
        outcome = {
            "judge_page": True,
            "1": False,
            "2": False,
            "3": False,
            "complete": False,
        }

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "3:00\u200aPM" in alarm["time"]:
                        outcome["1"] = True
                        try:
                            if self.split_string(alarm["label"], "Label") == "meeting":
                                outcome["2"] = True
                        except KeyError:
                            pass
                        try:
                            if alarm["status"] == "checked":
                                outcome["3"] = True
                        except KeyError:
                            pass
                        try:
                            if (
                                alarm["status"] == "checked"
                                and self.split_string(alarm["label"], "Label")
                                == "meeting"
                                and "3:00\u200aPM" in alarm["time"]
                            ):
                                outcome["complete"] = True
                        except KeyError:
                            pass
                except KeyError:
                    pass

        return outcome


class SingleTask_Clock_2(SingleTask_Clock_General):

    def judge_page(self, xml_compressed_tree):
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "6:45\u200aAM" in alarm["time"]:
                        self.time_flag = True
                        try:
                            if alarm["vibrate"] == "unchecked":
                                self.vibrate_flag = True
                            else:
                                self.vibrate_flag = False
                        except KeyError:
                            pass
                        try:
                            if "ringtone" in alarm:
                                if (
                                    self.split_string(alarm["ringtone"], "Ringtone")
                                    == "Argon"
                                ):
                                    self.ringtone_flag = True
                                else:
                                    self.ringtone_flag = False
                        except KeyError:
                            pass
                        try:
                            if alarm["status"] == "checked":
                                self.status_flag = True
                            else:
                                self.status_flag = False
                        except KeyError:
                            pass
                except KeyError:
                    pass

        outcome = {
            "judge_page": True,
            "1": self.time_flag,
            "2": self.vibrate_flag,
            "3": self.ringtone_flag,
            "4": self.status_flag,
            "complete": self.time_flag
            and self.vibrate_flag
            and self.ringtone_flag
            and self.status_flag,
        }
        return outcome


class SingleTask_Clock_3(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "7:00\u200aAM" in alarm["time"]:
                        self.time_flag = True
                        try:
                            if set(alarm["days"]) == set(
                                ["Mon", "Tue", "Wed", "Thu", "Fri"]
                            ):
                                self.days_flag = True
                        except KeyError:
                            pass
                        try:
                            if alarm["status"] == "checked":
                                self.status_flag = True
                            else:
                                self.status_flag = False
                        except KeyError:
                            pass
                except KeyError:
                    pass

        outcome = {
            "judge_page": True,
            "1": self.time_flag,
            "2": self.days_flag,
            "3": self.status_flag,
            "complete": self.time_flag and self.days_flag and self.status_flag,
        }
        return outcome


class SingleTask_Clock_4(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")
        outcome = {
            "judge_page": True,
            "1": False,
            "2": False,
            "3": False,
            "complete": False,
        }

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "9:00\u200aAM" in alarm["time"]:
                        self.time_flag = True
                        try:
                            if alarm["days"] == ["Every day"]:
                                self.days_flag = True
                        except KeyError:
                            pass
                        try:
                            if alarm["status"] == "checked":
                                self.status_flag = True
                            else:
                                self.status_flag = False
                        except KeyError:
                            pass
                except KeyError:
                    pass

        outcome = {
            "judge_page": True,
            "1": self.time_flag,
            "2": self.days_flag,
            "3": self.status_flag,
            "complete": self.time_flag and self.days_flag and self.status_flag,
        }
        return outcome


class SingleTask_Clock_5(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "10:30\u200aAM" in alarm["time"]:
                        self.time_flag = True
                        try:
                            if alarm["days"] == ["Tomorrow"]:
                                self.days_flag = True
                            else:
                                self.days_flag = False
                        except KeyError:
                            pass
                        try:
                            if alarm["status"] == "checked":
                                self.status_flag = True
                            else:
                                self.status_flag = False
                        except KeyError:
                            pass
                except KeyError:
                    pass

        outcome = {
            "judge_page": True,
            "1": self.time_flag,
            "2": self.days_flag,
            "3": self.status_flag,
            "complete": self.time_flag and self.days_flag and self.status_flag,
        }
        return outcome


class SingleTask_Clock_6(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")
        outcome = {
            "judge_page": True,
            "1": False,
            "2": False,
            "3": False,
            "4": False,
            "complete": False,
        }

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "10:30\u200aPM" in alarm["time"]:
                        self.time_flag = True
                        try:
                            if set(alarm["days"]) == set(["Sat", "Sun"]):
                                self.days_flag = True
                            else:
                                self.days_flag = False
                        except KeyError:
                            pass
                        try:
                            if (
                                self.split_string(alarm["label"], "Label")
                                == "Watch Football Games"
                            ):
                                self.label_flag = True
                            else:
                                self.label_flag = False
                        except KeyError:
                            pass
                        try:
                            if alarm["status"] == "checked":
                                self.status_flag = True
                            else:
                                self.status_flag = False
                        except KeyError:
                            pass
                except KeyError:
                    pass

        outcome = {
            "judge_page": True,
            "1": self.time_flag,
            "2": self.days_flag,
            "3": self.label_flag,
            "4": self.status_flag,
            "complete": self.time_flag
            and self.days_flag
            and self.label_flag
            and self.status_flag,
        }
        return outcome


class SingleTask_Clock_7(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        # outs = find_matching_subtrees(xml_compressed_tree, "Alarm")
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")
        outcome = {"judge_page": True, "1": False, "complete": False}
        if len(outs) == 0 or (
            len(outs) == 1 and "click ; ;;Alarm" in next(iter(outs[0]))
        ):
            return outcome

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if alarm["status"] != "unchecked":
                        return outcome
                except KeyError:
                    break

        outcome["1"] = True
        outcome["complete"] = True

        return outcome


class SingleTask_Clock_8(SingleTask_Clock_General):

    def get_time(self, str):
        strs = str.split(";")
        for substr in strs:
            if "PM" in substr:
                time = substr.split("\u200a")[0]
                hour = int(time.split(":")[0])
                minute = int(time.split(":")[1])
                return hour, minute

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        # outs = find_matching_subtrees(xml_compressed_tree, "Alarm")
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")
        outcome = {"judge_page": True, "1": False, "complete": False}
        if len(outs) == 0 or (
            len(outs) == 1 and "click ; ;;Alarm" in next(iter(outs[0]))
        ):
            return outcome

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "PM" in alarm["time"] and (
                        self.get_time(alarm["time"])[0] > 2
                        or (
                            self.get_time(alarm["time"])[0] == 2
                            and self.get_time(alarm["time"])[1] > 0
                        )
                    ):
                        return outcome
                except KeyError:
                    pass

        outcome["1"] = True
        outcome["complete"] = True

        return outcome


class SingleTask_Clock_9(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        # outs = find_matching_subtrees(xml_compressed_tree, "Alarm")
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")
        outcome = {"judge_page": True, "1": False, "complete": False}
        if len(outs) == 0 or (
            len(outs) == 1 and "click ; ;;Alarm" in next(iter(outs[0]))
        ):
            return outcome

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "4:00\u200aPM" in alarm["time"]:
                        if alarm["status"] == "unchecked":
                            outcome["1"] = True
                            outcome["complete"] = True
                            break
                except KeyError:
                    pass

        return outcome


class SingleTask_Clock_10(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "7:30AM"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Clock_11(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "No"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Clock_12(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "Yes"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Clock_13(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "Two alarms"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Clock_14(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "No"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Clock_15(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}
        outs_london = find_subtrees_of_parents_with_key(xml_compressed_tree, "London")
        outs_barcelona = find_subtrees_of_parents_with_key(
            xml_compressed_tree, "Barcelona"
        )

        if len(outs_london) > 0:
            outcome["1"] = True
        if len(outs_barcelona) > 0:
            outcome["2"] = True

        outcome["complete"] = outcome["1"] and outcome["2"]
        return outcome


class SingleTask_Clock_16(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "6 hours behind"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Clock_17(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs_barcelona = find_subtrees_of_parents_with_key(
            xml_compressed_tree, "Barcelona"
        )
        try:
            selected_dict = find_matching_subtrees(
                xml_compressed_tree, "focusable ; selected ; selected"
            )[0]
            selected = next(iter(selected_dict))
            if "Clock" not in selected:
                return outcome
        except:
            return {"judge_page": False}

        if len(outs_barcelona) == 0:
            outcome["1"] = True
            outcome["complete"] = True

        return outcome


class SingleTask_Clock_18(SingleTask_Clock_General):
    hour_flag = False
    minute_flag = False
    second_flag = False

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        # timer has not started
        flag_outs = find_matching_subtrees(xml_compressed_tree, "Start")
        if len(flag_outs) == 0:
            return {
                "judge_page": True,
                "1": self.hour_flag,
                "2": self.minute_flag,
                "3": self.second_flag,
                "complete": False,
            }

        outs = find_matching_subtrees(xml_compressed_tree, "TextView")
        outcome = {
            "judge_page": True,
            "1": False,
            "2": False,
            "3": False,
            "complete": False,
        }

        for out in outs:
            for key, value in out.items():
                if "hour" in key and "minute" in key and "second" in key:
                    hour = key.split("hour")[0].rstrip().split(" ")[-1]
                    minute = key.split("minute")[0].rstrip().split(" ")[-1]
                    second = key.split("second")[0].rstrip().split(" ")[-1]
                    if hour == "1":
                        outcome["1"] = True
                        self.hour_flag = True
                    if minute == "15":
                        outcome["2"] = True
                        self.minute_flag = True
                    if second == "0":
                        outcome["3"] = True
                        self.second_flag = True

        outcome["complete"] = outcome["1"] and outcome["2"] and outcome["3"]
        return outcome


class SingleTask_Clock_19(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "BEDTIME")

        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "Bedtime" in key:
                        bed_time = key.split("Bedtime")[-1].split()
                        b_time, m_or_n = bed_time[0], bed_time[1]
                        b_time_split = b_time.split(":")
                        if len(b_time_split) != 2:
                            outcome["1"] = False
                            continue

                        b_hour, b_min = b_time_split[0], b_time_split[1]
                        if m_or_n == "PM":
                            outcome["1"] = b_hour == "10" and b_min == "00"
                        else:
                            outcome["1"] = False
                    if "Wake-up" in key:
                        wake_time = key.split("Wake-up")[-1].split()
                        w_time, m_or_n = wake_time[0], wake_time[1]
                        w_hour, w_min = w_time.split(":")
                        if m_or_n == "AM":
                            outcome["2"] = w_hour == "7" and w_min == "00"
                        else:
                            outcome["2"] = False

        outcome["complete"] = outcome["1"] and outcome["2"]
        return outcome


class SingleTask_Clock_20(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")

        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "sleep sound" in key:
                        str = key.split("sleep sound ")[-1].rstrip()
                        if str == "Deep space":
                            outcome["1"] = True
                            outcome["complete"] = True
                            break

        return outcome


class SingleTask_Clock_21(SingleTask_Clock_General):

    def judge_page(self, xml_compressed_tree):
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "AM Wake-up 7:00")
        if len(outs) > 0:
            return True
        else:
            return False

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "AM Wake-up 7:00")

        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "click check ; checked" in key:
                        outcome["1"] = True
                        outcome["complete"] = True
                        break

        return outcome


class SingleTask_Clock_22(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": True, "complete": True}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Analog")

        if len(outs) == 0:
            outcome["1"] = False
            outcome["complete"] = False

        return outcome


class SingleTask_Clock_23(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Home time zone ")

        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    if "Tokyo" in key:
                        outcome["1"] = True
                        outcome["complete"] = True
                        break

        return outcome


class SingleTask_Clock_24(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Silence after ")

        for out in outs:
            out = out.values()
            for single_out in out:
                for key, value in single_out.items():
                    key = key.split(";")[-1]
                    if key == "5 minutes ":
                        outcome["1"] = True
                        outcome["complete"] = True
                        break

        return outcome


class SingleTask_Clock_25(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Alarm")
        outs_2 = find_subtrees_of_parents_with_key(xml_compressed_tree, "Clock")
        outs_3 = find_subtrees_of_parents_with_key(xml_compressed_tree, "Timer")
        outs_4 = find_subtrees_of_parents_with_key(xml_compressed_tree, "Stopwatch")

        if len(outs) > 0 and len(outs_2) > 0 and len(outs_3) > 0 and len(outs_4) > 0:
            outcome["1"] = True
            outcome["complete"] = True

        return outcome


class SingleTask_Clock_26(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "7:30" in alarm["time"] and "AM" in alarm["time"]:
                        if alarm["status"] == "unchecked":
                            outcome["1"] = True
                            outcome["complete"] = True
                            break
                except KeyError:
                    pass

        return outcome


class SingleTask_Clock_27(SingleTask_Clock_General):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "CardView")

        for out in outs:
            alarms_data = extract_alarms(out)
            for alarm in alarms_data:
                try:
                    if "3:00" in alarm["time"] and "PM" in alarm["time"]:
                        if alarm["status"] == "checked":
                            outcome["1"] = True
                            outcome["complete"] = True
                except KeyError:
                    pass

        return outcome
