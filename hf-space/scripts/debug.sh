#!/bin/bash

echo "Starting VLLM server with the downloaded model..."
srun -p Intern6 --job-name=scalecua \
    --gres=gpu:4 --ntasks=1 \
    --ntasks-per-node=1 --cpus-per-task=12 \
    --kill-on-bad-exit=1 --quotatype=reserved \
    --time 365-00:00 \
    python -m vllm.entrypoints.openai.api_server \
    --served-model-name scalecua \
    --limit-mm-per-prompt "image=5" \
    --tensor-parallel-size 4 \
    --port 8000 \
    --model /mnt/hwfile/share_data/liuzhaoyang/gui/work_dirs/qwen2_5_vl/merged_qwen2_5_vl_32b_ckpt6000_ckpt8400_ckpt8800_model