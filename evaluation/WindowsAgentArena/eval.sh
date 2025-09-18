#!/bin/bash

# ==============================================================================
# Interactively Run a SCALECUA WinArena Docker Container
# ==============================================================================
# This script presents a menu to the user to choose which container instance
# to launch. It then prompts for the agent type before running the command.
# ==============================================================================

# --- Configuration ---
# Array of model names. This allows for different models per instance.
MODELS=("your_model")

# --- Main Menu ---
PS3="Please enter your choice: "
options=(
    "Run Instance 1"
    "Run Instance 2"
    "Run Instance 3"
    "Run Instance 4"
    "Quit"
)

select opt in "${options[@]}"
do
    case $opt in
        "Run Instance 1" | "Run Instance 2" | "Run Instance 3" | "Run Instance 4")
            # --- Get Instance Details ---
            INSTANCE_ID=$(echo "$opt" | grep -o '[0-9]*')
            BROWSER_PORT=$((8004 + INSTANCE_ID))
            RDP_PORT=$((3388 + INSTANCE_ID))
            MODEL_NAME=${MODELS[$((INSTANCE_ID-1))]}

            # --- Prompt for Agent Type (New Feature) ---
            # Ask the user to input the agent type.
            # -p specifies the prompt string.
            # -r prevents backslashes from being interpreted.
            # -i 'SCALECUA' sets the default value shown in the prompt (requires Bash 4+).
            # For compatibility with older Bash, we'll use a simpler prompt and check if the variable is empty.
            read -p "Enter agent type [default: SCALECUA]: " AGENT_TYPE
            
            # If the user just pressed Enter, set AGENT_TYPE to the default value.
            if [ -z "$AGENT_TYPE" ]; then
                AGENT_TYPE="SCALECUA"
            fi

            # --- Confirmation and Execution ---
            echo "==> Preparing to start Instance #${INSTANCE_ID}..."
            echo "  Container Name: winarena${INSTANCE_ID}"
            echo "  VM Storage Dir: src/win-arena-container/vm/storage_instance${INSTANCE_ID}"
            echo "  Browser Port:   ${BROWSER_PORT}"
            echo "  RDP Port:       ${RDP_PORT}"
            echo "  Agent:          ${AGENT_TYPE}" # Display the chosen agent
            echo "  Model:          ${MODEL_NAME}"
            echo "---------------------------------"

            # Execute the run command with the specified agent type.
            bash scripts/run-local.sh \
              --container-name "winarena${INSTANCE_ID}" \
              --vm-storage-dir "src/win-arena-container/vm/storage_instance${INSTANCE_ID}" \
              --browser-port "${BROWSER_PORT}" \
              --rdp-port "${RDP_PORT}" \
              --agent "${AGENT_TYPE}" \
              --model "${MODEL_NAME}"
            
            break
            ;;
        "Quit")
            echo "Exiting."
            break
            ;;
        *) 
            echo "Invalid option. Please try again."
            ;;
    esac
done