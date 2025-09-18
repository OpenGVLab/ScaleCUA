import json
import logging
import re
from typing import Dict, List
# from mm_agents.planner.computer import Computer, WindowManager
from mm_agents.navi.gpt.gpt4v_planner import GPT4V_Planner
from mm_agents.navi.gpt import planner_messages
from mm_agents.navi.prompts import SYS_PROMPT_IN_SCREENSHOT_OUT_CODE
import copy
from io import BytesIO

logger = logging.getLogger("desktopenv.agent")

def remove_min_leading_spaces(text):  
    lines = text.split('\n')  
    min_spaces = min(len(line) - len(line.lstrip(' ')) for line in lines if line)  
    return '\n'.join([line[min_spaces:] for line in lines])  

def prev_actions_to_string(prev_actions, n_prev=3):  
    result = ""  
    n_prev = min(n_prev, len(prev_actions))  # Limit n_prev to the length of the array  
    for i in range(1, n_prev + 1):  
        action = prev_actions[-i]  # Get the element at index -i (from the end)  
        result += f"Screen is currently at time step T. Below is the action executed at time step T-{i}: \n{action}\n\n"  
    return result  

from PIL import Image

def resize_image_openai(image):
    """
    Resize the image to OpenAI's input resolution so that text written on it doesn't get processed any further.
    
    Steps:
    1. If the image's largest side is greater than 2048, scale it down so that the largest side is 2048, maintaining aspect ratio.
    2. If the shortest side of the image is longer than 768px, scale it so that the shortest side is 768px.
    3. Return the resized image.
    
    Reference: https://platform.openai.com/docs/guides/vision/calculating-costs
    """
    max_size = 2048
    target_short_side = 768
    
    out_w, out_h = image.size

    # Step 0: return the image without scaling if it's already within the target resolution
    if out_w <= max_size and out_h <= max_size and min(out_w, out_h) <= target_short_side:
        return image, out_w, out_h, 1.0
    
    # Initialize scale_factor
    scale_factor = 1.0
    
    # Step 1: Calculate new size to fit within a 2048 x 2048 square
    max_dim = max(out_w, out_h)
    if max_dim > max_size:
        scale_factor = max_size / max_dim
        out_w = int(out_w * scale_factor)
        out_h = int(out_h * scale_factor)
    
    # Step 2: Calculate new size if the shortest side is longer than 768px
    min_dim = min(out_w, out_h)
    if min_dim > target_short_side:
        new_scale_factor  = target_short_side / min_dim
        out_w = int(out_w * new_scale_factor)
        out_h = int(out_h * new_scale_factor)
        # Combine scale factors from both steps
        scale_factor *= new_scale_factor
    
    # Perform the resize operation once
    resized_image = image.resize((out_w, out_h))
    
    return resized_image, out_w, out_h, scale_factor

