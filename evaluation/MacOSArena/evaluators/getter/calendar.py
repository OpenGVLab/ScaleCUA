import paramiko
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
from pathlib import Path
import json
import time
from bs4 import BeautifulSoup
import shlex
import textwrap
import plistlib

script_dir = Path(__file__).resolve().parent.parent

logger = ProjectLogger(log_dir=script_dir / "logs")


def calendar_check_weekly_event(
    env, event_name: str, start_hour: int = 10, start_minute: int = 0
) -> bool:
    """
    Check if a Calendar event with the given name exists,
    and repeats weekly on Monday at 10:00 AM.

    :param env: MacOSEnv instance
    :param event_name: The event name to look for (e.g., "Lab Meeting")
    :return: True if matching event found, False otherwise
    """
    env.connect_ssh()

    apple_script = f"""
    set matched to false
    set debug_output to ""
    tell application "Calendar"
        repeat with c in calendars
            set theEvents to every event of c whose summary is "{event_name}"
            repeat with e in theEvents
                set startTime to start date of e
                set start_hour to hours of startTime
                set start_min to minutes of startTime
                set recur to recurrence of e

                -- Check time = 10:00 AM and recurrence contains "weekly"
                if start_hour = {start_hour} and start_min = {start_minute} and recur contains "FREQ=WEEKLY" and recur contains "BYDAY=MO" then
                    set matched to true
                    set debug_output to debug_output & "✓ Matching event found: " & summary of e & return
                end if
            end repeat
        end repeat
    end tell
    if matched then
        return "true__DEBUG__" & debug_output
    else
        return "false__DEBUG__" & debug_output
    end if
    """

    try:
        stdout, _ = env.run_command(f"osascript -e {shlex.quote(apple_script)}")

        output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        return output.startswith("true__")
    except Exception as e:
        logger.error(f"Failed to check calendar event: {e}")
        return False


def calendar_check_weekly_event_advanced(
    env,
    event_name: str,
    weekday: str = "MO",
    start_hour: int = None,
    start_minute: int = None,
    end_hour: int = None,
    end_minute: int = None,
) -> bool:
    """
    Check if a Calendar event with the given name exists,
    repeats weekly on a specific weekday, and (optionally) matches start/end time.

    Args:
        env (MacOSEnv): Remote macOS automation environment
        event_name (str): The calendar event title to search
        weekday (str): iCalendar day code (e.g., "MO", "TU", "WE", ...)
        start_hour (int | None): Optional start hour
        start_minute (int | None): Optional start minute
        end_hour (int | None): Optional end hour
        end_minute (int | None): Optional end minute

    Returns:
        bool: True if matching event found, False otherwise
    """
    env.connect_ssh()

    # Convert None to sentinel string for AppleScript comparison
    sh = "null" if start_hour is None else str(start_hour)
    sm = "null" if start_minute is None else str(start_minute)
    eh = "null" if end_hour is None else str(end_hour)
    em = "null" if end_minute is None else str(end_minute)

    apple_script = f"""
    set matched to false
    set debug_output to ""
    tell application "Calendar"
        repeat with c in calendars
            set theEvents to every event of c whose summary is "{event_name}"
            repeat with e in theEvents
                set startTime to start date of e
                set endTime to end date of e
                set start_hour to hours of startTime
                set start_min to minutes of startTime
                set end_hour to hours of endTime
                set end_min to minutes of endTime
                set recur to recurrence of e

                set check_start to (("{sh}" = "null") or (start_hour = {sh} and start_min = {sm}))
                set check_end to (("{eh}" = "null") or (end_hour = {eh} and end_min = {em}))
                set check_recur to (recur contains "FREQ=WEEKLY" and recur contains "BYDAY={weekday}")
                
                if check_start and check_end and check_recur then
                    set matched to true
                    set debug_output to debug_output & "✓ Matching event: " & summary of e & return
                end if
            end repeat
        end repeat
    end tell

    if matched then
        return "true__DEBUG__" & debug_output
    else
        return "false__DEBUG__" & debug_output
    end if
    """

    try:
        stdout, _ = env.run_command(f"osascript -e {shlex.quote(apple_script)}")
        logger.info(stdout)
        logger.info(_)
        output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        return output.startswith("true__")
    except Exception as e:
        logger.error(f"Failed to check calendar event: {e}")
        return False


