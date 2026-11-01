"""Scam signals. A fee on an official government/university site is normal in India,
so it is only noted, not called a scam. Elsewhere, any fee to apply is a scam signal."""
import re
from urllib.parse import urlparse

FEE = re.compile(r"(registration|application|processing|security|joining|training)\s*(fee|charge|deposit)|pay\s+(rs\.?|inr|₹)\s*\d+|refundable deposit", re.I)
PAY_TRAINING = re.compile(r"(pay|payment)\s+for\s+(the\s+)?training|paid\s+training\s+before", re.I)
WHATSAPP_ONLY = re.compile(r"(only|just)\s+(via|on|through)?\s*whats\s?app|whats\s?app\s+only|apply\s+(on|via)\s+whats\s?app\s*(no\.?|number)?\s*[:\-]?\s*\+?\d", re.I)
EMAIL_OR_FORM = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|apply online|application form|walk[- ]in", re.I)
ID_BANK = re.compile(r"(bank\s+(account|details)|aadhaa?r|pan\s+card|otp|atm\s+pin|upi\s+pin)", re.I)
BEFORE_INTERVIEW = re.compile(r"before\s+(the\s+)?interview|to\s+(confirm|reserve|book)\s+(your\s+)?(slot|seat|interview)|immediate(ly)?\s+send", re.I)
TOO_GOOD = re.compile(r"earn\s+(rs\.?|₹|inr)?\s*\d[\d,]*\s*(per|a)\s*day|no\s+interview|100%\s+job\s+guarantee|guaranteed\s+job", re.I)

OFFICIAL_TLDS = (".gov.in", ".nic.in", ".ac.in", ".edu.in", ".res.in", ".gov")


def is_official_domain(url):
    host = urlparse(url or "").netloc.lower()
    return any(host.endswith(t) for t in OFFICIAL_TLDS)


def check(item):
    """Return (is_scam, reasons, notes)."""
    text = " ".join(str(item.get(k) or "") for k in ("title", "eligibility", "how_to_apply", "description"))
    url = item.get("official_link") or item.get("link") or ""
    reasons, notes = [], []
    if FEE.search(text):
        if is_official_domain(url):
            notes.append("Application fee mentioned on an official site (common for government posts). Check before paying.")
        else:
            reasons.append("asks for a fee to apply")
    if PAY_TRAINING.search(text):
        reasons.append("asks for payment for training")
    if WHATSAPP_ONLY.search(text) and not EMAIL_OR_FORM.search(text):
        reasons.append("WhatsApp-only hiring")
    if ID_BANK.search(text) and (BEFORE_INTERVIEW.search(text) or not is_official_domain(url)):
        reasons.append("asks for bank/ID details before an interview")
    if TOO_GOOD.search(text):
        reasons.append("too-good-to-be-true promise")
    return bool(reasons), reasons, notes
