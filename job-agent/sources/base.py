"""Shared pieces for all sources.

Each source module exposes `SOURCE`, an object with `.name`, `.kind` and `.collect(fetcher, cfg)`.
`collect` returns a list of raw item dicts and never raises: failures are logged and returned in `.errors`.
"""
import re
from urllib.parse import urljoin, quote_plus

from bs4 import BeautifulSoup

from lib import fetch, log
from matcher import dates, scam

L = log.get("sources")

NOTICE_WORDS = re.compile(
    r"recruit|vacanc|advertis|guest\s*faculty|faculty|walk[- ]?in|\bjrf\b|\bsrf\b|research\s+(fellow|associate)|"
    r"fellowship|empanel|engagement\s+of|post\s+of|positions?\b|hiring|career|\bjobs?\b|"
    r"reporter|editor|correspondent|journalist|video|content|professor|lecturer|communication", re.I)
NAV_WORDS = re.compile(r"^(home|about|contact|login|sign in|register|careers?|jobs?|recruitments?|more|read more|click here|download|apply|view)$", re.I)
FOLLOW_WORDS = re.compile(r"recruit|career|vacanc|advertis|notification|employment|jobs", re.I)


class Source:
    kind = "official"          # official | media | aggregator | board | freelance | fellowship | snapshot

    def __init__(self, name, kind=None):
        self.name = name
        self.kind = kind or self.kind
        self.errors = []
        self.skipped = []

    @property
    def is_official(self):
        return self.kind in ("official", "media")

    def fail(self, url, err):
        msg = f"{self.name}: {url}: {err}"
        L.warning(msg)
        self.errors.append(msg)

    def skip(self, url, why):
        msg = f"{self.name}: {url}: skipped ({why})"
        L.info(msg)
        self.skipped.append(msg)

    def get(self, fetcher, url):
        """Fetch one page. Returns HTML or None. Never raises."""
        try:
            r = fetcher.get(url)
            return r.text
        except fetch.RobotsDisallowed as e:
            self.skip(url, str(e))
        except fetch.Blocked as e:
            self.skip(url, f"site blocked us, stopped for this site: {e}")
        except Exception as e:   # network, DNS, HTTP errors
            self.fail(url, f"{e.__class__.__name__}: {str(e)[:160]}")
        return None

    def collect(self, fetcher, cfg):
        raise NotImplementedError


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def extract_notices(html, page_url, employer, location, source_name, is_official, title_filter=None):
    """Generic notice-board parser: each link (with its table row / list item as context) that
    looks like a vacancy notice becomes one item."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "footer", "header"]):
        t.decompose()
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" "))
        if len(title) < 12 or NAV_WORDS.match(title) or not NOTICE_WORDS.search(title):
            continue
        if title_filter and not title_filter(title):
            continue
        href = urljoin(page_url, a["href"])
        if href in seen or href.startswith(("mailto:", "javascript:")):
            continue
        seen.add(href)
        ctx_el = a.find_parent(["tr", "li", "article", "p", "div"]) or a
        ctx = clean(ctx_el.get_text(" "))[:1500]
        d, kind = dates.parse_deadline(ctx)
        items.append({
            "title": title[:200],
            "employer": employer,
            "location": location,
            "type": guess_type(title),
            "deadline": d.isoformat() if d else "",
            "deadline_raw": ctx if d or kind == "rolling" else "",
            "posting_date": "",
            "eligibility": ctx if len(ctx) > len(title) + 20 else "",
            "link": href,
            "official_link": href if is_official else "",
            "source": source_name,
            "source_url": page_url,
            "is_official": is_official and scam.is_official_domain(href) or is_official,
        })
    return items


def follow_links(html, page_url, limit=3):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        if FOLLOW_WORDS.search(clean(a.get_text(" "))) or FOLLOW_WORDS.search(a["href"]):
            u = urljoin(page_url, a["href"])
            if u.startswith("http") and u not in out and u != page_url:
                out.append(u)
        if len(out) >= limit:
            break
    return out


def guess_type(title):
    t = title.lower()
    for k, v in (("guest", "guest faculty"), ("assistant professor", "faculty"), ("professor", "faculty"),
                 ("jrf", "research fellow"), ("srf", "research fellow"), ("research associate", "research associate"),
                 ("fellowship", "fellowship"), ("walk", "walk-in"), ("project", "project"), ("intern", "internship"),
                 ("freelance", "freelance"), ("editor", "editorial"), ("reporter", "editorial"), ("video", "video")):
        if k in t:
            return v
    return "job"


def slug(q):
    return re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")


def q(qs):
    return quote_plus(qs)


class OfficialPageSource(Source):
    """University / government notice pages: fetch start pages, follow up to 3 'recruitment' links."""

    def __init__(self, name, section="official", kind="official"):
        super().__init__(name, kind)
        self.section = section

    def targets(self, cfg):
        c = cfg[self.section][self.name]
        if c.get("entries") is not None:
            return [(e["url"], e["employer"], e["location"]) for e in c["entries"]]
        return [(u, c["employer"], c["location"]) for u in c.get("start_urls", [])]

    def title_filter(self, cfg):
        return None

    def collect(self, fetcher, cfg):
        items = []
        targets = self.targets(cfg)
        if not targets:
            self.skip("-", "no URL configured in config/sources.yaml")
        for url, employer, location in targets:
            html = self.get(fetcher, url)
            if html is None:
                continue
            pages = [(url, html)]
            for u in follow_links(html, url):
                h = self.get(fetcher, u)
                if h:
                    pages.append((u, h))
            for pu, ph in pages:
                items += extract_notices(ph, pu, employer, location, self.name, self.is_official, self.title_filter(cfg))
        return items


class SearchPageSource(Source):
    """Job boards / freelance sites: run each search query as a public search URL (no login)."""

    def __init__(self, name, section, kind, location="India", max_queries=None):
        super().__init__(name, kind)
        self.section, self.location, self.max_queries = section, location, max_queries

    def collect(self, fetcher, cfg):
        base = cfg[self.section][self.name]["base"]
        items = []
        for query in cfg["search_queries"][: self.max_queries]:
            url = base.format(q=q(query), slug=slug(query))
            html = self.get(fetcher, url)
            if html is None:
                break              # unreachable, robots.txt or a block applies to the whole site: stop here
            if fetch.needs_login(html) and "job" not in html.lower()[:5000]:
                self.skip(url, "login wall")
                break
            for it in extract_notices(html, url, "", self.location, self.name, False):
                it["employer"] = it["employer"] or "(see listing)"
                items.append(it)
        return items
