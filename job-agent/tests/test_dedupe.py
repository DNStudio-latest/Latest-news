from matcher.dedupe import dedupe, make_id, canonical_url


def test_same_title_employer_deadline_is_one_item():
    a = {"title": "Guest Faculty - JMC", "employer": "Tripura University", "deadline": "2026-08-25", "source": "agg"}
    b = {"title": "guest faculty  JMC!", "employer": "TRIPURA UNIVERSITY", "deadline": "2026-08-25", "source": "x"}
    assert len(dedupe([a, b])) == 1


def test_same_official_link_is_one_item():
    a = {"title": "A", "employer": "E", "official_link": "https://www.tripurauniv.ac.in/n.pdf"}
    b = {"title": "B", "employer": "F", "official_link": "http://tripurauniv.ac.in/n.pdf/"}
    assert len(dedupe([a, b])) == 1


def test_official_copy_wins():
    agg = {"title": "Reporter", "employer": "NE Now", "deadline": "", "is_official": False, "link": "https://agg/x"}
    off = {"title": "Reporter", "employer": "NE Now", "deadline": "", "is_official": True, "official_link": "https://nenow.in/x"}
    out = dedupe([agg, off])
    assert len(out) == 1 and out[0]["is_official"] is True and out[0]["official_link"] == "https://nenow.in/x"


def test_different_deadlines_are_different():
    a = {"title": "Guest Faculty", "employer": "TU", "deadline": "2026-01-01"}
    b = {"title": "Guest Faculty", "employer": "TU", "deadline": "2026-08-25"}
    assert make_id(a) != make_id(b) and len(dedupe([a, b])) == 2


def test_canonical_url():
    assert canonical_url("http://m.nenow.in/a/b/") == canonical_url("https://www.nenow.in/a/b")
