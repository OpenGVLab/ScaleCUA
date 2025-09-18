#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

source ./shared.sh

# Default parameters
mode="azure"
prepare_image=false
skip_build=false
interactive=false
connect=false
use_kvm=true
ram_size=8G
cpu_cores=8
mount_vm_storage=true
mount_client=true
mount_server=true
mount_storage=true
container_name="winarena"
browser_port=8006
rdp_port=3390
start_client=true
agent="navi"
model="gpt-4-vision-preview"
som_origin="oss"
a11y_backend="uia"
gpu_enabled=false
OPENAI_API_KEY=""
AZURE_API_KEY=""
AZURE_ENDPOINT=""
vm_storage_dir=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --container-name) container_name="$2"; shift 2 ;;
        --prepare-image) prepare_image=$2; shift 2 ;;
        --skip-build) skip_build=$2; shift 2 ;;
        --interactive) interactive=$2; shift 2 ;;
        --connect) connect=$2; shift 2 ;;
        --use-kvm) use_kvm=$2; shift 2 ;;
        --ram-size) ram_size=$2; shift 2 ;;
        --cpu-cores) cpu_cores=$2; shift 2 ;;
        --mount-vm-storage) mount_vm_storage=$2; shift 2 ;;
        --mount-client) mount_client=$2; shift 2 ;;
        --mount-server) mount_server=$2; shift 2 ;;
        --browser-port) browser_port="$2"; shift 2 ;;
        --rdp-port) rdp_port="$2"; shift 2 ;;
        --start-client) start_client=$2; shift 2 ;;
        --agent) agent=$2; shift 2 ;;
        --model) model=$2; shift 2 ;;
        --som-origin) som_origin=$2; shift 2 ;;
        --a11y-backend) a11y_backend=$2; shift 2 ;;
        --gpu-enabled) gpu_enabled=$2; shift 2 ;;
        --openai-api-key) OPENAI_API_KEY="$2"; shift 2 ;;
        --azure-api-key) AZURE_API_KEY="$2"; shift 2 ;;
        --azure-endpoint) AZURE_ENDPOINT="$2"; shift 2 ;;
        --mode) mode=$2; shift 2 ;;
        --vm-storage-dir) vm_storage_dir="$2"; shift 2 ;;
        --help)
            echo "Usage: $0 [options]"
            echo "  --vm-storage-dir <dir> : Path to custom VM storage (e.g. src/.../storage_instance1)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            log_error_exit "Unknown option: $1"
            ;;
    esac
done

# Determine image name
winarena_image_name="winarena"
[[ "$mode" = "dev" ]] && winarena_image_name="winarena-$mode"
winarena_full_image_name="windowsarena/$winarena_image_name"
winarena_image_tag="latest"

# Check Docker status
if ! docker info >/dev/null 2>&1; then
    log_error_exit "Docker daemon is not running. Please start Docker and try again."
fi

# Validate image
if ! docker images | grep -q -e $winarena_full_image_name; then
    echo "Docker image $winarena_full_image_name not found."
    [[ "$skip_build" = true ]] && log_error_exit "Image missing and skip_build=true. Build it or pull it."
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

# Paths
vm_setup_image_path=$(getrealpath "$SCRIPT_DIR/../src/win-arena-container/vm/image")
server_mount_path=$(getrealpath "$SCRIPT_DIR/../src/win-arena-container/vm/setup")
client_mount_path=$(getrealpath "$SCRIPT_DIR/../src/win-arena-container/client")
storage_mount_path=$(getrealpath "$SCRIPT_DIR/../src/win-arena-container/vm/storage")


# Determine VM storage path
if [[ -z "$vm_storage_dir" ]]; then
    vm_storage_mount_path=$(getrealpath "$SCRIPT_DIR/../src/win-arena-container/vm/storage")
else
    vm_storage_mount_path=$(getrealpath "$vm_storage_dir")
fi

echo "Using VM Setup Image path: $vm_setup_image_path"
echo "Using VM storage mount path: $vm_storage_mount_path"
echo "Using server mount path: $server_mount_path"
echo "Using client mount path: $client_mount_path"

[[ ! -e /dev/kvm ]] && use_kvm=false && echo "/dev/kvm not found. Disabling KVM."

if [[ -z "$OPENAI_API_KEY" && (-z "$AZURE_API_KEY" || -z "$AZURE_ENDPOINT") ]]; then
    log_error_exit "Missing API keys."
fi

build_container_image() {
    echo "Building container image..."
    source "$SCRIPT_DIR/build-container-image.sh" --mode $mode
}

invoke_docker_container() {
    docker_command="docker run"

    [[ -t 1 ]] && docker_command+=" -it"
    docker_command+=" --rm"
    docker_command+=" -p ${browser_port}:8006 -p ${rdp_port}:3389"
    docker_command+=" --name $container_name"
    docker_command+=" --platform linux/amd64 --privileged"
    [[ "$use_kvm" = true ]] && docker_command+=" --device=/dev/kvm" || docker_command+=" -e KVM=N"
    docker_command+=" -e RAM_SIZE=$ram_size -e CPU_CORES=$cpu_cores"

    [[ "$prepare_image" = true ]] && docker_command+=" --mount type=bind,source=${vm_setup_image_path}/setup.iso,target=/custom.iso"
    [[ "$mount_vm_storage" = true ]] && docker_command+=" -v ${vm_storage_mount_path}/.:/storage"
    [[ "$mount_server" = true ]] && docker_command+=" -v ${server_mount_path}/.:/shared"
    [[ "$mount_client" = true ]] && docker_command+=" -v ${client_mount_path}/.:/client"
    [[ "$mount_storage" = true ]] && docker_command+=" -v ${storage_mount_path}/.:/golden_storage"

    docker_command+=" --cap-add NET_ADMIN --stop-timeout 120 --entrypoint /bin/bash"

    [[ "$gpu_enabled" = true && $(command -v nvidia-smi) ]] && docker_command+=" --gpus all"
    [[ -n "$OPENAI_API_KEY" ]] && docker_command+=" -e OPENAI_API_KEY=$OPENAI_API_KEY"
    [[ -n "$AZURE_API_KEY" ]] && docker_command+=" -e AZURE_API_KEY=$AZURE_API_KEY"
    [[ -n "$AZURE_ENDPOINT" ]] && docker_command+=" -e AZURE_ENDPOINT=$AZURE_ENDPOINT"

    docker_command+=" $winarena_full_image_name:$winarena_image_tag"

    if [[ "$interactive" = true ]]; then
        docker_command+=""
    else
        docker_command+=" -c './entry.sh --prepare-image $prepare_image --start-client $start_client --agent $agent --model $model --som-origin $som_origin --a11y-backend $a11y_backend'"
    fi

    echo "Invoking Docker with:"
    echo "$docker_command"
    eval $docker_command
}

if [[ "$connect" = true ]]; then
    echo "Connecting to container $container_name..."
    docker_exec_command="docker exec"
    [[ -t 1 ]] && docker_exec_command+=" -it"
    docker_exec_command+=" $container_name /bin/bash"
    echo "Exec: $docker_exec_command"
    eval $docker_exec_command
    exit 0
fi

[[ "$skip_build" = false ]] && build_container_image

invoke_docker_container