class NaviAgent:
    def __init__(
            self,
            server: str = "azure",
            model: str = "gpt-4o-2024-11-20", # openai or "phi3-v"
            som_config = None,
            som_origin = "oss", # "oss", "a11y", "mixed-oss", "omni", "mixed-omni"
            obs_view = "screen", # "screen" or "window"
            auto_window_maximize = False,
            use_last_screen = True,
            temperature: float = 0.5,
    ):
        self.action_space = "code_block"
        self.server = server
        self.model = model
        self.som_origin = som_origin
        if som_config is None:
            config = {
                "ocr": {
                    "type": "deb"
                }
            }
        else:
            config = som_config
        self.obs_view = obs_view
        self.auto_window_maximize = auto_window_maximize
        self.prev_window_title = None
        self.prev_window_rect = None
        self.last_image = None
        self.use_last_screen = use_last_screen

        # hard-coded params
        device = "cpu"
        self.h, self.w = 1200, 1920 
        
        if som_origin in ["oss", "mixed-oss"]: # oss extractor
            from mm_agents.navi.screenparsing_oss.parser import ScreenParser
            self.extractor = ScreenParser(config)
        elif som_origin in ["omni", "mixed-omni"]: # omni extractor
            from mm_agents.navi.screenparsing_oss.omniparser.omniparser import Omniparser
            self.omni_proposal = Omniparser()

        if model == 'phi3-v':
            from mm_agents.navi.gpt.phi3_planner import Phi3_Planner
            self.gpt4v_planner = Phi3_Planner(server='azure',model='phi3-v',temperature=temperature)          
        else:
            self.gpt4v_planner = GPT4V_Planner(server=self.server, model=self.model, temperature=temperature)
            if use_last_screen:
                # self.gpt4v_planner.system_prompt = planner_messages.planning_system_message_shortened_previmg
                self.gpt4v_planner.system_prompt = SYS_PROMPT_IN_SCREENSHOT_OUT_CODE
        
        from mm_agents.navi.screenparsing_oss.utils.obs import parser_to_prompt
        self.parser_to_prompt = parser_to_prompt

        self.memory_block_text_empty = """
```memory
# empty memory block
```
"""
        self.memory_block_text = self.memory_block_text_empty

        self.prev_actions = []
        self.clipboard_content = None
        self.n_prev = 15
        self.step_counter = 0
      

    def predict(self, instruction: str, obs: Dict) -> List:
        """
        Predict the next action(s) based on the current observation.
        """
        logs={}
        
        if self.obs_view == "screen":
            image_file = BytesIO(obs['screenshot'])
            view_image = Image.open(image_file)
            view_rect = [0, 0, view_image.width, view_image.height]
        else:
            view_image = obs['window_image']
            view_rect = obs['window_rect']
        
        window_title, window_names_str, window_rect, computer_clipboard = obs['window_title'], obs['window_names_str'], obs['window_rect'], obs['computer_clipboard']
        original_h, original_w = view_image.height, view_image.width
        
        override_plan = False
        
        # if the window is different, maximize it
        if self.auto_window_maximize:
            # when we call .maximize(), windows switches to a overflow window for 1 step, so we need to ignore it
            if "System tray" not in window_title and "Defender" not in window_title:
                if window_title != self.prev_window_title and window_rect != self.prev_window_rect:
                    # debug logging {{{
                    logs['window_title'] = window_title
                    logs['window_rect'] = window_rect
                    logs['prev_window_title'] = self.prev_window_title
                    logs['prev_window_rect'] = self.prev_window_rect
                    # }}} debug logging
                    self.prev_window_title = window_title
                    self.prev_window_rect = window_rect
                    code_result = "\n".join([
                        "# forcing step to execute auto_window_maximize...",
                        "computer.os.maximize_window()"
                    ])
                    plan_result = f"```python\n{code_result}\n```"
                    w, h = original_w, original_h
                    rects = []
                    override_plan = True
                
        if not override_plan:
            logger.info("Processing screenshot...")
            
            image  = view_image
            w,h = original_w, original_h
            logs['foreground_window'] = image
            
            # extract regions
            if self.som_origin == "a11y":
                # a11y extractor
                from mm_agents.navi.a11y_demo import propose_ents as get_a11y_ents
                rendering = "N/A"
                regions = get_a11y_ents(obs['accessibility_tree'])
                rects = [[int(ent["shape"]["x"]), int(ent["shape"]["y"]), int((ent["shape"]["x"]+ent["shape"]["width"])), int((ent["shape"]["y"]+ent["shape"]["height"]))] for ent in regions]
                color_mapping_debug = {"a11y": "red"}
                color_mapping_prompt = {"a11y": "red"}
                image_debug, image_prompt, list_of_text = self.parser_to_prompt(image, regions, color_mapping_debug, color_mapping_prompt) # full set-of-marks drawing w/ visibility filtering, overlap detection, and colors
                logs['foreground_window_regions'] = image_debug
            
            elif self.som_origin == "mixed": #TODO: combine a11y and internal extractorsin a cleaner way
                # combine both a11y and internal extractors
                
                # a11y extractor
                from mm_agents.navi.a11y_demo import propose_ents as get_a11y_ents, get_mask_from_entities, filter_entities_with_mask, detections_to_entities
                from mm_agents.navi.screenparsing_oss.utils.som import  filter_entities
                import numpy as np
                rendering = "N/A"
                regions = get_a11y_ents(obs['accessibility_tree'])
                regions = filter_entities(regions)
                mask = get_mask_from_entities(regions, image.width, image.height)
                #convert mask to pil
                mask_img = np.stack([mask]*3, axis=-1).astype(np.uint8)
                logs['foreground_window_mask'] = Image.fromarray(mask_img*255)
                # proprietary extractor
                detected_regions, rendering_ex = self.extractor.build_regions(image)
                
                
                id_list, rects = self.extractor.get_rect_list(detected_regions)
                list_of_text = self.extractor.create_text_list(detected_regions, image.width, image.height)
                
                # create logging image with all the tags
                image_debug_ex = copy.deepcopy(image)
                color_mapping_debug = {"images": "red", "ocr": "blue", "icons": "green", "text/html": "magenta"}
                try:
                    image_debug_ex = draw_colored_image(image_debug_ex, detected_regions, color_mapping_debug, draw_numbers=True)
                except Exception as e:
                    logger.error("Did not find regions in the image. Error:", e)
                logs['foreground_window_regions_models'] = image_debug_ex
                
                regions_ex = detections_to_entities(detected_regions)
                
                new_regions = filter_entities_with_mask(regions_ex, mask, th=0.5)
                
                regions += new_regions
                rects = [[int(ent["shape"]["x"]), int(ent["shape"]["y"]), int((ent["shape"]["x"]+ent["shape"]["width"])), int((ent["shape"]["y"]+ent["shape"]["height"]))] for ent in regions]
                color_mapping_debug = {"a11y": "red", "images": "blue", "ocr": "blue", "icons": "green", "text/html": "magenta"}
                color_mapping_prompt = {"a11y": "red", "images": "blue", "icons": "green"}
                image_debug, image_prompt, list_of_text = self.parser_to_prompt(image, regions, color_mapping_debug, color_mapping_prompt) # full set-of-marks drawing w/ visibility filtering, overlap detection, and colors
                logs['foreground_window_regions'] = image_debug
                logs['foreground_window_prompt'] = image_prompt
                
            elif self.som_origin == "mixed-oss": 
                # combine both a11y and internal extractors
                
                # a11y extractor
                from mm_agents.navi.a11y_demo import propose_ents as get_a11y_ents, get_mask_from_entities, filter_entities_with_mask, detections_to_entities
                from mm_agents.navi.screenparsing_oss.utils.som import  filter_entities
                import numpy as np
                rendering = "N/A"
                regions = get_a11y_ents(obs['accessibility_tree'])
                regions = filter_entities(regions)
                mask = get_mask_from_entities(regions, image.width, image.height)
                #convert mask to pil
                mask_img = np.stack([mask]*3, axis=-1).astype(np.uint8)
                logs['foreground_window_mask'] = Image.fromarray(mask_img*255)
                
                
                # oss extractor
                regions_ex = self.extractor.propose_ents(image)
                
                # create logging image with all the tags
                color_mapping_debug = {"a11y": "red", "image": "red", "text": "blue", "icon": "green"}
                try:
                    image_debug_ex, _, models_debug_txt = self.parser_to_prompt(image, regions_ex, color_mapping_debug, color_mapping_debug)
                    # logs['entity_list_len'] = len(regions_ex)
                    # logs['entity_list_models'] = models_debug_txt
                except Exception as e:
                    logger.error("Did not find regions in the image. Error:", e)
                logs['foreground_window_regions_models'] = image_debug_ex
                
                
                # combine both outputs
                new_regions = filter_entities_with_mask(regions_ex, mask, th=0.5)
                regions += new_regions
                
                rects = [[int(ent["shape"]["x"]), int(ent["shape"]["y"]), int((ent["shape"]["x"]+ent["shape"]["width"])), int((ent["shape"]["y"]+ent["shape"]["height"]))] for ent in regions]
                color_mapping_debug = {"a11y": "red", "image": "red", "text": "blue", "icon": "green", "text/html": "magenta"}
                color_mapping_prompt = {"a11y": "red", "image": "red", "icon": "green"}
                image_debug, image_prompt, list_of_text = self.parser_to_prompt(image, regions, color_mapping_debug, color_mapping_prompt) # full set-of-marks drawing w/ visibility filtering, overlap detection, and colors
                logs['foreground_window_regions'] = image_debug
                logs['foreground_window_prompt'] = image_prompt
            
            elif self.som_origin == "mixed-omni":
                # combine both a11y and omni extractors
                
                # a11y extractor
                from mm_agents.navi.a11y_demo import propose_ents as get_a11y_ents, get_mask_from_entities, filter_entities_with_mask, detections_to_entities, filter_nonvis_and_oob_entities
                from mm_agents.navi.screenparsing_oss.utils.som import  filter_entities
                import numpy as np
                rendering = "N/A"
                regions_a11y = get_a11y_ents(obs['accessibility_tree'])
                regions_a11y = filter_entities(regions_a11y)
                regions_a11y = filter_nonvis_and_oob_entities(regions_a11y, image.width, image.height)
                mask = get_mask_from_entities(regions_a11y, image.width, image.height)
                #convert mask to pil
                mask_img = np.stack([mask]*3, axis=-1).astype(np.uint8)
                logs['foreground_window_mask'] = Image.fromarray(mask_img*255)
                
                
                # omni extractor
                rendering = "N/A"
                regions_omni = self.omni_proposal.propose_ents(image, with_captions=False)
                
                # create logging image
                color_mapping_debug = {"a11y": "magenta", "image": "red", "text": "blue", "icon": "green"}
                try:
                    image_debug_ex, _, models_debug_txt = self.parser_to_prompt(image, regions_a11y + regions_omni, color_mapping_debug, color_mapping_debug)
                    logs['foreground_window_regions_a11y_models'] = image_debug_ex
                except Exception: pass
                
                # combine both outputs
                regions_omni = filter_entities_with_mask(regions_omni, mask, th=0.5)
                regions = regions_a11y + regions_omni
                
                ### DEBUG CAPTION INPUT
                # width, height = image.size
                # ents_rects = [
                #     (ent, (
                #         ent['shape']['x'] / width, 
                #         ent['shape']['y'] / height, 
                #         (ent['shape']['x'] + ent['shape']['width']) / width, 
                #         (ent['shape']['y'] + ent['shape']['height']) / height
                #     ))
                #     for ent in regions
                #     if not ent.get('text', '').strip()
                # ]
                # target_ents, target_rects = [list(tup) for tup in zip(*ents_rects)]
                # logs['target_ents_before'] = copy.deepcopy(target_ents)
                # logs['target_ents'] = target_ents
                # logs['target_rects'] = target_rects
                ###
                
                # perform omni captioning on unlabeled ents
                try:
                    logs['parsed_content_icon'] = self.omni_proposal.caption_ents(image, regions)
                except Exception as e:
                    logger.error("Failed to caption icons.", e)
                
                # try to organize a11y tree into "icon" and "text" so on-screen text set-of-marks can be reduced
                for region in regions:
                    width, height = region['shape']['width'], region['shape']['height']
                    is_90_percent_square = 0.9 <= width / height <= 1.1
                    if region['type'] == 'a11y':
                        region['type'] = 'icon' if is_90_percent_square else 'text'
                
                rects = [[int(ent["shape"]["x"]), int(ent["shape"]["y"]), int((ent["shape"]["x"]+ent["shape"]["width"])), int((ent["shape"]["y"]+ent["shape"]["height"]))] for ent in regions]
                color_mapping_debug = {"image": "red", "text": "blue", "icon": "green"}
                color_mapping_prompt = {"image": "red", "icon": "green"}
                image_debug, image_prompt, list_of_text = self.parser_to_prompt(image, regions, color_mapping_debug, color_mapping_prompt) # full set-of-marks drawing w/ visibility filtering, overlap detection, and colors
                logs['foreground_window_regions'] = image_debug
                logs['foreground_window_prompt'] = image_prompt
                
            elif self.som_origin == "omni":
                
                # omni extractor
                rendering = "N/A"
                regions = self.omni_proposal.propose_ents(image, with_captions=True)
                
                rects = [[int(ent["shape"]["x"]), int(ent["shape"]["y"]), int((ent["shape"]["x"]+ent["shape"]["width"])), int((ent["shape"]["y"]+ent["shape"]["height"]))] for ent in regions]
                color_mapping_debug = {"image": "red", "text": "blue", "icon": "green"}
                color_mapping_prompt = {"image": "red", "icon": "green"}
                image_debug, image_prompt, list_of_text = self.parser_to_prompt(image, regions, color_mapping_debug, color_mapping_prompt) # full set-of-marks drawing w/ visibility filtering, overlap detection, and colors
                logs['foreground_window_regions'] = image_debug
                logs['foreground_window_prompt'] = image_prompt

            else:
                # OSS extractor
                rendering = "N/A"
                regions = self.extractor.propose_ents(image)
                
                rects = [[int(ent["shape"]["x"]), int(ent["shape"]["y"]), int((ent["shape"]["x"]+ent["shape"]["width"])), int((ent["shape"]["y"]+ent["shape"]["height"]))] for ent in regions]
                color_mapping_debug = {"image": "red", "text": "blue", "icon": "green", "text/html": "magenta"}
                color_mapping_prompt = {"image": "red", "icon": "green"}
                image_debug, image_prompt, list_of_text = self.parser_to_prompt(image, regions, color_mapping_debug, color_mapping_prompt) # full set-of-marks drawing w/ visibility filtering, overlap detection, and colors
                logs['foreground_window_regions'] = image_debug

            # construct prompt
            prev_actions_str = prev_actions_to_string(self.prev_actions, self.n_prev)

            logs['window_title'] = window_title
            logs['window_names_str'] = window_names_str
            logs['computer_clipboard'] = computer_clipboard
            logs['image_width'] = image.width
            logs['image_height'] = image.height
            logs['regions'] = regions

            user_question = planner_messages.build_user_msg_visual(instruction, window_title, window_names_str, computer_clipboard, rendering, list_of_text, prev_actions_str, self.memory_block_text)
            print(f"\n******************************* User Question ******************************* \n {user_question}")
            logs['user_question'] = user_question
            
            image_resized, w_resized, h_resized, factor = resize_image_openai(view_image)
            image_prompt_resized, w_resized, h_resized, factor = resize_image_openai(image_prompt)
            
            # image_prompts = [image_resized, image_prompt_resized]
            # origin image only 
            image_prompts = [image_resized]
            if self.use_last_screen:
                last_image = self.last_image if self.last_image is not None else image_resized
                self.last_image = image_resized
                logs['last_image'] = last_image
                
                #image_prompts = [last_image] + image_prompts
                # image_prompts = [last_image, image_prompt_resized]
                # origin image only 
                image_prompts = [last_image]

            # send to gpt
            logger.info("Thinking...")
            plan_result = self.gpt4v_planner.plan(image_prompts, user_question)

        logs['plan_result'] = plan_result

        # extract the textual memory block
        memory_block = re.search(r'```memory\n(.*?)```', plan_result, re.DOTALL)
        if memory_block:
            self.memory_block_text = '```memory\n' + memory_block.group(1) + '```'

        # extract the plan which is in a ```python ...``` code block
        code_block = re.search(r'```python\n(.*?)```', plan_result, re.DOTALL)
        if code_block:
            code_block_text = code_block.group(1)
            code_block_text = remove_min_leading_spaces(code_block_text)
            actions = [code_block_text]
        else:
            logger.error("Plan not found")
            code_block_text = "# plan not found"
            actions = ["# plan not found"]

        self.prev_actions.append(code_block_text)
        scale = (original_w/w, original_h/h)

        response = ""
        computer_update_args = {
            'rects': rects,
            'window_rect': view_rect,
            'screenshot': view_image,
            'scale': scale,
            'clipboard_content': computer_clipboard,
            'swap_ctrl_alt': False
        }

        self.step_counter += 1

        # actions = code_block.split("\n")
        # remove empty lines and comments
        # actions = [action for action in actions if action.strip() and not action.strip().startswith("#")]

        # extract the high-level decision block
        decision_block = re.search(r'```decision\n(.*?)```', plan_result, re.DOTALL)
        if decision_block:
            self.decision_block_text = decision_block.group(1)
            if "DONE" in self.decision_block_text:
                actions = ["DONE"]
            elif "FAIL" in self.decision_block_text:
                actions = ["FAIL"]
            elif "WAIT" in self.decision_block_text:
                actions = ["WAIT"]

        return response, actions, logs, computer_update_args


    def reset(self):
        self.memory_block_text = self.memory_block_text_empty
        self.prev_actions = []
        self.prev_window_title = None
        self.prev_window_rect = None
        self.clipboard_content = None
        self.step_counter = 0
        self.last_image = None