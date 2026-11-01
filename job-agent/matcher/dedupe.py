import hashlib
import re
from urllib.parse import urlparse, urlunparse

_WS = re.compile(r"[^a-z0-9]+")


def norm(s):
    return _WS.sub(" ", (s or "").lower()).strip()


def canonical_url(u):
    if not u:
        return ""
    p = urlparse(u.strip())
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    return urlunparse(("https", host, p.path.rstrip("/"), "", p.query, ""))


def make_id(item):
    key = "|".join([norm(item.get("title")), norm(item.get("employer")), (item.get("deadline") or "")[:10]])
    return hashlib.sha1(key.encode()).hexdigest()[:10]


def dedupe(items):
    """Drop repeats. Two items are the same if they share an id (title+employer+deadline)
    or the same canonical official link. When a repeat comes from an official source, it wins."""
    by_key, out = {}, []
    for it in items:
        it.setdefault("id", make_id(it))
        keys = [it["id"]]
        cu = canonical_url(it.get("official_link") or "")
        if cu:
            keys.append(cu)
        hit = next((by_key[k] for k in keys if k in by_key), None)
        if hit is None:
            out.append(it)
            for k in keys:
                by_key[k] = it
        elif it.get("is_official") and not hit.get("is_official"):
            hit.update({k: v for k, v in it.items() if v not in (None, "")})
    return out
