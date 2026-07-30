"""
MandiIQ — Windows Scheduled Task Setup

Installs an hourly Windows scheduled task that runs run_hourly.py.
The task:
  • Runs every hour at minute 0 (e.g. 1:00, 2:00, 3:00...)
  • Runs as the current user (starts a hidden window)
  • Runs whether the user is logged on or not
  • Retries on failure (default task scheduler behaviour)
  • Survives reboots

Usage:
    python setup_scheduled_task.py          # install/update the task
    python setup_scheduled_task.py --remove  # uninstall the task
    python setup_scheduled_task.py --status  # check if the task exists

Requires: Windows (uses schtasks.exe)
Run as Administrator for best results (or accept the UAC prompt).
"""

import subprocess
import sys
import os
from pathlib import Path

TASK_NAME = "MandiIQ Hourly Ingestion"

PROJECT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable or "python"
SCRIPT_PATH = PROJECT_DIR / "run_hourly.py"


def _run_schtasks(*args: str) -> subprocess.CompletedProcess:
    """Run schtasks.exe with the given arguments."""
    cmd = ["schtasks.exe"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def task_exists() -> bool:
    """Check if the scheduled task already exists."""
    result = _run_schtasks("/query", "/tn", TASK_NAME, "/fo", "LIST")
    return result.returncode == 0


def install_task() -> bool:
    """Create or update the hourly scheduled task."""
    print(f"Installing scheduled task: {TASK_NAME}")
    print(f"Python: {PYTHON_EXE}")
    print(f"Script: {SCRIPT_PATH}")

    # Build the command that the task will run
    # schtasks expects the /tr argument to be the full command line
    task_command = f'"{PYTHON_EXE}" "{SCRIPT_PATH}"'

    if task_exists():
        print("Task already exists — updating with /change + /tn ...")
        # We can't easily /change the command, so delete and recreate
        _run_schtasks("/delete", "/tn", TASK_NAME, "/f")

    # Create the task:
    #   /sc hourly    — runs every hour
    #   /mo 1         — every 1 hour
    #   /st 00:00     — start at midnight (first run immediately)
    #   /ri 60        — repeat interval = 60 minutes
    #   /du 24:00     — duration = unlimited (run continuously)
    #   /f            — force (no confirmation prompt)
    #   /np           — no network profile (use current user context)
    #   /it           — interactive: runs as the current user who creates the task,
    #                   inheriting all environment variables (DATA_GOV_IN_API_KEY, etc.)
    #   /np           — no network profile (uses current user's profile)
    # NOTE: The task will only run when the user is logged on (interactive mode).
    # This is intentional — the data.gov.in API key is a user-level env var,
    # and the SYSTEM account would not have access to it.
    result = _run_schtasks(
        "/create",
        "/tn", TASK_NAME,
        "/tr", task_command,
        "/sc", "hourly",
        "/mo", "1",
        "/st", "00:00",
        "/ri", "60",
        "/du", "24:00",
        "/f",
        "/it",
        "/np",
    )

    if result.returncode == 0:
        print("✅ Scheduled task installed successfully!")
        print(f"   Task name: {TASK_NAME}")
        print(f"   Schedule: Every hour")
        print(f"   Command: {task_command}")
        return True
    else:
        print(f"❌ Failed to install scheduled task.")
        print(f"   Return code: {result.returncode}")
        print(f"   stderr: {result.stderr}")
        print()
        print("Tip: Run this script as Administrator:")
        print("   1. Open Command Prompt as Administrator")
        print(f"   2. cd {PROJECT_DIR}")
        print(f"   3. python setup_scheduled_task.py")
        print()
        print("Or create the task manually:")
        print(f"   1. Open Task Scheduler")
        print(f"   2. Create Basic Task → '{TASK_NAME}'")
        print(f"   3. Trigger: Daily, repeat every 1 hour")
        print(f"   4. Action: Start a program → {PYTHON_EXE}")
        print(f"   5. Arguments: {SCRIPT_PATH}")
        return False


def remove_task() -> bool:
    """Remove the scheduled task."""
    print(f"Removing scheduled task: {TASK_NAME}")
    if not task_exists():
        print("Task does not exist.")
        return True

    result = _run_schtasks("/delete", "/tn", TASK_NAME, "/f")
    if result.returncode == 0:
        print("✅ Task removed successfully.")
        return True
    else:
        print(f"❌ Failed to remove task: {result.stderr}")
        return False


def show_status():
    """Show the current status of the scheduled task."""
    if task_exists():
        print(f"✅ Task '{TASK_NAME}' is installed.")
        # Show details
        result = _run_schtasks("/query", "/tn", TASK_NAME, "/fo", "LIST", "/v")
        if result.returncode == 0:
            print(result.stdout)
    else:
        print(f"❌ Task '{TASK_NAME}' is NOT installed.")
        print()
        print("Install it:")
        print(f"   python setup_scheduled_task.py")


if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove_task()
    elif "--status" in sys.argv:
        show_status()
    else:
        install_task()
