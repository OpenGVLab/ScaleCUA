HOSTCONDA_DIR=$(conda info --base)
PYTHON="${CONDA_PREFIX}/bin/python"

# If a proxy is needed for GPT API during evaluation, configure this parameter
PROXY="10.1.8.5:23128"
NO_PROXY="localhost,127.0.0.1"

# Your OPENAI_API_KEY and OPENAI_BASE_URL
OPENAI_API_KEY="xxx"
OPENAI_BASE_URL="xxx"

docker run -it --rm \
    --name webarena_lite_v2_eval \
    --ipc=host \
    --net=host \
    -e HTTP_PROXY="${PROXY}" \
    -e HTTPS_PROXY="${PROXY}" \
    -e NO_PROXY="${NO_PROXY}" \
    -e PYTHON="${PYTHON}" \
    -v "${PWD}:${PWD}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
    -e OPENAI_BASE_URL="${OPENAI_BASE_URL}" \
    -v "${HOSTCONDA_DIR}:${HOSTCONDA_DIR}" \
    -w "${PWD}" \
    mcr.microsoft.com/playwright/python:v1.50.0-jammy \
    bash -c '
        ${PYTHON} single_agent_run.py \
          --platform web \
          --env_config_path config/envs/web.yaml \
          --agent_config_path config/agent/scalecua_native_agent.yaml \
          --task_config_path tasks/ \
          --num_workers 8 \
          --exp_name test_0721_1 \
          --max_steps 15
    '
