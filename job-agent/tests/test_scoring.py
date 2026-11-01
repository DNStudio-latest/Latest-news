from datetime import date

from matcher import scoring

TODAY = date(2026, 11, 1)


def base(**kw):
    it = {"title": "Guest Faculty in Journalism and Mass Communication", "employer": "Tripura University",
          "location": "Agartala, Tripura", "deadline": "2026-11-20",
          "eligibility": "Master's degree in Journalism and Mass Communication and UGC NET.",
          "official_link": "https://tripurauniv.ac.in/notice.pdf", "is_official": True}
    it.update(kw)
    return it


def test_perfect_academic_tripura_is_strong(profile, cfgs):
    r = scoring.evaluate(base(), profile, *cfgs, today=TODAY)
    assert r["score"] == 100 and r["label"] == "Strong" and r["status"] == "CANDIDATE"
    assert r["category"] == "academic"


def test_weights_add_up(cfgs):
    assert sum(cfgs[1]["weights"].values()) == 100


def test_aggregator_gets_half_source_points(profile, cfgs):
    r = scoring.evaluate(base(is_official=False), profile, *cfgs, today=TODAY)
    assert r["score_breakdown"]["source"] == 5 and r["score"] == 95


def test_short_deadline_loses_points(profile, cfgs):
    r = scoring.evaluate(base(deadline="2026-11-03"), profile, *cfgs, today=TODAY)
    assert r["score_breakdown"]["deadline"] == 3


def test_expired_is_filtered(profile, cfgs):
    r = scoring.evaluate(base(deadline="2026-08-25"), profile, *cfgs, today=TODAY)
    assert r["status"] == "EXPIRED"


def test_phd_required_excludes(profile, cfgs):
    r = scoring.evaluate(base(title="Assistant Professor, Mass Communication",
                              eligibility="Ph.D. degree is mandatory."), profile, *cfgs, today=TODAY)
    assert r["status"] == "EXCLUDED" and r["score_breakdown"]["eligibility"] == 0


def test_location_outside_preferences_excluded(profile, cfgs):
    r = scoring.evaluate(base(title="Reporter", employer="X", location="London, UK"), profile, *cfgs, today=TODAY)
    assert r["status"] == "EXCLUDED"


def test_remote_ok(profile, cfgs):
    r = scoring.evaluate(base(title="Freelance content writer", employer="X", location="Remote"), profile, *cfgs, today=TODAY)
    assert r["status"] in ("CANDIDATE", "LOW") and r["score_breakdown"]["location_tier"] == "Remote"


def test_weak_items_not_candidates(profile, cfgs):
    r = scoring.evaluate(base(title="Communication officer", employer="Bank", location="Mumbai, India",
                              eligibility="", deadline="", is_official=False), profile, *cfgs, today=TODAY)
    assert r["score"] < 60 and r["label"] == "Weak" and r["status"] == "LOW"


def test_experience_years(profile, cfgs):
    r = scoring.evaluate(base(title="News Editor", eligibility="Minimum 10 years of experience required"), profile, *cfgs, today=TODAY)
    assert r["status"] == "EXCLUDED"
    r = scoring.evaluate(base(title="News Editor", eligibility="Minimum 3 years of experience"), profile, *cfgs, today=TODAY)
    assert r["status"] == "CANDIDATE"
