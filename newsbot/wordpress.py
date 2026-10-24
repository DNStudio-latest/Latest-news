"""Optional: also publish each article to a WordPress site via its REST API.

Enable by setting WP_URL, WP_USER and WP_APP_PASSWORD (a WordPress
"Application Password", created under Users -> Profile).
"""
from __future__ import annotations

import html
import logging
import os

import requests

log = logging.getLogger(__name__)


class WordPressPublisher:
    def __init__(self) -> None:
        self.url = os.environ.get("WP_URL", "").rstrip("/")
        user, password = os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD")
        self.enabled = bool(self.url and user and password)
        self.auth = (user, password)
        self._categories: dict[str, int] = {}

    def _category_id(self, name: str) -> int | None:
        if name in self._categories:
            return self._categories[name]
        api = f"{self.url}/wp-json/wp/v2/categories"
        found = requests.get(api, params={"search": name}, auth=self.auth, timeout=20).json()
        match = next((c for c in found if c.get("name", "").lower() == name.lower()), None)
        if match is None:
            resp = requests.post(api, json={"name": name}, auth=self.auth, timeout=20)
            if not resp.ok:
                return None
            match = resp.json()
        self._categories[name] = match["id"]
        return match["id"]

    def publish(self, article: dict) -> None:
        """Create the post, or update it if this article was published before."""
        if not self.enabled:
            return
        content = "".join(f"<p>{html.escape(p)}</p>" for p in article["body"])
        content += "<h3>Sources</h3><ul>" + "".join(
            f'<li><a href="{html.escape(s["url"])}" rel="nofollow noopener">{html.escape(s["source"])}: '
            f'{html.escape(s["title"])}</a></li>'
            for s in article["sources"]
        ) + "</ul>"
        payload = {
            "title": article["headline"],
            "excerpt": article["summary"],
            "content": content,
            "status": "publish",
            "slug": article["id"],
        }
        try:
            cat = self._category_id(article["category"])
            if cat:
                payload["categories"] = [cat]
            post_id = article.get("wordpress_id")
            endpoint = f"{self.url}/wp-json/wp/v2/posts" + (f"/{post_id}" if post_id else "")
            resp = requests.post(endpoint, json=payload, auth=self.auth, timeout=30)
            resp.raise_for_status()
            article["wordpress_id"] = resp.json()["id"]
            log.info("wordpress: published %s", resp.json().get("link"))
        except Exception as exc:  # noqa: BLE001
            log.error("wordpress publish failed for %s: %s", article["id"], exc)
