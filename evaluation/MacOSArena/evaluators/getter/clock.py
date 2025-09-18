import json
from typing import List
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
import time
import datetime
import pytz

logger = ProjectLogger().get()

def force_close_clock(env: MacOSEnv):
    env.connect_ssh()
    cmds = [
        "sudo pkill -9 'Clock'",
        "sudo pkill -9 securityagent"
        "sudo pkill -9 'Clock.app'",
        "sudo pkill -9 'Clock Widgets'",
        "sudo pkill -9 'com.apple.clock'",
        "sudo pkill -9 'application.com.apple.clock.*'"
    ]
    for cmd in cmds:
        env.run_command(f"{cmd}")
    time.sleep(3)
    
def clock_reset_window_status(env: MacOSEnv):
    send_esc_script = '''
    tell application "System Events"
        key code 53 -- Esc key
    end tell
    '''
    env.run_command(f"osascript -e '{send_esc_script.strip()}'")
    time.sleep(0.5)
    env.connect_ssh()

    force_close_clock(env)
    env.run_command(f"open -a 'Clock'")
    stdout, _ = env.run_command(f"osascript -e '{send_esc_script.strip()}'")
    time.sleep(5)

# click radio button 2 of radio group 1 of group 1 of toolbar 1 of window 1 -- ALARMS

def clock_debug(env: MacOSEnv) -> str:
    """
    Debug UI structure of Clock.app: get class, name, description, and value of each top-level UI element.

    Returns:
        str: Formatted information for each UI element in Clock's main window.
    """
    env.connect_ssh()
    # force_close_clock(env)
    clock_reset_window_status(env)

    apple_script = '''
    tell application "System Events"
        tell application process "Clock"
            if (count of windows) = 0 then
                return "No window found"
            end if
            
            click menu item "World Clock" of menu "View" of menu bar 1
            delay 5

            set output to ""
            set elems to every UI element of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of window 1
            repeat with elem in elems
                set elem_class to (class of elem as string)

                -- name
                try
                    set elem_name to name of elem
                    if (class of elem_name is not text) then set elem_name to "<non-text name>"
                on error
                    set elem_name to "<no name>"
                end try

                -- description
                try
                    set elem_desc to description of elem
                    if (class of elem_desc is not text) then set elem_desc to "<non-text description>"
                on error
                    set elem_desc to "<no description>"
                end try

                -- value
                try
                    set elem_value to value of elem
                    if (class of elem_value is not text) then set elem_value to "<non-text value>"
                on error
                    set elem_value to "<no value>"
                end try

                set output to output & "[class: " & elem_class & "] "
                set output to output & "[name: " & elem_name & "] "
                set output to output & "[description: " & elem_desc & "] "
                set output to output & "[value: " & elem_value & "]\\n"
            end repeat

            return output
        end tell
    end tell
    '''
    
#     apple_script = '''
#     tell application "System Events"
#         tell application process "Clock"
#             if (count of windows) = 0 then
#                 return "No window found"
#             end if

#             set output to ""
#             set current_group to window 1
#             set path_desc to "window 1"
#             set max_depth to 20
#             repeat with depth from 1 to max_depth
#                 try
#                     set current_group to group 1 of current_group
#                     set path_desc to path_desc & " -> group 1"
#                 on error
#                     set output to output & "Reached max or no group 1 at depth " & depth & "\\n"
#                     exit repeat
#                 end try

#                 set elems to every UI element of current_group
#                 set class_list to {}

#                 repeat with elem in elems
#                     set elem_class to (class of elem as string)
#                     copy elem_class to the end of class_list
#                 end repeat

#                 -- group search 
#                 if class_list contains "static text" or class_list contains "button" or class_list contains "checkbox" or class_list contains "text field" or class_list contains "image" then
#                     set output to output & "⤵ Found mixed content at: " & path_desc & "\\n"

#                     repeat with elem in elems
#                         set elem_class to (class of elem as string)
#                         try
#                             set elem_name to name of elem
#                             if (class of elem_name is not text) then set elem_name to "<non-text name>"
#                         on error
#                             set elem_name to "<no name>"
#                         end try

#                         try
#                             set elem_desc to description of elem
#                             if (class of elem_desc is not text) then set elem_desc to "<non-text description>"
#                         on error
#                             set elem_desc to "<no description>"
#                         end try

#                         try
#                             set elem_value to value of elem
#                             if (class of elem_value is not text) then set elem_value to "<non-text value>"
#                         on error
#                             set elem_value to "<no value>"
#                         end try

#                         set output to output & "[class: " & elem_class & "] "
#                         set output to output & "[name: " & elem_name & "] "
#                         set output to output & "[description: " & elem_desc & "] "
#                         set output to output & "[value: " & elem_value & "]\\n"
#                     end repeat

