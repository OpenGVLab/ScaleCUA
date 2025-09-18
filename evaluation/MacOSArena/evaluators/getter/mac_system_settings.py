import paramiko
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
from pathlib import Path
import json
import time
from dateutil import parser as dateparser
from bs4 import BeautifulSoup
import datetime
import textwrap
import os

script_dir = Path(__file__).resolve().parent.parent

logger = ProjectLogger(log_dir=script_dir / "logs")



    # tell application "System Settings"
    #     activate
    #     reveal anchor "Siri" of pane id "com.apple.Siri-Settings.extension"
    # end tell


    # tell application "System Events"
    #     tell application process "System Settings"
    #         set selected_name to name of (first UI element of group 1 of row 1 of outline 1 of scroll area 1 of splitter group 1 of group 1 of window 1 whose selected is true)
    #         return selected_name -- e.g., "Appearance"
    #     end tell
    # end tell
    # delay 2
def settings_ally_debug(env, expected_voice="British (Voice 4)") -> bool:
    """
    Check if Siri is enabled and the selected Siri voice is set correctly.

    :param env: MacOSEnv instance with SSH connection to macOS
    :param expected_voice: Expected Siri voice (e.g., "British (Voice 4)")
    :return: True if both Siri is enabled and voice matches, False otherwise
    """
    env.connect_ssh()
# set all_elems to every UI element of group 2 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
    apple_script = """
    set output to ""

    on get_info_of(elem, level)
        if level > 5 then return ""
        set local_output to ""

        try
            set elem_class to class of elem
        on error
            set elem_class to ""
        end try

        try
            set elem_name to name of elem
        on error
            set elem_name to ""
        end try

        try
            set elem_desc to description of elem
        on error
            set elem_desc to ""
        end try

        try
            set elem_value to value of elem
        on error
            set elem_value to ""
        end try
        set local_output to "LEVEL " & level & ": class=" & elem_class & ", name=\\"" & elem_name & "\\", description=\\"" & elem_desc & "\\", value=\\"" & elem_value & "\\"" & linefeed

        


        return local_output
    end get_info_of

    tell application "System Events"
        tell application process "Clock"
            try
                
                set win to group 1 of group 1 of group 2 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of window 1
                return value of win
                set elems to every UI element of win
                repeat with e in elems
                    set output to output & my get_info_of(e, 1)
                end repeat
            on error errMsg
                set output to "Error: " & errMsg
            end try

        end tell
    end tell

    return output
    """.strip()
    
    #          click button 1 of group 1 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
    
                # click button 1 of group 2 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
    
        #     try
        #     repeat with sub_elem in UI elements of elem
        #         set local_output to local_output & my get_info_of(sub_elem, level + 1)
        #     end repeat
        # end try

    try:
        command = f"osascript -e '{apple_script}'"
        print(apple_script[851:890])
        stdout, stderr = env.run_command(command)
        logger.info(stdout)
        logger.info(stderr)
        output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()

        if "||" not in output:
            return False

        enabled_str, voice_str = output.split("||")
        siri_on = enabled_str.strip() == "1"
        return siri_on and expected_voice in voice_str

    except Exception as e:
        env.logger.error(f"Failed to check Siri settings: {e}")
        return False

def force_close_system_settings(env: MacOSEnv):
    env.connect_ssh()
    cmds = [
        "sudo pkill -9 'System Settings'",
        "sudo pkill -9 'System Settings.app'",
        "sudo pkill -9 'System Preferences'",
        "sudo pkill -9 securityagent"
    ]
    for cmd in cmds:
        env.run_command(f"{cmd}")
        
def settings_reset_window_status(env: MacOSEnv):
    send_esc_script = '''
    tell application "System Events"
        key code 53 -- Esc key
    end tell
    '''
    env.run_command(f"osascript -e '{send_esc_script.strip()}'")
    time.sleep(0.5)
    env.connect_ssh()

    force_close_system_settings(env)
    env.run_command(f"open -a 'System Settings'")
    stdout, _ = env.run_command(f"osascript -e '{send_esc_script.strip()}'")
    time.sleep(5)


def setting_get_siri_status_and_voice(env: MacOSEnv) -> dict:
    """
    Check Siri settings in macOS System Settings.

    Returns:
        dict: {
            "enabled": True/False,
            "voice": str
        }
    """
    env.connect_ssh()
    force_close_system_settings(env)
    
    open_script = """
    tell application "System Settings"
        if it is running then quit
    end tell
    delay 0.5
    tell application "System Settings"
        activate
        reveal anchor "Siri" of pane id "com.apple.Siri-Settings.extension"
    end tell
    """
    env.run_command(f"sudo osascript -e '{open_script.strip()}'")

    time.sleep(5)

    apple_script = '''
    tell application "System Events"
        tell application process "System Settings"
            try
                set siri_enabled to value of checkbox 1 of group 1 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
            on error
                set siri_enabled to "Error"
            end try

            try
                set voice_info to value of static text 4 of group 2 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
            on error
                set voice_info to "Error"
            end try

            return "Siri Enabled: " & siri_enabled & " | Voice: " & voice_info
        end tell
    end tell
    '''

    try:
        stdout, stderr = env.run_command(f"osascript -e '{apple_script}'")
        output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        logger.info(f"[setting_check_siri_status] Raw output: {output}")

        enabled = "Siri Enabled: 1" in output
        voice = output.split("Voice: ")[-1] if "Voice: " in output else "Unknown"

        return {
            "enabled": enabled,
            "voice": voice
        }
    except Exception as e:
        logger.error(f"Failed to check Siri setting: {e}")
        return {
            "enabled": False,
            "voice": "Error"
        }

    
