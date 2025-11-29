"""AI agent using Claude API for topic monitoring."""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import anthropic
import httpx
from bs4 import BeautifulSoup


@dataclass
class WatchTopic:
    """A topic to monitor for updates."""
    name: str
    description: str
    search_queries: list[str]
    urls_to_check: list[str] = field(default_factory=list)
    check_interval_hours: int = 24
    last_checked: datetime | None = None
    last_content_hash: str | None = None


@dataclass
class UpdateResult:
    """Result of checking a topic for updates."""
    topic_name: str
    has_update: bool
    summary: str
    source_url: str | None = None
    confidence: float = 0.0


class WatchdogAgent:
    """AI agent that monitors topics using Claude."""

    def __init__(self, api_key: str | None = None, cache_dir: Path | None = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.cache_dir = cache_dir or Path.home() / ".cache" / "watchdog-agent"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.http_client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}
        )

    def _get_cache_path(self, topic_name: str) -> Path:
        safe_name = "".join(c if c.isalnum() else "_" for c in topic_name)
        return self.cache_dir / f"{safe_name}.json"

    def _load_topic_cache(self, topic: WatchTopic) -> dict:
        cache_path = self._get_cache_path(topic.name)
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_topic_cache(self, topic: WatchTopic, data: dict):
        cache_path = self._get_cache_path(topic.name)
        cache_path.write_text(json.dumps(data, indent=2, default=str))

    def _fetch_url_content(self, url: str) -> str | None:
        """Fetch and extract text content from a URL."""
        try:
            response = self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            text = soup.get_text(separator="\n", strip=True)
            # Limit content size
            return text[:15000]
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return None

    def _search_web(self, query: str) -> list[dict]:
        """
        Search the web using DuckDuckGo HTML (no API needed).

        Returns list of {title, url, snippet} dicts.
        """
        results = []
        try:
            search_url = "https://html.duckduckgo.com/html/"
            response = self.http_client.post(
                search_url,
                data={"q": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for result in soup.select(".result")[:5]:  # Top 5 results
                title_elem = result.select_one(".result__title a")
                snippet_elem = result.select_one(".result__snippet")

                if title_elem:
                    # DuckDuckGo wraps URLs, extract the actual URL
                    href = title_elem.get("href", "")
                    # Extract uddg parameter which contains the actual URL
                    if "uddg=" in href:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        actual_url = parsed.get("uddg", [href])[0]
                    else:
                        actual_url = href

                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "url": actual_url,
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                    })

        except Exception as e:
            print(f"Search failed for '{query}': {e}")

        return results

    def check_topic(self, topic: WatchTopic) -> UpdateResult:
        """Check a topic for updates using Claude."""
        cache = self._load_topic_cache(topic)

        # Gather information
        gathered_info = []

        # Search for recent news/updates
        for query in topic.search_queries[:3]:  # Limit queries
            search_results = self._search_web(f"{query} 2024 2025")
            for result in search_results[:3]:
                gathered_info.append(
                    f"Search result for '{query}':\n"
                    f"Title: {result['title']}\n"
                    f"URL: {result['url']}\n"
                    f"Snippet: {result['snippet']}\n"
                )

        # Check specific URLs
        for url in topic.urls_to_check[:3]:
            content = self._fetch_url_content(url)
            if content:
                gathered_info.append(
                    f"Content from {url}:\n{content[:3000]}\n"
                )

        if not gathered_info:
            return UpdateResult(
                topic_name=topic.name,
                has_update=False,
                summary="Could not gather any information",
                confidence=0.0
            )

        # Create content hash to detect changes
        content_hash = hashlib.md5("\n".join(gathered_info).encode()).hexdigest()

        # Check if content has changed
        previous_hash = cache.get("content_hash")
        previous_summary = cache.get("last_summary", "")

        # Use Claude to analyze the information
        prompt = f"""You are monitoring a topic for updates. Analyze the gathered information and determine if there are any significant NEW updates or developments.

Topic: {topic.name}
Description: {topic.description}

Previous summary (if any): {previous_summary}

Gathered information:
{chr(10).join(gathered_info)}

Analyze this information and respond with a JSON object:
{{
    "has_significant_update": true/false,
    "summary": "Brief 1-2 sentence summary of any updates or current status",
    "confidence": 0.0-1.0,
    "source_url": "most relevant URL or null"
}}

Only set has_significant_update to true if there is genuinely NEW information that the user should know about. Don't report updates for things that haven't changed."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
            else:
                result_data = {
                    "has_significant_update": False,
                    "summary": "Could not parse response",
                    "confidence": 0.0,
                    "source_url": None
                }

            # Update cache
            cache["content_hash"] = content_hash
            cache["last_checked"] = datetime.now().isoformat()
            cache["last_summary"] = result_data.get("summary", "")
            self._save_topic_cache(topic, cache)

            return UpdateResult(
                topic_name=topic.name,
                has_update=result_data.get("has_significant_update", False),
                summary=result_data.get("summary", "No summary"),
                source_url=result_data.get("source_url"),
                confidence=result_data.get("confidence", 0.0)
            )

        except Exception as e:
            return UpdateResult(
                topic_name=topic.name,
                has_update=False,
                summary=f"Error checking topic: {e}",
                confidence=0.0
            )

    def close(self):
        """Clean up resources."""
        self.http_client.close()
