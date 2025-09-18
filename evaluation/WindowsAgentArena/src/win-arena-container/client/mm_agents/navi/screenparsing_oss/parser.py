import os
import copy
from collections import defaultdict
  
def resolve_path(path):
    cwd = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(cwd, path))

def make_proposer_instance(proposer_name, config):
    inst_config = copy.deepcopy(config.get(proposer_name, {}))
    base_path = inst_config.get('base_path', None)
    if base_path:
        inst_config['base_path'] = resolve_path(base_path)
    
    proposer_name = proposer_name.lower()
    if proposer_name == 'ocr':
        from mm_agents.navi.screenparsing_oss.ocr.oneocr import OneOcr
        return OneOcr(**inst_config)
    elif proposer_name == 'groundingdino':
        from mm_agents.navi.screenparsing_oss.groundingdino.groundingdino import GroundingDino
        return GroundingDino(**inst_config)
    elif proposer_name == 'webparse':
        from mm_agents.navi.screenparsing_oss.webparse.webparse import WebParse
        return WebParse(**inst_config)
    elif proposer_name == 'omniparser':
        from mm_agents.navi.screenparsing_oss.omniparser.omniparser import Omniparser
        return Omniparser(**inst_config)
    else:
        raise ValueError(f"Unknown proposer: {proposer_name}")

class ScreenParser:
    def __init__(self, parser_config=None) -> None:
        default_config = defaultdict(lambda: defaultdict(str), 
        {
            "pipeline": ["webparse", "groundingdino", "ocr"],
            "groundingdino": {
                "prompts": ["icon", "image"]
            },
            "ocr": {
                "class_name": "TesseractOCR"
            },
            "webparse": {
                "cdp_url": f"http://20.20.20.21:9222" 
            }
        }
        )
        
        if parser_config:
            config = {**default_config, **parser_config}
        else:
            config = default_config
        
        # Load all the proposers
        self.parsers = [
            make_proposer_instance(proposer_name, config)
            for proposer_name in config['pipeline']
        ]
        
    def propose_ents(self, image):
        
        image = image.convert('RGB')
        
        # We'll be storing all on-screen entities we can extract in here
        entities = []
        
        # Run all the proposers
        for proposer in self.parsers:
            entities += proposer.propose_ents(image)
        
        return entities
    

