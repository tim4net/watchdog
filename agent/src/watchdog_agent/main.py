"""Main entry point for Watchdog Agent."""

import argparse
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .agent import WatchdogAgent, WatchTopic
from .config import load_config, save_default_config, AgentConfig
from .monitors import should_run_check, is_on_ac_power
from .notifier import notify_update, notify_error, notify_started

console = Console()

# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    console.print("\n[yellow]Shutdown requested, finishing current task...[/yellow]")


def check_single_topic(agent: WatchdogAgent, topic: WatchTopic, verbose: bool = False) -> bool:
    """Check a single topic and notify if there's an update."""
    if verbose:
        console.print(f"[blue]Checking:[/blue] {topic.name}")

    result = agent.check_topic(topic)

    if verbose:
        status = "[green]UPDATE[/green]" if result.has_update else "[dim]No update[/dim]"
        console.print(f"  {status}: {result.summary}")

    if result.has_update and result.confidence > 0.3:
        notify_update(topic.name, result.summary, result.source_url)
        return True

    return False


def run_daemon(config: AgentConfig, verbose: bool = False):
    """Run the agent as a background daemon."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not config.anthropic_api_key:
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not set")
        console.print("Set it in config or environment: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    if not config.topics:
        console.print("[yellow]Warning:[/yellow] No topics configured")
        console.print(f"Edit config at: {config.config_dir / 'config.yaml'}")
        sys.exit(1)

    agent = WatchdogAgent(api_key=config.anthropic_api_key, cache_dir=config.cache_dir)

    # Track last check time for each topic
    last_checks: dict[str, datetime] = {}

    console.print(f"[green]Watchdog Agent started[/green] - monitoring {len(config.topics)} topic(s)")
    notify_started()

    try:
        while not _shutdown_requested:
            # Check if we should run
            can_run, reason = should_run_check(
                require_ac=config.require_ac_power,
                idle_threshold_minutes=config.idle_threshold_minutes
            )

            if not can_run:
                if verbose:
                    console.print(f"[dim]Skipping checks: {reason}[/dim]")
                time.sleep(60)  # Check again in a minute
                continue

            # Check each topic if enough time has passed
            now = datetime.now()
            for topic in config.topics:
                if _shutdown_requested:
                    break

                last_check = last_checks.get(topic.name)
                interval = timedelta(hours=topic.check_interval_hours)

                # Ensure minimum interval
                min_interval = timedelta(minutes=config.min_check_interval_minutes)
                interval = max(interval, min_interval)

                if last_check is None or (now - last_check) >= interval:
                    try:
                        check_single_topic(agent, topic, verbose)
                        last_checks[topic.name] = now
                    except Exception as e:
                        console.print(f"[red]Error checking {topic.name}:[/red] {e}")

            # Sleep before next round of checks
            time.sleep(60)

    finally:
        agent.close()
        console.print("[yellow]Watchdog Agent stopped[/yellow]")


def run_once(config: AgentConfig, topic_name: str | None = None):
    """Run a single check for all topics or a specific topic."""
    if not config.anthropic_api_key:
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not set")
        sys.exit(1)

    topics = config.topics
    if topic_name:
        topics = [t for t in topics if t.name.lower() == topic_name.lower()]
        if not topics:
            console.print(f"[red]Topic not found:[/red] {topic_name}")
            sys.exit(1)

    agent = WatchdogAgent(api_key=config.anthropic_api_key, cache_dir=config.cache_dir)

    try:
        for topic in topics:
            console.print(f"\n[bold]Checking: {topic.name}[/bold]")
            result = agent.check_topic(topic)

            if result.has_update:
                console.print(f"[green]UPDATE FOUND![/green]")
            else:
                console.print(f"[dim]No significant updates[/dim]")

            console.print(f"Summary: {result.summary}")
            console.print(f"Confidence: {result.confidence:.0%}")
            if result.source_url:
                console.print(f"Source: {result.source_url}")

    finally:
        agent.close()


def list_topics(config: AgentConfig):
    """List configured topics."""
    if not config.topics:
        console.print("[yellow]No topics configured[/yellow]")
        return

    table = Table(title="Watched Topics")
    table.add_column("Name", style="cyan")
    table.add_column("Interval", style="green")
    table.add_column("Queries", style="dim")

    for topic in config.topics:
        table.add_row(
            topic.name,
            f"{topic.check_interval_hours}h",
            str(len(topic.search_queries))
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="AI agent that monitors topics and notifies you of updates"
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to config file"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run as background daemon")

    # check command
    check_parser = subparsers.add_parser("check", help="Run a single check")
    check_parser.add_argument("--topic", "-t", help="Specific topic to check")

    # list command
    list_parser = subparsers.add_parser("list", help="List configured topics")

    # init command
    init_parser = subparsers.add_parser("init", help="Create default config file")

    # status command
    status_parser = subparsers.add_parser("status", help="Show current status")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    if args.command == "init":
        config_path = args.config or (config.config_dir / "config.yaml")
        if config_path.exists():
            console.print(f"[yellow]Config already exists:[/yellow] {config_path}")
        else:
            save_default_config(config_path)
        return

    if args.command == "list":
        list_topics(config)
        return

    if args.command == "status":
        console.print(f"Config dir: {config.config_dir}")
        console.print(f"Cache dir: {config.cache_dir}")
        console.print(f"Topics: {len(config.topics)}")
        console.print(f"AC power: {'[green]Connected[/green]' if is_on_ac_power() else '[yellow]Battery[/yellow]'}")
        console.print(f"API key: {'[green]Set[/green]' if config.anthropic_api_key else '[red]Not set[/red]'}")
        return

    if args.command == "check":
        run_once(config, args.topic)
        return

    if args.command == "daemon" or args.command is None:
        run_daemon(config, args.verbose)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
