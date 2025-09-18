#!/bin/bash

# ================================
# Required Environment Variables
# ================================

# Path to system image files used by the container
export MACOS_ARENA_MAC_HDD_IMG_PATH="/absolute/path/to/mac_hdd_ng_src.img"
export MACOS_ARENA_BASESYSTEM_IMG_PATH="/absolute/path/to/BaseSystem_src.img"

# Optional: export keys for GPT-based models if used
# export OPENAI_API_KEY="your-api-key-here"
# export ANTHROPIC_API_KEY="your-api-key-here"

# ================================
# Configurable constants
# ================================

WORK_DIR="path/to/MacOSArena"  # Change to your local path

# DOMAINS: Task domain to evaluate.
#          Use "single_app" to test all single-app tasks,
#          or "multi_app" to test all cross-app tasks.
DOMAINS=("multi_app")

# MODELS: List of agent model names to evaluate.
#         Use ("none") for planner + grounder agent (requires PLANNER_EXECUTOR_MODEL).
MODELS=("opencua-3b")


# MODEL_TYPE_LIST: Explicit model types matching MODELS
MODEL_TYPE_LIST=("opencua")

# URL_LIST: Model API URLs for each agent in MODELS (same order).
URL_LIST=("http://localhost:8000")

# PLANNER_EXECUTOR_MODEL: List of (planner, executor) pairs. Used if MODELS=("none")
# EXEC_MODEL_URL_LIST: URL list for each executor
PLANNER_EXECUTOR_MODEL=()
EXEC_MODEL_URL_LIST=()

# MODEL_SUB_DIR: Subdirectory under RESULT_ROOT/{model_name}/ to store logs of this evaluation run.
MODEL_SUB_DIR="multi_task"

# CONFIG_FILE: Path to YAML configuration file
CONFIG_FILE="config/default_config_linux.yaml"  # For Linux
# CONFIG_FILE="config/default_config.yaml"      # For WSL

# RESULT_ROOT: Root directory to store all agent evaluation outputs
RESULT_ROOT="${WORK_DIR}/results"

# ================================
# Preparation
# ================================

cd "${WORK_DIR}" || exit 1
mkdir -p "${RESULT_ROOT}"

# ================================
# Run evaluation
# ================================

# ⚠️ NOTE:
# This command requires `sudo` because the evaluation will remove and start Docker containers before each task.
# Make sure that the `python` used under sudo is still the one from your conda environment.
# You can check it via `sudo which python`, and replace `python` with the absolute path if needed.
# (i.e., the result of `which python` in your activated conda environment).

sudo python -m batch_run \
  --domains "${DOMAINS[@]}" \
  --models "${MODELS[@]}" \
  --url_list "${URL_LIST[@]}" \
  --model_type_list "${MODEL_TYPE_LIST[@]}" \
  --planner_executor_model "${PLANNER_EXECUTOR_MODEL[@]}" \
  --exec_model_url_list "${EXEC_MODEL_URL_LIST[@]}" \
  --model_sub_dir "${MODEL_SUB_DIR}" \
  --config_file "${CONFIG_FILE}" \
  --result_root "${RESULT_ROOT}"