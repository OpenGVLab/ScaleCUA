import json
from typing import List
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
import time
from pathlib import Path
import shlex
import base64

script_dir = Path(__file__).resolve().parent.parent

MACNOTESAPP_PATH = "/usr/local/bin/notes"
logger = ProjectLogger(log_dir=script_dir / "logs")

def notes_find_note_by_title(env: MacOSEnv, title: str) -> bool:
    """
    Check if a note with the given title exists in the default Notes folder.
    """
    script = f'''
    tell application "Notes"
        set found to false
        repeat with n in notes of folder "Notes"
            if name of n is "{title}" then
                set found to true
                exit repeat
            end if
        end repeat
        return found
    end tell
    '''
    stdout, _ = env.run_command(f"osascript -e '{script.strip()}'")
    output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    return output.lower() == "true"


def notes_list_locked_note_titles(env: MacOSEnv) -> list[str]:
    """
    Remotely use macnotesapp to list all locked (password_protected) note titles from macOS Notes.
    Requires: macnotesapp is installed and Notes permissions are granted.
    """
    env.connect_ssh()

    python_script = """
from macnotesapp import NotesApp
try:
    app = NotesApp()
    notes = app.notes()
    locked_titles = [n.name for n in notes if getattr(n, 'password_protected', False)]
    if not locked_titles:
        print("__NO_LOCKED__")
    else:
        print("__LOCKED__:" + "|||".join(locked_titles))
except Exception as e:
    print("__ERROR__:" + str(e))
"""

    safe_code = shlex.quote(python_script.strip())
    stdout, _ = env.run_command(f"python3 -c {safe_code}")
    output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    # logger.info(stdout)
    # logger.info(_)

    if output.startswith("__LOCKED__:"):
        return output.replace("__LOCKED__:", "").split("|||")
    elif output == "__NO_LOCKED__":
        return []
    elif output.startswith("__ERROR__"):
        logger.error(f"Notes access error: {output}")
        return []
    else:
        logger.error(f"Unexpected output from notes listing: {output}")
        return []
    
def notes_count_notes_in_folder(env, folder_name: str) -> int:
    """
    Count the number of notes inside a specific folder.

    :param env: MacOSEnv instance
    :param folder_name: The name of the folder to search in.
    :return: Number of notes in the folder.
    """
    env.connect_ssh()

    remote_py = f"""
from macnotesapp import NotesApp
try:
    app = NotesApp()
    count = sum(1 for n in app.notes() if n.folder == {folder_name!r})
    print("__COUNT__:" + str(count))
except Exception as e:
    print("__ERROR__:" + str(e))
"""

    safe_code = shlex.quote(remote_py.strip())
    stdout, _ = env.run_command(f"python3 -c {safe_code}")
    output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()

    if output.startswith("__COUNT__:"):
        return int(output.replace("__COUNT__:", ""))
    elif output.startswith("__ERROR__"):
        logger.error(f"Notes count error: {output}")
        return 0
    else:
        logger.error(f"Unexpected count output: {output}")
        return 0
    

def notes_get_note_plaintext_by_name(env, name: str, folder: str = None) -> list[str]:
    """
    Fetch plaintext contents of all notes with given title (and folder, if specified).

    :param env: MacOSEnv instance
    :param name: The title of the note to find
    :param folder: Optional folder name to restrict search
    :return: List of plaintext contents of matching notes
    """
    env.connect_ssh()

    folder_filter = f" and n.folder == {folder!r}" if folder else ""

    remote_py = f"""
from macnotesapp import NotesApp
try:
    app = NotesApp()
    notes = [n for n in app.notes() if n.name == {name!r}{folder_filter}]
    if not notes:
        print("__NOT_FOUND__")
    else:
        print("__TEXT__:" + "|||".join(n.plaintext.strip().replace("\\n", "\\\\n") for n in notes))
except Exception as e:
    print("__ERROR__:" + str(e))
"""
    safe_code = shlex.quote(remote_py.strip())
    stdout, _ = env.run_command(f"python3 -c {safe_code}")
    output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()

    if output.startswith("__TEXT__:"):
        return [s.replace("\\n", "\n") for s in output.replace("__TEXT__:", "").split("|||")]
    elif output == "__NOT_FOUND__":
        return []
    elif output.startswith("__ERROR__"):
        logger.error(f"Notes read error: {output}")
        return []
    else:
        logger.error(f"Unexpected notes output: {output}")
        return []


def notes_get_properties_by_name(env, note_name: str) -> dict:
    """
    Use AppleScript to find the first note with given name and return its properties.

    :param env: MacOSEnv instance
    :param note_name: Title of the note (exact match)
    :return: Dictionary of note properties
    """
    env.connect_ssh()

    apple_script = f'''
    on run
        try
            tell application "Notes"
                set theNote to first note whose name is "document"
                set noteBody to properties of attachments of theNote
                return "__BODY__\\n" & noteBody
            end tell
        on error errMsg
            return "__ERROR__" & errMsg
        end try
    end run
    '''

    safe_code = shlex.quote(apple_script.strip())
    stdout, _ = env.run_command(f"osascript -e {safe_code}")
    output = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()

    if output.startswith("__PROPERTIES__"):
        props_block = output.replace("__PROPERTIES__\n", "")
        result = {}
        for line in props_block.splitlines():
            if ':' in line:
                k, v = line.split(":", 1)
                result[k.strip()] = v.strip()
        return result
    elif output.startswith("__ERROR__"):
        logger.error(f"AppleScript error: {output}")
        return {}
    else:
        logger.error(f"Unexpected AppleScript output: {output}")
        return {}

def notes_list_attachment_names_by_note_name(env, note_name: str) -> list[str]:
    """
    Get names of all attachments in the first note matching a given name using AppleScript.

    :param env: MacOSEnv instance
    :param note_name: The title of the note
    :return: List of attachment names
    """
    env.connect_ssh()

    apple_script = f'''
    on run
        try
            tell application "Notes"
                set theNote to first note whose name is "{note_name}"
                set theAttachments to attachments of theNote
                set nameList to ""
                repeat with a in theAttachments
                    set nameList to nameList & name of a & linefeed
                end repeat
                return "__RESULT__" & nameList
            end tell
        on error errMsg
            return "__ERROR__" & errMsg
        end try
    end run
    '''

    safe_code = shlex.quote(apple_script.strip())
    stdout, _ = env.run_command(f"osascript -e {safe_code}")
    output = stdout.read().decode().strip() if hasattr(stdout, 'read') else stdout.strip()

    if output.startswith("__RESULT__"):
        lines = output.replace("__RESULT__", "").strip().splitlines()
        return [line.strip() for line in lines if line.strip()]
    else:
        logger.error(f"Attachment list error: {output}")
        return []
    



if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()
    
    # Connect to Docker container
    macos_env.connect_ssh()
 
    value = notes_list_attachment_names_by_note_name(macos_env, "document")
    logger.info(value)
    
    import time
    time.sleep(3)
    macos_env.close_connection()