"""Simple, explainable eligibility checks against profile facts.

Returns 'met', 'not_met' or 'unclear' plus reasons. 'not_met' is used only when the notice
clearly asks for something the CV clearly does not have.
"""
import re

PHD_REQUIRED = re.compile(r"ph\.?\s?d\.?\s*(degree\s*)?(is\s*)?(awarded|mandatory|essential|required|compulsory)|must\s+(have|hold)\s+(a\s+)?ph\.?\s?d|ph\.?\s?d\.?\s+in\s+[\w &]+\s+(is\s+)?(essential|mandatory)", re.I)
NET = re.compile(r"\b(ugc[- ]?)?net\b|\bslet\b|\bset\b", re.I)
MASTERS = re.compile(r"master'?s?|post[- ]?graduat|\bm\.?a\.?\b|\bmjmc\b|\bmmc\b", re.I)
EXP_YEARS = re.compile(r"(?:minimum|at\s+least|min\.?)?\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:relevant\s+|post[- ]qualification\s+|teaching\s+|professional\s+)?experience", re.I)
LANG = re.compile(r"\b(english|bengali|bangla|hindi|assamese|nepali|kokborok|manipuri|mizo|khasi|garo|odia|tamil|telugu|marathi|gujarati|kannada|malayalam|punjabi|urdu)\b", re.I)
FIELD_JMC = re.compile(r"journalism|mass\s+comm|media\s+studies|communication|jmc|mcj", re.I)
AGE = re.compile(r"(?:age|aged)[^.]{0,40}?(?:not\s+(?:more|exceed)|below|under|maximum|max\.?)[^.]{0,15}?(\d{2})", re.I)


def check(text, profile):
    text = text or ""
    facts = profile.get("eligibility_facts", {})
    reasons_bad, reasons_ok, reasons_unclear = [], [], []

    if PHD_REQUIRED.search(text):
        if facts.get("phd_awarded"):
            reasons_ok.append("PhD required: awarded")
        else:
            reasons_bad.append("notice requires an awarded PhD; CV says PhD is being pursued")
    if NET.search(text) and facts.get("ugc_net_jmc"):
        reasons_ok.append("UGC NET (JMC) qualified")
    if MASTERS.search(text) and facts.get("masters_jmc"):
        reasons_ok.append("Master's in JMC (CGPA 7.61)")
        if re.search(r"55\s*%", text):
            reasons_unclear.append("55% at Master's: CV gives CGPA 7.61; check the university's CGPA-to-% rule")

    yrs = [int(m) for m in EXP_YEARS.findall(text)]
    if yrs:
        need = max(yrs)
        have = facts.get("years_media_experience_min", 0)
        if "teaching" in text.lower() and re.search(r"\d+\s*years?\s*(of\s+)?teaching", text, re.I):
            have = facts.get("years_teaching_min", 0)
        (reasons_ok if have >= need else reasons_bad).append(f"needs {need} years experience; CV supports {have}+")

    langs = {l.lower().replace("bangla", "bengali") for l in LANG.findall(text)}
    mine = {l.lower() for l in facts.get("languages", [])}
    if langs:
        if langs & mine:
            reasons_ok.append("language match: " + ", ".join(sorted(langs & mine)))
        elif re.search(r"(must|essential|required|mandatory)[^.]{0,40}(" + "|".join(langs) + ")", text, re.I) or \
             re.search(r"(" + "|".join(langs) + r")[^.]{0,20}(is\s+)?(must|essential|required|mandatory)", text, re.I):
            reasons_bad.append("required language not in CV: " + ", ".join(sorted(langs)))
        else:
            reasons_unclear.append("languages mentioned: " + ", ".join(sorted(langs)))

    if AGE.search(text):
        reasons_unclear.append("age limit mentioned; date of birth is not in the CV")

    if reasons_bad:
        return "not_met", reasons_bad + reasons_unclear
    if reasons_ok and not reasons_unclear:
        return "met", reasons_ok
    if reasons_ok:
        return "met", reasons_ok + reasons_unclear
    return "unclear", reasons_unclear or ["eligibility text missing or too short to check"]
