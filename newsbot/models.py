from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Platforms that publish edited news (vs. user posts on social networks).
NEWS_PLATFORMS = {"rss", "google_news", "hackernews"}


@dataclass
class Item:
    """One raw piece of information picked up from a source."""

    title: str
    url: str
    source: str  # outlet or account, e.g. "BBC World", "r/worldnews"
    platform: str  # rss | google_news | reddit | hackernews | mastodon | bluesky
    published: datetime  # timezone-aware, UTC
    summary: str = ""
    category: str = "World"
    score: int = 0  # upvotes / points / boosts when available

    @property
    def is_news(self) -> bool:
        return self.platform in NEWS_PLATFORMS


@dataclass
class Cluster:
    """A group of items that all describe the same development."""

    items: list[Item] = field(default_factory=list)

    @property
    def sources(self) -> set[str]:
        return {i.source for i in self.items}

    @property
    def has_news_anchor(self) -> bool:
        return any(i.is_news for i in self.items)

    @property
    def category(self) -> str:
        counts: dict[str, int] = {}
        for i in self.items:
            counts[i.category] = counts.get(i.category, 0) + 1
        return max(counts, key=counts.get)

    @property
    def weight(self) -> float:
        """Rough importance: independent sources count most, social buzz helps."""
        return len(self.sources) * 10 + sum(min(i.score, 5000) for i in self.items) / 500
