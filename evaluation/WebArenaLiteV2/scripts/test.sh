export HTTP_PROXY=""
export HTTPS_PROXY=""
export NO_PROXY=""
export OPENAI_API_KEY=""
export OPENAI_BASE_URL=""

python agent_run.py \
    --platform web \
    --env_config_path config/env/web.yaml \
    --agent_config_path config/agent/scalecua_native_agent.yaml \
    --task_config_path test/ \
    --num_workers 8 \
    --exp_name test_0721_1 \
    --max_steps 15
