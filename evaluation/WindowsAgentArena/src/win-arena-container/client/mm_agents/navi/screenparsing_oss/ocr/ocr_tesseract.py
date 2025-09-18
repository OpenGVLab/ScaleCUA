"""
OCR implementation using PyTessaract instead of internal OCR model

Instructions for installing Tessaract on Windows:
1. Follow the instructions here - https://github.com/UB-Mannheim/tesseract/wiki
2. Add the path to Tesseract installation directory to Path environment variable
"""

from PIL import Image
import pytesseract
import json


class TesseractOCR:
    def __init__(self):
        pass

    def _parse_raw_ocr_data(self, raw_ocr_data: dict):
        parsed_data = {"RawData": {"lines": []}}
        parsed_words = []
        idx = -1

        num_rows = len(raw_ocr_data["text"])
        for i in range(num_rows):
            parsed_word = {}
            if raw_ocr_data["conf"][i] != -1:
                idx += 1

                parsed_word["index"] = idx
                parsed_word["text"] = raw_ocr_data["text"][i]
                parsed_word["level"] = raw_ocr_data["level"][i]
                parsed_word["page_num"] = raw_ocr_data["page_num"][i]
                parsed_word["block_num"] = raw_ocr_data["block_num"][i]
                parsed_word["par_num"] = raw_ocr_data["par_num"][i]
                parsed_word["line_num"] = raw_ocr_data["line_num"][i]
                parsed_word["word_num"] = raw_ocr_data["word_num"][i]

                top = raw_ocr_data["top"][i]
                left = raw_ocr_data["left"][i]
                width = raw_ocr_data["width"][i]
                height = raw_ocr_data["height"][i]
                parsed_word["bb"] = [
                    [left, top],
                    [left + width, top],
                    [left + width, top + height],
                    [left, top + height],
                ]

                parsed_word["words"] = [
                    {"bb": parsed_word["bb"], "conf": raw_ocr_data["conf"][i]}
                ]

                parsed_words.append(parsed_word)

        parsed_data["RawData"]["lines"] = parsed_words

        return parsed_data

    def propose_ents(self, image):

        ocr_data = self.calculate_ocr(image)

        def ocr2ent(ocr_line):

            bb = ocr_line["bb"]
            bb_tuples = [tuple(coord) for coord in bb]

            # Calculate the minimum and maximum values of the bounding box coordinates
            min_x = min(coord[0] for coord in bb_tuples)
            min_y = min(coord[1] for coord in bb_tuples)
            max_x = max(coord[0] for coord in bb_tuples)
            max_y = max(coord[1] for coord in bb_tuples)

            # Calculate width and height
            width = max_x - min_x
            height = max_y - min_y
            shape = {"x": min_x, "y": min_y, "width": width, "height": height}

            return {
                "from": "oneocr",
                "type": "text",
                "shape": shape,
                "text": ocr_line["text"],
            }

        return [ocr2ent(el) for el in ocr_data["RawData"]["lines"]]

    def calculate_ocr(self, img: Image.Image):
        self.raw_ocr_data = pytesseract.image_to_data(
            img, config="--psm 11 --oem 3", output_type=pytesseract.Output.DICT
        )  # default config='--psm 6 --oem 3'

        ocr_data = self._parse_raw_ocr_data(self.raw_ocr_data)
        ocr_data["AllTextRendered"] = pytesseract.image_to_string(img).split("\n")

        return ocr_data


if __name__ == "__main__":

    from pathlib import Path
    import argparse

    image_path = (
        Path(__file__).resolve().parent.parent.parent
        / "test"
        / "figs"
        / "1360x768_cnn.png"
    )
    out_path = (
        Path(__file__).resolve().parent.parent.parent
        / "test"
        / "out"
        / "test_tesseractocr_rects.json"
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--img", type=str, help="Path to img file", default=image_path)

    args = parser.parse_args()

    # compare tessaract OCR with PS OCR
    ts_ocr = TesseractOCR()

    # image data
    img = Image.open(args.img)

    ts_ocr_data = ts_ocr.calculate_ocr(img)
    with open(out_path, "w") as json_file:
        json.dump(ts_ocr_data, json_file, indent=4)
