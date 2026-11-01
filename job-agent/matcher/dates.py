"""Deadline parsing for Indian notices (e.g. '25.08.2026', '25th August, 2026', 'Last date: 25/08/2026 (4:30 PM)')."""
import re
from datetime import date, datetime

from dateutil import parser as dparser

ROLLING = re.compile(r"\b(rolling|ongoing|open until filled|till filled|asap)\b", re.I)
DMY = re.compile(r"(?<!\d)(?<!\d[./-])(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)(?![./-]\d)")
ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
WORDY = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s*(\d{4})\b"
    r"|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})\b",
    re.I)
DEADLINE_HINT = re.compile(r"(last\s*date|deadline|closing\s*date|on\s*or\s*before|apply\s*(?:by|before)|due\s*(?:by|on)|walk[- ]?in)", re.I)


MAX_YEARS_AHEAD = 1      # a job deadline more than ~1 year away is almost always a misread number
MAX_YEARS_BACK = 3


def plausible(d, today=None):
    today = today or date.today()
    return date(today.year - MAX_YEARS_BACK, 1, 1) <= d <= date(today.year + MAX_YEARS_AHEAD, 12, 31)


def parse_deadline(text, today=None):
    """Return (date or None, kind) where kind is 'date', 'rolling' or 'unknown'.

    If the text has several dates, prefer the one right after a 'last date'/'deadline' phrase,
    otherwise the latest date (deadlines come after posting dates).
    """
    if not text:
        return None, "unknown"
    if ROLLING.search(text):
        return None, "rolling"
    hint = DEADLINE_HINT.search(text)
    if hint:
        d = [x for x in _dates_in(text[hint.end(): hint.end() + 80]) if plausible(x, today)]
        if d:
            return d[0], "date"
    d = [x for x in _dates_in(text) if plausible(x, today)]
    if d:
        return max(d), "date"
    return None, "unknown"


def _dates_in(text):
    out = []
    for m in ISO.finditer(text):
        out.append(_safe(int(m[1]), int(m[2]), int(m[3])))
    for m in DMY.finditer(text):
        y = int(m[3])
        y = y + 2000 if y < 100 else y
        out.append(_safe(y, int(m[2]), int(m[1])))   # Indian format: day first
    for m in WORDY.finditer(text):
        try:
            out.append(dparser.parse(m[0].replace("of ", ""), dayfirst=True, fuzzy=True).date())
        except (ValueError, OverflowError):
            pass
    return [d for d in out if d]


def _safe(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def days_left(deadline, today=None):
    if deadline is None:
        return None
    if isinstance(deadline, str):
        deadline = datetime.strptime(deadline[:10], "%Y-%m-%d").date()
    return (deadline - (today or date.today())).days
