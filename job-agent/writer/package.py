"""Write output/queue/<id>-<short-title>/ for one item."""
import json
import re

from lib import log, paths
from .cv_facts import CV, check_text, check_traces, drop_placeholder_lines, read_cv
from . import tailor
from .export import md_to_pdf


def short(title):
    return re.sub(r"[^a-z0-9]+", "-", (title or "item").lower()).strip("-")[:40]


def folder_for(item, base=None):
    return (base or paths.QUEUE) / f"{item['id']}-{short(item.get('title'))}"


def prepare(item, profile, base=None):
    """Create the package. Returns (folder, status, missing) where status is QUEUED or BLOCKED."""
    cv_text = read_cv()
    cv = CV(cv_text)
    out = folder_for(item, base)
    out.mkdir(parents=True, exist_ok=True)
    extra = " ".join(str(item.get(k) or "") for k in ("title", "employer", "location", "department"))

    cv_md, t1 = tailor.tailored_cv(item, cv, profile)
    cv_md, dropped = drop_placeholder_lines(cv_md)
    if dropped:
        log.get("writer").warning("dropped lines with placeholders from tailored CV: %s", dropped)
    letter, t2 = tailor.cover_letter(item, cv, profile)
    answers, t3, needs = tailor.form_answers(item, cv, profile)
    problems = []
    for name, text, tr in (("tailored_cv", cv_md, t1), ("cover_letter", letter, t2), ("form_answers", answers, t3)):
        problems += [f"{name}: {p}" for p in check_text(text, cv_text, extra) + check_traces(tr, cv_text)]

    (out / "tailored_cv.md").write_text(cv_md, encoding="utf-8")
    (out / "cover_letter.md").write_text(letter, encoding="utf-8")
    (out / "form_answers.md").write_text(answers, encoding="utf-8")
    try:
        pages = md_to_pdf(cv_md, out / "tailored_cv.pdf")
    except Exception as e:
        pages = None
        problems.append(f"PDF export failed: {e}")

    missing = tailor.required_facts(item, profile)
    docs = tailor.required_docs(item)
    status = "BLOCKED" if (missing or problems) else "QUEUED"
    item = dict(item, status=status, missing=missing, needs=needs, required_documents=docs,
                cover_letter_words=len(letter.split()), cv_pages=pages, fact_check_problems=problems)
    (out / "checklist.md").write_text(tailor.checklist(item, missing, needs, docs, pages, problems), encoding="utf-8")
    (out / "item.json").write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
    return out, status, missing + problems
