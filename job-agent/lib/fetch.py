"""Polite HTTP fetcher.

- Checks robots.txt before every request (and skips the site if robots.txt disallows us).
- Waits at least `min_delay` seconds (default 3) between requests to the same domain.
- Stops for a domain when it sees a block (403/429/503, CAPTCHA, login wall). It never tries to get around it.
"""
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from . import log

USER_AGENT = "PersonalJobSearchAgent/1.0 (+personal use; respects robots.txt)"
BLOCK_MARKERS = ("captcha", "are you a robot", "unusual traffic", "cf-challenge", "access denied",
                 "verify you are human", "cloudflare ray id")
LOGIN_MARKERS = ('type="password"', "type='password'", "sign in to continue", "login to continue",
                 "please log in", "please login")

L = log.get("fetch")


class Blocked(Exception):
    """The site blocked us or needs a login. Stop for this site."""


class RobotsDisallowed(Exception):
    pass


class Fetcher:
    def __init__(self, min_delay=3.0, timeout=25, session=None):
        self.min_delay = max(3.0, float(min_delay))
        self.timeout = timeout
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.8"})
        self._last = {}
        self._robots = {}
        self.blocked_domains = {}

    def _wait(self, domain):
        last = self._last.get(domain)
        if last is not None:
            gap = time.monotonic() - last
            if gap < self.min_delay:
                time.sleep(self.min_delay - gap)
        self._last[domain] = time.monotonic()

    def allowed(self, url):
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait(p.netloc)
                r = self.s.get(base + "/robots.txt", timeout=self.timeout)
                if r.status_code in (401, 403):
                    rp.disallow_all = True       # robots.txt forbidden -> treat as "do not crawl"
                elif r.status_code >= 400:
                    rp.allow_all = True          # no robots.txt -> allowed
                else:
                    rp.parse(r.text.splitlines())
            except requests.RequestException as e:
                raise ConnectionError(f"cannot reach {p.netloc}: {e.__class__.__name__}") from e
            self._robots[base] = rp
        return self._robots[base].can_fetch(USER_AGENT, url)

    def get(self, url):
        domain = urlparse(url).netloc
        if domain in self.blocked_domains:
            raise Blocked(f"{domain} already blocked this run: {self.blocked_domains[domain]}")
        if not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        self._wait(domain)
        r = self.s.get(url, timeout=self.timeout)
        reason = detect_block(r.status_code, r.text[:20000] if "text" in r.headers.get("content-type", "text") else "")
        if reason:
            self.blocked_domains[domain] = reason
            L.warning("stopping for %s: %s", domain, reason)
            raise Blocked(f"{domain}: {reason}")
        r.raise_for_status()
        return r


def detect_block(status, text):
    if status in (403, 429, 503):
        return f"HTTP {status} (blocked or rate limited)"
    low = (text or "").lower()
    for m in BLOCK_MARKERS:
        if m in low:
            return f"bot check detected ('{m}')"
    return None


def needs_login(html):
    low = (html or "").lower()
    return any(m in low for m in LOGIN_MARKERS)
