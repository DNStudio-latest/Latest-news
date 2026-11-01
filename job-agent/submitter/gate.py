"""Every check that must pass before anything is submitted. Pure functions, easy to test."""
import json
from datetime import date
from urllib.parse import urlparse

from lib import config, paths, store
from matcher import dates
from writer.package import folder_for


def site_entry(url, trusted_cfg):
    host = urlparse(url or "").netloc.lower().removeprefix("www.")
    for s in trusted_cfg.get("sites") or []:
        d = s["domain"].lower().removeprefix("www.")
        if host == d or host.endswith("." + d):
            return s
    return None


def check(item, decisions=None, trusted_cfg=None, profile=None, today=None):
    """Return a list of reasons NOT to submit. Empty list = allowed to go to the live re-check."""
    decisions = store.latest_decisions() if decisions is None else decisions
    trusted_cfg = config.trusted() if trusted_cfg is None else trusted_cfg
    profile = config.profile() if profile is None else profile
    today = today or date.today()
    no = []
    d = decisions.get(item["id"])
    if not d or d["decision"] != "approve":
        no.append(f"no approval recorded (latest decision: {d['decision'] if d else 'none'})")
    if not profile.get("confirmed_by_user"):
        no.append("profile not confirmed yet (set confirmed_by_user: true in config/profile.yaml after checking it)")
    url = item.get("official_link")
    s = site_entry(url, trusted_cfg)
    if not url:
        no.append("no official link")
    elif not s:
        no.append(f"site {urlparse(url).netloc} is not in config/trusted_sites.yaml")
    elif s.get("status") != "approved":
        no.append(f"site {s['domain']} is in the trusted list but status is '{s.get('status')}', not 'approved'")
    if not item.get("deadline"):
        no.append("deadline unknown")
    elif dates.days_left(item["deadline"], today) < 0:
        no.append(f"deadline passed ({item['deadline']})")
    if item.get("status") == "BLOCKED":
        no.append("item is BLOCKED (missing facts: see checklist.md)")
    if item.get("verification") != "VERIFIED":
        no.append("not verified on the official site")
    f = folder_for(item)
    for need in ("cover_letter.md", "form_answers.md", "item.json"):
        if not (f / need).exists():
            no.append(f"package file missing: {need}")
    if not ((f / "tailored_cv.pdf").exists() or (f / "tailored_cv.docx").exists()):
        no.append("tailored CV export missing")
    if any(r.get("item_id") == item["id"] and r.get("result") == "submitted" for r in store.load_submissions()):
        no.append("already submitted")
    return no


def load_package(item):
    f = folder_for(item)
    return f, json.loads((f / "item.json").read_text(encoding="utf-8"))
