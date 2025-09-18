import io
import os
from PIL import Image

class OCR_FACTORY:

    def __init__(self, base_path=None):
        cwd = os.path.dirname(os.path.abspath(__file__))
        self.base_path = base_path or cwd
        self.output_path=None

    def create_instance(self, class_name, base_path=None):
        self.output_path=os.path.join(self.base_path, 'output', f'bounding_boxes_image_{class_name}.png')
        if class_name == "TesseractOCR":
            from mm_agents.navi.screenparsing_oss.ocr.ocr_tesseract   import  TesseractOCR
            return TesseractOCR()
        else:
            raise ValueError(f"Unknown class name: {class_name}")
        
def main():
    image_path = "../../test/figs/1360x768_cnn.png"
    image = Image.open(image_path)
    
    ocr_factory = OCR_FACTORY()
    ocr_instance = ocr_factory.create_instance("TesseractOCR")
    image=ocr_instance.calculate_ocr_and_draw_boxes(image)
    print(image)

if __name__ == "__main__":
    main()