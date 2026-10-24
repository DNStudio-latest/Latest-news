"""Collectors: pull recent items from news feeds and social platforms.

Every collector is failure-tolerant — one broken source never stops a run.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import requests

from .models import Item

log = logging.getLogger(__name__)

USER_AGENT = "LatestNewsBot/1.0 (+https://github.com/dnstudio-latest/latest-news)"
TIMEOUT = 20

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(value: str | None, limit: int = 600) -> str:
    text = html.unescape(_TAG_RE.sub(" ", value or ""))
    text = _WS_RE.sub(" ", text).strip()
    return text[:limit]


def _headline_from_post(text: str) -> str:
    """Social posts have no title — use their first sentence."""
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first[:160]


def _get_json(url: str, **params) -> dict | list:
    resp = requests.get(url, params=params or None, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(str(value))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# --------------------------------------------------------------------------- news


def collect_feed(url: str, source: str, category: str, platform: str = "rss") -> list[Item]:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries:
        published = None
        for key in ("published_parsed", "updated_parsed"):
            if entry.get(key):
                published = datetime(*entry[key][:6], tzinfo=timezone.utc)
                break
        title = clean_text(entry.get("title"), 300)
        link = entry.get("link")
        if not title or not link:
            continue
        outlet = source
        if platform == "google_news":
            # Google News titles look like "Headline - Outlet"; keep the outlet.
            src = entry.get("source", {})
            outlet = src.get("title") if isinstance(src, dict) and src.get("title") else source
            title = re.sub(r"\s+-\s+[^-]+$", "", title)
        items.append(
            Item(
                title=title,
                url=link,
                source=outlet,
                platform=platform,
                published=published or datetime.now(timezone.utc),
                summary=clean_text(entry.get("summary")),
                category=category,
            )
        )
    return items


def collect_google_news(cfg: dict) -> list[Item]:
    hl, gl = cfg.get("language", "en-US"), cfg.get("country", "US")
    out = []
    for query in cfg.get("queries", []):
        url = (
            f"https://news.google.com/rss/search?q={quote_plus(query['q'])}+when:1d"
            f"&hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
        )
        out += _safe(collect_feed, url, "Google News", query.get("category", "World"), "google_news")
    return out


def collect_hackernews(cfg: dict) -> list[Item]:
    data = _get_json("https://hn.algolia.com/api/v1/search", tags="front_page", hitsPerPage=50)
    out = []
    for hit in data.get("hits", []):
        if (hit.get("points") or 0) < cfg.get("min_points", 100) or not hit.get("url"):
            continue
        out.append(
            Item(
                title=clean_text(hit.get("title"), 300),
                url=hit["url"],
                source="Hacker News",
                platform="hackernews",
                published=_parse_date(hit.get("created_at")) or datetime.now(timezone.utc),
                category="Technology",
                score=hit.get("points") or 0,
            )
        )
    return out


# ------------------------------------------------------------------------- social


def collect_reddit(cfg: dict) -> list[Item]:
    out = []
    for sub in cfg.get("subreddits", []):
        try:
            data = _get_json(f"https://www.reddit.com/r/{sub}/top.json", t="day", limit=30)
        except Exception as exc:  # noqa: BLE001
            log.warning("reddit r/%s failed: %s", sub, exc)
            continue
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            if post.get("stickied") or post.get("over_18") or post.get("score", 0) < cfg.get("min_score", 100):
                continue
            out.append(
                Item(
                    title=clean_text(post.get("title"), 300),
                    # Prefer the linked article; fall back to the discussion.
                    url=post.get("url_overridden_by_dest") or f"https://www.reddit.com{post.get('permalink', '')}",
                    source=f"r/{sub}",
                    platform="reddit",
                    published=_parse_date(post.get("created_utc")) or datetime.now(timezone.utc),
                    summary=clean_text(post.get("selftext")),
                    category=_guess_category(sub),
                    score=post.get("score", 0),
                )
            )
    return out


def collect_mastodon(cfg: dict) -> list[Item]:
    instance = cfg.get("instance", "https://mastodon.social").rstrip("/")
    out = []
    for tag in cfg.get("hashtags", []):
        try:
            statuses = _get_json(f"{instance}/api/v1/timelines/tag/{tag}", limit=40)
        except Exception as exc:  # noqa: BLE001
            log.warning("mastodon #%s failed: %s", tag, exc)
            continue
        for st in statuses:
            text = clean_text(st.get("content"))
            if len(text) < 40 or st.get("sensitive"):
                continue
            card = st.get("card") or {}
            out.append(
                Item(
                    title=clean_text(card.get("title"), 300) or _headline_from_post(text),
                    url=card.get("url") or st.get("url"),
                    source=f"@{st.get('account', {}).get('acct', 'mastodon')}",
                    platform="mastodon",
                    published=_parse_date(st.get("created_at")) or datetime.now(timezone.utc),
                    summary=text,
                    score=(st.get("reblogs_count") or 0) + (st.get("favourites_count") or 0),
                )
            )
    return out


def collect_bluesky(cfg: dict) -> list[Item]:
    out = []
    for query in cfg.get("queries", []):
        try:
            data = _get_json(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts", q=query, limit=50, sort="top"
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("bluesky '%s' failed: %s", query, exc)
            continue
        for post in data.get("posts", []):
            record = post.get("record", {})
            text = clean_text(record.get("text"))
            if len(text) < 40:
                continue
            external = (post.get("embed") or {}).get("external") or {}
            handle = post.get("author", {}).get("handle", "bsky")
            rkey = post.get("uri", "").rsplit("/", 1)[-1]
            out.append(
                Item(
                    title=clean_text(external.get("title"), 300) or _headline_from_post(text),
                    url=external.get("uri") or f"https://bsky.app/profile/{handle}/post/{rkey}",
                    source=f"@{handle}",
                    platform="bluesky",
                    published=_parse_date(record.get("createdAt")) or datetime.now(timezone.utc),
                    summary=text,
                    score=(post.get("likeCount") or 0) + (post.get("repostCount") or 0),
                )
            )
    return out


def _guess_category(name: str) -> str:
    name = name.lower()
    for key, cat in (("tech", "Technology"), ("sport", "Sports"), ("india", "India"), ("business", "Business")):
        if key in name:
            return cat
    return "World"


def _safe(fn, *args) -> list[Item]:
    try:
        items = fn(*args)
        log.info("%-12s %-28s %3d items", fn.__name__.replace("collect_", ""), str(args[1] if len(args) > 1 else ""), len(items))
        return items
    except Exception as exc:  # noqa: BLE001
        log.warning("%s%s failed: %s", fn.__name__, args[:2], exc)
        return []


def collect_all(sources: dict, max_age_hours: int) -> list[Item]:
    items: list[Item] = []
    for feed in sources.get("rss", []):
        items += _safe(collect_feed, feed["url"], feed["name"], feed.get("category", "World"))
    if "google_news" in sources:
        items += _safe(collect_google_news, sources["google_news"])
    if "hackernews" in sources:
        items += _safe(collect_hackernews, sources["hackernews"])
    if "reddit" in sources:
        items += _safe(collect_reddit, sources["reddit"])
    if "mastodon" in sources:
        items += _safe(collect_mastodon, sources["mastodon"])
    if "bluesky" in sources:
        items += _safe(collect_bluesky, sources["bluesky"])

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    seen: set[str] = set()
    fresh = []
    for item in items:
        if item.published < cutoff or item.url in seen or not item.title:
            continue
        seen.add(item.url)
        fresh.append(item)
    log.info("collected %d fresh items (%d raw)", len(fresh), len(items))
    return fresh
