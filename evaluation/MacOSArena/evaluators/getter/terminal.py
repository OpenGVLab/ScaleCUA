import paramiko
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
from pathlib import Path
import json
import time
from bs4 import BeautifulSoup
import datetime


script_dir = Path(__file__).resolve().parent.parent
logger = ProjectLogger(log_dir=script_dir / "logs")

CONDA_PATH = r"/opt/anaconda3/condabin/conda"

def force_close_terminal(env: MacOSEnv):
    env.connect_ssh()
    cmds = [
        "osascript -e 'tell application \"Terminal\" to quit'"
    ]
    for cmd in cmds:
        env.run_command(f"{cmd}")
    time.sleep(3)
    
def terminal_reset_window_status(env: MacOSEnv):
    force_close_terminal(env)
    env.connect_ssh()
    env.run_command(f"open -a 'Terminal'")
    time.sleep(2)

def terminal_check_package_in_conda_env(env, env_name: str, package_name: str) -> bool:
    """
    Check if a given package is installed in a specified conda environment.

    :param env: MacOSEnv instance for SSH connection
    :param env_name: Name of the conda environment
    :param package_name: Package to check
    :return: True if the package is installed in the environment, else False
    """
    env.connect_ssh()

    check_cmd = f'{CONDA_PATH} list -n {env_name} | grep "^{package_name}\\s"'
    stdout, _ = env.run_command(check_cmd)
    # logger.info(_)
    output = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()
    return bool(output)


def terminal_check_files_in_directory(env, folder_path: str, required_files: list[str]) -> bool:
    """
    Check if all files in `required_files` exist in the given folder (non-recursive).

    :param env: MacOSEnv instance for SSH connection
    :param folder_path: Absolute path to the target directory
    :param required_files: List of filenames to check (no subdirectory paths)
    :return: True if all files exist in the folder, else False
    """
    env.connect_ssh()

    folder_path = folder_path.replace("~", "$HOME")
    # Construct shell command: list files in folder and check for presence
    check_cmd = f'ls "{folder_path}"'
    stdout, _ = env.run_command(check_cmd)
    logger.info(_)
    output = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()
    existing_files = set(output.splitlines())

    return all(filename in existing_files for filename in required_files)


def terminal_check_command_in_history(env, target_command: str) -> bool:
    """
    Check if a specific command is present in the user's terminal history.

    :param env: MacOSEnv instance for SSH connection
    :param target_command: Command string to search in history
    :return: True if command exists in history, else False
    """
    env.connect_ssh()

    # Read full history from remote
    check_cmd = 'cat ~/.zsh_history || cat ~/.bash_history'
    stdout, _ = env.run_command(check_cmd)
    logger.info(stdout)
    output = stdout.read().decode() if hasattr(stdout, 'read') else stdout

    # Check if target command appears as exact substring
    return target_command in output

def terminal_check_archive_validity_count_name_mod(env, base_path="/Users/Shared") -> bool:
    """
    Check in whether a tar.gz archive with today's container date exists in the given directory,
    contains at least 5 files, and has permission 100 (execute-only for user).

    :param env: MacOSEnv instance
    :param base_path: Directory to search for archive
    :return: True if valid archive found and permissions match, else False
    """
    env.connect_ssh()

    # 1. Get container time
    date_cmd = 'date "+%Y%m%d"'
    stdout, _ = env.run_command(date_cmd)
    date_str = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()

    if not date_str or not date_str.isdigit():
        logger.error(f"Failed to parse container date: {date_str}")
        return False

    filename = f"archive_{date_str}.tar.gz"
    archive_path = f"{base_path}/{filename}"

    # 2. Check if archive exists
    check_cmd = f'test -f "{archive_path}" && echo "Exists" || echo "NotFound"'
    stdout, _ = env.run_command(check_cmd)
    if "NotFound" in (stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()):
        logger.info("Archive not found.")
        return False

    # 3. Check number of files in the archive
    count_cmd = f'sudo tar -tzf "{archive_path}" | wc -l'
    stdout, _ = env.run_command(count_cmd)
    try:
        count = int(stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip())
        logger.info(count)
        if count < 5:
            logger.info(count)
            logger.info("Archive does not contain enough files.")
            return False
    except Exception as e:
        logger.error(f"Failed to count files in archive: {e}")
        return False

    # 4. Check permission: user execute-only = 100
    perm_cmd = f'sudo stat -f "%p" "{archive_path}"'
    stdout, _ = env.run_command(perm_cmd)
    raw_perm = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()
    if not raw_perm.endswith("100"):
        logger.info(f"Incorrect permissions: {raw_perm}")
        return False

    return True

def terminal_check_echo_macos_script(env, base_path="/Users/Shared") -> bool:
    """
    Check for a valid hidden shell script matching 'echo_macos' in /Users/Shared/.
    Conditions:
    - File name contains 'echo_macos' and starts with a dot
    - Only one such file exists
    - File has only user execute permission (no group/other read/write/execute)
    - Script outputs the correct message on execution
    """
    env.connect_ssh()

    try:
        # 1. List matching hidden files
        cmd_list = f'sudo find {base_path} -maxdepth 1 -name ".*echo_macos*" -type f'
        stdout, _ = env.run_command(cmd_list)
        logger.info(stdout)
        logger.info(_)
        
        matches = stdout.read().decode().strip().splitlines() if hasattr(stdout, 'read') else stdout.strip().splitlines()
        logger.info(f"[Check] Matching files: {matches}")

        # 2. Ensure exactly one match
        if len(matches) != 1:
            logger.error(f"Expected 1 match, got {len(matches)}")
            return False

        filepath = matches[0]

        # 3. Check permission: only user execute
        cmd_perm = f'stat -f "%A" "{filepath}"'
        stdout, _ = env.run_command(cmd_perm)
        perms = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()
        logger.info(f"[Check] Permissions: {perms}")
        valid_perms = {'100', '300', '500', '700'}
        if perms not in valid_perms:
            logger.error(f"Error permissions: {perms}.")
            return False
        # if not perms.isdigit() or not int(perms) & 0o100:
        #     logger.error("User does not have execute permission.")
        #     return False
        
        # 4. Execute and check output
        cmd_exec = f'bash "{filepath}"'
        stdout, _ = env.run_command(cmd_exec)
        output = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()
        logger.info(f"[Check] Script output: {output}")
        return output == "macOS task complete"

    except Exception as e:
        logger.error(f"Script validation failed: {e}")
        return False


if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()
    
    # Connect to Docker container
    macos_env.connect_ssh()
    
    value = terminal_check_echo_macos_script(macos_env)
    logger.info(value)
    
    import time
    time.sleep(3)
    macos_env.close_connection()