#                     exit repeat
#                 end if
#             end repeat

#             return output
#         end tell
#     end tell    
# '''

    try:
        stdout, stderr = env.run_command(f"osascript -e '{apple_script.strip()}'")
        logger.info(stderr)
        output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        # logger.info(f"[clock_debug] Clock UI detailed structure:\n{output}")
        return output
    except Exception as e:
        logger.error(f"[clock_debug] Failed to extract Clock UI structure: {e}")
        return "Error: Unable to retrieve UI elements"


def clock_list_alarms(env) -> list[dict]:
    """
    Launch Clock.app, switch to Alarm tab, and extract structured alarm data including 'enabled' status.

    Returns:
        list of dicts: [
            {
                "time": "6:30AM",
                "label": "Morning run",
                "repeat": "Weekdays",
                "sound": "Ripples",
                "enabled": True
            },
            ...
        ]
    """
    env.connect_ssh()
    env.run_command("open -a 'Clock'")
    time.sleep(2)

    apple_script = '''
    tell application "System Events"
        tell application process "Clock"
            if (count of windows) = 0 then
                return "No window found"
            end if

            click menu item "Alarms" of menu "View" of menu bar 1
            delay 3

            set output to "["
            set alarm_buttons to every button of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of window 1

            repeat with alarm_button in alarm_buttons
                set alarm_data to {"", "", "", "", "false"} -- time, label, repeat, sound, enabled
                set text_items to every static text of alarm_button
                set checkbox_items to every checkbox of alarm_button

                -- checkbox: get enabled status
                
                if (count of checkbox_items) > 0 then
                    set checkbox_value to value of item 1 of checkbox_items
                    if checkbox_value = "1" then
                        set item 5 of alarm_data to "true"
                    else
                        set item 5 of alarm_data to "false"
                    end if
                end if


                -- static text: parse time/label/repeat/sound
                repeat with t in text_items
                    try
                        set d to description of t
                        if d starts with "Repeat:" then
                            set item 3 of alarm_data to text ((offset of ":" in d) + 2) thru -1 of d
                        else if d starts with "Sound:" then
                            set item 4 of alarm_data to text ((offset of ":" in d) + 2) thru -1 of d
                        else if d contains "AM" or d contains "PM" then
                            set item 1 of alarm_data to d
                        else
                            set item 2 of alarm_data to d
                        end if
                    end try
                end repeat

                set output to output & "{"
                set output to output & "\\"time\\":\\"" & item 1 of alarm_data & "\\","
                set output to output & "\\"label\\":\\"" & item 2 of alarm_data & "\\","
                set output to output & "\\"repeat\\":\\"" & item 3 of alarm_data & "\\","
                set output to output & "\\"sound\\":\\"" & item 4 of alarm_data & "\\","
                set output to output & "\\"enabled\\":" & item 5 of alarm_data & "},"
            end repeat

            if output ends with "," then
                set output to text 1 thru -2 of output
            end if
            set output to output & "]"
            return output
        end tell
    end tell
    '''

    try:
        stdout, _ = env.run_command(f"osascript -e '{apple_script.strip()}'")
        logger.info(_)
        raw_output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        logger.info(f"[clock_list_alarms] Raw AppleScript output:\n{raw_output}")

        # Convert to JSON
        alarms = json.loads(raw_output)
        return alarms

    except Exception as e:
        logger.error(f"[clock_list_alarms] Failed to extract alarms: {e}")
        return []


def clock_get_world_clock_order(env) -> list[str]:
    """
    Switch to World Clock tab and extract the current order of world clocks shown.

    Returns:
        list of city names in order of appearance (top to bottom).
    """
    env.connect_ssh()
    
    open_script = '''
    tell application "System Events"
        tell application process "Clock"
            if (count of windows) = 0 then
                return "No window found"
            end if
            click menu item "World Clock" of menu "View" of menu bar 1
        end tell
    end tell
    '''
    env.run_command(f"osascript -e '{open_script.strip()}'")
    time.sleep(3)

    apple_script = '''
    tell application "System Events"
        tell application process "Clock"
            if (count of windows) = 0 then
                return "No window found"
            end if

            set output to ""
            set elems to every UI element of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of window 1
            
            repeat with e in elems
                try
                    set d to description of e
                    if d is not "group" and d is not "World map" then
                        set city to text 1 thru ((offset of "," in d) - 1) of d
                        set output to output & city & "|||"
                    end if
                end try
            end repeat

            return output
        end tell
    end tell
    '''

    try:
        stdout, _ = env.run_command(f"osascript -e '{apple_script.strip()}'")
        raw_output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
        # logger.info(f"[clock_get_world_clock_order] Raw output: {raw_output}")

        if raw_output == "No window found":
            return []

        # Split by custom delimiter
        cities = [c.strip() for c in raw_output.split("|||") if c.strip()]
        return cities

    except Exception as e:
        logger.error(f"Failed to get world clock order: {e}")
        return []

