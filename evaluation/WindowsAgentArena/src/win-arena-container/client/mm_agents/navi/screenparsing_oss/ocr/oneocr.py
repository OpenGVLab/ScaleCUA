import sys
import os
from pprint import pprint
from PIL import Image
from json import load
from mm_agents.navi.screenparsing_oss.ocr.ocr_factory import OCR_FACTORY
from PIL import Image, ImageDraw, ImageFont
from mm_agents.navi.screenparsing_oss.utils import draw


class OneOcr:

    def __init__(self, base_path=None, class_name=None) -> None:
        ocr_class = class_name

        self.ocr = OCR_FACTORY().create_instance(
            class_name=ocr_class, base_path=base_path
        )

    def propose_ents(self, image):
        return self.ocr.propose_ents(image)

    def propose_rects(self, image_pil):
        ents = self.ocr.propose_ents(image_pil)
        pprint(ents)
        image = draw.draw_ents(image_pil, ents)
        return image


if __name__ == "__main__":

    def resolve_path(path):
        cwd = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(cwd, path))

    ocr_instance = OneOcr(class_name="TesseractOCR")

    image_path = resolve_path("../../test/figs/1360x768_cnn.png")
    image = Image.open(image_path)
    image = image.convert("RGB")
    ocr_instance.ocr.calculate_ocr_and_draw_boxes(image)
