RESULT_DIR=$1
NUM_ENVS=$2

mkdir -p ${RESULT_DIR}

python run_multienv_cua.py \
    --path_to_vm docker_vm_data/Ubuntu.qcow2 \
    --headless \
    --action_space pyautogui \
    --observation_type screenshot \
    --screen_width 1920 \
    --screen_height 1080 \
    --sleep_after_execution 2.0 \
    --max_steps 50 \
    --max_trajectory_length 100 \
    --temperature 0.0 \
    --top_p 0.9 \
    --max_tokens 1000 \
    --result_dir ${RESULT_DIR} \
    --num_envs ${NUM_ENVS} \
    --model scalecua \
    --url_set http://10.140.66.46:10029/v1,http://10.140.66.27:10025/v1 \
    2>&1 | tee -a ${RESULT_DIR}/run.log

