"""Open the official link and confirm deadline + eligibility text. Marks VERIFIED / UNVERIFIED."""
import hashlib
import io
import re

from bs4 import BeautifulSoup

from lib import fetch, log, store
from . import dates

L = log.get("verify")


def page_text(resp):
    ctype = resp.headers.get("content-type", "")
    if "pdf" in ctype or resp.url.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, "PDF notice: install pypdf to read it"
        return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(resp.content)).pages), None
    soup = BeautifulSoup(resp.text, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")), None


def fingerprint(text):
    """Dates + eligibility-ish sentences: if these change, we must ask again."""
    ds = sorted({d.isoformat() for d in dates._dates_in(text or "")})
    elig = " ".join(sorted(set(re.findall(r"[^.]*(?:eligib|qualif|experience|essential)[^.]*\.", text or "", re.I))))
    return hashlib.sha1((" ".join(ds) + "|" + elig).encode()).hexdigest()[:16], ds


def verify(item, fetcher):
    url = item.get("official_link")
    if not url:
        return _set(item, "UNVERIFIED", "no official link yet (aggregator listing): find the notice on the employer's site")
    try:
        r = fetcher.get(url)
    except fetch.RobotsDisallowed as e:
        return _set(item, "UNVERIFIED", f"robots.txt disallows the official page: {e}")
    except fetch.Blocked as e:
        return _set(item, "UNVERIFIED", f"official site blocked us: {e}")
    except Exception as e:
        return _set(item, "UNVERIFIED", f"could not open official page ({e.__class__.__name__})")
    text, err = page_text(r)
    if text is None:
        return _set(item, "UNVERIFIED", err)
    fp, ds = fingerprint(text)
    item["page_fingerprint"] = fp
    if item.get("deadline"):
        if item["deadline"] not in ds:
            return _set(item, "UNVERIFIED", f"deadline {item['deadline']} not found on the official page (dates there: {', '.join(ds[-5:]) or 'none'})")
    else:
        d, kind = dates.parse_deadline(text)
        if d:
            item["deadline"], item["deadline_raw"] = d.isoformat(), f"from official page: {d.isoformat()}"
        elif kind != "rolling":
            return _set(item, "UNVERIFIED", "official page has no clear deadline")
    if not item.get("eligibility"):
        m = re.search(r"(eligib|qualif)[^.]{0,600}", text, re.I)
        if m:
            item["eligibility"] = m[0]
    return _set(item, "VERIFIED", f"checked {url}")


def _set(item, status, note):
    item["verification"], item["verification_note"], item["verified_at"] = status, note, store.now_iso()
    return item
