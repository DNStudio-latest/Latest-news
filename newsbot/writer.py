"""Turn a cluster of source items into one original, attributed news article."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from .models import Cluster

log = logging.getLogger(__name__)

CATEGORIES = ["World", "India", "Business", "Technology", "Sports", "Science", "Health", "Entertainment", "Politics"]

SYSTEM_PROMPT = """You are the staff writer of an independent online news site. You receive raw \
material about one developing story: headlines and snippets from news outlets plus posts from \
social media. Write one original news article about it.

Rules:
- Use only facts present in the material. Never invent names, numbers, quotes, dates or places.
- Attribute claims ("according to BBC", "Reuters reported"). Where outlets disagree, say so.
- Social-media posts are unverified: only mention them as reactions or claims, clearly labelled.
- Write in your own words. Do not copy sentences from the sources; short quotes must be in quotation marks and attributed.
- Neutral, factual, inverted-pyramid style. No opinion, no clickbait, no speculation.
- If the material is not a real news development (ads, listicles, deals, opinion pieces, \
unrelated items lumped together), set skip to true."""

ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "skip": {"type": "boolean", "description": "True if this is not a real news development."},
        "headline": {"type": "string", "description": "Clear factual headline, max ~90 characters."},
        "summary": {"type": "string", "description": "One-sentence standfirst."},
        "key_points": {"type": "array", "items": {"type": "string"}, "description": "2-4 short bullet facts."},
        "body": {"type": "array", "items": {"type": "string"}, "description": "4-8 paragraphs of plain text."},
        "category": {"type": "string", "enum": CATEGORIES},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "3-6 short topic tags."},
    },
    "required": ["skip", "headline", "summary", "key_points", "body", "category", "tags"],
    "additionalProperties": False,
}


@dataclass
class Draft:
    headline: str
    summary: str
    body: list[str]
    key_points: list[str] = field(default_factory=list)
    category: str = "World"
    tags: list[str] = field(default_factory=list)
    written_by: str = "ai"


def _material(cluster: Cluster, previous: str | None) -> str:
    lines = []
    for n, item in enumerate(sorted(cluster.items, key=lambda i: (not i.is_news, i.published)), 1):
        kind = "NEWS OUTLET" if item.is_news else f"SOCIAL POST ({item.platform})"
        lines.append(
            f"[{n}] {kind} — {item.source} — {item.published:%Y-%m-%d %H:%M} UTC\n"
            f"Title: {item.title}\nSnippet: {item.summary or '(none)'}\nURL: {item.url}"
        )
    text = "\n\n".join(lines)
    if previous:
        text = (
            "We already published an article on this story. Write an UPDATED version that leads with "
            f"what is new.\n\nPrevious article:\n{previous}\n\nNew material:\n\n" + text
        )
    return text


class Writer:
    def __init__(self, model: str, effort: str = "medium"):
        self.model = model
        self.effort = effort
        self.client = None
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            import anthropic

            self.client = anthropic.Anthropic()
        else:
            log.warning("ANTHROPIC_API_KEY not set — using the basic extractive writer")

    def write(self, cluster: Cluster, previous: str | None = None) -> Draft | None:
        if self.client is None:
            return fallback_draft(cluster)
        import anthropic

        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _material(cluster, previous)}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": ARTICLE_SCHEMA}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            log.warning("writer temporarily unavailable (%s) — skipping story this run", exc)
            return None
        except anthropic.APIStatusError as exc:
            log.error("writer request failed: %s", exc)
            return None

        if response.stop_reason in ("refusal", "max_tokens"):
            log.warning("writer stopped (%s) — skipping story", response.stop_reason)
            return None
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            return None
        data = json.loads(text)
        if data["skip"] or not data["body"]:
            log.info("writer skipped non-story: %s", data.get("headline"))
            return None
        return Draft(
            headline=data["headline"].strip(),
            summary=data["summary"].strip(),
            body=[p.strip() for p in data["body"] if p.strip()],
            key_points=data["key_points"],
            category=data["category"],
            tags=[t.strip() for t in data["tags"]][:6],
        )


def fallback_draft(cluster: Cluster) -> Draft:
    """No-AI mode: a short round-up that attributes each outlet's own summary."""
    news = [i for i in cluster.items if i.is_news] or cluster.items
    lead = max(news, key=lambda i: len(i.summary))
    body = [f"{lead.summary or lead.title} ({lead.source})"]
    for item in news:
        if item is not lead and item.summary:
            body.append(f"{item.source} reports: {item.summary}")
    social = [i for i in cluster.items if not i.is_news]
    if social:
        body.append(f"The story is also being discussed on social media ({len(social)} posts tracked).")
    return Draft(
        headline=lead.title,
        summary=lead.summary[:200] or lead.title,
        body=body[:6],
        category=cluster.category,
        written_by="digest",
    )
