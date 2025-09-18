# If a proxy is needed for GPT API during evaluation, configure this parameter
export HTTP_PROXY=""
export HTTPS_PROXY=""
export NO_PROXY="localhost,127.0.0.1"

# Your OPENAI_API_KEY and OPENAI_BASE_URL
export OPENAI_API_KEY="xxx"
export OPENAI_BASE_URL="xxx"

python single_agent_run.py \
    --platform web \
    --env_config_path config/envs/web.yaml \
    --agent_config_path config/agent/scalecua_native_agent.yaml \
    --task_config_path tasks/ \
    --num_workers 8 \
    --exp_name test_0721_1 \
    --max_steps 15
