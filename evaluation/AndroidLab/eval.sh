#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./eval.sh [NAME] [PARALLEL] [CONFIG] [TASK_IDS] [JUDGE_MODEL] [API_BASE] [API_KEY]
#   NAME        : experiment name (default: InternVL)
#   PARALLEL    : number of parallel processes (default: 8)
#   CONFIG      : path to config.yaml (default: config.yaml)
#   TASK_IDS    : comma-separated task ids (optional, e.g. taskid_1,taskid_3)
#   JUDGE_MODEL : judge LLM name (optional, default: gpt-4o-2024-05-13)
#   API_BASE    : judge API base url (optional, default: https://api.openai.com/v1)
#   API_KEY     : judge API key (optional, default: empty -> use env var OPENAI_API_KEY)

NAME="${1:-InternVL}"
PARALLEL="${2:-8}"
CONFIG="${3:-config.yaml}"
TASK_IDS="${4:-}"

JUDGE_MODEL="${5:-gpt-4o-2024-05-13}"
API_BASE="${6:-https://api.openai.com/v1}"
API_KEY="${7:-${OPENAI_API_KEY:-}}"

# ---- Paths (edit as needed) ----
BASE_LOG_DIR="/home/lizehao/Android-Lab_primary/logs/evaluation"   # MUST match log.base_log_dir in config.yaml
INPUT_FOLDER="${BASE_LOG_DIR}/"
OUTPUT_BASE="${BASE_LOG_DIR}/${NAME}_result"
OUTPUT_FOLDER="${OUTPUT_BASE}/result"
OUTPUT_EXCEL="${OUTPUT_BASE}/${NAME}_result.xlsx"

# ---- Scripts ----
EVAL_SCRIPT="eval.py"
RESULT_SCRIPT="generate_result.py"

mkdir -p "${OUTPUT_FOLDER}"

echo "========== Evaluation =========="
echo "NAME        = ${NAME}"
echo "PARALLEL    = ${PARALLEL}"
echo "CONFIG      = ${CONFIG}"
echo "TASK_IDS    = ${TASK_IDS:-<ALL>}"
echo "BASE_LOG_DIR= ${BASE_LOG_DIR}"
echo "--------------------------------"

CMD="python ${EVAL_SCRIPT} -n ${NAME} -p ${PARALLEL} -c ${CONFIG}"
[[ -n "${TASK_IDS}" ]] && CMD+=" --task_id ${TASK_IDS}"

echo "Running: ${CMD}"
eval "${CMD}"

echo "========== Generate Result =========="

JUDGE_ARGS="--judge_model ${JUDGE_MODEL} --api_base ${API_BASE}"
[[ -n "${API_KEY}" ]] && JUDGE_ARGS+=" --api_key ${API_KEY}"

python "${RESULT_SCRIPT}" \
  --input_folder "${INPUT_FOLDER}" \
  --output_folder "${OUTPUT_FOLDER}" \
  --output_excel "${OUTPUT_EXCEL}" \
  ${JUDGE_ARGS}

echo "Done. Excel saved to: ${OUTPUT_EXCEL}"