def calendar_debug(
    env, event_name: str, start_hour: int = 10, start_minute: int = 0
) -> bool:
    env.connect_ssh()

    apple_script = f"""
    set matched to false
    set debug_output to ""
    tell application "Calendar"
        repeat with c in calendars
            set theEvents to every event of c whose summary is "{event_name}"
            repeat with e in theEvents
                set startTime to start date of e
                set start_hour to hours of startTime
                set start_min to minutes of startTime
                set eventNotes to properties of e
                return eventNotes
                set recur to recurrence of e

                -- Check time = 10:00 AM and recurrence contains "weekly"
                if start_hour = {start_hour} and start_min = {start_minute} and recur contains "FREQ=WEEKLY" and recur contains "BYDAY=MO" then
                    set matched to true
                    set debug_output to debug_output & "✓ Matching event found: " & summary of e & return
                end if
            end repeat
        end repeat
    end tell
    if matched then
        return "true__DEBUG__" & debug_output
    else
        return "false__DEBUG__" & debug_output
    end if
    """

    try:
        stdout, _ = env.run_command(f"osascript -e {shlex.quote(apple_script)}")

        output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        return output
    except Exception as e:
        logger.error(f"Failed to check calendar event: {e}")
        return False


# id:2A7C6C19-3DF7-41D2-A363-D006497BB934, recurrence:missing value, stamp date:date Thursday, May 15, 2025 at 3:36:55 AM, class:event, url:1111, end date:date Monday, May 12, 2025 at 7:15:00 AM, excluded dates:, description:hahaha, summary:test_note, location:missing value, allday event:false, start date:date Monday, May 12, 2025 at 6:15:00 AM, sequence:0, status:none


def calendar_check_calendar_with_at_least_3_events(env, calendar_name: str) -> bool:
    """
    Check if a calendar with the given name exists and has at least three events.

    :param env: MacOSEnv instance
    :param calendar_name: Name of the calendar to check (e.g., "group meeting")
    :return: True if calendar exists and contains >= 3 events, False otherwise
    """
    env.connect_ssh()

    apple_script = f"""
    set matched to false
    set event_count to 0
    tell application "Calendar"
        if (exists calendar "{calendar_name}") then
            set theCal to calendar "{calendar_name}"
            set theEvents to every event of theCal
            set event_count to count of theEvents
            if event_count ≥ 3 then
                set matched to true
            end if
        end if
    end tell
    if matched then
        return "true__DEBUG__event_count=" & event_count
    else
        return "false__DEBUG__event_count=" & event_count
    end if
    """

    try:
        stdout, _ = env.run_command(f"osascript -e '{apple_script}'")
        logger.info(stdout)
        logger.info(_)
        output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        return output.startswith("true__")
    except Exception as e:
        logger.error(f"Calendar check failed: {e}")
        return False


def calendar_check_calendar_contains_events(
    env, calendar_name: str, event_names: list[str]
) -> bool:
    """
    Check if a named calendar exists and contains all specified event names.

    Args:
        env (MacOSEnv): macOS automation environment
        calendar_name (str): Name of the calendar to check (e.g., "Work")
        event_names (list[str]): List of event titles to search for in the calendar

    Returns:
        bool: True if calendar exists and all specified events are present, else False
    """
    env.connect_ssh()

    # Construct AppleScript list of event names
    applescript_event_names = (
        "{" + ", ".join([f'"{name}"' for name in event_names]) + "}"
    )

    apple_script = f"""
    set matched to false
    set found_names to {{}}
    set required_names to {applescript_event_names}
    set missing_names to required_names

    tell application "Calendar"
        if exists calendar "{calendar_name}" then
            set theCal to calendar "{calendar_name}"
            set theEvents to every event of theCal
            repeat with e in theEvents
                set event_title to summary of e
                if required_names contains event_title and (event_title is not in found_names) then
                    copy (event_title as string) to end of found_names
                end if
            end repeat

            -- compute missing
            set missing_names to {{}}
            repeat with name in required_names
                if name is not in found_names then
                    copy (name as string) to end of missing_names
                end if
            end repeat

            if (count of missing_names = 0) then
                set matched to true
            end if
        end if
    end tell

    -- prepare debug output safely
    set AppleScript's text item delimiters to ", "
    set found_str to found_names as string
    set missing_str to missing_names as string
    set AppleScript's text item delimiters to ""

    if matched then
        return "true__DEBUG__found=" & found_str
    else
        return "false__DEBUG__missing=" & missing_str
    end if
    """

    try:
        stdout, _ = env.run_command(f"osascript -e {shlex.quote(apple_script)}")
        # logger.info(apple_script[1216:1250])
        # logger.info(_)
        output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        logger.info(f"[calendar_check_calendar_contains_events] Raw output: {output}")
        return output.startswith("true__")
    except Exception as e:
        logger.error(f"Calendar event list check failed: {e}")
        return False


if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()

    # Connect to Docker container
    macos_env.connect_ssh()

    value = calendar_debug(macos_env, "test_note")
    logger.info(value)

    import time

    time.sleep(3)
    macos_env.close_connection()
