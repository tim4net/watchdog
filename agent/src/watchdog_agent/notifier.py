"""KDE desktop notification integration."""

import subprocess
from dataclasses import dataclass
from enum import Enum


class Urgency(Enum):
    LOW = "low"
    NORMAL = "normal"
    CRITICAL = "critical"


@dataclass
class Notification:
    title: str
    body: str
    urgency: Urgency = Urgency.NORMAL
    icon: str = "dialog-information"
    timeout_ms: int = 10000  # 10 seconds
    app_name: str = "Watchdog Agent"


def send_notification(notification: Notification) -> bool:
    """Send a desktop notification using notify-send."""
    try:
        cmd = [
            "notify-send",
            "--app-name", notification.app_name,
            "--urgency", notification.urgency.value,
            "--icon", notification.icon,
            "--expire-time", str(notification.timeout_ms),
            notification.title,
            notification.body
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Failed to send notification: {e}")
        return False


def notify_update(topic: str, summary: str, url: str | None = None) -> bool:
    """Send a notification about a topic update."""
    body = summary
    if url:
        body += f"\n\n{url}"

    return send_notification(Notification(
        title=f"Update: {topic}",
        body=body,
        urgency=Urgency.NORMAL,
        icon="dialog-information",
        timeout_ms=15000
    ))


def notify_error(message: str) -> bool:
    """Send an error notification."""
    return send_notification(Notification(
        title="Watchdog Agent Error",
        body=message,
        urgency=Urgency.LOW,
        icon="dialog-warning",
        timeout_ms=5000
    ))


def notify_started() -> bool:
    """Send a notification that the agent has started."""
    return send_notification(Notification(
        title="Watchdog Agent",
        body="Monitoring started",
        urgency=Urgency.LOW,
        icon="dialog-information",
        timeout_ms=3000
    ))
