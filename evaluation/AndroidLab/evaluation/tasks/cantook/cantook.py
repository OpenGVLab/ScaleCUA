from evaluation.task import SingleTask
from evaluation.utils import find_matching_subtrees


def extract_books_info(xml_compressed_tree):
    books_data = find_matching_subtrees(xml_compressed_tree, "TextView")
    books_set = set()
    for book_data in books_data:
        book_data = list(book_data.keys())[0]
        book_data = book_data.split(";; ;;")[-1].strip()
        books_set.add(book_data)
    return books_set


def check_selected(xml_compressed_tree, key_filter):
    def helper(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if key_filter in key:
                    return True
                if helper(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if helper(item):
                    return True
        return False

    selected_data = find_matching_subtrees(xml_compressed_tree, "selected, ;")
    return helper(selected_data)


class SingleTask_cantook_1(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "No"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_cantook_2(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "The Scarlet Letter"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_cantook_3(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "William Shakespeare"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_cantook_4(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "Two"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_cantook_5(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "37.8%"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_cantook_6(SingleTask):

    def judge_page(self, xml_compressed_tree):
        book_info = extract_books_info(xml_compressed_tree)
        for info in book_info:
            if ".epub" in info or "Help" in info:
                return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_book = False

        book_info = extract_books_info(xml_compressed_tree)

        if "Alice's Adventures in Wonderland" in book_info:
            judge_book = True

        return {
            "judge_page": True,
            "1": judge_book,
            "complete": judge_book
        }


class SingleTask_cantook_7(SingleTask):

    def judge_page(self, xml_compressed_tree):
        outs = find_matching_subtrees(xml_compressed_tree, "My Books")
        for out in outs:
            select = find_matching_subtrees(out, "selected")
            if len(select) > 0:
                return True
        return False

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_book = False

        book_info = extract_books_info(xml_compressed_tree)

        if "Don Quixote" not in book_info:
            judge_book = True

        return {
            "judge_page": True,
            "1": judge_book,
            "complete": judge_book
        }


class SingleTask_cantook_8(SingleTask):

    def judge_page(self, xml_compressed_tree):
        book_info = extract_books_info(xml_compressed_tree)
        for info in book_info:
            if "Info" not in info and "Read" not in info:
                return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_book = judge_read = False

        book_info = extract_books_info(xml_compressed_tree)

        if "Hamlet" in book_info:
            judge_book = True

        if "Mark as unread" in book_info and "100.0%" in book_info:
            judge_read = True

        return {
            "judge_page": True,
            "1": judge_book,
            "2": judge_read,
            "complete": judge_book & judge_read
        }


class SingleTask_cantook_9(SingleTask):

    def judge_page(self, xml_compressed_tree):
        book_info = extract_books_info(xml_compressed_tree)
        for info in book_info:
            if "Info" not in info and "Read" not in info:
                return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_book = judge_read = False

        book_info = extract_books_info(xml_compressed_tree)

        if "Oliver Twist" in book_info:
            judge_book = True

        if "Mark as read" in book_info:
            judge_read = True

        return {
            "judge_page": True,
            "1": judge_book,
            "2": judge_read,
            "complete": judge_book & judge_read
        }


class SingleTask_cantook_10(SingleTask):

    def judge_page(self, xml_compressed_tree):
        book_info = extract_books_info(xml_compressed_tree)
        for info in book_info:
            if ".epub" in info or "Help" in info:
                return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_book = False

        book_info = extract_books_info(xml_compressed_tree)

        if "Mer. Thou desir'st me to stop in my tale against the haire" in book_info:
            judge_book = True

        return {
            "judge_page": True,
            "1": judge_book,
            "complete": judge_book
        }


class SingleTask_cantook_11(SingleTask):
    judge_cate = False

    def judge_page(self, xml_compressed_tree):
        book_info = extract_books_info(xml_compressed_tree)
        if "Tragedies" in book_info:
            return True
        else:
            return False

    def judge(self, xml_compressed_tree, line):
        if check_selected(xml_compressed_tree, "Categories"):
            self.judge_cate = True

        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_trag = judge_book = False

        book_info = extract_books_info(xml_compressed_tree)

        if "Tragedies" in book_info:
            judge_trag = True

        if "Hamlet" in book_info and "Romeo and Juliet" in book_info:
            judge_book = True

        return {
            "judge_page": True,
            "1": self.judge_cate,
            "2": judge_trag,
            "3": judge_book,
            "complete": self.judge_cate & judge_trag & judge_book
        }


class SingleTask_cantook_12(SingleTask):

    def judge_page(self, xml_compressed_tree):
        return check_selected(xml_compressed_tree, "Collections")

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_coll = judge_favo = False

        if check_selected(xml_compressed_tree, "Collections"):
            judge_coll = True

        book_info = extract_books_info(xml_compressed_tree)

        if "Favorite" in book_info:
            judge_favo = True

        return {
            "judge_page": True,
            "1": judge_coll,
            "2": judge_favo,
            "complete": judge_coll & judge_favo
        }
