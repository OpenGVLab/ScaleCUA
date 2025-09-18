#!/bin/bash

docker_name=$1
host_port=$2

# Read image paths from environment variables or assign default fallback values
mac_hdd_img=${MACOS_ARENA_MAC_HDD_IMG_PATH:-"path/to/mac_hdd_ng_copy.img"}
base_system_img=${MACOS_ARENA_BASESYSTEM_IMG_PATH:-"path/to/BaseSystem.img"}

if [ -z "$docker_name" ] || [ -z "$host_port" ]; then
    echo "Usage: $0 <docker_name> <host_port>"
    exit 1
fi

sudo docker run -itd \
    --name "$docker_name" \
    --device /dev/kvm \
    -p "$host_port":10022 \
    -v /mnt/wslg/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -v "$mac_hdd_img:/home/arch/OSX-KVM/mac_hdd_ng_src.img" \
    -v "$base_system_img:/home/arch/OSX-KVM/BaseSystem_src.img" \
    -e CPU='Haswell-noTSX' \
    -e CPUID_FLAGS='kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on' \
    -e SHORTNAME=sonoma \
    -e USERNAME=pipiwu \
    -e PASSWORD='1234' \
    numbmelon/docker-osx-evalkit-auto:latest

# Note:
# Some tasks require internet connectivity inside the Docker container.
# Make sure the container has proper network access. If necessary, you can
# inject proxy settings using `-e` options during container startup.
# For example:
#   -e http_proxy="http://<proxy_host>:<proxy_port>" \
#   -e https_proxy="http://<proxy_host>:<proxy_port>" \
#   -e HTTP_PROXY="http://<proxy_host>:<proxy_port>" \
#   -e HTTPS_PROXY="http://<proxy_host>:<proxy_port>" \