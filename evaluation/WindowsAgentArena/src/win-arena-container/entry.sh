#!/bin/bash

# Fix for Azure ML Job not using the correct root path
cd /

echo "Starting WinArena..."

prepare_image=false
start_client=true
agent="navi"
model="gpt-4-vision-preview"
som_origin="oss"
a11y_backend="uia"
clean_results=false
worker_id="0"
num_workers="1"
result_dir="./results"
json_name="evaluation_examples_windows/test_all.json" 

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-image)
            prepare_image=$2
            shift 2
            ;;
        --start-client)
            start_client=$2
            shift 2
            ;;
        --agent)
            agent=$2
            shift 2
            ;;
        --model)
            model=$2
            shift 2
            ;;
        --som-origin)
            som_origin=$2
            shift 2
            ;;
        --a11y-backend)
            a11y_backend=$2
            shift 2
            ;;
        --clean-results)
            clean_results=$2
            shift 2
            ;;
        --worker-id)
            worker_id=$2
            shift 2
            ;;
        --num-workers)
            num_workers=$2
            shift 2
            ;;
        --result-dir)
            result_dir=$2
            shift 2
            ;;
        --json-name)
            json_name=$2
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --prepare-image <true/false>    Prepare an arena image (default: false)"
            echo "  --start-client <true/false>     Start the arena client process (default: true)"
            echo "  --agent <agent>                 The agent to use (default: navi)"
            echo "  --model <model>                 The model to use (default: gpt-4-vision-preview, available options are: gpt-4o-mini, gpt-4-vision-preview, gpt-4o, gpt-4-1106-vision-preview)"
            echo "  --som-origin <som_origin>       The SoM (Set-of-Mark) origin to use (default: oss, available options are: oss, a11y, mixed-oss)"
            echo "  --a11y-backend <a11y_backend>   The a11y accessibility backend to use (default: uia, available options are: uia, win32)"
            echo "  --clean-results <bool>          Clean the results directory before running the client (default: true)"
            echo "  --worker-id <id>                The worker ID"
            echo "  --num-workers <num>             The number of workers"
            echo "  --result-dir <dir>              The directory to store the results (default: ./results)"
            echo "  --json-name <name>              The name of the JSON file to use (default: test_all.json)"
            exit 0
            ;;
        *)
    esac
done

# # Starts the VM and blocks until the Windows Arena Server is ready
# echo "Starting VM..."
# ./entry_setup.sh
# echo "VM started, server ready"

if [ "$prepare_image" = "true" ]; then
    echo "Preparing Arena image by gracefully shutting down the Windows VM..."
    response=$(curl --write-out '%{http_code}' --silent --output /dev/null -X POST 20.20.20.21:5000/shutdown)

    if [ $response -eq 200 ]; then
        echo "Windows VM is shutting down..."
        sleep 180 # Wait for any updates to be saved, and for windows.boot to be created
    else
        echo "Failed to shut down the Windows VM. Exiting..."
    fi
else
    echo "Skipping image preparation..."
    # Start the client script
    if [ "$start_client" = "true" ]; then
        echo "Starting client..."
        ./start_client.sh --agent $agent --model $model --som-origin $som_origin --a11y-backend $a11y_backend --clean-results $clean_results --worker-id $worker_id --num-workers $num_workers --result-dir $result_dir --json-name $json_name
    else
        echo "Keeping container alive"
        while true; do
            sleep 60
        done
        echo "Exiting..."
    fi
fi

# Wait for any process to exit
wait -n

# Exit with the status of the process that exited first
exit $?