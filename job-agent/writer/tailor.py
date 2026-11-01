"""Builds the application package for one item. Uses only CV facts (see writer/cv_facts.py)."""
import json
import re

from .cv_facts import CV, display_dates, check_text, check_traces

ROLE_ORDER = {
    "academic":      ["Guest Lecturer", "Journalist", "Founder and Editor", "Chief Reporter", "Video Content Creator", "Assistant Project Coordinator", "Member"],
    "journalism":    ["Journalist", "Founder and Editor", "Chief Reporter", "Video Content Creator", "Guest Lecturer", "Assistant Project Coordinator", "Member"],
    "video":         ["Video Content Creator", "Founder and Editor", "Journalist", "Chief Reporter", "Guest Lecturer", "Assistant Project Coordinator", "Member"],
    "freelance":     ["Founder and Editor", "Video Content Creator", "Journalist", "Chief Reporter", "Guest Lecturer", "Assistant Project Coordinator", "Member"],
    "communication": ["Founder and Editor", "Journalist", "Video Content Creator", "Member", "Chief Reporter", "Guest Lecturer", "Assistant Project Coordinator"],
    "fellowship":    ["Journalist", "Founder and Editor", "Guest Lecturer", "Video Content Creator", "Chief Reporter", "Assistant Project Coordinator", "Member"],
}
SKILL_FIRST = {
    "academic": ["Teaching", "Climate", "News reporting"],
    "journalism": ["News reporting", "News website", "Climate"],
    "video": ["Video editing", "Documentary", "News website"],
    "freelance": ["News reporting", "Video editing", "Documentary"],
    "communication": ["Climate", "News website", "News reporting"],
    "fellowship": ["Climate", "News reporting", "Teaching"],
}
SUMMARY_KEYS = {
    "academic": ["Guest Lecturer", "UGC NET", "Journalist and editor", "founded"],
    "journalism": ["Journalist and editor", "founded", "travel videos", "Guest Lecturer"],
    "video": ["travel videos", "founded", "Journalist and editor"],
    "freelance": ["Journalist and editor", "travel videos", "founded"],
    "communication": ["Journalist and editor", "founded", "Guest Lecturer"],
    "fellowship": ["Journalist and editor", "Guest Lecturer", "founded"],
}
REQUIRED_FACT_PATTERNS = {
    "date_of_birth": (r"date of birth|\bdob\b|age\s+(limit|not|below|as on)|years of age", "Date of birth"),
    "category": (r"\bcategory\b|\bsc\b|\bst\b|\bobc\b|\bews\b|caste", "Category (General/SC/ST/OBC/EWS)"),
    "ba_percentage": (r"percentage|% marks|marks in|graduation marks|division", "BA percentage / division"),
    "address": (r"postal address|permanent address|correspondence address", "Postal address"),
    "clips": (r"\bclips\b|writing samples|portfolio of (published|articles)|published (work|articles) samples|samples of", "3-5 bylined clips (titles, dates, links)"),
    "phd_enrolment": (r"ph\.?\s?d\.?\s*(registration|enrol)", "PhD year of enrolment"),
}
DOC_PATTERNS = [
    (r"photograph|photo", "Recent passport photo"), (r"signature", "Scanned signature"),
    (r"mark ?sheets?|certificates?|testimonials?", "Mark sheets and certificates (self-attested)"),
    (r"\bnet\b", "UGC NET certificate"), (r"experience certificate", "Experience certificate(s)"),
    (r"\bnoc\b|no objection", "NOC from current employer"), (r"bio-?data|curriculum vitae|\bcv\b|resume", "CV"),
    (r"cover letter", "Cover letter"),
]


def _lc_first(s):
    return s[0].lower() + s[1:] if s and not s[:2].isupper() else s


def _order(names, cv):
    out = []
    for n in names:
        r = cv.role(n)
        if r and r not in out:
            out.append(r)
    out += [r for r in cv.roles if r not in out]
    return out


def tailored_cv(item, cv, profile):
    cat = item.get("category") or "journalism"
    traces = []
    L = [f"# {profile['name'].title()}", "", profile["headline"], ""]
    c, l = profile["contact"], profile["links"]
    L += [f"Phone: {c['phone']} | Email: {c['email_personal']} | {c['email_official']}",
          f"Website: {l['website']} | YouTube: {l['youtube']} | LinkedIn: {l['linkedin']}", ""]

    L += ["## Professional Summary", ""]
    sents = cv.summary_sentences()
    keys = SUMMARY_KEYS.get(cat, SUMMARY_KEYS["journalism"])
    chosen = sorted(sents, key=lambda s: next((i for i, k in enumerate(keys) if k in s[1]), 99))
    L.append(" ".join(s for _, s in chosen))
    traces += [(s, s) for _, s in chosen]
    L.append("")

    if cat in ("academic", "fellowship"):
        L += _education(cv, traces) + _research(cv, traces)

    L += ["## Work Experience", ""]
    for r in _order(ROLE_ORDER.get(cat, ROLE_ORDER["journalism"]), cv):
        if not r["org"] and not cv.clean_bullets(r):
            continue          # e.g. "Other Experience": only placeholder text in the CV
        dates = display_dates(r["dates"])
        L.append(f"**{r['title']}** | {r['org']}" + (f" | {dates}" if dates else ""))
        traces.append((r["title"], r["raw"].split("|")[0].strip()))
        for _, b in cv.clean_bullets(r):
            L.append(f"- {b}")
            traces.append((b, b))
        L.append("")

    if cat not in ("academic", "fellowship"):
        L += _education(cv, traces) + _research(cv, traces)

    L += ["## Skills", ""]
    skills = [s[2:] for _, s in cv.section_lines("SKILLS") if s.startswith("* ")]
    first = SKILL_FIRST.get(cat, [])
    skills.sort(key=lambda s: next((i for i, k in enumerate(first) if s.startswith(k)), 99))
    L += [f"- {s}" for s in skills]
    traces += [(s, s) for s in skills]
    L += [f"- Languages: {', '.join(profile['languages'])}", ""]
    return "\n".join(L).strip() + "\n", traces


