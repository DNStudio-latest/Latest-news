"""Run the newsroom: python -m newsbot [run|build]

  run    collect -> cluster -> write new articles -> build the site (default)
  build  only rebuild the website from stored articles
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml

from .cluster import cluster_items, signature, signature_similarity
from .collectors import collect_all
from .models import Cluster
from .site import build_site
from .store import State, load_articles, new_article_id, now_iso, save_article
from .wordpress import WordPressPublisher
from .writer import Writer

log = logging.getLogger("newsbot")
CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"

# Re-write a published story only once this many new sources have appeared.
UPDATE_AFTER_NEW_SOURCES = 3


def _source_entry(item) -> dict:
    return {"title": item.title, "url": item.url, "source": item.source, "platform": item.platform}


def _find_existing(cluster: Cluster, articles: list[dict], threshold: float) -> dict | None:
    sig = signature(" ".join(i.title for i in cluster.items))
    best, best_sim = None, max(threshold, 0.3)
    for art in articles[:300]:
        sim = signature_similarity(sig, art.get("signature", []))
        if sim >= best_sim:
            best, best_sim = art, sim
    return best


def run(cfg: dict, dry_run: bool = False) -> None:
    pipe = cfg["pipeline"]
    state = State()
    articles = load_articles()
    writer = Writer(cfg["writer"]["model"], cfg["writer"].get("effort", "medium"))
    wordpress = WordPressPublisher()

    items = [i for i in collect_all(cfg["sources"], pipe["max_age_hours"]) if not state.is_seen(i.url)]
    clusters = cluster_items(items, pipe["similarity_threshold"])
    eligible = [c for c in clusters if c.has_news_anchor and len(c.sources) >= pipe["min_sources"]]
    log.info("%d new items -> %d developments, %d eligible", len(items), len(clusters), len(eligible))

    written = 0
    for cluster in eligible:
        if written >= pipe["max_new_articles_per_run"]:
            break
        lead = next(i for i in cluster.items if i.is_news)
        if dry_run:
            log.info("[dry-run] %d sources: %s", len(cluster.sources), lead.title)
            continue

        existing = _find_existing(cluster, articles, pipe["similarity_threshold"])
        if existing:
            known = {s["url"] for s in existing["sources"]}
            fresh = [i for i in cluster.items if i.url not in known]
            existing["sources"] += [_source_entry(i) for i in fresh]
            if len(fresh) >= UPDATE_AFTER_NEW_SOURCES and writer.client is not None:
                previous = existing["headline"] + "\n\n" + "\n\n".join(existing["body"])
                draft = writer.write(cluster, previous=previous)
                if draft:
                    existing.update(headline=draft.headline, summary=draft.summary, body=draft.body,
                                    key_points=draft.key_points, tags=draft.tags)
                    written += 1
            existing["updated_at"] = now_iso()
            wordpress.publish(existing)
            save_article(existing)
            state.mark(i.url for i in cluster.items)
            log.info("updated: %s (+%d sources)", existing["headline"], len(fresh))
            continue

        draft = writer.write(cluster)
        if draft is None:
            # Refused, skipped as non-news, or API trouble. Mark as seen only
            # for deliberate skips so transient errors get retried next run.
            if writer.client is not None:
                state.mark(i.url for i in cluster.items)
            continue
        stamp = now_iso()
        article = {
            "id": new_article_id(draft.headline, {a["id"] for a in articles}),
            "headline": draft.headline,
            "summary": draft.summary,
            "key_points": draft.key_points,
            "body": draft.body,
            "category": draft.category,
            "tags": draft.tags,
            "sources": [_source_entry(i) for i in cluster.items],
            "signature": signature(" ".join(i.title for i in cluster.items)),
            "written_by": draft.written_by,
            "published_at": stamp,
            "updated_at": stamp,
        }
        wordpress.publish(article)
        save_article(article)
        articles.insert(0, article)
        state.mark(i.url for i in cluster.items)
        written += 1
        log.info("published: %s", article["headline"])

    if not dry_run:
        state.save()
    log.info("done — %d articles written this run", written)


def main() -> None:
    parser = argparse.ArgumentParser(prog="newsbot")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "build"])
    parser.add_argument("--dry-run", action="store_true", help="collect and cluster only; write nothing")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if args.command == "run":
        run(cfg, dry_run=args.dry_run)
    if not args.dry_run:
        build_site(load_articles(), cfg["site"])
        log.info("site built in public/")


if __name__ == "__main__":
    main()
