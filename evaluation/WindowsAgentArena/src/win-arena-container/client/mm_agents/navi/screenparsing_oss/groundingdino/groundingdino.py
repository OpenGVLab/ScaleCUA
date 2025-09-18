from mm_agents.navi.screenparsing_oss.element_extractor.utils import crop_image, draw_multiple_bboxes
from mm_agents.navi.screenparsing_oss.groundingdino.icon_localization import load_dino_model, det
import os
import torch

# TODO: right now det() is called for each prompt
# this can be optimized by sending all prompts to the model at once and processing the output

class GroundingDino():
    def __init__(self, prompts=["icon"], config_path=None, weights_path=None, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.prompts = prompts
        
        config_path = config_path or os.path.join(os.path.dirname(__file__), "config/GroundingDINO_SwinT_OGC.py")
        weights_path = weights_path or "/models/groundingDINO/groundingdino_swint_ogc.pth"
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found at {config_path}")
        
        if not os.path.exists(weights_path):
            raise FileNotFoundError(f"Weights file not found at {weights_path}")

        self.groundingdino_model = load_dino_model(config_path, weights_path,device=self.device).eval()

    def propose_ents(self, image_pil):
        def det2ent(prompt, coords):
            x1, y1, x2, y2 = coords
            width, height = x2 - x1, y2 - y1
            shape = {"x": x1, "y": y1, "width": width, "height": height}
            
            return {
                "from": "groundingdino",
                "type": prompt,
                "shape": shape
            }
        
        return [
            det2ent(prompt, coords) 
            for prompt in self.prompts
                for coords in det(image_pil, prompt, self.groundingdino_model)]
    
    def propose_rects(self, image_pil, text_prompt="icon"):
        coordinates = det(image_pil, text_prompt, self.groundingdino_model)
        labels = [text_prompt for i in range(len(coordinates))]
        return coordinates, labels

    def propose_regions(self, image_pil, text_prompt="icon"):
        coordinates = det(image_pil, text_prompt, self.groundingdino_model)
        image_proposals = []
        for i, coord in enumerate(coordinates):
            # print(i)
            cropped_image = crop_image(image_pil, coord, "any")
            if cropped_image:
                image_proposals.append((cropped_image, coord))
        return image_proposals



if __name__ == "__main__":

    from PIL import Image
    from pathlib import Path
    from screenparsing.utils.draw import draw_ents
    import json
    
    region_proposer = GroundingDino()

    image_path = Path(__file__).resolve().parent.parent.parent / "test" / "figs" / "1360x768_cnn.png"
    image = Image.open(image_path)
    # image_proposals = region_proposer.propose_regions(image, "icon")
    
    region_proposals = region_proposer.propose_rects(image, "icon . input")
    
    rects_path = Path(__file__).resolve().parent.parent.parent / "test" / "out" / "test_dino_rects.json"
    with open(rects_path, 'w') as f:
        f.write(json.dumps(region_proposals, indent=4))

    # image_drawn = draw_bbox(image, image_proposals[0][1], None, "red")
    # image_drawn = draw_multiple_bboxes(image, region_proposals, None, "red")
    
    ents = region_proposer.propose_ents(image)
    
    rects_path = Path(__file__).resolve().parent.parent.parent / "test" / "out" / "test_dino_ents.json"
    with open(rects_path, 'w') as f:
        f.write(json.dumps(region_proposals, indent=4))
    out_path = Path(__file__).resolve().parent.parent.parent / "test" / "out" / "test_dino_out.png"
    draw_ents(image, ents, labelKey='type').save(out_path)
    
    print(f"Saved output to {out_path}")
    