"""Articles are stored as JSON files in data/articles — the repo is the database."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ARTICLES_DIR = DATA_DIR / "articles"
STATE_FILE = DATA_DIR / "state.json"


def slugify(text: str, limit: int = 70) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "story"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_articles() -> list[dict]:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    articles = [json.loads(p.read_text(encoding="utf-8")) for p in ARTICLES_DIR.glob("*.json")]
    articles.sort(key=lambda a: a["updated_at"], reverse=True)
    return articles


def save_article(article: dict) -> None:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTICLES_DIR / f"{article['id']}.json"
    path.write_text(json.dumps(article, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def new_article_id(headline: str, existing: set[str]) -> str:
    base = f"{datetime.now(timezone.utc):%Y-%m-%d}-{slugify(headline)}"
    candidate, n = base, 2
    while candidate in existing:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


class State:
    """Remembers which source URLs were already used, so stories are not rewritten every hour."""

    def __init__(self) -> None:
        self.seen: dict[str, str] = {}
        if STATE_FILE.exists():
            self.seen = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("seen_urls", {})

    def is_seen(self, url: str) -> bool:
        return url in self.seen

    def mark(self, urls) -> None:
        stamp = now_iso()
        for url in urls:
            self.seen[url] = stamp

    def save(self, keep_days: int = 7) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
        self.seen = {u: t for u, t in self.seen.items() if t >= cutoff}
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"seen_urls": self.seen}, indent=1) + "\n", encoding="utf-8")