def _education(cv, traces):
    L = ["## Education", ""]
    for _, s in cv.sections.get("EDUCATION", []):
        clean = re.sub(r"\s*\|\s*\[[^\]]*\]", "", s)          # drop "| [placeholder]" parts
        if "[" in clean:
            continue
        L.append(f"- {clean[2:]}" if clean.startswith("* ") else f"**{clean}**")
        traces.append((clean, clean.lstrip("* ")))
    return L + [""]


def _research(cv, traces):
    lines = [s for _, s in cv.section_lines("RESEARCH INTERESTS")]
    traces += [(s, s) for s in lines]
    return ["## Research Interests", ""] + lines + [""]


def cover_letter(item, cv, profile, max_words=250):
    cat = item.get("category") or "journalism"
    title, employer = item.get("title", "the advertised post"), item.get("employer") or "your organisation"
    traces = []
    claims = []

    def from_summary(key):
        s = next((s for _, s in cv.summary_sentences() if key in s), None)
        return s

    def role_line(role_prefix, n_bullets=1):
        r = cv.role(role_prefix)
        if not r:
            return None
        bl = cv.clean_bullets(r)[:n_bullets]
        if not bl:
            return None
        text = f"As {r['title']} ({r['org'].split('(')[0].strip()}), I " + " I also ".join(_lc_first(b).rstrip(".") + "." for _, b in bl)
        for _, b in bl:
            traces.append((text, b))
        traces.append((text, r["title"]))
        return text

    s1 = from_summary("Journalist and editor")
    if s1:
        claims.append("I am a " + _lc_first(s1))
        traces.append((claims[-1], s1))
    plan = {
        "academic": [("summary", "Guest Lecturer"), ("Guest Lecturer", 2), ("summary", "UGC NET"), ("research", None)],
        "journalism": [("Journalist", 2), ("summary", "founded"), ("Chief Reporter", 1)],
        "video": [("Video Content Creator", 2), ("summary", "travel videos"), ("summary", "founded")],
        "freelance": [("summary", "founded"), ("Video Content Creator", 1), ("Journalist", 1)],
        "communication": [("summary", "founded"), ("Founder and Editor", 1), ("research", None)],
        "fellowship": [("summary", "Guest Lecturer"), ("Journalist", 1), ("research", None)],
    }.get(cat, [])
    for kind, arg in plan:
        if kind == "summary":
            s = from_summary(arg)
            if s and s not in claims and not any(s in c for c in claims):
                claims.append(s)
                traces.append((s, s))
        elif kind == "research":
            ri = cv.section_lines("RESEARCH INTERESTS")
            if ri:
                t = "My research interests are " + _lc_first(ri[0][1])
                claims.append(t)
                traces.append((t, ri[0][1]))
        else:
            t = role_line(kind, arg)
            if t:
                claims.append(t)

    opening = f"I am writing to apply for the post of {title} at {employer}."
    closing = ["My CV is attached.", f"I would be glad to discuss how I can contribute to {employer}.",
               "Thank you for your time and consideration."]
    name = profile["name"].title()

    def build(cl):
        body = [opening, " ".join(cl), " ".join(closing)]
        return "\n\n".join(["Dear Selection Committee,"] + body + [f"Yours sincerely,\n{name}\n{profile['contact']['phone']} | {profile['contact']['email_personal']}"])

    letter = build(claims)
    while len(letter.split()) > max_words and len(claims) > 1:
        claims.pop()
        letter = build(claims)
    kept = set(claims)
    traces = [t for t in traces if t[0] in kept]
    return letter + "\n", traces


