import json
from datetime import date

from lib import paths, store
from lib.fetch import detect_block
from sources.base import extract_notices
from tests.conftest import FakeFetcher

HTML = """<html><body><table>
<tr><td><a href="/site/images/notice1.pdf">Advertisement for engagement of Guest Faculty in Journalism and Mass Communication</a></td>
<td>Last date: 20.11.2026</td></tr>
<tr><td><a href="/about">About</a></td></tr>
<tr><td><a href="/n2.pdf">Walk-in interview for JRF in Physics</a> on 01/12/2026</td></tr>
</table></body></html>"""


def test_notice_parser():
    items = extract_notices(HTML, "https://tripurauniv.ac.in/x", "Tripura University", "Agartala, Tripura", "tripura_university", True)
    assert len(items) == 2
    a = items[0]
    assert a["link"] == "https://tripurauniv.ac.in/site/images/notice1.pdf" and a["deadline"] == "2026-11-20"
    assert a["type"] == "guest faculty"


def test_block_detection():
    assert detect_block(429, "")
    assert detect_block(200, "Please complete the CAPTCHA")
    assert detect_block(200, "<h1>Jobs</h1>") is None


def test_pipeline_end_to_end_with_snapshot(home, no_net):
    import pipeline
    snap = {"provenance": "test", "items": [
        {"title": "Guest Faculty in Journalism and Mass Communication", "employer": "Tripura University",
         "location": "Agartala, Tripura", "deadline": "2026-08-25", "source": "tripura_university",
         "eligibility": "UGC Regulations 2018", "official_link": "https://tripurauniv.ac.in/a.pdf", "is_official": True},
        {"title": "Reporter", "employer": "Scam News", "location": "Agartala, Tripura", "deadline": "2026-12-01",
         "eligibility": "Pay registration fee Rs 999", "link": "https://scam.example/x", "source": "naukri"},
        {"title": "Guest Faculty in Mass Communication", "employer": "Tripura University",
         "location": "Agartala, Tripura", "deadline": "2026-12-01", "source": "tripura_university",
         "eligibility": "Master's in JMC and NET", "official_link": "https://tripurauniv.ac.in/b.pdf", "is_official": True},
    ]}
    paths.SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    (paths.SNAPSHOTS / "t.json").write_text(json.dumps(snap), encoding="utf-8")
    rep, summary = pipeline.run(use_network=False, today=date(2026, 11, 1), fetcher=no_net, out=lambda s: None)
    st = {i["title"]: i["status"] for i in store.load_opportunities().values()}
    assert st["Guest Faculty in Journalism and Mass Communication"] == "EXPIRED"
    assert st["Reporter"] == "SUSPECTED SCAM"
    assert st["Guest Faculty in Mass Communication"] == "UNVERIFIED"     # never queued without verification
    assert not any(paths.QUEUE.glob("*/item.json"))
    assert summary.exists() and "Suspected scams" in summary.read_text(encoding="utf-8")


def test_source_failure_does_not_stop_run(home, no_net):
    import pipeline
    rep, _ = pipeline.run(source_names=["tripura_university", "nehu"], use_network=True, use_snapshots=False,
                          today=date(2026, 11, 1), fetcher=no_net, out=lambda s: None)
    assert len(rep["failed_sources"]) == 2


def test_verified_item_gets_queued(home):
    import pipeline
    page = "<html>Guest faculty JMC. Eligibility: Master's and NET. Last date 01.12.2026</html>"
    snap = {"items": [{"title": "Guest Faculty in Mass Communication", "employer": "Tripura University",
                       "location": "Agartala, Tripura", "deadline": "2026-12-01", "source": "tripura_university",
                       "eligibility": "Master's in JMC and NET", "official_link": "https://tripurauniv.ac.in/b",
                       "is_official": True}]}
    (paths.SNAPSHOTS / "t.json").write_text(json.dumps(snap), encoding="utf-8")
    rep, _ = pipeline.run(use_network=True, source_names=["tripura_university"], today=date(2026, 11, 1),
                          fetcher=FakeFetcher({"https://tripurauniv.ac.in/b": page}), out=lambda s: None)
    queued = list(paths.QUEUE.glob("*/item.json"))
    assert len(queued) == 1 and (paths.QUEUE / "README.md").exists()


def test_real_world_false_positives_are_dropped(profile, cfgs):
    """Cases from the first live run (Tezpur University / NEHU pages)."""
    from matcher import scoring
    from sources.base import is_vacancy
    for t in ("Seniority list of Professors of NEHU, Shillong Campus",
              "Seniority List of Assistant Professors of North-Eastern Hill University",
              "Interview Notice for Faculty positions, Department of Chemical Sciences",
              "Interview for Faculty Positions under the Department of Education",
              "Result of Ph.D. entrance", "List of candidates selected for provisional admission"):
        assert not is_vacancy(t), t
    assert is_vacancy("Walk-in interview for Guest Faculty in Mass Communication")
    assert is_vacancy("Advertisement for Assistant Professor, Department of Mass Communication and Journalism")
    r = scoring.evaluate({"title": "Recruitment of Assistant Professor, Department of Chemical Sciences",
                          "employer": "Tezpur University", "location": "Tezpur, Assam", "deadline": "2026-11-30",
                          "eligibility": "", "is_official": True}, profile, *cfgs, today=date(2026, 11, 1))
    assert r["status"] == "EXCLUDED"


def test_far_future_dates_are_ignored():
    from matcher.dates import parse_deadline
    assert parse_deadline("notice_26.03.35.pdf", today=date(2026, 11, 1)) == (None, "unknown")
    assert parse_deadline("Last date 01.04.2086", today=date(2026, 11, 1)) == (None, "unknown")
    assert parse_deadline("file 1757353300 dated 19.12.2099 last date 20.11.2026", today=date(2026, 11, 1))[0] == date(2026, 11, 20)


def test_context_is_the_row_not_the_whole_page():
    big = "<div>" + "Department of Mass Communication news. " * 40 + \
          '<a href="/x.pdf">Advertisement for Assistant Professor, Department of Education</a></div>'
    items = extract_notices(big, "https://tezu.ernet.in/", "Tezpur University", "Tezpur, Assam", "ne", True)
    assert items and "Mass Communication" not in items[0]["eligibility"]
