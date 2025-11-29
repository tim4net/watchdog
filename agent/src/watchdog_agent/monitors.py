"""System state monitors for power and user activity."""

import subprocess
from pathlib import Path


def is_on_ac_power() -> bool:
    """Check if the system is running on AC power."""
    ac_paths = list(Path("/sys/class/power_supply").glob("AC*")) + \
               list(Path("/sys/class/power_supply").glob("ACAD*"))

    for ac_path in ac_paths:
        online_file = ac_path / "online"
        if online_file.exists():
            try:
                return online_file.read_text().strip() == "1"
            except (IOError, PermissionError):
                continue

    # Fallback: assume AC if we can't detect
    return True


def get_idle_time_ms() -> int:
    """Get user idle time in milliseconds using KDE's idle detection."""
    try:
        # Try KDE's idle time via D-Bus
        result = subprocess.run(
            ["qdbus", "org.kde.screensaver", "/ScreenSaver", "GetSessionIdleTime"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) * 1000  # Convert to ms
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass

    try:
        # Fallback: use xprintidle if available
        result = subprocess.run(
            ["xprintidle"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass

    # Can't detect idle time, assume active
    return 0


def is_user_active(idle_threshold_minutes: int = 5) -> bool:
    """Check if user has been active within the threshold."""
    idle_ms = get_idle_time_ms()
    threshold_ms = idle_threshold_minutes * 60 * 1000
    return idle_ms < threshold_ms


def should_run_check(require_ac: bool = True, idle_threshold_minutes: int = 5) -> tuple[bool, str]:
    """
    Determine if we should run a check based on system state.

    Returns:
        Tuple of (should_run, reason_if_not)
    """
    if require_ac and not is_on_ac_power():
        return False, "On battery power"

    if not is_user_active(idle_threshold_minutes):
        return False, f"User idle for >{idle_threshold_minutes} minutes"

    return True, "OK"
