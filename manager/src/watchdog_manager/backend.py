"""Backend for Watchdog Manager - handles Claude API and topic management."""

import json
import os
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QObject, Signal, Slot, Property, QAbstractListModel, Qt, QModelIndex
import anthropic


SYSTEM_PROMPT = """You are a helpful assistant for managing a topic monitoring system called "Watchdog Agent".
The user wants to monitor various topics for updates (software releases, hardware support, news, etc.).

When the user wants to add a topic to monitor, you should EXPAND their request intelligently:
1. Create a concise, descriptive name
2. Write a clear description of what to monitor
3. Generate 2-4 SMART search queries that would find relevant updates (include year like "2024 2025" for recency)
4. Suggest specific URLs to check if you know relevant official sources (release pages, forums, etc.)
5. Suggest an appropriate check interval (24h for fast-moving topics, 48-72h for slower ones)

IMPORTANT: First explain to the user what you're setting up, then output the JSON on its own line.

Example response:
"I'll set up monitoring for Fedora 44. I'll search for release announcements, beta news, and check the official Fedora Magazine.

```json
{"action": "add_topic", "topic": {"name": "Fedora 44 Release", "description": "Monitor for Fedora 44 release date and announcements", "search_queries": ["Fedora 44 release date 2024 2025", "Fedora 44 beta announcement", "Fedora 44 schedule"], "urls_to_check": ["https://fedoramagazine.org/"], "check_interval_hours": 48}}
```"

When listing topics, respond with:
```json
{"action": "list_topics"}
```

When removing a topic, respond with:
```json
{"action": "remove_topic", "name": "Topic Name"}
```

For general questions or clarifications, respond naturally without JSON.
Always be concise and helpful. If the user's request is unclear, ask for clarification."""


class TopicListModel(QAbstractListModel):
    """Model for displaying topics in QML ListView."""

    NameRole = Qt.UserRole + 1
    DescriptionRole = Qt.UserRole + 2
    IntervalRole = Qt.UserRole + 3
    QueriesRole = Qt.UserRole + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._topics: list[dict] = []

    def roleNames(self):
        return {
            self.NameRole: b"name",
            self.DescriptionRole: b"description",
            self.IntervalRole: b"interval",
            self.QueriesRole: b"queries",
        }

    def rowCount(self, parent=QModelIndex()):
        return len(self._topics)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._topics):
            return None

        topic = self._topics[index.row()]

        if role == self.NameRole:
            return topic.get("name", "")
        elif role == self.DescriptionRole:
            return topic.get("description", "")
        elif role == self.IntervalRole:
            return f"{topic.get('check_interval_hours', 24)}h"
        elif role == self.QueriesRole:
            return ", ".join(topic.get("search_queries", []))

        return None

    def setTopics(self, topics: list[dict]):
        self.beginResetModel()
        self._topics = topics
        self.endResetModel()


