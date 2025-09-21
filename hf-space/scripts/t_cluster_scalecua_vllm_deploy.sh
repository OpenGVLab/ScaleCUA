#!/bin/bash

MODEL_NAME="OpenGVLab/ScaleCUA-3B"
LOCAL_PATH="/mnt/petrelfs/yangbowen/yangbowen/ScaleCUADemo/models"

export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DOWNLOAD_TIMEOUT=500
export HF_HUB_ETAG_TIMEOUT=500
echo "Downloading model ${MODEL_NAME} to ${LOCAL_PATH}..."
mkdir -p "${LOCAL_PATH}"
huggingface-cli download "${MODEL_NAME}" --local-dir "${LOCAL_PATH}" --local-dir-use-symlinks False --max-workers 50 --resume-download --force-download

if [ $? -eq 0 ]; then
    echo "Model downloaded successfully to ${LOCAL_PATH}"
else
    echo "Failed to download model. Exiting."
    exit 1
fi

echo "Starting VLLM server with the downloaded model..."
srun -p Intern6 --job-name=scalecua \
    --gres=gpu:1 --ntasks=1 \
    --ntasks-per-node=1 --cpus-per-task=12 \
    --kill-on-bad-exit=1 --quotatype=reserved \
    --time 365-00:00 \
    python -m vllm.entrypoints.openai.api_server \
    --served-model-name scalecua \
    --limit-mm-per-prompt "image=5" \
    --tensor-parallel-size 1 \
    --port 8000 \
    --model "${LOCAL_PATH}"