# Training Computer Use Agents with Qwen2.5VL

This repository provides a training framework for building **computer-use agents** based on **Qwen2.5-VL** models. It supports fine-tuning with customized datasets and multi-GPU training.

---

## 1. Environment Setup

Install the required dependencies:

```bash
pip install -r requirements.txt
```

---

## 2. Download Pretrained Models

Before fine-tuning, download the pretrained checkpoints:

```bash
mkdir pretrained/
huggingface-cli download --resume-download --local-dir-use-symlinks False \
    Qwen/Qwen2.5-VL-7B-Instruct \
    --local-dir pretrained/Qwen2.5-VL-7B-Instruct
```

---

## 3. Prepare Customized Data

You can organize your dataset with the following configuration:

```json
{
  "your-custom-dataset-1": {
    "root": "path/to/the/image/",
    "annotation": "path/to/the/jsonl/annotation",
    "conv_style": "internvl2_5_mobile_planning_cot_v1",
    "data_augment": false,
    "max_dynamic_patch": 12,
    "repeat_time": 1,
    "length": "number of samples in the dataset"
  }
}
```

For more details, please refer to [Prepare Customized Data](https://github.com/OpenGVLab/OpenCUA/blob/main/agent-sft/internvl_chat/README.md#prepare-customized-data)

---

## 4. Training

To fine-tune with 8 GPUs, run:

```bash
bash scripts/sft_3b.sh \
    ../internvl_chat/data/internvl_meta/meta/mobile_meta_250908_1.json \ # training data
    work_dirs/Qwen2.5-VL-3B-SFT-exp1 \ # output dir
    pretrained/Qwen2.5-VL-3B-Instruct # finetune the model based on this pretrained model
```

---

## 5. References

```bibtex
@article{liu2025scalecua,
  title = {ScaleCUA: Scaling Open-Source Computer Use Agents with Cross-Platform Data},
  author = {Liu, Zhaoyang and Xie, Jingjing and Ding, Zichen and Li, Zehao and Yang, Bowen and Wu, Zhenyu and Wang, Xuehui and Sun, Qiushi and Liu, Shi and Wang, Weiyun and Ye, Shenglong and Li, Qingyun and Dong, Xuan and Yu, Yue and Lu, Chenyu and Mo, YunXiang and Yan, Yao and Tian, Zeyue and Zhang, Xiao and Huang, Yuan and Liu, Yiqian and Su, Weijie and Luo, Gen and Yue, Xiangyu and Qi, Biqing and Chen, Kai and Zhou, Bowen and Qiao, Yu and Chen, Qifeng and Wang, Wenhai},
  year = {2025},
  url = {https://github.com/OpenGVLab/ScaleCUA}
}
```