class ChatBackend(QObject):
    """Backend handling Claude API and topic management."""

    messageReceived = Signal(str, bool)  # message, isUser
    topicsChanged = Signal()
    errorOccurred = Signal(str)
    busyChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_path = Path.home() / ".config" / "watchdog-agent" / "config.yaml"
        self._topics: list[dict] = []
        self._topic_model = TopicListModel(self)
        self._busy = False
        self._conversation: list[dict] = []

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key and api_key != "sk-ant-YOUR-KEY-HERE":
            self._client = anthropic.Anthropic(api_key=api_key)
        else:
            self._client = None

        self._load_config()

    def _get_busy(self) -> bool:
        return self._busy

    def _set_busy(self, value: bool):
        if self._busy != value:
            self._busy = value
            self.busyChanged.emit()

    busy = Property(bool, _get_busy, notify=busyChanged)

    @Property(QObject, constant=True)
    def topicModel(self):
        return self._topic_model

    def _load_config(self):
        """Load topics from config file."""
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    data = yaml.safe_load(f) or {}
                    self._topics = data.get("topics", [])
                    self._topic_model.setTopics(self._topics)
            except Exception as e:
                self.errorOccurred.emit(f"Failed to load config: {e}")

    def _save_config(self):
        """Save topics to config file."""
        try:
            # Load existing config to preserve other settings
            if self._config_path.exists():
                with open(self._config_path) as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}

            data["topics"] = self._topics

            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            self._topic_model.setTopics(self._topics)
            self.topicsChanged.emit()

        except Exception as e:
            self.errorOccurred.emit(f"Failed to save config: {e}")

    def _add_topic(self, topic: dict) -> str:
        """Add a new topic."""
        # Check for duplicate
        for existing in self._topics:
            if existing.get("name", "").lower() == topic.get("name", "").lower():
                return f"Topic '{topic['name']}' already exists."

        self._topics.append(topic)
        self._save_config()
        return f"Added topic: {topic['name']}"

    def _remove_topic(self, name: str) -> str:
        """Remove a topic by name."""
        for i, topic in enumerate(self._topics):
            if topic.get("name", "").lower() == name.lower():
                self._topics.pop(i)
                self._save_config()
                return f"Removed topic: {name}"
        return f"Topic not found: {name}"

    def _list_topics(self) -> str:
        """List all topics."""
        if not self._topics:
            return "No topics configured yet. Tell me what you'd like to monitor!"

        lines = ["**Current topics:**\n"]
        for topic in self._topics:
            lines.append(f"• **{topic['name']}** ({topic.get('check_interval_hours', 24)}h)")
            lines.append(f"  {topic.get('description', '')}\n")
        return "\n".join(lines)

    def _extract_json(self, text: str) -> dict | None:
        """Extract JSON object from text, handling nested structures."""
        import re

        # Try to find JSON in code blocks first
        code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find a JSON object by matching braces
        start = text.find('{"action"')
        if start == -1:
            start = text.find('{ "action"')
        if start == -1:
            return None

        # Count braces to find the end
        depth = 0
        end = start
        for i, char in enumerate(text[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        return None

    def _process_ai_response(self, response: str) -> str:
        """Process AI response and execute any actions."""
        data = self._extract_json(response)

        if data:
            action = data.get("action")

            if action == "add_topic" and "topic" in data:
                topic = data["topic"]
                result = self._add_topic(topic)
                # Show the user what was configured
                details = [
                    f"**{result}**\n",
                    f"**Description:** {topic.get('description', 'N/A')}",
                    f"**Search queries:**"
                ]
                for q in topic.get("search_queries", []):
                    details.append(f"  • {q}")
                if topic.get("urls_to_check"):
                    details.append("**URLs to check:**")
                    for u in topic["urls_to_check"]:
                        details.append(f"  • {u}")
                details.append(f"**Check interval:** {topic.get('check_interval_hours', 24)} hours")

                # Include AI's explanation if present
                explanation = response.split('```')[0].strip() if '```' in response else ""
                if explanation:
                    return explanation + "\n\n" + "\n".join(details)
                return "\n".join(details)

            elif action == "remove_topic" and "name" in data:
                return self._remove_topic(data["name"])
            elif action == "list_topics":
                return self._list_topics()

        # Return original response if no action found
        return response

    @Slot(str)
    def sendMessage(self, message: str):
        """Send a message to Claude and get a response."""
        if not message.strip():
            return

        if not self._client:
            self.errorOccurred.emit("API key not configured. Set ANTHROPIC_API_KEY environment variable.")
            return

        # Emit user message
        self.messageReceived.emit(message, True)

        self._set_busy(True)

        try:
            # Add to conversation
            self._conversation.append({"role": "user", "content": message})

            # Keep conversation manageable
            if len(self._conversation) > 20:
                self._conversation = self._conversation[-20:]

            # Add context about current topics
            context = f"\n\nCurrent topics: {json.dumps([t['name'] for t in self._topics])}"

            response = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=SYSTEM_PROMPT + context,
                messages=self._conversation
            )

            ai_message = response.content[0].text

            # Process any actions in the response
            result = self._process_ai_response(ai_message)

            # Add AI response to conversation
            self._conversation.append({"role": "assistant", "content": ai_message})

            # Emit processed result
            self.messageReceived.emit(result, False)

        except Exception as e:
            self.errorOccurred.emit(str(e))

        finally:
            self._set_busy(False)

    @Slot()
    def refreshTopics(self):
        """Reload topics from config."""
        self._load_config()

    @Slot(str)
    def removeTopic(self, name: str):
        """Remove a topic directly."""
        result = self._remove_topic(name)
        self.messageReceived.emit(result, False)

    @Slot()
    def checkAllTopics(self):
        """Force check all topics now (ignores power/idle state)."""
        if not self._topics:
            self.messageReceived.emit("No topics to check.", False)
            return

        self._set_busy(True)
        self.messageReceived.emit("Checking all topics...", False)

        try:
            # Import watchdog agent
            from watchdog_agent.agent import WatchdogAgent, WatchTopic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key or api_key == "sk-ant-YOUR-KEY-HERE":
                self.errorOccurred.emit("API key not configured")
                return

            agent = WatchdogAgent(api_key=api_key)

            results = []
            for topic_data in self._topics:
                topic = WatchTopic(
                    name=topic_data["name"],
                    description=topic_data.get("description", ""),
                    search_queries=topic_data.get("search_queries", []),
                    urls_to_check=topic_data.get("urls_to_check", []),
                    check_interval_hours=topic_data.get("check_interval_hours", 24)
                )

                result = agent.check_topic(topic)

                if result.has_update:
                    results.append(f"**{topic.name}**: {result.summary}")
                else:
                    results.append(f"**{topic.name}**: No updates")

            agent.close()

            if results:
                self.messageReceived.emit("\n\n".join(results), False)
            else:
                self.messageReceived.emit("All checks complete. No updates found.", False)

        except ImportError:
            self.errorOccurred.emit("watchdog-agent not installed. Run: pip install -e ~/code/apps/watchdog-agent")
        except Exception as e:
            self.errorOccurred.emit(f"Check failed: {e}")
        finally:
            self._set_busy(False)

    @Slot(str, str, str, str, int)
    def addTopicManual(self, name: str, description: str,
                       queries_text: str, urls_text: str, interval: int):
        """Add a new topic manually from the dialog."""
        if not name.strip():
            self.errorOccurred.emit("Topic name is required")
            return

        # Parse text areas into lists
        queries = [q.strip() for q in queries_text.split("\n") if q.strip()]
        urls = [u.strip() for u in urls_text.split("\n") if u.strip()]

        topic = {
            "name": name.strip(),
            "description": description.strip(),
            "search_queries": queries,
            "urls_to_check": urls,
            "check_interval_hours": interval
        }

        result = self._add_topic(topic)
        self.messageReceived.emit(result, False)

    @Slot(str, result="QVariant")
    def getTopicDetails(self, name: str):
        """Get full topic details for editing."""
        for topic in self._topics:
            if topic.get("name", "").lower() == name.lower():
                return {
                    "name": topic.get("name", ""),
                    "description": topic.get("description", ""),
                    "search_queries": topic.get("search_queries", []),
                    "urls_to_check": topic.get("urls_to_check", []),
                    "check_interval_hours": topic.get("check_interval_hours", 24)
                }
        return None

    @Slot(str, str, str, str, str, int)
    def updateTopic(self, original_name: str, name: str, description: str,
                    queries_text: str, urls_text: str, interval: int):
        """Update an existing topic."""
        # Parse text areas into lists
        queries = [q.strip() for q in queries_text.split("\n") if q.strip()]
        urls = [u.strip() for u in urls_text.split("\n") if u.strip()]

        # Find and update the topic
        for i, topic in enumerate(self._topics):
            if topic.get("name", "").lower() == original_name.lower():
                self._topics[i] = {
                    "name": name,
                    "description": description,
                    "search_queries": queries,
                    "urls_to_check": urls,
                    "check_interval_hours": interval
                }
                self._save_config()
                self.messageReceived.emit(f"Updated topic: {name}", False)
                return

        self.errorOccurred.emit(f"Topic not found: {original_name}")

    @Slot(str)
    def checkSingleTopic(self, name: str):
        """Force check a single topic now."""
        topic_data = None
        for t in self._topics:
            if t.get("name", "").lower() == name.lower():
                topic_data = t
                break

        if not topic_data:
            self.errorOccurred.emit(f"Topic not found: {name}")
            return

        self._set_busy(True)
        self.messageReceived.emit(f"Checking {name}...", False)

        try:
            from watchdog_agent.agent import WatchdogAgent, WatchTopic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key or api_key == "sk-ant-YOUR-KEY-HERE":
                self.errorOccurred.emit("API key not configured")
                return

            agent = WatchdogAgent(api_key=api_key)

            topic = WatchTopic(
                name=topic_data["name"],
                description=topic_data.get("description", ""),
                search_queries=topic_data.get("search_queries", []),
                urls_to_check=topic_data.get("urls_to_check", []),
                check_interval_hours=topic_data.get("check_interval_hours", 24)
            )

            result = agent.check_topic(topic)
            agent.close()

            if result.has_update:
                msg = f"**Update found for {topic.name}!**\n\n{result.summary}"
                if result.source_url:
                    msg += f"\n\nSource: {result.source_url}"
            else:
                msg = f"**{topic.name}**: No updates found.\n\n{result.summary}"

            self.messageReceived.emit(msg, False)

        except ImportError:
            self.errorOccurred.emit("watchdog-agent not installed")
        except Exception as e:
            self.errorOccurred.emit(f"Check failed: {e}")
        finally:
            self._set_busy(False)
