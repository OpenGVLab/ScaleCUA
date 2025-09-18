import paramiko
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
from pathlib import Path
import json
import time
from bs4 import BeautifulSoup
import datetime

import json
from pathlib import Path
import shlex

script_dir = Path(__file__).resolve().parent.parent
logger = ProjectLogger(log_dir=script_dir / "logs")


def vscode_check_workspace_folders(
    env: MacOSEnv, expected_folder_list=["1", "11"]
) -> bool:
    """
    Check that the VSCode workspace includes ONLY the folders
    /Users/Shared/data1 and /Users/Shared/data2, no more, no less.

    :param env: MacOSEnv instance for SSH execution
    :return: True if valid, False otherwise
    """
    env.connect_ssh()

    search_cmd = 'find /Users/Shared -name "*.code-workspace" | head -n 1'
    stdout, _ = env.run_command(search_cmd)
    workspace_path = (
        stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    )

    if not workspace_path:
        logger.error("No workspace file found.")
        return False

    logger.info(f"Found workspace file: {workspace_path}")

    local_path = "/tmp/current_workspace.code-workspace"
    try:
        env.connect_sftp()
        env.sftp_client.get(workspace_path, local_path)
        with open(local_path, "r") as f:
            workspace = json.load(f)

        folders = workspace.get("folders", [])
        folder_paths = sorted([f["path"] for f in folders])

        expected = sorted(expected_folder_list)
        if folder_paths == expected:
            return True
        else:
            logger.error(f"Unexpected folders: {folder_paths}")
            return False

    except Exception as e:
        logger.error(f"Failed to verify workspace folders: {e}")
        return False


def extract_original_file_contents(
    env, workspace_dir: str, preset_files: list[str]
) -> dict[str, str]:
    """
    Extract the original content of preset files from a remote workspace.
    Useful for validating user modifications later (e.g., Tab -> 4-space conversion).

    :param env: MacOSEnv instance
    :param workspace_dir: Remote base directory (e.g., ~/Library/example_code)
    :param preset_files: List of target file names
    :return: Dict mapping file names to original content strings
    """
    env.connect_ssh()

    remote_py = f"""
import os
import json

workspace = os.path.expanduser(r\"\"\"{workspace_dir}\"\"\")
preset_files = {preset_files!r}
original_contents = {{}}

for pf in preset_files:
    pf_path = os.path.join(workspace, pf)
    if os.path.exists(pf_path):
        try:
            with open(pf_path, "r", encoding="utf-8", errors="ignore") as f:
                original_contents[pf] = f.read()
        except Exception as e:
            original_contents[pf] = "__ERROR__:" + str(e)
    else:
        original_contents[pf] = "__MISSING__"

print("__ORIGINAL_JSON__:" + json.dumps(original_contents))
"""

    safe_code = shlex.quote(remote_py.strip())
    stdout, _ = env.run_command(f"python3 -c {safe_code}")
    output = (
        stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    )

    try:
        marker = "__ORIGINAL_JSON__:"
        if marker in output:
            json_str = output.split(marker, 1)[-1].strip()
            return json.loads(json_str)
        else:
            raise ValueError("No __ORIGINAL_JSON__ marker found in output.")
    except Exception as e:
        logger.error(f"Failed to extract original file contents: {e}")
        return {}


def vscode_check_tab_to_4space_replacement(
    env, folder: str, files: list[str], original_contents: dict[str, str]
) -> bool:
    """
    Check whether each file in `files` under `folder` has all its tab characters replaced by four spaces,
    and that no other content was changed.

    :param env: MacOSEnv instance
    :param folder: Remote directory path (e.g., ~/Library/example_code)
    :param files: List of file names to check (e.g., ['1.py', '2.txt'])
    :param original_contents: Dict mapping filenames to original content with tabs
    :return: True if all files are modified correctly, False otherwise
    """
    import shlex
    import json

    env.connect_ssh()

    remote_py = f"""
import os
import json

folder = os.path.expanduser(r\"\"\"{folder}\"\"\")
files = {files!r}
current_contents = {{}}

for fname in files:
    fpath = os.path.join(folder, fname)
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                current_contents[fname] = f.read()
        except Exception as e:
            current_contents[fname] = "__ERROR__:" + str(e)
    else:
        current_contents[fname] = "__MISSING__"

print("__MODIFIED_JSON__:" + json.dumps(current_contents))
"""

    safe_code = shlex.quote(remote_py.strip())
    stdout, _ = env.run_command(f"python3 -c {safe_code}")
    output = (
        stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    )

    try:
        marker = "__MODIFIED_JSON__:"
        if marker not in output:
            logger.error("Modified content marker not found.")
            return False
        json_str = output.split(marker, 1)[-1].strip()
        modified_map = json.loads(json_str)
    except Exception as e:
        logger.error(f"Failed to parse modified content JSON: {e}")
        return False

    for fname in files:
        original = original_contents.get(fname)
        modified = modified_map.get(fname)

        if original is None:
            logger.warning(f"Original content for {fname} not found.")
            return False
        if (
            modified is None
            or modified.startswith("__ERROR__")
            or modified == "__MISSING__"
        ):
            logger.warning(f"Modified content for {fname} not found or error.")
            return False

        expected = original.replace("\t", "    ")
        if modified != expected:
            logger.warning(
                f"Mismatch in file {fname}: Tab not properly replaced or content altered."
            )
            return False

    return True


