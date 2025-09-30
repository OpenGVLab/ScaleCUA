#!/bin/bash

MODEL_NAME="OpenGVLab/ScaleCUA-3B"
LOCAL_PATH="./ScaleCUA-3B"
TP=1

echo "Downloading model ${MODEL_NAME} to ${LOCAL_PATH}..."
mkdir -p "${LOCAL_PATH}"
# export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download "${MODEL_NAME}" --repo-type model --local-dir-use-symlinks False --local-dir "${LOCAL_PATH}" 

if [ $? -eq 0 ]; then
    echo "Model downloaded successfully to ${LOCAL_PATH}"
else
    echo "Failed to download model. Exiting."
    exit 1
fi

echo "Starting VLLM server with the downloaded model..."
python -m vllm.entrypoints.openai.api_server \
        --served-model-name ScaleCUA-3B \
        --limit-mm-per-prompt "image=7" \
        --tensor-parallel-size $TP \
        --port 10024 \
        --model "${LOCAL_PATH}" \
        --mm-processor-kwargs '{"min_pixels": 3136, "max_pixels": 3750656}'