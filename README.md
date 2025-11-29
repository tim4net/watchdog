# Watchdog

AI-powered topic monitoring system with desktop notifications. Uses Claude to intelligently search the web and notify you when topics you care about have updates.

## Components

### watchdog-agent

Background daemon that monitors topics and sends KDE desktop notifications.

**Features:**
- Monitors configurable topics using Claude AI + web search
- KDE desktop notifications when updates are found
- Power-aware: only runs on AC power (configurable)
- Activity-aware: silent when you're idle
- Systemd user service for autostart

### watchdog-manager

Kirigami GUI for managing topics with AI chat assistance.

**Features:**
- Chat interface to add topics using natural language
- Claude AI expands your requests into smart search queries
- Manual topic editor for full control
- Force check topics (bypasses power/idle restrictions)
- Real-time sync with watchdog-agent config

## Installation

### Prerequisites

```bash
# Fedora/KDE
sudo dnf install python3-pyside6 python3-pip
```

### Install both components

```bash
# Install the agent
cd agent
pip install -e .

# Install the manager
cd ../manager
pip install -e .
```

### Configuration

1. Set your Anthropic API key:
   ```bash
   # Add to /etc/environment for system-wide access
   sudo bash -c 'echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> /etc/environment'
   ```

2. Initialize config:
   ```bash
   watchdog-agent init
   ```

3. Start the background service:
   ```bash
   cp agent/watchdog-agent.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now watchdog-agent
   ```

4. Install desktop entry for manager:
   ```bash
   cp manager/watchdog-manager.desktop ~/.local/share/applications/
   ```

## Usage

### CLI (watchdog-agent)

```bash
watchdog-agent status      # Show status
watchdog-agent list        # List topics
watchdog-agent check       # Run checks now
watchdog-agent daemon -v   # Run in foreground (verbose)
```

### GUI (watchdog-manager)

Launch from KDE menu or run `watchdog-manager`.

**Adding topics via chat:**
- "Watch for Fedora 44 release"
- "Monitor AMD GPU driver updates"
- "Track when KDE Plasma 6.2 is released"

**Manual topic management:**
- Click "Add Topic" to create manually
- Click any topic to edit
- Swipe left for Check/Edit/Remove actions

## Configuration File

Topics are stored in `~/.config/watchdog-agent/config.yaml`:

```yaml
require_ac_power: true
idle_threshold_minutes: 5

topics:
  - name: "Fedora 44 Release"
    description: "Monitor for Fedora 44 release announcements"
    search_queries:
      - "Fedora 44 release date 2025"
      - "Fedora 44 beta announcement"
    urls_to_check:
      - "https://fedoramagazine.org/"
    check_interval_hours: 48
```

## License

MIT