def vscode_check_extension_installed(
    env, extension_id: str = "ms-python.python"
) -> bool:
    """
    Checks if a specific VS Code extension is installed in the remote environment.

    :param env: MacOSEnv instance
    :param extension_id: The ID of the VS Code extension (e.g., 'ms-python.python')
    :return: True if installed, False otherwise
    """
    env.connect_ssh()

    try:
        stdout, _ = env.run_command(f"/usr/local/bin/code --list-extensions")
        # logger.info(stdout)
        # logger.info(_)
        output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        return extension_id in output
    except Exception as e:
        logger.error(f"Failed to check VS Code extension: {e}")
        return False


def vscode_check_python_extension_and_conda_path(env) -> bool:
    """
    Check if 'ms-python.python' is installed and if user-level conda path is set to /opt/anaconda3/bin/conda.

    :param env: MacOSEnv instance
    :return: True if both checks pass
    """
    env.connect_ssh()

    try:
        # Check extension
        stdout, _ = env.run_command("/usr/local/bin/code --list-extensions")
        ext_output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        if "ms-python.python" not in ext_output:
            logger.warning("VS Code Python extension not installed.")
            return False

        # Check user settings
        check_cmd = 'cat "$HOME/Library/Application Support/Code/User/settings.json"'
        stdout, _ = env.run_command(check_cmd)
        logger.info(stdout)
        logger.info(_)
        settings = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )

        if '"python.condaPath"' in settings and "/opt/anaconda3/bin/conda" in settings:
            return True
        else:
            logger.warning("python.condaPath not correctly set.")
            return False

    except Exception as e:
        logger.error(f"Failed to check settings: {e}")
        return False


if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()

    # Connect to Docker container
    macos_env.connect_ssh()

    value = vscode_check_extension_installed(macos_env)
    logger.info(value)
    #     original_map = {
    #   "1.py": "\nimport os\nfrom pathlib import Path\ntry:\n    from osxmetadata import OSXMetaData\n    path = Path(r\"\"\"/Users/Shared/1/11/11/1/empty.txt\"\"\").expanduser().resolve()\n    if \t\tnot \tpath.exists():\n        \tprint(\"__NOT_FOUND__\")\t\t\n    else:\n        \tmd = OSXMetaData(str(path))\n        \ttags = md.tags or []\t\t\t\n        \tprint(\"__TAGS__:\" + \",\".join(str(tag) for tag in tags))\nexcept Exception as e:\t\t\t\t\t\t\n    print(\"__ERROR__:\" + str(e))\n\n\n\t\t\n\t\t\n    1   \t\t\t1\t\n\t\t\n\n\n\n\n\n\n\n",
    #   "2.txt": " \n    123131\n    ewqrfwr3r32r3rqwtgqgqghhq\t\tthg\t\trhaft               \n    wwzfzsfzsdfa\t\tefg\n\t\t\n\t\t\t\t\n        ewerwqrq\twrfqegwra\n\t\t\t\n            wwzfzsfzsdfa\tefgwer  \t\twwzfzsfzsdfaefgwer      F\n\n\t            sdfsfaf\n\t\n\t\n                wwzfzsfzsdfaefg fef\n\t\n\t\n\t\n\t\n\t\t\t\t\t\t\n\n\t\t\t\n\n\n\n\n\n\n\n\n\n\n\n\n                                                                                    "
    # }
    #
    #     ok = vscode_check_tab_to_4space_replacement(
    #         macos_env,
    #         folder="~/Library/example_code1",
    #         files=["1.py", "2.txt"],
    #         original_contents=original_map
    # )

    # print("✅ All files are correctly modified." if ok else "❌ Replacement incorrect.")

    import time

    time.sleep(3)
    macos_env.close_connection()
