"""Fill a public web form with Playwright, stop before Submit, show a preview, submit only on 'yes'.

Stops if the page needs a login, shows a CAPTCHA, or has no recognisable form. Never creates accounts.
"""
import re

from lib import paths, store
from writer.cv_facts import read_cv

FIELD_MAP = [
    (r"full\s*name|^name|applicant'?s?\s*name", lambda p, a: p["name"].title()),
    (r"e-?mail", lambda p, a: p["contact"]["email_personal"]),
    (r"phone|mobile|contact\s*no", lambda p, a: p["contact"]["phone"]),
    (r"linkedin", lambda p, a: p["links"]["linkedin"]),
    (r"website|portfolio|url", lambda p, a: p["links"]["website"]),
    (r"experience", lambda p, a: a.get("Total experience")),
    (r"qualification", lambda p, a: a.get("Highest qualification")),
    (r"language", lambda p, a: a.get("Languages")),
    (r"cover\s*letter|why|message|statement", lambda p, a: a.get("_cover_letter")),
]


def parse_answers(md):
    out, cur = {}, None
    for line in md.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
        elif cur and line.strip() and not line.startswith("_Source"):
            out.setdefault(cur, line.strip())
    return out


def submit_form(item, pkg, folder, ask, out, fetcher):
    from lib import config
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out("  STOPPED: Playwright is not installed. Use method 'manual' or 'email'.")
        return ("stopped", item["id"], ["playwright missing"])
    profile = config.profile()
    answers = parse_answers((folder / "form_answers.md").read_text(encoding="utf-8"))
    answers["_cover_letter"] = (folder / "cover_letter.md").read_text(encoding="utf-8")
    cv_file = next((folder / n for n in ("tailored_cv.pdf", "tailored_cv.docx") if (folder / n).exists()), None)
    ev = paths.SUBMITTED / item["id"]
    ev.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        page.goto(item["official_link"], wait_until="domcontentloaded")
        html = page.content().lower()
        if page.locator("input[type=password]").count() or "captcha" in html or "recaptcha" in html:
            b.close()
            out("  STOPPED: the form needs a login or shows a CAPTCHA. Please apply yourself.")
            return ("stopped", item["id"], ["login or captcha"])
        filled = []
        for el in page.locator("input:not([type=hidden]):not([type=submit]):not([type=file]), textarea").all():
            label = " ".join(filter(None, [el.get_attribute("name"), el.get_attribute("id"), el.get_attribute("placeholder"),
                                           el.get_attribute("aria-label")])).lower()
            for pat, fn in FIELD_MAP:
                if re.search(pat, label):
                    val = fn(profile, answers)
                    if val and "NEEDS YOUR INPUT" not in val:
                        el.fill(val)
                        filled.append((label, val[:80]))
                    break
        uploads = []
        for fi in page.locator("input[type=file]").all():
            if cv_file:
                fi.set_input_files(str(cv_file))
                uploads.append(cv_file.name)
                break
        page.screenshot(path=str(ev / "preview.png"), full_page=True)
        out("\n  ---- PREVIEW (not submitted) ----")
        for l, v in filled:
            out(f"  {l}: {v}")
        out("  Files attached: " + (", ".join(uploads) or "none"))
        out(f"  Screenshot: {ev / 'preview.png'}")
        ans = ask("\n  Submit this application? (yes / no): ").strip().lower()
        if ans != "yes":
            b.close()
            store.record_submission(item_id=item["id"], title=item["title"], site=item["official_link"], method="form",
                                    decision="no", result="not submitted", evidence_path=str(ev / "preview.png"))
            return ("declined", item["id"], [])
        err, ref = None, ""
        for attempt in (1, 2):
            try:
                page.locator("button[type=submit], input[type=submit]").first.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                body = page.inner_text("body")
                if re.search(r"error|failed|invalid", body, re.I) and not re.search(r"thank|success|received", body, re.I):
                    raise RuntimeError("site shows an error after submit")
                m = re.search(r"(application|reference|ref\.?)\s*(no\.?|number|id)\s*[:#]?\s*([A-Z0-9/-]{4,})", body, re.I)
                ref = m[3] if m else ""
                err = None
                break
            except Exception as e:
                err = str(e)[:200]
                out(f"  Submit attempt {attempt} failed: {err}")
        page.screenshot(path=str(ev / "after_submit.png"), full_page=True)
        (ev / "confirmation_page.html").write_text(page.content(), encoding="utf-8")
        b.close()
    store.record_submission(item_id=item["id"], title=item["title"], site=item["official_link"], method="form",
                            decision="yes", result="submitted" if not err else "failed", confirmation_ref=ref,
                            evidence_path=str(ev), note=err or "")
    return ("submitted" if not err else "failed", item["id"], [err] if err else [])
