"""CSV storage. Opportunities are keyed by id. Approvals and submissions are append-only logs."""
import csv
import json
from datetime import datetime, timezone
from . import paths

OPP_FIELDS = [
    "id", "title", "employer", "department", "location", "type", "category", "deadline", "deadline_raw",
    "posting_date", "eligibility", "how_to_apply", "link", "official_link", "source", "source_url",
    "is_official", "remote", "verification", "verified_at", "verification_note", "score", "label",
    "score_breakdown", "status", "flags", "provenance", "page_fingerprint", "found_at", "updated_at",
]
APPROVAL_FIELDS = ["timestamp", "item_id", "title", "decision", "note"]
SUBMISSION_FIELDS = ["timestamp", "item_id", "title", "site", "method", "decision", "result",
                     "confirmation_ref", "evidence_path", "note"]


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(r.get(k)) for k in fields})


def _append(path, fields, row):
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: _cell(row.get(k)) for k in fields})


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return v


def init_files():
    paths.ensure_dirs()
    for p, f in ((paths.OPPORTUNITIES, OPP_FIELDS), (paths.APPROVALS, APPROVAL_FIELDS),
                 (paths.SUBMISSIONS, SUBMISSION_FIELDS)):
        if not p.exists():
            _write(p, f, [])


# ---- opportunities
def load_opportunities():
    rows = _read(paths.OPPORTUNITIES)
    for r in rows:
        for k in ("flags", "score_breakdown"):
            try:
                r[k] = json.loads(r[k]) if r.get(k) else ([] if k == "flags" else {})
            except json.JSONDecodeError:
                r[k] = [] if k == "flags" else {}
    return {r["id"]: r for r in rows}


def save_opportunities(by_id):
    rows = sorted(by_id.values(), key=lambda r: (-(float(r.get("score") or 0)), r.get("id", "")))
    _write(paths.OPPORTUNITIES, OPP_FIELDS, rows)


# ---- approvals
def load_approvals():
    return _read(paths.APPROVALS)


def latest_decisions():
    """Latest decision per item id (the log keeps every past decision)."""
    out = {}
    for r in load_approvals():
        out[r["item_id"]] = r
    return out


def record_approval(item_id, title, decision, note=""):
    assert decision in ("approve", "reject", "hold"), decision
    row = {"timestamp": now_iso(), "item_id": item_id, "title": title, "decision": decision, "note": note}
    _append(paths.APPROVALS, APPROVAL_FIELDS, row)
    return row


# ---- submissions
def load_submissions():
    return _read(paths.SUBMISSIONS)


def record_submission(**row):
    row.setdefault("timestamp", now_iso())
    _append(paths.SUBMISSIONS, SUBMISSION_FIELDS, row)
    return row
