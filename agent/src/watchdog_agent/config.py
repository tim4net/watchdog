"""Configuration management for Watchdog Agent."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .agent import WatchTopic


@dataclass
class AgentConfig:
    """Main configuration for the watchdog agent."""
    # API settings
    anthropic_api_key: str | None = None

    # Behavior settings
    require_ac_power: bool = True
    idle_threshold_minutes: int = 5
    default_check_interval_hours: int = 24
    min_check_interval_minutes: int = 30  # Don't check more often than this

    # Topics to watch
    topics: list[WatchTopic] = field(default_factory=list)

    # Paths
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "watchdog-agent")
    config_dir: Path = field(default_factory=lambda: Path.home() / ".config" / "watchdog-agent")


def load_config(config_path: Path | None = None) -> AgentConfig:
    """Load configuration from file and environment."""
    config = AgentConfig()

    # Default config path
    if config_path is None:
        config_path = config.config_dir / "config.yaml"

    # Load from file if exists
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
                _apply_config_data(config, data)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")

    # Override with environment variables
    if api_key := os.environ.get("ANTHROPIC_API_KEY"):
        config.anthropic_api_key = api_key

    if os.environ.get("WATCHDOG_REQUIRE_AC", "").lower() == "false":
        config.require_ac_power = False

    return config


def _apply_config_data(config: AgentConfig, data: dict[str, Any]):
    """Apply configuration data from parsed YAML."""
    if "anthropic_api_key" in data:
        config.anthropic_api_key = data["anthropic_api_key"]

    if "require_ac_power" in data:
        config.require_ac_power = bool(data["require_ac_power"])

    if "idle_threshold_minutes" in data:
        config.idle_threshold_minutes = int(data["idle_threshold_minutes"])

    if "default_check_interval_hours" in data:
        config.default_check_interval_hours = int(data["default_check_interval_hours"])

    if "topics" in data:
        for topic_data in data["topics"]:
            topic = WatchTopic(
                name=topic_data["name"],
                description=topic_data.get("description", ""),
                search_queries=topic_data.get("search_queries", []),
                urls_to_check=topic_data.get("urls_to_check", []),
                check_interval_hours=topic_data.get(
                    "check_interval_hours",
                    config.default_check_interval_hours
                )
            )
            config.topics.append(topic)


def save_default_config(config_path: Path):
    """Save a default configuration file with examples."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    default_config = """# Watchdog Agent Configuration

# Anthropic API key (or set ANTHROPIC_API_KEY environment variable)
# anthropic_api_key: sk-ant-...

# Only run checks when on AC power
require_ac_power: true

# Only notify when user has been active within this many minutes
idle_threshold_minutes: 5

# Default interval between checks for each topic
default_check_interval_hours: 24

# Topics to monitor
topics:
  - name: "HP ZBook Battery Charge Limit"
    description: "Monitor for HP ZBook Ultra G1a battery charge threshold/limit support in BIOS or Linux"
    search_queries:
      - "HP ZBook Ultra G1a battery charge limit"
      - "HP ZBook G1a BIOS update battery"
      - "HP laptop Linux charge threshold support"
    urls_to_check:
      - "https://h30434.www3.hp.com/t5/Notebook-Software-and-How-To-Questions/Limit-Battery-Charge-to-80/td-p/8380809"
    check_interval_hours: 48

  # Example: Monitor for software updates
  # - name: "Example Software Release"
  #   description: "Watch for new releases of Example Software"
  #   search_queries:
  #     - "example software release notes"
  #     - "example software changelog"
  #   urls_to_check:
  #     - "https://example.com/releases"
  #   check_interval_hours: 24
"""

    config_path.write_text(default_config)
    print(f"Created default config at: {config_path}")
