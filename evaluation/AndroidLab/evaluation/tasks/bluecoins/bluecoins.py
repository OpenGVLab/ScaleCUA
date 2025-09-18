import re
from typing import Dict

from evaluation.task import SingleTask
from evaluation.utils import find_matching_subtrees, find_subtrees_of_parents_with_key


def extract_bills_NewEditBK(xml_compressed_tree) -> Dict:
    """
    {type, date, cash, note}
    type: TextView ;; ;; -> str
    date: TextView ;; ;; -> str()
    cash: EditText ;click long-click ; ;; -> int
    note: EditText ;click long-click ; ;; -> str
    """
    type = date = cash = note = ""
    results = {
        "type": type,
        "date": date,
        "cash": cash,
        "note": note
    }

    try:
        type_date_datas = find_matching_subtrees(xml_compressed_tree, "TextView ;; ;;")
        keys = [key for d in type_date_datas for key in d.keys()]
        type_key = keys[0]
        type_key = type_key.split(";; ;;")[-1].strip()
        type = type_key.split()[-1].strip()
        for key in keys:
            if re.search(r"January|February|March|April|May|June|July|August|September|October|November|December", key):
                date = key.split(";; ;;")[-1].strip()
                break
        results["type"] = type
        results["date"] = date
    except IndexError:
        pass

    try:
        cash_datas = find_subtrees_of_parents_with_key(xml_compressed_tree, "click ; ;;CNY")  
        cash_datas = list(cash_datas[0].values())[0] 
        for key in cash_datas.keys():
            if "EditText" in key and "long-click" in key:
                cash = key.split(";;")[-1].strip()
                results["cash"] = cash
    except IndexError:
        pass

    try:
        note_datas = find_matching_subtrees(xml_compressed_tree, "EditText")[-1]
        note = list(note_datas.keys())[0].split(";;")[-1].strip()
        results["note"] = "None" if note in ("Notes", "Payee or item purchased", "Name of income") else note
    except IndexError:
        pass

    return results


class SingleTask_bluecoins_1(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "11,400.00 CNY"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_bluecoins_2(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "Buying cake"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_bluecoins_3(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "69.51 CNY"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_bluecoins_4(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "Three transactions"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_bluecoins_5(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "60.12 CNY"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_bluecoins_6(SingleTask):

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_type = judge_cash = False

        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("type") == "Expense":
            judge_type = True

        if bill.get("cash") in ("512", "512.00"):
            judge_cash = True

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_cash,
            "complete": judge_type & judge_cash
        }


class SingleTask_bluecoins_7(SingleTask):

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_type = judge_cash = judge_note = False

        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("type") == "Income":
            judge_type = True

        if bill.get("cash") in ("8000", "8000.00"):
            judge_cash = True

        if bill.get("note").lower() == "salary":
            judge_note = True

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_cash,
            "3": judge_note,
            "complete": judge_type & judge_cash & judge_note
        }


class SingleTask_bluecoins_8(SingleTask):

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_type = judge_date = judge_cash = False

        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("type") == "Expense":
            judge_type = True

        if bill.get("date") == "May 11, 2024":
            judge_date = True

        if bill.get("cash") in ("768", "768.00"):
            judge_cash = True

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_date,
            "3": judge_cash,
            "complete": judge_type & judge_date & judge_cash
        }


class SingleTask_bluecoins_9(SingleTask):

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_type = judge_date = judge_cash = judge_note = False

        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("type") == "Income":
            judge_type = True

        if bill.get("date") == "March 8, 2024":
            judge_date = True

        if bill.get("cash") == "3.14":
            judge_cash = True

        if bill.get("note").lower() == "weixin red packet":
            judge_note = True

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_date,
            "3": judge_cash,
            "4": judge_note,
            "complete": judge_type & judge_date & judge_cash & judge_note
        }


class SingleTask_bluecoins_10(SingleTask):

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_type = judge_date = judge_cash = judge_note = False
        bill = extract_bills_NewEditBK(xml_compressed_tree)

        if bill.get("type") == "Expense":
            judge_type = True

        if bill.get("date") == "May 14, 2024":
            judge_date = True

        if bill.get("cash") in ("256", "256.00"):
            judge_cash = True

        if bill.get("note").lower() == "eating":
            judge_note = True

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_date,
            "3": judge_cash,
            "4": judge_note,
            "complete": judge_type & judge_date & judge_cash & judge_note
        }


