#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

source ./shared.sh

mode=azure
build_base_image=false

# Default proxy URL
PROXY_URL="http://your-proxy-url:port" # Your proxy URL here

# Parse the command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            mode=$2
            shift 2
            ;;
        --build-base-image)
            build_base_image=$2
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --mode <dev/azure> : Mode (default: azure)"
            echo "  --build-base-image <true/false> : Whether to build the winarena-base image (default: false)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "$SCRIPT_DIR/../"

if [ "$build_base_image" = true ]; then
  echo "Building winarena-base image"
  docker build \
    --build-arg HTTP_PROXY="$PROXY_URL" \
    --build-arg HTTPS_PROXY="$PROXY_URL" \
    --build-arg PROFILE_MODE=false \
    -f $SCRIPT_DIR/../src/win-arena-container/Dockerfile-WinArena-Base \
    -t winarena-base:latest $SCRIPT_DIR/../
  docker tag winarena-base:latest windowsarena/winarena-base:latest
else
  echo "Skipping winarena-base image build"
fi

if [ "$mode" = "dev" ]; then # Only for dev mode
  winarena_image_name="winarena-$mode"
else
  winarena_image_name="winarena"
fi

docker build \
  --build-arg HTTP_PROXY="$PROXY_URL" \
  --build-arg HTTPS_PROXY="$PROXY_URL" \
  --build-arg DEPLOY_MODE=$mode \
  -f $SCRIPT_DIR/../src/win-arena-container/Dockerfile-WinArena \
  -t $winarena_image_name:latest $SCRIPT_DIR/../

docker tag $winarena_image_name:latest windowsarena/$winarena_image_name:latest