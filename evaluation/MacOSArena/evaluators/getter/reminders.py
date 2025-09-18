import paramiko
from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
from pathlib import Path
import json
import time
from dateutil import parser as dateparser
from bs4 import BeautifulSoup
import datetime
import shlex

script_dir = Path(__file__).resolve().parent.parent

logger = ProjectLogger(log_dir=script_dir / "logs")


def reminders_debug(env, reminder_name="111") -> bool:
    env.connect_ssh()

    try:
        stdout, _ = env.run_command("date '+%Y-%m-%d'")
        current_date_str = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        current_date = datetime.datetime.strptime(current_date_str, "%Y-%m-%d").date()
        current_iso_week = current_date.isocalendar()[1]
    except Exception as e:
        logger.error(f"Failed to get current date from container: {e}")
        return False

    apple_script = f"""
    tell application "Reminders"
        set workReminder to first reminder whose name is "{reminder_name}"
        set workDueDate to properties of workReminder
    end tell
    return workDueDate
    """
    try:
        stdout, stderr = env.run_command(f"osascript -e '{apple_script}'")
        logger.info(stderr)
        reminder_info = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        return reminder_info
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False


def reminders_get_body_by_name(env, reminder_name: str) -> str:
    """
    Get the note (body) content of a reminder with a specific name.

    :param env: MacOSEnv instance
    :param reminder_name: The exact name of the reminder
    :return: The body content (note) of the reminder, or "" if not found
    """
    env.connect_ssh()

    apple_script = f"""
    try
        tell application "Reminders"
            set r to first reminder whose name is "{reminder_name}"
            return "__BODY__" & body of r
        end tell
    on error errMsg
        return "__ERROR__" & errMsg
    end try
    """

    safe_code = shlex.quote(apple_script.strip())
    stdout, _ = env.run_command(f"osascript -e {safe_code}")
    output = (
        stdout.read().decode().strip() if hasattr(stdout, "read") else stdout.strip()
    )

    if output.startswith("__BODY__"):
        return output.replace("__BODY__", "").strip()
    elif output.startswith("__ERROR__"):
        logger.error(f"AppleScript reminder body error: {output}")
        return ""
    else:
        logger.error(f"Unexpected output when getting reminder body: {output}")
        return ""


def reminders_check_work_due_next_week(env, reminder_name="work") -> bool:
    """
    Check if a reminder named 'work' exists and its due date is in the next calendar week.
    :param env: MacOSEnv instance
    :return: True if found and valid, False otherwise
    """
    env.connect_ssh()

    try:
        stdout, _ = env.run_command("date '+%Y-%m-%d'")
        current_date_str = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        current_date = datetime.datetime.strptime(current_date_str, "%Y-%m-%d").date()
        current_iso_week = current_date.isocalendar()[1]
    except Exception as e:
        logger.error(f"Failed to get current date from container: {e}")
        return False

    apple_script = f"""
    tell application "Reminders"
        set workReminder to first reminder whose name is "{reminder_name}"
        set workDueDate to due date of workReminder
    end tell
    return workDueDate as string
    """
    try:
        stdout, stderr = env.run_command(f"osascript -e '{apple_script}'")
        due_str = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        logger.info(f"Work reminder due date string: {due_str}")
        due_date = dateparser.parse(due_str).date()
        due_week = due_date.isocalendar()[1]
        return due_week == current_iso_week + 1
    except Exception as e:
        logger.error(f"Failed to retrieve or parse due date: {e}")
        return False


def reminders_check_due_time(
    env, reminder_name: str = "work", target_hour: int = 23, target_minute: int = 59
) -> bool:
    """
    Check whether a reminder with a specific name is set to a target time (e.g., 3:00 PM).

    :param env: MacOSEnv instance
    :param reminder_name: The name of the reminder to check
    :param target_hour: Target hour (24-hour format)
    :param target_minute: Target minute
    :return: True if due time matches exactly, False otherwise
    """
    env.connect_ssh()

    apple_script = f"""
    tell application "Reminders"
        set matchedReminder to first reminder whose name is "{reminder_name}"
        set dueTime to due date of matchedReminder
    end tell
    return dueTime as string
    """

    try:
        stdout, stderr = env.run_command(f"osascript -e '{apple_script}'")

        raw = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        logger.info(f"Due time for reminder '{reminder_name}': {raw}")
        dt = dateparser.parse(raw)
        return dt.hour == target_hour and dt.minute == target_minute
    except Exception as e:
        logger.error(f"Failed to check due time for reminder '{reminder_name}': {e}")
        return False