def form_answers(item, cv, profile):
    cat = item.get("category") or "journalism"
    rows, needs = [], []

    def add(q, a, src):
        rows.append((q, a, src))

    s = next((s for _, s in cv.summary_sentences() if "six years" in s), None)
    add("Total experience", s or "NEEDS YOUR INPUT", s)
    cur = [r for r in cv.roles if "Present" in r["dates"]]
    add("Current roles", "; ".join(f"{r['title']}, {r['org']}" for r in cur), cur[0]["raw"].split("|")[0].strip() if cur else None)
    gl = cv.role("Guest Lecturer")
    if gl:
        add("Teaching experience", f"{gl['title']}, {gl['org']}, {gl['dates']}. " + " ".join(b for _, b in cv.clean_bullets(gl)), gl["raw"])
    add("Highest qualification",
        "Master of Journalism and Mass Communication, Tripura University (CGPA: 7.61). Ph.D. (Pursuing), Journalism and Mass Communication, Tripura University. UGC NET (Journalism and Mass Communication): Qualified four times.",
        "Master of Journalism and Mass Communication | Tripura University")
    thesis = next((s for _, s in cv.sections.get("EDUCATION", []) if "Thesis" in s), None)
    if thesis:
        add("PhD research topic", thesis[2:], thesis[2:])
    ri = cv.section_lines("RESEARCH INTERESTS")
    if ri:
        add("Research interests", ri[0][1], ri[0][1])
    why_src = {"academic": "Teach journalism and mass communication to postgraduate students.",
               "video": "Produce, shoot, and edit news, analysis, and travel videos.",
               "communication": "Climate change and environmental reporting",
               "fellowship": "Climate change and environmental reporting"}.get(cat, "Write, edit, and publish news reports with accuracy and clarity.")
    add("Why this role (draft, edit in your own words)",
        f"The post of {item.get('title')} at {item.get('employer')} matches my work. " +
        ("In my current work I " + _lc_first(why_src).rstrip(".") + "." if not why_src.startswith("Climate") else f"My skills include: {why_src}."),
        why_src)
    add("Availability / notice period", "NEEDS YOUR INPUT (not in CV)", None)
    needs.append("Availability / notice period")
    add("Languages", ", ".join(profile["languages"]) + " (levels: NEEDS YOUR INPUT)",
        "Languages: English, Bengali, Hindi, Assamese, Nepali")
    needs.append("Language levels")
    l = profile["links"]
    add("Portfolio links", f"Website: {l['website']} | YouTube: {l['youtube']} | LinkedIn: {l['linkedin']} | Facebook: {l['facebook']} | Instagram: {l['instagram']}",
        "Website: insightnenews.in")
    add("Bylined work samples", "NEEDS YOUR INPUT (CV has only placeholders for titles and dates)", None)
    if cat in ("journalism", "freelance", "fellowship"):
        needs.append("3-5 bylined clips")

    md = [f"# Form answers: {item.get('title')} ({item.get('employer')})", "",
          "Every answer is traced to a CV line. Edit anything before approving.", ""]
    traces = []
    for q, a, src in rows:
        ln = cv.line_of(src) if src else None
        md += [f"## {q}", "", a, "", f"_Source: CV line {ln}: \"{src}\"_" if ln else "_Source: not in CV_", ""]
        if src:
            traces.append((a, src))
    return "\n".join(md), traces, needs


def required_facts(item, profile):
    text = " ".join(str(item.get(k) or "") for k in ("eligibility", "how_to_apply", "title"))
    missing = []
    known = profile.get("extra_facts", {}) or {}
    for key, (pat, label) in REQUIRED_FACT_PATTERNS.items():
        if re.search(pat, text, re.I) and not known.get(key):
            missing.append(label)
    return missing


def required_docs(item):
    text = " ".join(str(item.get(k) or "") for k in ("eligibility", "how_to_apply"))
    docs = [label for pat, label in DOC_PATTERNS if re.search(pat, text, re.I)]
    for d in ("CV", "Cover letter"):
        if d not in docs:
            docs.append(d)
    return docs


def checklist(item, missing_facts, needs, docs, pages, problems):
    L = [f"# Checklist: {item.get('title')}", "",
         f"- Employer: {item.get('employer')}",
         f"- Deadline: {item.get('deadline') or 'unknown'} ({item.get('deadline_raw','')[:120]})",
         f"- Official link: {item.get('official_link') or 'NOT FOUND - verify before applying'}",
         f"- How to apply: {item.get('how_to_apply') or 'see notice'}",
         f"- Verification: {item.get('verification')} {item.get('verification_note','')}",
         f"- Score: {item.get('score')} ({item.get('label')})", "",
         "## Required documents", ""] + [f"- [ ] {d}" for d in docs] + ["",
         "## Eligibility notes", ""] + [f"- {r}" for r in item.get("score_breakdown", {}).get("eligibility_reasons", [])] + ["",
         "## Missing items (you must provide)", ""]
    miss = missing_facts + [n for n in needs if n not in missing_facts]
    L += [f"- [ ] {m}" for m in miss] or ["- none"]
    L += ["", "## Quality checks", "",
          f"- Tailored CV length: {pages} page(s)" + (" (OVER 2 PAGES: trim before sending)" if pages and pages > 2 else ""),
          "- Fact check: " + ("passed (every claim found in CV)" if not problems else "PROBLEMS: " + "; ".join(problems))]
    return "\n".join(L) + "\n"
