#!/bin/bash

MODEL_NAME="OpenGVLab/ScaleCUA-3B"
LOCAL_PATH="/mnt/petrelfs/yangbowen/yangbowen/ScaleCUADemo/models"
TP=1

echo "Downloading model ${MODEL_NAME} to ${LOCAL_PATH}..."
mkdir -p "${LOCAL_PATH}"
huggingface-cli download "${MODEL_NAME}" --local-dir "${LOCAL_PATH}" --local-dir-use-symlinks False

if [ $? -eq 0 ]; then
    echo "Model downloaded successfully to ${LOCAL_PATH}"
else
    echo "Failed to download model. Exiting."
    exit 1
fi

echo "Starting VLLM server with the downloaded model..."
python -m vllm.entrypoints.openai.api_server \
        --served-model-name scalecua \
        --limit-mm-per-prompt "image=5" \
        --tensor-parallel-size "${TP}" \
        --port 8000 \
        --model "${LOCAL_PATH}"