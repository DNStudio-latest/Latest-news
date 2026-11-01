"""python run.py submit: approved items only, on trusted sites only, with a final yes/no for each one.

It never runs without a person at the keyboard, never creates accounts, never retries more than once.
"""
import getpass
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from email.utils import make_msgid

from lib import config, fetch, log, paths, store
from matcher import verify
from . import gate

L = log.get("submit")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def submit_all(ask=input, out=print, fetcher=None, interactive=None, item_ids=None, sender=None):
    interactive = sys.stdin.isatty() if interactive is None else interactive
    if not interactive:
        out("REFUSED: submit needs a person at the keyboard. It never runs on a schedule.")
        return []
    store.init_files()
    items = store.load_opportunities()
    decisions = store.latest_decisions()
    approved = [i for iid, i in items.items() if decisions.get(iid, {}).get("decision") == "approve"]
    if item_ids:
        approved = [i for i in approved if i["id"] in item_ids]
        for iid in item_ids:
            if iid not in {i["id"] for i in approved}:
                out(f"REFUSED [{iid}]: no 'approve' decision in data/approvals.csv.")
    if not approved:
        out("No approved items. Nothing to submit.")
        return []
    fetcher = fetcher or fetch.Fetcher()
    results = []
    for item in approved:
        results.append(submit_one(item, decisions, ask, out, fetcher, sender))
    return results


def submit_one(item, decisions, ask, out, fetcher, sender=None):
    out("\n" + "=" * 70 + f"\n[{item['id']}] {item['title']}")
    reasons = gate.check(item, decisions)
    if reasons:
        for r in reasons:
            out(f"  REFUSED: {r}")
        L.info("refused %s: %s", item["id"], reasons)
        return ("refused", item["id"], reasons)

    # live re-check of the official page
    old_fp, old_deadline = item.get("page_fingerprint"), item.get("deadline")
    fresh = dict(item)
    verify.verify(fresh, fetcher)
    if fresh["verification"] != "VERIFIED" or fresh.get("page_fingerprint") != old_fp or fresh.get("deadline") != old_deadline:
        out("  STOPPED: the official page changed or could not be re-checked:")
        out(f"    {fresh.get('verification_note')}")
        out("  Please look at the page yourself, then run `python run.py run` and `review` again.")
        store.record_submission(item_id=item["id"], title=item["title"], site=item.get("official_link"),
                                method="-", decision="stopped", result="page changed or unreachable",
                                note=fresh.get("verification_note", ""))
        return ("stopped", item["id"], [fresh.get("verification_note")])

    site = gate.site_entry(item["official_link"], config.trusted())
    folder, pkg = gate.load_package(item)
    method = site.get("method", "manual")
    if method == "email":
        return _email(item, pkg, folder, ask, out, sender)
    if method == "form":
        from .form import submit_form
        return submit_form(item, pkg, folder, ask, out, fetcher)
    out("  Method is 'manual'. Your package is ready in: " + str(folder))
    store.record_submission(item_id=item["id"], title=item["title"], site=item["official_link"], method="manual",
                            decision="manual", result="prepared only")
    return ("manual", item["id"], [])


def build_email(item, pkg, folder, profile):
    text = " ".join(str(item.get(k) or "") for k in ("how_to_apply", "eligibility"))
    to = [e for e in EMAIL.findall(text)]
    letter = (folder / "cover_letter.md").read_text(encoding="utf-8")
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM") or profile["contact"]["email_personal"]
    msg["To"] = to[0] if to else ""
    msg["Subject"] = f"Application for the post of {item['title']}"
    msg["Message-ID"] = make_msgid()
    msg.set_content(letter)
    for name in ("tailored_cv.pdf", "tailored_cv.docx"):
        p = folder / name
        if p.exists():
            sub = "pdf" if name.endswith("pdf") else "vnd.openxmlformats-officedocument.wordprocessingml.document"
            msg.add_attachment(p.read_bytes(), maintype="application", subtype=sub,
                               filename=f"{profile['name'].title().replace(' ', '_')}_CV.{name.split('.')[-1]}")
            break
    for p in sorted((folder / "attachments").glob("*")) if (folder / "attachments").exists() else []:
        msg.add_attachment(p.read_bytes(), maintype="application", subtype="octet-stream", filename=p.name)
    return msg


def _email(item, pkg, folder, ask, out, sender=None):
    profile = config.profile()
    msg = build_email(item, pkg, folder, profile)
    if not msg["To"]:
        out("  STOPPED: no email address found in the notice. Add it to the item's how_to_apply and re-run.")
        return ("stopped", item["id"], ["no recipient address"])
    site = gate.site_entry(item["official_link"], config.trusted()) or {}
    dom = site.get("domain", "").lower()
    if dom and not msg["To"].lower().split("@")[1].endswith(dom):
        out(f"  WARNING: the address {msg['To']} is not on the trusted domain {dom}. Check it on the notice.")
    out("\n  ---- PREVIEW ----")
    out(f"  To: {msg['To']}\n  From: {msg['From']}\n  Subject: {msg['Subject']}")
    out("  Attachments: " + ", ".join(p.get_filename() for p in msg.iter_attachments()))
    out("  Body:\n" + "\n".join("    " + l for l in msg.get_body().get_content().splitlines()))
    out("  Form answers file: " + str(folder / "form_answers.md"))
    ans = ask("\n  Submit this application? (yes / no): ").strip().lower()
    store_dir = paths.SUBMITTED / item["id"]
    store_dir.mkdir(parents=True, exist_ok=True)
    if ans != "yes":
        store.record_submission(item_id=item["id"], title=item["title"], site=item["official_link"], method="email",
                                decision="no", result="not sent")
        out("  Not sent.")
        return ("declined", item["id"], [])
    send = sender or _smtp_send
    err = None
    for attempt in (1, 2):                     # at most one retry
        try:
            send(msg)
            err = None
            break
        except Exception as e:
            err = f"{e.__class__.__name__}: {e}"
            L.warning("send attempt %d failed: %s", attempt, err)
            out(f"  Send failed (attempt {attempt}): {err}")
    eml = store_dir / "sent_message.eml"
    eml.write_bytes(bytes(msg))
    store.record_submission(item_id=item["id"], title=item["title"], site=item["official_link"], method="email",
                            decision="yes", result="submitted" if not err else "failed",
                            confirmation_ref=msg["Message-ID"] if not err else "", evidence_path=str(eml), note=err or "")
    out("  SENT." if not err else "  FAILED after one retry. Logged. Not retrying again.")
    return ("submitted" if not err else "failed", item["id"], [err] if err else [])


def _smtp_send(msg):
    host, port, user = os.environ.get("SMTP_HOST"), int(os.environ.get("SMTP_PORT", "587")), os.environ.get("SMTP_USER")
    if not host or not user:
        raise RuntimeError("set SMTP_HOST and SMTP_USER environment variables first")
    pw = os.environ.get("SMTP_PASSWORD") or getpass.getpass("  SMTP password (not saved, not shown): ")
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
