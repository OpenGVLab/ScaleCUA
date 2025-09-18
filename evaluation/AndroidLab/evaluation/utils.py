import getpass
import os
import shutil
import socket
import subprocess

from evaluation.docker_utils import execute_adb_command


def find_matching_subtrees(tree, search_str):
    """
    Finds all subtrees in a given JSON-like dictionary tree where any key or
    leaf node value contains the given string. Returns a list of all matching subtrees,
    ensuring that no higher-level nodes are included unless they themselves match.

    Parameters:
    - tree (dict): The tree to search within.
    - search_str (str): The substring to search for in keys and leaf node values.

    Returns:
    - list: A list of dictionaries, each representing a matching subtree.
    """
    matched_subtrees = []

    # Helper function to recursively search through the tree
    def search_tree(current_tree):
        # Initialize a local variable to store potential matches within this subtree
        local_matches = []

        # Iterate through each key and value pair in the current tree
        for key, value in current_tree.items():
            # Check if the key itself contains the search string
            if search_str in key:
                # Directly append this subtree since the key matches
                local_matches.append({key: value})
            elif isinstance(value, dict):
                # If the value is a dictionary, recurse into it
                result = search_tree(value)
                if result:
                    # Only append if the recursion found a match
                    local_matches.extend(result)
            elif isinstance(value, str) and search_str in value:
                # If the value is a string and contains the search string, append this leaf
                local_matches.append({key: value})

        # Return any matches found in this part of the tree
        return local_matches

    # Start the search from the root of the tree
    matched_subtrees = search_tree(tree)

    return matched_subtrees


def find_subtrees_of_parents_with_key(tree, search_key):
    """
    Finds the entire subtrees for all parent nodes of any nodes containing the given key in a JSON-like dictionary tree.
    Each subtree is collected in a list.

    Parameters:
    - tree (dict): The tree to search within.
    - search_key (str): The key to search for in the tree.

    Returns:
    - list: A list of dictionaries, each representing the subtree of a parent that has a child node with the search_key.
    """
    parent_subtrees = []  # To store the subtrees of parents that contain the search_key

    # Helper function to recursively search through the tree
    def search_tree(current_tree, parent=None):
        # Iterate through each key and value pair in the current tree
        for key, value in current_tree.items():
            if search_key in key:
                if parent:
                    parent_subtrees.append({parent: current_tree})  # Capture the parent's subtree
                return True  # Found the key, mark this path as containing the key
            elif isinstance(value, dict):
                # If the value is a dictionary, recurse into it
                search_tree(value, key)  # Continue to search deeper

    # Start the recursive search from the root
    search_tree(tree)

    return parent_subtrees


def get_avd_serial_number(avd_name):
    try:
        result = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        devices_output = result.stdout

        devices = [line.split()[0] for line in devices_output.splitlines() if 'device' in line and 'List' not in line]

        for device in devices:
            result = subprocess.run(['adb', '-s', device, 'emu', 'avd', 'name'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            avd_output = result.stdout.replace("OK", "").strip()
            # print(avd_output.replace("OK", "").strip())

            if avd_output == avd_name:
                return device

        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def extract_bounds(node, path=""):
    result = []
    for key, value in node.items():
        current_path = key
        if isinstance(value, dict):
            result.extend(extract_bounds(value, current_path))
        elif key == "bounds":
            result.append({"key": path.strip(), "value": value})
    return result


def execute_adb(adb_command, type="cmd", output=True, port=None):
    if type == "cmd":
        env = os.environ.copy()
        env["PATH"] = f"/Users/{getpass.getuser()}/Library/Android/sdk/platform-tools:" + env["PATH"]
        env["PATH"] = f"/Users/{getpass.getuser()}/Library/Android/sdk/tools:" + env["PATH"]
        result = subprocess.run(adb_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                executable='/bin/zsh', env=env)
        if result.returncode == 0:
            return result.stdout.strip()
        if output:
            print(f"Command execution failed: {adb_command}", "red")
            print(result.stderr, "red")
        return "ERROR"
    elif type == "docker":
        assert port is not None, "Port must be provided for docker type"
        result = execute_adb_command(port, adb_command)
        assert "result" in result, "Error in executing adb command"
        return result["result"]


def list_all_devices(type="cmd", port=None):
    adb_command = "adb devices"
    device_list = []
    result = execute_adb(adb_command, type, port)
    if result != "ERROR":
        devices = result.split("\n")[1:]
        for d in devices:
            device_list.append(d.split()[0])

    return device_list


def get_adb_device_name(avd_name=None):
    device_list = list_all_devices()
    for device in device_list:
        command = f"adb -s {device} emu avd name"
        ret = execute_adb(command, output=False)
        ret = ret.split("\n")[0]
        if ret == avd_name:
            return device
    return None


def find_free_ports(start_port=6060):
    def is_port_free(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0

    port = start_port
    while True:
        if is_port_free(port):
            return port
        port += 1


def clone_avd(src_avd_name, tar_avd_name, android_avd_home):
    """
    Clone the source AVD to the target AVD.

    Parameters:
    - src_avd_name: The name of the source AVD folder.
    - tar_avd_name: The name of the target AVD folder.
    - android_avd_home: The path to the .android/avd directory.

    This function copies the source AVD folder and its .ini file to a new target AVD
    and updates the paths inside the .ini files accordingly.
    """

    # Paths for source and target AVD directories and .ini files
    src_avd_dir = os.path.join(android_avd_home, src_avd_name + '.avd')
    tar_avd_dir = os.path.join(android_avd_home, tar_avd_name + '.avd')
    src_ini_file = os.path.join(android_avd_home, src_avd_name + '.ini')
    tar_ini_file = os.path.join(android_avd_home, tar_avd_name + '.ini')

    # Copy the AVD folder
    print(f"====Copying the AVD folder from {src_avd_dir} to {tar_avd_dir}====")
    print("This may take a while...")
    if not os.path.exists(tar_avd_dir):
        shutil.copytree(src_avd_dir, tar_avd_dir)

    # Copy the .ini file and modify it for the new AVD
    with open(src_ini_file, 'r') as src_ini, open(tar_ini_file, 'w') as tar_ini:
        for line in src_ini:
            tar_ini.write(line.replace(src_avd_name, tar_avd_name))

    # Update paths inside the target AVD's .ini files
    for ini_name in ['config.ini', 'hardware-qemu.ini']:
        ini_path = os.path.join(tar_avd_dir, ini_name)
        if os.path.exists(ini_path):
            with open(ini_path, 'r') as file:
                lines = file.readlines()
            with open(ini_path, 'w') as file:
                for line in lines:
                    # Update paths and AVD name/ID
                    new_line = line.replace(src_avd_name, tar_avd_name)
                    file.write(new_line)

    # Update the snapshots' hardware.ini file if it exists
    snapshots_hw_ini = os.path.join(tar_avd_dir, 'snapshots', 'default_boot', 'hardware.ini')
    if os.path.exists(snapshots_hw_ini):
        with open(snapshots_hw_ini, 'r') as file:
            lines = file.readlines()
        with open(snapshots_hw_ini, 'w') as file:
            for line in lines:
                # Update AVD name/ID
                new_line = line.replace(src_avd_name, tar_avd_name)
                file.write(new_line)

    return tar_avd_dir, tar_ini_file