def reminders_get_due_year(
    env, reminder_name: str, list_name: str = "Reminders"
) -> int:
    """
    Get the due year of a specific reminder in a specified list.

    :param env: MacOSEnv instance
    :param reminder_name: The name of the reminder to check
    :param list_name: The name of the reminder list
    :return: Year of due date if found, else -1
    """
    env.connect_ssh()

    apple_script = f"""
    tell application "Reminders"
        set theList to list "{list_name}"
        set matchedReminder to first reminder of theList whose name is "{reminder_name}"
        set dueTime to due date of matchedReminder
    end tell
    return dueTime as string
    """

    try:
        stdout, _ = env.run_command(f"osascript -e '{apple_script.strip()}'")
        raw = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        logger.info(f"Raw due date for reminder '{reminder_name}': {raw}")
        dt = dateparser.parse(raw)
        return dt.year if dt else -1
    except Exception as e:
        logger.error(f"Failed to retrieve due year for reminder '{reminder_name}': {e}")
        return -1


def reminders_check_all_completed_with_expected_items(
    env, list_name: str = "Groceries", preset_items: list[str] = None
) -> bool:
    """
    Check whether all reminders in the specified list are marked as completed,
    and that the list contains all required preset items.

    :param env: MacOSEnv instance
    :param list_name: The name of the reminder list
    :param preset_items: A list of expected item names (must be present and completed)
    :return: True if all items are completed AND all preset items are present
    """
    # if preset_items is None:
    #     preset_items = ["Milk", "Eggs", "Bread", "Apples", "Bananas", "Chicken Breast", "Rice", "Toilet Paper"]

    env.connect_ssh()

    # AppleScript to get names and completed status
    apple_script = f"""
    tell application "Reminders"
        set theList to list "{list_name}"
        set remindersInList to reminders of theList
        set resultList to ""
        repeat with r in remindersInList
            set resultList to resultList & name of r & "||" & completed of r & ";;"
        end repeat
    end tell
    return resultList
    """

    try:
        stdout, _ = env.run_command(f"osascript -e '{apple_script.strip()}'")
        raw_output = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )

        reminders = [r.strip() for r in raw_output.split(";;") if r.strip()]
        parsed = {}
        for entry in reminders:
            name, completed = entry.split("||")
            parsed[name.strip()] = completed.strip().lower() == "true"

        # Check: all preset items must exist and be completed
        if preset_items:
            for item in preset_items:
                if item not in parsed:
                    logger.warning(f"Missing expected item: {item}")
                    return False
                if not parsed[item]:
                    logger.warning(f"Item not completed: {item}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Failed to validate reminders in '{list_name}': {e}")
        return False


def reminders_check_on_date(
    env, reminder_name: str, date_str: str = "20250512"
) -> bool:
    """
    Check if a reminder with a specific name exists and is due on a given date.

    :param env: MacOSEnv instance
    :param reminder_name: The name of the reminder to check
    :param date_str: The date string in "YYYYMMDD" format
    :return: True if the reminder exists and is due on that date, False otherwise
    """
    env.connect_ssh()

    # Format input date to compare (date only, ignore time)
    try:
        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        logger.error(f"Invalid date format: {date_str}. Use 'YYYYMMDD'.")
        return False

    apple_script = f"""
    tell application "Reminders"
        set matchedReminder to first reminder whose name is "{reminder_name}"
        set dueDate to due date of matchedReminder
    end tell
    return dueDate as string
    """

    try:
        stdout, stderr = env.run_command(f"osascript -e '{apple_script}'")
        raw = (
            stdout.read().decode().strip()
            if hasattr(stdout, "read")
            else stdout.strip()
        )
        logger.info(f"Due date for reminder '{reminder_name}': {raw}")

        dt = dateparser.parse(raw)
        if dt:
            return dt.date() == target_date
        else:
            logger.warning(f"Could not parse date from reminder output: {raw}")
            return False
    except Exception as e:
        logger.error(f"Failed to check due date for reminder '{reminder_name}': {e}")
        return False


if __name__ == "__main__":
    # Initialize the environment with default config
    macos_env = MacOSEnv()

    # Connect to Docker container
    macos_env.connect_ssh()

    value = reminders_get_body_by_name(macos_env, "111")
    logger.info(value)
    # value = reminders_check_due_time(macos_env)
    # logger.info(value)
    import time

    time.sleep(3)
    macos_env.close_connection()