def clock_get_world_clock_top_item(env):
    clock_list = clock_get_world_clock_order(env)
    if clock_list != []:
        return clock_list[0]
    
    
def clock_check_korea_alarm(env) -> bool:
    """
    Check whether the first alarm in Clock app is named 'Korea' and its time matches current Korea time (±3 minutes).

    Returns:
        bool: True if matched, False otherwise
    """
    env.connect_ssh()

    # Step 1: Get current time in Korea (Seoul timezone)
    try:
        korea_tz = pytz.timezone("Asia/Seoul")
        korea_time = datetime.datetime.now(korea_tz)
        korea_hour = korea_time.hour
        korea_minute = korea_time.minute
        logger.info(f"current korea time: {korea_time}")
    except Exception as e:
        logger.error(f"[clock_check_korea_alarm] Failed to get Korea time: {e}")
        return False

    # Step 2: Get alarm list from Clock.app
    try:
        alarms = clock_list_alarms(env)
        if not alarms:
            logger.warning("[clock_check_korea_alarm] No alarms found.")
            return False

        alarm = alarms[0]  # First alarm
        alarm_label = alarm.get("label", "")
        alarm_time_str = alarm.get("time", "")

        # Validate label
        if alarm_label.lower() != "korea":
            logger.warning(f"[clock_check_korea_alarm] First alarm label is not 'Korea': {alarm_label}")
            return False

        # Parse alarm time string (e.g., '3:00PM')
        try:
            alarm_dt = datetime.datetime.strptime(alarm_time_str.strip(), "%I:%M%p")
        except ValueError:
            logger.error(f"[clock_check_korea_alarm] Invalid alarm time format: {alarm_time_str}")
            return False

        # Convert alarm time to 24-hour
        alarm_hour = alarm_dt.hour
        alarm_minute = alarm_dt.minute

        # Step 3: Compare time with Korea time (±3 min)
        delta = abs((alarm_hour * 60 + alarm_minute) - (korea_hour * 60 + korea_minute))
        logger.info(f"[clock_check_korea_alarm] Korea time: {korea_hour}:{korea_minute:02d}, "
                    f"Alarm: {alarm_hour}:{alarm_minute:02d}, Δ={delta}min")

        return delta <= 3
    except Exception as e:
        logger.error(f"[clock_check_korea_alarm] Failed to evaluate alarm: {e}")
        return False
    

def clock_check_clock_timer_value(env: MacOSEnv, hours=0, minutes=0, seconds=0) -> bool:
    """
    Check whether the Clock app's Timer matches the given (hours, minutes, seconds).

    Args:
        env (MacOSEnv): Remote macOS environment
        hours (int): Expected hour value (default: 0)
        minutes (int): Expected minute value (default: 0)
        seconds (int): Expected second value (default: 0)

    Returns:
        bool: True if matches, False otherwise
    """
    env.connect_ssh()

    open_timer_script = '''
    tell application "Clock" to activate
    delay 1
    tell application "System Events"
        tell process "Clock"
            click menu item "Timers" of menu "View" of menu bar 1
        end tell
    end tell
    '''
    env.run_command(f"osascript -e '{open_timer_script.strip()}'")
    time.sleep(2)

    read_timer_script = '''
    tell application "System Events"
        tell process "Clock"
            try
                set timer_value to value of group 1 of group 1 of group 2 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of window 1
                return timer_value
            on error errMsg
                return "ERROR: Failed to retrieve timer value. A previous timer record may be present."
            end try
        end tell
    end tell
    '''

    stdout, stderr = env.run_command(f"osascript -e '{read_timer_script.strip()}'")
    output = stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    logger.info(f"[settings_check_clock_timer_value] Raw output: {output}")

    try:
        if "Error" in output:
            return False

        timer_parts = output.strip().split(":")
        if len(timer_parts) != 3:
            return False

        actual_h, actual_m, actual_s = map(int, timer_parts)
        return (actual_h == hours and actual_m == minutes and actual_s == seconds)

    except Exception as e:
        logger.error(f"Failed to parse timer output: {e}")
        return False

if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()
    
    # Connect to Docker container
    macos_env.connect_ssh()
    
    # prop = "ShowFavorites"
    value = clock_check_clock_timer_value(macos_env, minutes=1, seconds=20)
    logger.info(value)
    
    import time
    time.sleep(3)
    macos_env.close_connection()