class SingleTask_bluecoins_11(SingleTask):
    origin_bill = False

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        bill = extract_bills_NewEditBK(xml_compressed_tree)

        if self.origin_bill is not True:
            if bill.get("date") == "May 15, 2024" and bill.get("cash") == "400.00":
                self.origin_bill = True
        else:
            judge_date = judge_cash = False

            if bill.get("date") == "May 15, 2024":
                judge_date = True

            if bill.get("cash") in ("500", "500.00"):
                judge_cash = True

            return {
                "judge_page": True,
                "1": judge_date,
                "2": judge_cash,
                "complete": judge_date & judge_cash
            }

        return {"judge_page": False}


class SingleTask_bluecoins_12(SingleTask):
    origin_bill = False

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        bill = extract_bills_NewEditBK(xml_compressed_tree)

        if self.origin_bill is not True:
            if bill.get("date") == "May 12, 2024" and bill.get("cash") == "18000.00":
                self.origin_bill = True
        else:
            judge_date = judge_cash = False

            if bill.get("date") == "May 10, 2024":
                judge_date = True

            if bill.get("cash") in ("18250", "18250.00"):
                judge_cash = True

            return {
                "judge_page": True,
                "1": judge_date,
                "2": judge_cash,
                "complete": judge_date & judge_cash
            }

        return {"judge_page": False}


class SingleTask_bluecoins_13(SingleTask):
    origin_bill = False

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        bill = extract_bills_NewEditBK(xml_compressed_tree)

        if self.origin_bill is not True:
            if bill.get("date") == "May 13, 2024" and bill.get("type") == "Expense":
                self.origin_bill = True
        else:
            judge_type = judge_sign = judge_date = judge_note = False
            if bill.get("type") == "Income":
                judge_type = True

            if bill.get("date") == "May 13, 2024":
                judge_date = True

            if bill.get("note").lower() == "gift":
                judge_note = True

            tvc_datas = find_matching_subtrees(xml_compressed_tree, "TextView ;click")
            keys = [key for d in tvc_datas for key in d.keys()]
            for key in keys:
                key = key.split("; ;;")[-1].strip()
                if key in ("+", "-"):
                    sign = key
                    break

            if sign == "+":
                judge_sign = True

            return {
                "judge_page": True,
                "1": judge_type,
                "2": judge_sign,
                "3": judge_date,
                "4": judge_note,
                "complete": judge_type & judge_sign & judge_date & judge_note
            }

        return {"judge_page": False}


class SingleTask_bluecoins_14(SingleTask):
    origin_bill = False

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        bill = extract_bills_NewEditBK(xml_compressed_tree)

        if self.origin_bill is not True:
            if bill.get("date") == "May 2, 2024" and bill.get("type") == "Income":
                self.origin_bill = True
        else:
            judge_type = judge_sign = judge_date = judge_cash = judge_note = False

            if bill.get("type") == "Expense":
                judge_type = True

            if bill.get("date") == "May 2, 2024":
                judge_date = True

            if bill.get("cash") in ("520", "520.00"):
                judge_cash = True

            if bill.get("note").lower() == "wrong operation":
                judge_note = True
            sign = ""
            tvc_datas = find_matching_subtrees(xml_compressed_tree, "TextView ;click")
            keys = [key for d in tvc_datas for key in d.keys()]
            for key in keys:
                key = key.split("; ;;")[-1].strip()
                if key in ("+", "-"):
                    sign = key
                    break

            if sign == "-":
                judge_sign = True

            return {
                "judge_page": True,
                "1": judge_type,
                "2": judge_sign,
                "3": judge_date,
                "4": judge_cash,
                "5": judge_note,
                "complete": judge_type & judge_sign & judge_date & judge_cash & judge_note
            }

        return {"judge_page": False}


class SingleTask_bluecoins_15(SingleTask):
    origin_bill = False

    def judge_page(self, xml_compressed_tree):
        bill = extract_bills_NewEditBK(xml_compressed_tree)
        if bill.get("cash") == bill.get("note") == "":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        bill = extract_bills_NewEditBK(xml_compressed_tree)

        if self.origin_bill is not True:
            if bill.get("date") == "May 12, 2024" and bill.get("cash") == "794.20":
                self.origin_bill = True
        else:
            judge_date = judge_cash = judge_note = False

            if bill.get("date") == "May 13, 2024":
                judge_date = True

            if bill.get("cash") == "936.02":
                judge_cash = True

            if bill.get("note").lower() == "grocery shopping":
                judge_note = True

            return {
                "judge_page": True,
                "1": judge_date,
                "2": judge_cash,
                "3": judge_note,
                "complete": judge_date & judge_cash & judge_note
            }

        return {"judge_page": False}
