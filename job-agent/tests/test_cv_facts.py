"""Every claim in generated documents must come from cv/cv.md."""
import json
import re
from pathlib import Path

import yaml

from writer import package
from writer.cv_facts import CV, check_text, placeholders, read_cv

FIX = Path(__file__).parent / "fixtures" / "sample_item.json"


def _strings(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k not in ("eligibility_facts", "confirmed_by_user"):
                yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)
    elif isinstance(o, str):
        yield o


def test_profile_values_all_in_cv(home):
    cv = read_cv()
    prof = yaml.safe_load((home / "config" / "profile.yaml").read_text(encoding="utf-8"))
    for s in _strings(prof):
        assert s in cv, f"profile value not in CV: {s!r}"
    for src in prof["eligibility_facts"]["derived_from"].values():
        assert src in cv


def test_placeholders_found():
    ph = placeholders("published [20+] stories\nBA | [2013-2016] | [Percentage / Division]\nno placeholder here")
    assert [p["placeholder"] for p in ph] == ["[20+]", "[2013-2016]", "[Percentage / Division]"]
    assert [p["line"] for p in ph] == [1, 2, 2]


def test_missing_fields_file_lists_every_placeholder_line(home):
    md = (home / "config" / "missing_fields.md").read_text(encoding="utf-8").lower()
    for key in ("20+", "start month", "subscriber", "end month", "year of enrolment", "percentage", "software", "level"):
        assert key in md


def test_no_placeholder_facts_used(profile, home):
    cv = CV(read_cv())
    for _, s in cv.summary_sentences():
        assert "[" not in s
    assert not any("[20+]" in s for _, s in cv.summary_sentences())


def test_generated_package_passes_fact_check(profile, home):
    for cat in ("academic", "journalism", "video", "freelance", "communication", "fellowship"):
        item = json.loads(FIX.read_text(encoding="utf-8"))
        item["category"], item["id"] = cat, f"t-{cat}"
        folder, status, problems = package.prepare(item, profile)
        assert not [p for p in problems if "not in the CV" in p or "trace" in p or "placeholder" in p], (cat, problems)
        for name in ("tailored_cv.md", "cover_letter.md", "form_answers.md", "checklist.md", "item.json", "tailored_cv.pdf"):
            assert (folder / name).exists()
        letter = (folder / "cover_letter.md").read_text(encoding="utf-8")
        assert len(letter.split()) <= 250
        assert "[" not in (folder / "tailored_cv.md").read_text(encoding="utf-8")
        assert json.loads((folder / "item.json").read_text(encoding="utf-8"))["cv_pages"] <= 2


def test_checker_catches_invented_claims(home):
    cv = read_cv()
    assert check_text("I won the Pulitzer Prize in 2019.", cv)
    assert check_text("I have 12 years of experience at BBC.", cv)
    assert not check_text("I founded InsightNE News, a news website covering all eight Northeast states in five languages.", cv)


def test_missing_required_fact_blocks_item(profile, home):
    item = json.loads(FIX.read_text(encoding="utf-8"))
    item["eligibility"] += " Candidates must give date of birth and category."
    _, status, missing = package.prepare(item, profile)
    assert status == "BLOCKED" and "Date of birth" in missing


def test_every_form_answer_has_a_source_line(profile, home):
    item = json.loads(FIX.read_text(encoding="utf-8"))
    folder, _, _ = package.prepare(item, profile)
    md = (folder / "form_answers.md").read_text(encoding="utf-8")
    blocks = re.split(r"\n## ", md)[1:]
    cv = read_cv()
    for b in blocks:
        m = re.search(r'_Source: CV line \d+: "(.+)"_', b)
        if m:
            assert m[1] in cv
        else:
            assert "Source: not in CV" in b and "NEEDS YOUR INPUT" in b
