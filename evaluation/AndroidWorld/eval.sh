#!/usr/bin/env bash

# eval.sh: Launch the Android emulator agent with configurable parameters.
# Note: Make sure to configure the corresponding agent parameters
#       in run.py's _get_agent() method before running.
#
# Usage:
#   ./eval.sh [AGENT_NAME] [CONSOLE_PORT] [CHECKPOINT_DIR] [GRPC_PORT]
#
#   AGENT_NAME:     Name of the agent (default: qwenvl)
#   CONSOLE_PORT:   Emulator console port (default: 5554)
#   CHECKPOINT_DIR: Directory for model checkpoints (default: gui_v123)
#   GRPC_PORT:      gRPC server port (default: 8554)

# --- Configurable variables ---
AGENT_NAME="${1:-qwenvl}"
CONSOLE_PORT="${2:-5554}"
CHECKPOINT_DIR="${3:-test}"
GRPC_PORT="${4:-8554}"

# Run the emulator agent
echo "Starting emulator agent '${AGENT_NAME}'"
python run.py \
  --perform_emulator_setup=true \
  --agent_name "${AGENT_NAME}" \
  --console_port "${CONSOLE_PORT}" \
  --checkpoint_dir "${CHECKPOINT_DIR}" \
  --grpc_port "${GRPC_PORT}"
