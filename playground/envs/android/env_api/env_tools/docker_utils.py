import json
import subprocess
import time

import requests


def run_docker_command(command):
    full_command = f"{command}"
    result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def create_docker_container(docker_image_name, docker_port, docker_local_port):
    command = f"docker run -itd --privileged  -p {docker_local_port}:{docker_port} {docker_image_name}"
    returncode, stdout, stderr = run_docker_command(command)
    time.sleep(10)
    if returncode == 0:
        container_id = stdout.strip()
        # TODO: add to final docker
        command = f"docker cp adb_client.py {container_id}:/"
        returncode, stdout, stderr = run_docker_command(command)
        return container_id
    else:
        print(returncode, stdout, stderr)
        raise Exception(f"Error creating container: {stderr}")


def execute_command_in_container(container_id, command):
    full_command = f'docker exec -d {container_id} /bin/bash -c "{command}"'
    returncode, stdout, stderr = run_docker_command(full_command)
    if returncode == 0:
        return stdout
    else:
        print(returncode, stdout, stderr)
        raise Exception(f"Error executing command: {stderr}")


def remove_docker_container(container_id):
    stop_command = f"docker stop {container_id}"
    remove_command = f"docker rm {container_id}"

    run_docker_command(stop_command)
    returncode, stdout, stderr = run_docker_command(remove_command)
    if returncode == 0:
        return f"Container {container_id} has been removed."
    else:
        raise Exception(f"Error removing container: {stderr}")


def cp_docker(local_path, docker_path, container_id, local_to_docker=True):
    if local_to_docker:
        command = f"docker cp {local_path} {container_id}:{docker_path}"
        returncode, stdout, stderr = run_docker_command(command)
        if returncode == 0:
            return stdout
        else:
            print(returncode, stdout, stderr)
            raise Exception(f"Error copying file: {stderr}")
    else:
        command = f"docker cp {container_id}:{docker_path} {local_path}"
        returncode, stdout, stderr = run_docker_command(command)
        if returncode == 0:
            return stdout
        else:
            print(returncode, stdout, stderr)
            raise Exception(f"Error copying file: {stderr}")


def send_post_request(
    url, headers, data, max_attempts=10, retry_interval=3, timeout=6000
):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = requests.post(
                url, headers=headers, data=json.dumps(data), timeout=timeout
            )
            return response.json()
        except Exception as e:
            print(f"Error occurred: {e}")
            attempts += 1
            if attempts < max_attempts:
                print(
                    f"Timeout occurred. Retrying... Attempt {attempts}/{max_attempts}"
                )
                print(data)
                time.sleep(retry_interval)
            else:
                return {"error": f"Timeout occurred after {max_attempts} attempts"}


def start_avd(port, avd_name):
    print(f"Starting AVD: {avd_name}")
    url = f"http://localhost:{port}/start"
    headers = {"Content-Type": "application/json"}
    data = {"avd_name": avd_name}
    return send_post_request(url, headers, data)


def execute_adb_command(port, command):
    # print(f"Executing ADB command: {command}")
    url = f"http://localhost:{port}/execute"
    headers = {"Content-Type": "application/json"}
    data = {"command": command}
    return send_post_request(url, headers, data)


def stop_avd(port, avd_name):
    url = f"http://localhost:{port}/stop"
    headers = {"Content-Type": "application/json"}
    data = {"avd_name": avd_name}
    return send_post_request(url, headers, data)
