from evaluation.task import *


class SingleTask_Contacts_1(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "John"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        outcome = {"judge_page": False, "1": False, "2": False, "complete": False}

        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome["judge_page"] = True

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "John")
        if outs:
            outcome["1"] = True

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "1 (234) 567-8")
        if outs:
            outcome["2"] = True

        if outcome["1"] and outcome["2"]:
            outcome["complete"] = True

        return outcome


class SingleTask_Contacts_2(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "John Smith"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "1 (234) 567-8")

        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if key == "Call Mobile 1 (234) 567-8 ":
                        outcome["1"] = True
                    if key == "Email Work 123456@qq.com ":
                        outcome["2"] = True
                    if outcome["1"] and outcome["2"]:
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_3(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Xu"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "1 (234) 567-8")

        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if key == "Call Work 1 (234) 567-8 ":
                        outcome["1"] = True
                    if key == "Call Mobile (876) 543-21 ":
                        outcome["2"] = True
                    if outcome["1"] and outcome["2"]:
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_4(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Chen"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact photo ")

        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if key == "Tsinghua University ":
                        outcome["1"] = True
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_5(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "work • l"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Add contacts"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {
            "judge_page": True,
            "1": False,
            "2": False,
            "3": False,
            "complete": False,
        }
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "work • ")

        for out in outs:
            for single_out in out.values():
                for key, value in single_out.items():
                    if "work • " in key:
                        key = key.split(";")[-1]
                        if "contacts" in key and not "3 contacts " in key:
                            return {"judge_page": True, "1": False}
                    try:
                        for it in value.keys():
                            key = it.split(";")[-1]
                            if key == "Chen Chen ":
                                outcome["1"] = True
                            elif key == "Lee Lee ":
                                outcome["2"] = True
                            elif key == "Xu Xu ":
                                outcome["3"] = True
                            if outcome["1"] and outcome["2"] and outcome["3"]:
                                outcome["complete"] = True
                                return outcome
                    except:
                        pass

        return outcome


class SingleTask_Contacts_6(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "00112233 ")

        if len(outs) > 0:
            outcome["1"] = True
            outcome["complete"] = True

        return outcome


class SingleTask_Contacts_7(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Birthday ")

        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if key == "October 24, 1996 ":
                        outcome["1"] = True
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_8(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "abc.github.com")
        if len(outs) > 0:
            outcome["1"] = True
            outcome["complete"] = True

        return outcome


class SingleTask_Contacts_9(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(
            xml_compressed_tree, "Texting with ABC"
        ):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        key_1 = False
        key_2 = False
        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}

        if find_subtrees_of_parents_with_key(xml_compressed_tree, "Texting with ABC"):
            key_1 = True
            if find_subtrees_of_parents_with_key(
                xml_compressed_tree, "Nice to meet you"
            ):
                key_2 = True

        outcome["1"] = key_1
        outcome["2"] = key_2
        outcome["complete"] = key_1 and key_2

        return outcome


class SingleTask_Contacts_10(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "End call"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Contacts_11(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_key = not find_subtrees_of_parents_with_key(
            xml_compressed_tree, "AAA AAA "
        )

        return {"judge_page": True, "1": judge_key, "complete": judge_key}


class SingleTask_Contacts_12(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "22331144 or (223) 311-44"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_13(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "22334455@gmail.com"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_14(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "October 24, 1996"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_15(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "Tsinghua university"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_16(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(
            xml_compressed_tree, "Search contacts "
        )
        if len(outs) == 0:
            return {"judge_page": True, "1": False, "complete": False}

        return {"judge_page": True, "1": True, "complete": True}
