"""Render stored articles into a static website (public/)."""
from __future__ import annotations

import shutil
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .store import slugify

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public"


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["date"] = lambda iso: datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M UTC")
    env.filters["slug"] = slugify
    return env


def build_site(articles: list[dict], site: dict) -> None:
    env = _env()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "article").mkdir(parents=True)
    (OUT / "category").mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")

    categories = sorted({a["category"] for a in articles})
    ctx = {"site": site, "categories": categories, "year": datetime.now().year}

    def render(template: str, path: Path, root: str, **kw) -> None:
        path.write_text(env.get_template(template).render(**ctx, root=root, **kw), encoding="utf-8")

    home = articles[: site.get("articles_on_home", 30)]
    render("index.html", OUT / "index.html", "", articles=home, heading=None)
    for cat in categories:
        in_cat = [a for a in articles if a["category"] == cat]
        render("index.html", OUT / "category" / f"{slugify(cat)}.html", "../", articles=in_cat, heading=cat)
    for art in articles:
        related = [a for a in articles if a["category"] == art["category"] and a["id"] != art["id"]][:4]
        render("article.html", OUT / "article" / f"{art['id']}.html", "../", article=art, related=related)

    _write_feed(articles[:50], site)
    _write_sitemap(articles, categories, site)
    (OUT / ".nojekyll").write_text("")


def _write_feed(articles: list[dict], site: dict) -> None:
    base = site["base_url"].rstrip("/")
    items = "".join(
        f"<item><title>{escape(a['headline'])}</title>"
        f"<link>{base}/article/{a['id']}.html</link><guid>{base}/article/{a['id']}.html</guid>"
        f"<pubDate>{format_datetime(datetime.fromisoformat(a['published_at']))}</pubDate>"
        f"<category>{escape(a['category'])}</category>"
        f"<description>{escape(a['summary'])}</description></item>"
        for a in articles
    )
    (OUT / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        f"<title>{escape(site['title'])}</title><link>{base}/</link>"
        f"<description>{escape(site.get('tagline', ''))}</description>{items}</channel></rss>",
        encoding="utf-8",
    )


def _write_sitemap(articles: list[dict], categories: list[str], site: dict) -> None:
    base = site["base_url"].rstrip("/")
    urls = [f"{base}/"] + [f"{base}/category/{slugify(c)}.html" for c in categories]
    urls += [f"{base}/article/{a['id']}.html" for a in articles]
    body = "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
        encoding="utf-8",
    )
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
