import subprocess
from pathlib import Path
from utils.logger import ProjectLogger
import shutil

# Container name and script directory
# container_name = "evalkit_macos"
script_dir = Path(__file__).resolve().parent.parent
DOCKER_RUN_SCRIPT_PATH = script_dir / "docker" / "start_container_wsl.sh"  # Startup script for new container
image_src = script_dir.parent / "system_image" / "mac_hdd_ng.img"  # Original .img file
# image_copy = script_dir.parent.parent / "system_image" / "mac_hdd_ng_copy.img"  # New copied .img file

# Logger setup
logger = ProjectLogger(log_dir=script_dir / "logs")

# Function to check if the container exists
def container_exists(name):
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        stdout=subprocess.PIPE, text=True
    )
    return name in result.stdout.splitlines()

# Function to check if the container is running
def container_running(name):
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        stdout=subprocess.PIPE, text=True
    )
    return name in result.stdout.splitlines()

def docker_run_container(container_name, platform="wsl", docker_name="evalkit_macos_auto", port=50922):
    run_script_path = script_dir / "docker" / f"start_container_{platform}.sh"

    if container_exists(container_name):
        logger.info(f"Container '{container_name}' already exists. Skipping creation.")
    else:
        logger.info(f"Creating new container using script '{run_script_path.name}'.")
        subprocess.run([
            "bash",
            str(run_script_path),
            docker_name,
            str(port)
        ], check=True)

def docker_reset_container(container_name, image_src=image_src):
    # Abort 
    
    # if not container_exists(container_name):
    #     logger.error(f"Container '{container_name}' does not exist.")
    #     raise RuntimeError("Cannot reset non-existent container.")

    # if not image_src.exists():
    #     logger.error(f"Image file not found: {image_src}")
    #     raise FileNotFoundError(f"Missing system image file: {image_src}")

    # if container_running(container_name):
    #     logger.info(f"Stopping running container: {container_name}")
    #     subprocess.run(["docker", "stop", container_name], check=True)

    # logger.info(f"Copying image to container: {image_src} -> {container_name}:/home/arch/OSX-KVM/mac_hdd_ng.img")
    # subprocess.run([
    #     "docker", "cp",
    #     f"{image_src}",
    #     f"{container_name}:/home/arch/OSX-KVM/mac_hdd_ng.img"
    # ], check=True)
    pass

    # logger.info(f"Starting container: {container_name}")
    # subprocess.run(["docker", "start", container_name], check=True)
    
def docker_start_container(container_name):
    logger.info(f"Starting container: {container_name}")
    subprocess.run(["docker", "start", container_name], check=True)
    
def docker_stop_container(container_name):
    logger.info(f"Stopping container: {container_name}")
    subprocess.run(["docker", "stop", container_name], check=True)
    
def docker_remove_container(container_name):
    if container_exists(container_name):
        if container_running(container_name):
            logger.info(f"Stopping container before removal: {container_name}")
            subprocess.run(["docker", "stop", container_name], check=True)
        logger.info(f"Removing container: {container_name}")
        subprocess.run(["docker", "rm", container_name], check=True)
    else:
        logger.info(f"Container '{container_name}' does not exist. Nothing to remove.")

# # Main execution flow
# if __name__ == "__main__":
#     # Check if the source .img file exists
#     if not image_src.exists():
#         logger.error(f".img file not found at: {image_src}")
#         raise FileNotFoundError(f"Missing system image file: {image_src}")

#     # If the copy of the .img file exists, remove it
#     if image_copy.exists():
#         logger.info(f"Removing old copy of the .img file: {image_copy}")
#         image_copy.unlink()  # Remove the existing copy

#     # Copy the source .img to a new copy
#     logger.info(f"Creating a copy of the .img file: {image_copy}")
#     shutil.copy(image_src, image_copy)  # Create a copy of the image file

#     # If the container already exists
#     if container_exists(container_name):
#         logger.info(f"Container '{container_name}' exists.")

#         # If the container is running, stop it
#         if container_running(container_name):
#             logger.info(f"Stopping running container: {container_name}")
#             subprocess.run(["docker", "stop", container_name], check=True)

#         # Replace the image inside the container with the new copied image
#         logger.info(f"Copying the .img file to the container: {image_copy}")
#         subprocess.run([
#             "docker", "cp",
#             str(image_copy),
#             f"{container_name}:/home/arch/OSX-KVM/mac_hdd_ng.img"
#         ], check=True)

#         # Start the container
#         logger.info(f"Starting container: {container_name}")
#         subprocess.run(["docker", "start", container_name], check=True)

#     else:
#         logger.info(f"No existing container found. Creating new one with startup script.")
#         # If no existing container, create and start a new container using the startup script
#         subprocess.run(["bash", str(sh_script)], check=True)
