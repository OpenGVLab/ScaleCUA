set -x
proxy_off

PARTITION=${PARTITION:-"Intern5"}
GPUS=${GPUS:-512}
GPUS_PER_NODE=${GPUS_PER_NODE:-8}
QUOTA_TYPE=${QUOTA_TYPE:-"reserved"}
NODES=$((GPUS / GPUS_PER_NODE))
CPUS_PER_TASK=${CPUS_PER_TASK:-10}
SRUN_ARGS=${SRUN_ARGS:-""}
META_PATH=${1:-"data/train_data.json"}
OUTPUT_DIR=${2:-"work_dirs/gui/exp1"}
PRETRAINED_MODEL=${3:-"OpenGVLab/InternVL3-8B"}

export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export MASTER_PORT=34229
export TF_CPP_MIN_LOG_LEVEL=3

if [ ! -d "$OUTPUT_DIR" ]; then
  mkdir -p "$OUTPUT_DIR"
fi

for ((i=0; i<1; i++))
do
  echo "Running iteration $i with NNODES=$NODES, META=$META_PATH, OUTPUT=$OUTPUT_DIR"
  srun -p ${PARTITION} \
    --gres=gpu:${GPUS_PER_NODE} \
    --nodes=${NODES} \
    --ntasks=${GPUS} \
    --ntasks-per-node=${GPUS_PER_NODE} \
    --cpus-per-task=${CPUS_PER_TASK} \
    --kill-on-bad-exit=1 \
    --quotatype=${QUOTA_TYPE} \
    ${SRUN_ARGS} \
    python -u internvl/train/internvl_chat_pretrain.py \
    --model_name_or_path $PRETRAINED_MODEL \
    --conv_style "internvl2_5" \
    --use_fast_tokenizer False \
    --output_dir ${OUTPUT_DIR} \
    --meta_path $META_PATH \
    --overwrite_output_dir True \
    --force_image_size 448 \
    --down_sample_ratio 0.5 \
    --drop_path_rate 0.1 \
    --min_num_frame 8 \
    --max_num_frame 32 \
    --freeze_llm False \
    --freeze_mlp False \
    --freeze_backbone True \
    --vision_select_layer -1 \
    --dataloader_num_workers 8 \
    --bf16 True \
    --max_steps 30000 \
    --per_device_train_batch_size 1 \
    --gradient_accumulation_steps 1 \
    --evaluation_strategy "no" \
    --save_strategy "steps" \
    --save_steps 1000 \
    --save_total_limit 4 \
    --learning_rate 4e-5 \
    --weight_decay 0.05 \
    --warmup_ratio 0.03 \
    --lr_scheduler_type "cosine" \
    --logging_steps 1 \
    --max_seq_length 20480 \
    --do_train True \
    --grad_checkpoint True \
    --group_by_length False \
    --dynamic_image_size True \
    --use_thumbnail True \
    --ps_version 'v2' \
    --deepspeed "zero_stage1_config.json" \
    --report_to "tensorboard" \
    --use_packed_ds True \
    --num_images_expected 48 \
    --max_packed_tokens 20480 \
    --max_buffer_size 20 \
    --log_freq 1000 \
    --strict_mode False \
    --replacement False \
    --allow_overflow False \
    --remove_unused_columns False \
    --loss_reduction "square" \
    --loss_reduction_all_gather True \
    2>&1 | tee -a "${OUTPUT_DIR}/training_log.txt"
done