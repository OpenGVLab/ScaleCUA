import transformers
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, List


@dataclass
class ModelArguments:
    model_name_or_path: Optional[str] = field(default="Qwen/Qwen2.5-VL-3B-Instruct")
    tune_mm_llm: bool = field(default=False)
    tune_mm_mlp: bool = field(default=False)
    tune_mm_vision: bool = field(default=False)

@dataclass
class DataArguments:
    data_path: str = field(default="")
    meta_path: str = field(default="")
    conv_style: Optional[int] = field(default=None)
    video_max_frames: Optional[int] = field(default=8)
    video_min_frames: Optional[int] = field(default=4)
    data_flatten: bool = field(default=False)
    base_interval: int = field(default=2)
    coord_norm: bool = field(default=True)
    group_sampling: bool = field(default=False)
    custom_seed: int = field(default=42)
    min_pixels: int = field(default=3136)  # 4 * 28 * 28
    max_pixels: int = field(default=2109744)  # 1080p, 69 * 39 * 28 * 28
    # max_pixels: int = field(default=937664)  # 720p, 46 * 26 * 28 * 28
    # max_pixels: int = field(default=3750656)  # 2k, 92 * 52 * 28 * 28
    # max_pixels: int = field(default=8438976)  # 4k, 138 * 78 * 28 * 28
    video_max_frame_pixels: int = field(default=32 * 28 * 28)
    video_min_frame_pixels: int = field(default=4 * 28 * 28)


@dataclass
class TrainingArguments(transformers.TrainingArguments):
    cache_dir: Optional[str] = field(default=None)
    optim: str = field(default="adamw_torch")
    model_max_length: int = field(
        default=512,
        metadata={
            "help": "Maximum sequence length. Sequences will be right padded (and possibly truncated)."
        },
    )
    mm_projector_lr: Optional[float] = None
    vision_tower_lr: Optional[float] = None
