#!/bin/bash

# ================================
# Required Environment Variables
# ================================

# Path to system image files used by the container
export MACOS_ARENA_MAC_HDD_IMG_PATH="/absolute/path/to/mac_hdd_ng_src.img"
export MACOS_ARENA_BASESYSTEM_IMG_PATH="/absolute/path/to/BaseSystem_src.img"

# OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# ================================
# Configurable constants
# ================================

WORK_DIR="path/to/MacOSArena" # Change to your local path
CONFIG_FILE="config/default_config_linux.yaml"  # For Linux
# CONFIG_FILE="config/default_config.yaml"      # For WSL

# ================================
# Preparation
# ================================

cd "${WORK_DIR}" || exit 1
mkdir -p results/example_run

# ================================
# Run evaluation
# ================================

python -m single_run --config_file "${CONFIG_FILE}"