def setting_dump_siri_panel(env):
    """
    Return all visible static texts and UI elements from the Siri & Spotlight panel in System Settings.
    """
    env.connect_ssh()

    open_script = """
    tell application "System Settings"
        activate
        reveal anchor "Siri" of pane id "com.apple.Siri-Settings.extension"
    end tell
    """
    env.run_command(f"osascript -e '{open_script.strip()}'")

    import time
    time.sleep(2)  

    dump_script = '''
    tell application "System Events"
        tell application process "System Settings"
            set ui_texts to ""
            set win to window 1
            set all_elems to every UI element of win
            repeat with e in all_elems
                try
                    set ui_texts to ui_texts & name of e & linefeed
                end try
            end repeat
        end tell
    end tell
    return ui_texts
    '''
    try:
        stdout, stderr = env.run_command(f"osascript -e '{dump_script.strip()}'")
        logger.info(stdout)
        logger.info(stderr)
        output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        return output.splitlines()
    except Exception as e:
        env.logger.error(f"Failed to dump Siri panel UI: {e}")
        return []
    
def settings_check_purple_and_tinting_off(env) -> bool:
    """
    Check if accent color is set to purple and 'Allow wallpaper tinting in windows' is disabled.

    - Accent color is read from defaults.
    - Wallpaper tinting checkbox is read via Accessibility tree after navigating to Appearance panel.
    """
    env.connect_ssh()

    try:
        # 1. Check accent color via defaults
        cmd_accent = "defaults read -g AppleAccentColor || echo -1"
        stdout, _ = env.run_command(cmd_accent)
        accent_str = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        accent_ok = accent_str == "5"

        # 2. Navigate to Appearance via View menu
        nav_script = '''
        tell application "System Settings" to activate
        delay 1
        tell application "System Events"
            tell application process "System Settings"
                click menu item "Appearance" of menu "View" of menu bar 1
            end tell
        end tell
        delay 2
        '''
        env.run_command(f"osascript -e '{nav_script}'")

        # 3. Read checkbox value for 'Allow wallpaper tinting'
        tint_script = '''
        tell application "System Events"
            tell application process "System Settings"
                set checkbox_val to value of checkbox 1 of group 1 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
                return checkbox_val as string
            end tell
        end tell
        '''
        stdout, _ = env.run_command(f"osascript -e '{tint_script}'")
        checkbox_val = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        tinting_ok = checkbox_val == "0"

        logger.info(f"[Accent] {accent_str} (purple? {accent_ok}) | [Wallpaper Tinting] {checkbox_val} (disabled? {tinting_ok})")

        return accent_ok and tinting_ok

    except Exception as e:
        logger.error(f"Failed to check appearance settings: {e}")
        return False
    
def settings_set_desktop_wallpaper(env: MacOSEnv) -> str:
    """
    Return the filename of the current desktop wallpaper.

    Returns:
        str: The wallpaper filename (e.g., 'curry.jpg')
    """
    env.connect_ssh()

    try:
        stdout, stderr = env.run_command("osascript -e 'tell app \"finder\" to get posix path of (get desktop picture as alias)'")
        output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        logger.info(stderr)
        logger.info(f"[settings_set_desktop_wallpaper] Wallpaper filename: {output}")
        return output

    except Exception as e:
        logger.error(f"Failed to get wallpaper filename: {e}")
        return "Error"
    
def settings_check_dnd_repeated_calls_enabled(env: MacOSEnv) -> bool:
    """
    Check if 'Allow repeated calls' is enabled in Do Not Disturb settings (macOS Sonoma+).

    Returns:
        bool: True if enabled, False otherwise.
    """
    env.connect_ssh()
    force_close_system_settings(env)

    open_focus_script = '''
    tell application "System Settings" to activate
    delay 1
    tell application "System Events"
        tell process "System Settings"
            click menu item "Focus" of menu "View" of menu bar 1
        end tell
    end tell
    '''
    env.run_command(f"osascript -e '{open_focus_script.strip()}'")
    time.sleep(2)

    click_dnd_script = '''
    tell application "System Events"
        tell process "System Settings"
            try
                click button 1 of group 1 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
                delay 0.5
                click button 1 of group 2 of scroll area 1 of group 1 of group 2 of splitter group 1 of group 1 of window 1
                delay 0.5
            on error errMsg
                return "Click error: " & errMsg
            end try
        end tell
    end tell
    '''
    env.run_command(f"osascript -e '{click_dnd_script.strip()}'")
    time.sleep(1)

    read_checkbox_script = '''
    tell application "System Events"
        tell process "System Settings"
            try
                set repeated_call_value to value of checkbox 1 of group 2 of scroll area 1 of group 1 of sheet 1 of window 1
                return repeated_call_value
            on error errMsg
                return "Read error: " & errMsg
            end try
        end tell
    end tell
    '''
    stdout, stderr = env.run_command(f"osascript -e '{read_checkbox_script.strip()}'")
    logger.info(stderr)
    output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    logger.info(f"[settings_check_dnd_repeated_calls_enabled] Raw output: {output}")

    return output == "1"


if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()
    
    # Connect to Docker container
    macos_env.connect_ssh()
    value = settings_ally_debug(macos_env)
    logger.info(value)
    # value = settings_get_display_brightness(macos_env)
    # logger.info(value)
    import time
    time.sleep(3)
    macos_env.close_connection()