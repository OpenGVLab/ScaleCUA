import torch
import numpy as np
from PIL import Image
import mm_agents.navi.screenparsing_oss.groundingdino.datasets.transforms as T
from mm_agents.navi.screenparsing_oss.groundingdino.models import build_model
from mm_agents.navi.screenparsing_oss.groundingdino.util.slconfig import SLConfig
from mm_agents.navi.screenparsing_oss.groundingdino.util.utils import clean_state_dict, get_phrases_from_posmap

def compute_size(box):
    return (box[2]-box[0]) * (box[3]-box[1])


def compute_iou(box1, box2):
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])
    
    interArea = max(0, xB - xA) * max(0, yB - yA)
    box1Area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2Area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    unionArea = box1Area + box2Area - interArea
    iou = interArea / unionArea
    
    return iou

def transform_image(image_pil):

    transform = T.Compose(
        [
            T.RandomResize([800], max_size=1333),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    image, _ = transform(image_pil, None)  # 3, h, w
    return image


def load_dino_model(model_config_path, model_checkpoint_path, device):
    args = SLConfig.fromfile(model_config_path)
    args.device = device
    model = build_model(args)
    checkpoint = torch.load(model_checkpoint_path, map_location="cpu")
    load_res = model.load_state_dict(clean_state_dict(checkpoint["model"]), strict=False)
    _ = model.eval()
    return model


def get_grounding_output(model, image, caption, box_threshold, text_threshold, with_logits=True):
    caption = caption.lower()
    caption = caption.strip()
    if not caption.endswith("."):
        caption = caption + "."

    with torch.no_grad():
        outputs = model(image[None], captions=[caption])
    logits = outputs["pred_logits"].cpu().sigmoid()[0]  # (nq, 256)
    boxes = outputs["pred_boxes"].cpu()[0]  # (nq, 4)
    logits.shape[0]

    logits_filt = logits.clone()
    boxes_filt = boxes.clone()
    filt_mask = logits_filt.max(dim=1)[0] > box_threshold
    logits_filt = logits_filt[filt_mask]  # num_filt, 256
    boxes_filt = boxes_filt[filt_mask]  # num_filt, 4
    logits_filt.shape[0]

    tokenlizer = model.tokenizer
    tokenized = tokenlizer(caption)

    pred_phrases = []
    scores = []
    for logit, box in zip(logits_filt, boxes_filt):
        pred_phrase = get_phrases_from_posmap(logit > text_threshold, tokenized, tokenlizer)
        if with_logits:
            pred_phrases.append(pred_phrase + f"({str(logit.max().item())[:4]})")
        else:
            pred_phrases.append(pred_phrase)
        scores.append(logit.max().item())

    return boxes_filt, torch.Tensor(scores), pred_phrases


def remove_boxes(boxes_filt, size, iou_threshold=0.5,  ):
    boxes_to_remove = set()
    box_size_lim =  0.05 *size[0]*size[1]
    for i in range(len(boxes_filt)):
        if compute_size(boxes_filt[i]) > box_size_lim:
            boxes_to_remove.add(i)
        for j in range(len(boxes_filt)):
            if compute_size(boxes_filt[j]) > box_size_lim:
                boxes_to_remove.add(j)
            if i == j:
                continue
            if i in boxes_to_remove or j in boxes_to_remove:
                continue
            #iou = compute_iou(boxes_filt[i], boxes_filt[j])
            #if iou >= iou_threshold:
            #    boxes_to_remove.add(j)

    boxes_filt = [box for idx, box in enumerate(boxes_filt) if idx not in boxes_to_remove]
    
    return boxes_filt


def det(image, text_prompt, groundingdino_model, box_threshold=0.03, text_threshold=0.4):
    if isinstance(image, str):
        image = Image.open(image)
    size = image.size

    image_pil = image.convert("RGB")
    image = np.array(image_pil)
    
    transformed_image = transform_image(image_pil)
    boxes_filt, _, _ = get_grounding_output(
        groundingdino_model, transformed_image, text_prompt, box_threshold, text_threshold
    )
    
    # print(_)

    H, W = size[1], size[0]
    for i in range(boxes_filt.size(0)):
        boxes_filt[i] = boxes_filt[i] * torch.Tensor([W, H, W, H])
        boxes_filt[i][:2] -= boxes_filt[i][2:] / 2
        boxes_filt[i][2:] += boxes_filt[i][:2]

    boxes_filt = boxes_filt.cpu().int().tolist()
    filtered_boxes = remove_boxes(boxes_filt, size)
    
    image_data = []
    for box in filtered_boxes:
        image_data.append([max(0, box[0]-10), max(0, box[1]-10), min(box[2]+10, size[0]), min(box[3]+10, size[1])])
    return image_data