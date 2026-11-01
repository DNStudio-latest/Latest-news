"""Score 0-100 using config/scoring.yaml weights, and apply hard filters."""
import re
from datetime import date

from . import dates, eligibility, scam


def _is_vacancy(title):
    from sources.base import is_vacancy
    return is_vacancy(title)


def _kw_hit(text, words):
    low = (text or "").lower()
    return any(w.lower() in low for w in words)


OTHER_DEPT = re.compile(r"(?:department|dept\.?|school|centre|center)\s+of\s+([A-Za-z &,]+)", re.I)


def role_points(item, prefs, weight):
    """Highest-priority category that matches the title (or type) gets most points."""
    title = f"{item.get('title','')} {item.get('type','')} {item.get('department','')}"
    best, cat = 0.0, ""
    cats = prefs["role_categories"]
    for i, c in enumerate(cats):
        if _kw_hit(title, c["title_keywords"]):
            if c.get("field_keywords"):
                head = f"{item.get('title','')} {item.get('department','')}"
                if _kw_hit(head, c["field_keywords"]):
                    factor_field = 1.0
                elif OTHER_DEPT.search(head):
                    factor_field = 0.0      # names another department, e.g. "Department of Chemical Sciences"
                elif c["name"] == "academic":
                    factor_field = 0.5 if _kw_hit(item.get("eligibility", ""), c["field_keywords"]) else 0.25
                else:
                    factor_field = 0.5
            else:
                factor_field = 1.0
            factor = c.get("weight", 1.0) * factor_field
            if factor * weight > best:
                best, cat = factor * weight, c["name"]
    return round(best, 1), cat


def location_points(item, prefs, weight):
    loc = f"{item.get('location','')} {item.get('employer','')}".lower()
    tiers = prefs["locations"]
    if _kw_hit(loc, tiers["first"]):
        return weight, "Tripura"
    if _kw_hit(loc, tiers["northeast"]):
        return round(weight * 0.8, 1), "Northeast"
    if str(item.get("remote", "")).lower() in ("true", "yes", "1") or _kw_hit(loc, ["remote", "work from home", "online"]):
        return round(weight * 0.6, 1), "Remote"
    if _kw_hit(loc, tiers["india"]):
        return round(weight * 0.65, 1), "India"
    return 0, "outside preferences"


def deadline_points(item, weight, min_days, today):
    d, kind = (item.get("deadline") or None), None
    if d:
        left = dates.days_left(d, today)
        if left < 0:
            return 0, "expired"
        if not dates.plausible(dates.datetime.strptime(d[:10], "%Y-%m-%d").date(), today):
            return round(weight * 0.5, 1), "deadline looks wrong (too far ahead)"
        return (weight, f"{left} days left") if left >= min_days else (round(weight * 0.3, 1), f"only {left} days left")
    parsed, kind = dates.parse_deadline(item.get("deadline_raw") or "")
    if kind == "rolling":
        return round(weight * 0.7, 1), "rolling"
    return round(weight * 0.5, 1), "deadline unknown"


def evaluate(item, profile, prefs, cfg, today=None):
    """Return dict with score, label, breakdown, status, flags. Does not change item."""
    today = today or date.today()
    w = cfg["weights"]
    flags, notes = [], []

    # deadline normalisation
    if item.get("deadline") and not dates.plausible(dates.datetime.strptime(item["deadline"][:10], "%Y-%m-%d").date(), today):
        item["deadline"] = ""      # misread number from an earlier run
    if not item.get("deadline") and item.get("deadline_raw"):
        d, kind = dates.parse_deadline(item["deadline_raw"])
        if d:
            item["deadline"] = d.isoformat()

    is_scam, scam_reasons, scam_notes = scam.check(item)
    notes += scam_notes
    elig, elig_reasons = eligibility.check(item.get("eligibility", ""), profile)

    rp, cat = role_points(item, prefs, w["role_match"])
    lp, loc_tier = location_points(item, prefs, w["location_match"])
    ep = {"met": 1.0, "unclear": 0.5, "not_met": 0.0}[elig] * w["eligibility"]
    dp, dl_note = deadline_points(item, w["deadline_open"], cfg["deadline_min_days"], today)
    official = str(item.get("is_official", "")).lower() in ("true", "1", "yes")
    sp = w["source_reliability"] * (1.0 if official else cfg["aggregator_factor"])
    score = round(rp + lp + ep + dp + sp)

    breakdown = {"role": rp, "location": lp, "eligibility": ep, "deadline": dp, "source": sp,
                 "category": cat, "location_tier": loc_tier, "eligibility_result": elig,
                 "eligibility_reasons": elig_reasons, "deadline_note": dl_note, "notes": notes}

    # hard filters
    status = None
    if is_scam:
        status = "SUSPECTED SCAM"
        flags += scam_reasons
    elif dl_note == "expired":
        status = "EXPIRED"
    elif elig == "not_met":
        status = "EXCLUDED"
        flags.append("eligibility not met: " + "; ".join(elig_reasons))
    elif loc_tier == "outside preferences":
        status = "EXCLUDED"
        flags.append("location outside preferences and no remote option")
    elif not _is_vacancy(item.get("title", "")):
        status = "EXCLUDED"
        flags.append("not a vacancy (list, result, interview schedule, admission, tender...)")
    elif rp == 0:
        status = "EXCLUDED"
        flags.append("role does not match preferences")

    labels = cfg["labels"]
    label = "Strong" if score >= labels["strong"] else "Good" if score >= labels["good"] else "Weak"
    if status is None:
        status = "CANDIDATE" if score >= labels["good"] else "LOW"
    return {"score": score, "label": label, "score_breakdown": breakdown, "status": status,
            "flags": flags, "category": cat}
