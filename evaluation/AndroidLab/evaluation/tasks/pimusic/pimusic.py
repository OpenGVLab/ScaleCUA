import re
from typing import Dict, List

from evaluation.task import SingleTask
from evaluation.utils import find_matching_subtrees


def extract_songs(xml_compressed_tree) -> List[Dict]:
    songs_data = find_matching_subtrees(xml_compressed_tree, "TextView ;; ;;")
    song_data = [list(sd.keys())[0].split(";; ;;")[-1].strip() for sd in songs_data]
    duration_pattern = re.compile(r'^(\d+:)?[0-5]?\d:[0-5]?\d$')
    start_index = 0
    for i in range(4):
        if i + 2 < len(song_data):
            if duration_pattern.match(song_data[i + 2]):
                start_index = i
                break
    result = []
    for i in range(start_index, len(song_data), 3):
        if i + 2 < len(song_data):
            song = song_data[i]
            artist = song_data[i + 1]
            duration = song_data[i + 2]
            if duration_pattern.match(duration):
                song_info = {
                    'song': song,
                    'artist': artist,
                    'duration': duration
                }
                result.append(song_info)
            else:
                break
    return result


def parse_duration(duration):
    parts = list(map(int, duration.split(':')))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError("Invalid duration format")


def extract_info(xml_compressed_tree):
    songs_data = find_matching_subtrees(xml_compressed_tree, "TextView")
    songs_set = set()
    for song_data in songs_data:
        song_data = list(song_data.keys())[0]
        song_data = song_data.split(";; ;;")[-1].strip()
        songs_set.add(song_data)
    return songs_set


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


class SingleTask_pimusic_1(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "12 songs"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_pimusic_2(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "4 songs"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_pimusic_3(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "Pulse Live"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_pimusic_4(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "1 hour, 21 minutes and 3 seconds"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_pimusic_5(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "The second song is 'Dark Side Of The Moon' and the fourth song is 'Future sounds'"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_pimusic_6(SingleTask):

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "11 minutes and 50 seconds"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_pimusic_7(SingleTask):
    judge_list = False
    judge_favo = False

    def judge_page(self, xml_compressed_tree):
        page_info = extract_info(xml_compressed_tree)
        for info in page_info:
            if "Now Playing list" in info and "Equalizer" in info:
                return True
        return False

    def judge(self, xml_compressed_tree, line):
        if not self.judge_list:
            if check_selected(xml_compressed_tree, "PLAYLISTS"):
                self.judge_list = True

        if not self.judge_favo:
            get_pf = find_matching_subtrees(xml_compressed_tree, "] ;; ;;Favorite")
            if len(get_pf) == 1:
                self.judge_favo = True

        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        if self.judge_favo:
            judge_play = False
            play_info = extract_info(xml_compressed_tree)
            if "PINK BLOOD" in play_info:
                judge_play = True

        return {
            "judge_page": True,
            "1": self.judge_list,
            "2": self.judge_favo,
            "3": judge_play,
            "complete": self.judge_list & self.judge_favo & judge_play
        }


class SingleTask_pimusic_8(SingleTask):
    judge_arti = False
    judge_sort_step = False

    def judge_page(self, xml_compressed_tree):
        get_pf = find_matching_subtrees(xml_compressed_tree, "] ;; ;;Pink Floyd")
        if len(get_pf) != 1:
            return False
        else:
            return True

    def judge(self, xml_compressed_tree, line):
        if not self.judge_arti:
            if check_selected(xml_compressed_tree, "ARTISTS"):
                self.judge_arti = True

        if not self.judge_sort_step:
            sort_info = extract_info(xml_compressed_tree)
            if "Sort By" in sort_info:
                self.judge_sort_step = True

        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_pf = judge_sort_final = False
        get_pf = find_matching_subtrees(xml_compressed_tree, "] ;; ;;Pink Floyd")
        if len(get_pf) == 1:
            judge_pf = True

        if self.judge_sort_step:
            song_data = extract_songs(xml_compressed_tree)
            def dur2sec(duration):
                return parse_duration(duration)
            dur2sec_list = [dur2sec(song['duration']) for song in song_data]
            judge_sort_final = all(dur2sec_list[i] >= dur2sec_list[i + 1] for i in range(len(dur2sec_list) - 1))

        return {
            "judge_page": True,
            "1": self.judge_arti,
            "2": judge_pf,
            "3": self.judge_sort_step,
            "4": judge_sort_final,
            "complete": self.judge_arti & judge_pf & self.judge_sort_step & judge_sort_final
        }


class SingleTask_pimusic_9(SingleTask):

    def judge_page(self, xml_compressed_tree):
        return check_selected(xml_compressed_tree, "PLAYLISTS")

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_list = judge_cree = False

        if check_selected(xml_compressed_tree, "PLAYLISTS"):
            judge_list = True

        list_info = extract_info(xml_compressed_tree)
        if "Creepy" in list_info:
            judge_cree = True

        return {
            "judge_page": True,
            "1": judge_list,
            "2": judge_cree,
            "complete": judge_list & judge_cree
        }


class SingleTask_pimusic_10(SingleTask):

    def judge_page(self, xml_compressed_tree):
        page_info = extract_info(xml_compressed_tree)
        for info in page_info:
            if "Now Playing list" in info and "Equalizer" in info:
                return True
        return False

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_time = False
        play_info = extract_info(xml_compressed_tree)
        if "1:27" in play_info:
            judge_time = True

        return {
            "judge_page": True,
            "1": judge_time,
            "complete": judge_time
        }


class SingleTask_pimusic_11(SingleTask):

    def judge_page(self, xml_compressed_tree):
        page_info = extract_info(xml_compressed_tree)
        for info in page_info:
            if "Now Playing list" in info and "Equalizer" in info:
                return True
        return False

    def judge(self, xml_compressed_tree, line):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_play = False
        play_info = extract_info(xml_compressed_tree)
        if "Lightship" in play_info:
            judge_play = True

        return {
            "judge_page": True,
            "1": judge_play,
            "complete": judge_play
        }


class SingleTask_pimusic_12(SingleTask):
    judge_sort_step = False

    def judge_page(self, xml_compressed_tree):
        return check_selected(xml_compressed_tree, "TRACKS")

    def judge(self, xml_compressed_tree, line):
        if not self.judge_sort_step:
            sort_info = extract_info(xml_compressed_tree)
            if "Sort By" in sort_info:
                self.judge_sort_step = True

        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        judge_sort_final = False

        song_data = extract_songs(xml_compressed_tree)
        def dur2sec(duration):
            return parse_duration(duration)
        dur2sec_list = [dur2sec(song['duration']) for song in song_data]
        judge_sort_final = all(dur2sec_list[i] <= dur2sec_list[i + 1] for i in range(len(dur2sec_list) - 1))

        return {
            "judge_page": True,
            "1": self.judge_sort_step,
            "2": judge_sort_final,
            "complete": self.judge_sort_step & judge_sort_final
        }
