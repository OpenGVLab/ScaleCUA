#!/bin/bash

cleanup() {
  pkill -P $$
}
# 捕获常见终止信号
for sig in INT QUIT HUP TERM; do
  trap "cleanup; trap - \$sig EXIT; kill -s \$sig \"$$\"" "$sig"
done
trap cleanup EXIT

export TRITON_CACHE_DIR="/tmp/triton/"

pkill -f python
datasets=${1:-"../internvl_chat/data/train_data.json"}
output_dir=${2:-"work_dirs/Qwen2.5-VL-7B-SFT-exp1"}
pretrained=${3:-"Qwen/Qwen2.5-VL-7B-Instruct"}
max_pixels=${4:-2109744}
# echo "pretrained: $pretrained"
# exit 0
mkdir -p output_dir
sleep $(echo "scale=3; 0.0 + $RANDOM/32767 * 1.5" | bc)
HOSTNAMES=$(scontrol show hostnames "$SLURM_JOB_NODELIST")
# NNODES=$(printf "$HOSTNAMES" | echo -e)
NNODES=$(wc -l <<< "$(echo -e "$HOSTNAMES")")
# NNODES=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | wc -l)
MASTER_PORT=${MASTER_PORT:-31518}
export MASTER_ADDR=$(head -n 1 <<< "$(echo -e "$HOSTNAMES")")
THEID=$(echo -e $HOSTNAMES | python3 -c "import sys;[sys.stdout.write(str(i)) for i,line in enumerate(next(sys.stdin).split(' ')) if line.strip() == '$(hostname)'.strip()]")
# NPROC_PER_NODE=8
sleep $(echo "scale=3; 0.0 + $RANDOM/32767 * 1.5" | bc)
NPROC_PER_NODE=$(scontrol show job $SLURM_JOB_ID | grep -oP 'TresPerNode=gpu:\K\d+')
# export MASTER_ADDR=$(echo $HOSTNAMES | head -n 1)

# DeepSpeed configuration
deepspeed=./scripts/zero3.json

# Training hyperparameters
lr=1e-5
batch_size=2
grad_accum_steps=$(( NNODES <= 8 ? 4 : (NNODES <= 16 ? 2 : 1) ))

# Training entry point
entry_file=qwenvl/train/train_qwen.py

# Output configuration
run_name="qwen2.5vl-7b-baseline"

echo SLURM_JOB_ID=$SLURM_JOB_ID, NNODES=$NNODES, NPROC_PER_NODE=$NPROC_PER_NODE, MASTER_ADDR=$MASTER_ADDR, MASTER_PORT=$MASTER_PORT

# export CUDA_LAUNCH_BLOCKING=1
# Training arguments
args="
    --deepspeed ${deepspeed} \
    --model_name_or_path "${pretrained}" \
    --meta_path ${datasets} \
    --data_flatten True \
    --group_sampling True \
    --tune_mm_vision False \
    --tune_mm_mlp True \
    --tune_mm_llm True \
    --bf16 \
    --coord_norm False \
    --output_dir ${output_dir} \
    --num_train_epochs 2 \
    --per_device_train_batch_size ${batch_size} \
    --per_device_eval_batch_size $((batch_size*2)) \
    --gradient_accumulation_steps ${grad_accum_steps} \
    --eval_strategy "no" \
    --save_strategy "steps" \
    --save_steps 500 \
    --save_total_limit 3 \
    --learning_rate ${lr} \
    --weight_decay 0 \
    --warmup_ratio 0.03 \
    --max_grad_norm 1 \
    --lr_scheduler_type "cosine" \
    --logging_steps 1 \
    --model_max_length 30720 \
    --gradient_checkpointing True \
    --dataloader_num_workers 2 \
    --run_name ${run_name} \
    --report_to none"

# Launch training
torchrun --nproc_per_node=${NPROC_PER_NODE} \
         --master_addr=${MASTER_ADDR} \
         --master_port=${MASTER_PORT} \
         --node_rank ${THEID} \
         --nnodes ${NNODES} \
         ${entry_file} ${args} \
         2>&1 | tee -a "${output_dir}/training_log_truc.txt"
