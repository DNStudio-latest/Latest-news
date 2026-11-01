"""Turns cv/cv.md into traceable facts, and checks generated text against the CV.

Rule: any line containing a [placeholder] is never used as a fact.
"""
import re

from lib import paths

PLACEHOLDER = re.compile(r"\[[^\]]*\]")
SECTIONS = ["PROFESSIONAL SUMMARY", "WORK EXPERIENCE", "BYLINED WORK", "EDUCATION", "SKILLS",
            "RESEARCH INTERESTS", "ADDITIONAL INTERESTS"]


def read_cv(path=None):
    return (path or paths.CV).read_text(encoding="utf-8")


def placeholders(cv_text):
    out = []
    for n, line in enumerate(cv_text.splitlines(), 1):
        for m in PLACEHOLDER.finditer(line):
            out.append({"line": n, "placeholder": m[0], "context": line.strip()})
    return out


class CV:
    def __init__(self, text):
        self.text = text
        self.lines = text.splitlines()
        self.sections = self._split()
        self.roles = self._roles()

    def _split(self):
        cur, out = "HEADER", {"HEADER": []}
        for n, raw in enumerate(self.lines, 1):
            s = raw.strip()
            if s in SECTIONS:
                cur = s
                out[cur] = []
                continue
            if s:
                out[cur].append((n, s))
        return out

    def _roles(self):
        """Work experience: role header lines contain ' | '; bullets start with '* '."""
        roles, cur = [], None
        for n, s in self.sections.get("WORK EXPERIENCE", []):
            if s.startswith("* "):
                if cur is not None:
                    cur["bullets"].append((n, s[2:]))
            else:
                parts = [p.strip() for p in s.split("|")]
                cur = {"line": n, "raw": s, "title": parts[0], "org": parts[1] if len(parts) > 1 else "",
                       "dates": parts[2] if len(parts) > 2 else "", "bullets": []}
                roles.append(cur)
        return roles

    def summary_sentences(self):
        text = " ".join(s for _, s in self.sections.get("PROFESSIONAL SUMMARY", []))
        line = next((n for n, _ in self.sections.get("PROFESSIONAL SUMMARY", [])), 0)
        sents = re.split(r"(?<=[.])\s+(?=[A-Z])", text)
        return [(line, s) for s in sents if s and not PLACEHOLDER.search(s)]

    def role(self, title_prefix):
        return next((r for r in self.roles if r["title"].lower().startswith(title_prefix.lower())), None)

    def clean_bullets(self, role):
        return [(n, b) for n, b in role["bullets"] if not PLACEHOLDER.search(b)]

    def section_lines(self, name, drop_placeholders=True):
        return [(n, s) for n, s in self.sections.get(name, []) if not (drop_placeholders and PLACEHOLDER.search(s))]

    def line_of(self, needle):
        for n, l in enumerate(self.lines, 1):
            if needle in l:
                return n
        return None


def drop_placeholder_lines(md):
    """Safety net: a generated line that still holds a [placeholder] is removed, never sent."""
    keep, dropped = [], []
    for l in md.splitlines():
        (dropped if PLACEHOLDER.search(re.sub(r"\[(NEEDS YOUR INPUT| |x|X)\]", "", l)) else keep).append(l)
    return "\n".join(keep) + "\n", dropped


def display_dates(d):
    """'[Start month and year] – Present' -> 'Present'; 'May 2021 – [End...]' -> 'From May 2021'."""
    if not d:
        return ""
    if not PLACEHOLDER.search(d):
        return d
    stripped = PLACEHOLDER.sub("", d).strip(" –-")
    if d.strip().startswith("["):
        return stripped
    return f"From {stripped}" if stripped else ""


# --------------------------------------------------------------------------- fact checking
TEMPLATE_VOCAB = {
    # words the templates themselves use (not claims about you)
    "dear", "i", "am", "writing", "to", "apply", "for", "the", "post", "of", "at", "my", "cv", "is", "attached",
    "thank", "you", "yours", "sincerely", "selection", "committee", "hiring", "team", "in", "role", "as",
    "would", "be", "glad", "discuss", "how", "can", "contribute", "and", "a", "an", "with", "on", "this",
    "research", "interests", "are", "include", "time", "consideration", "position", "experience", "also",
    "present", "from", "summary", "work", "education", "skills", "languages", "links", "contact", "tailored",
    "professional", "relevant", "other", "bylined", "teaching", "academic", "journalism", "video", "media",
    "editorial", "communication", "fellowship", "freelance", "source", "cv", "line", "needs", "your", "input",
    "not", "confirmed", "levels", "website", "youtube", "facebook", "instagram", "linkedin", "phone", "email",
    "regards", "respected", "sir", "madam", "subject", "application", "interest", "every", "answer", "traced",
    "edit", "anything", "before", "approving", "draft", "own", "words", "why", "current", "roles", "highest",
    "qualification", "availability", "notice", "period", "portfolio", "samples", "total", "topic", "matches",
}
TOKEN = re.compile(r"\b(?:\d[\d.,%+]*|[A-Z][A-Za-z'’.&-]+)")


def check_text(text, cv_text, allowed_extra=""):
    """Return a list of problems. Every number and every capitalised word in `text` must appear
    in the CV (or in the job item fields given in `allowed_extra`, or the template vocabulary).
    Any [placeholder] left in the text is also a problem."""
    problems = []
    # headings and "_Source: CV line N_" lines are structure, not claims (sources are checked by check_traces)
    text = "\n".join(l for l in text.splitlines() if not l.startswith("#") and not l.startswith("_Source"))
    for l in text.splitlines():
        m = PLACEHOLDER.search(re.sub(r"\[(NEEDS YOUR INPUT|x|X| )\]", "", l))
        if m:
            problems.append(f"placeholder text left in document: {l.strip()[:120]!r}")
    hay = (cv_text + " " + (allowed_extra or "")).lower()
    for tok in set(TOKEN.findall(text)):
        t = tok.strip(".,%+’'").lower()
        if not t or t in TEMPLATE_VOCAB:
            continue
        if t not in hay:
            problems.append(f"'{tok}' is not in the CV")
    return sorted(problems)


def check_traces(traces, cv_text):
    """Each trace is (generated_sentence, cv_source_text). The source must be in the CV verbatim."""
    return [f"trace not in CV: {src!r}" for _, src in traces if src and src not in cv_text]
