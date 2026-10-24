from datetime import datetime, timezone

from newsbot import site, store
from newsbot.__main__ import run
from newsbot.cluster import cluster_items
from newsbot.models import Item

NOW = datetime.now(timezone.utc)


def item(title, source, platform="rss", summary="", url=None):
    return Item(title=title, url=url or f"https://example.com/{source}/{abs(hash(title))}", source=source,
                platform=platform, published=NOW, summary=summary, category="Technology")


SAMPLE = [
    item("Acme unveils Rocket X1 electric scooter with 200 km range", "Outlet A", summary="Acme launched the X1 scooter."),
    item("Acme's Rocket X1 scooter promises 200km range on one charge", "Outlet B", summary="The X1 goes on sale in May."),
    item("Rocket X1: Acme electric scooter range hits 200 km", "r/technology", "reddit"),
    item("City council approves new riverside park budget", "Outlet C", summary="The park will open next year."),
]


def test_clustering_groups_same_development():
    clusters = cluster_items(SAMPLE, threshold=0.32)
    biggest = clusters[0]
    assert len(biggest.items) == 3
    assert biggest.sources == {"Outlet A", "Outlet B", "r/technology"}
    assert len(clusters) == 2


def test_full_run_builds_site(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(store, "ARTICLES_DIR", tmp_path / "data" / "articles")
    monkeypatch.setattr(store, "STATE_FILE", tmp_path / "data" / "state.json")
    monkeypatch.setattr(site, "OUT", tmp_path / "public")
    monkeypatch.setattr("newsbot.__main__.collect_all", lambda *a: list(SAMPLE))

    cfg = {
        "pipeline": {"max_age_hours": 24, "min_sources": 2, "max_new_articles_per_run": 5, "similarity_threshold": 0.32},
        "writer": {"model": "claude-opus-5-5"},
        "sources": {},
        "site": {"title": "Test News", "tagline": "t", "base_url": "https://example.org", "language": "en"},
    }
    run(cfg)
    articles = store.load_articles()
    assert len(articles) == 1  # the single-source park story is held back
    assert len(articles[0]["sources"]) == 3

    # Second run with the same items must not duplicate the story.
    run(cfg)
    assert len(store.load_articles()) == 1

    site.build_site(store.load_articles(), cfg["site"])
    out = tmp_path / "public"
    page = (out / "article" / f"{articles[0]['id']}.html").read_text()
    assert "Outlet A" in page and "Sources" in page
    assert (out / "index.html").exists() and (out / "feed.xml").exists() and (out / "sitemap.xml").exists()
