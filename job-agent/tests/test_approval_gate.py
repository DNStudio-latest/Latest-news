"""No submission without approval, a trusted+approved site, an open deadline and a person saying yes."""
import json
from datetime import date
from pathlib import Path

import yaml

from lib import paths, store
from submitter import gate, submit
from writer import package
from tests.conftest import FakeFetcher

FIX = Path(__file__).parent / "fixtures" / "sample_item.json"
from datetime import timedelta
DEADLINE = date.today() + timedelta(days=60)
PAGE = (f"<html><body>Guest faculty. Eligibility: Master's in JMC and NET. Last date {DEADLINE:%d.%m.%Y}. "
        "Apply by email to demo@example.org</body></html>")


def setup_item(profile, trusted_status="approved", confirm_profile=True):
    item = json.loads(FIX.read_text(encoding="utf-8"))
    item["eligibility"] = "Master's in JMC and NET. Send CV."
    item["deadline"] = DEADLINE.isoformat()
    from matcher.verify import fingerprint
    item["page_fingerprint"] = fingerprint(PAGE)[0]
    folder, status, _ = package.prepare(item, profile)
    item["status"] = status
    store.init_files()
    store.save_opportunities({item["id"]: item})
    t = {"sites": [{"domain": "example.org", "method": "email", "status": trusted_status}]}
    paths.TRUSTED.write_text(yaml.safe_dump(t), encoding="utf-8")
    if confirm_profile:
        p = yaml.safe_load(paths.PROFILE.read_text(encoding="utf-8"))
        p["confirmed_by_user"] = True
        paths.PROFILE.write_text(yaml.safe_dump(p, allow_unicode=True), encoding="utf-8")
    return item


class Sender:
    def __init__(self):
        self.sent = []

    def __call__(self, msg):
        self.sent.append(msg)


def run_submit(answer="yes"):
    sender, said = Sender(), []
    res = submit.submit_all(ask=lambda q: answer, out=said.append, interactive=True,
                            fetcher=FakeFetcher({"https://example.org/demo": PAGE}), sender=sender)
    return res, sender, "\n".join(said)


def test_refuses_without_approval(home, profile):
    setup_item(profile)
    res, sender, said = run_submit()
    assert res == [] and not sender.sent and "No approved items" in said


def test_refuses_named_item_without_approval(home, profile):
    item = setup_item(profile)
    said = []
    submit.submit_all(ask=lambda q: "yes", out=said.append, interactive=True, item_ids=[item["id"]], sender=Sender())
    assert any("REFUSED" in s and "no 'approve'" in s for s in said)


def test_reject_and_hold_do_not_submit(home, profile):
    item = setup_item(profile)
    for d in ("reject", "hold"):
        store.record_approval(item["id"], item["title"], d)
        res, sender, _ = run_submit()
        assert not sender.sent


def test_latest_decision_wins(home, profile):
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve")
    store.record_approval(item["id"], item["title"], "reject")
    _, sender, _ = run_submit()
    assert not sender.sent


def test_pending_trusted_site_refused(home, profile):
    item = setup_item(profile, trusted_status="pending")
    store.record_approval(item["id"], item["title"], "approve")
    res, sender, said = run_submit()
    assert not sender.sent and "status is 'pending'" in said


def test_untrusted_site_refused(home, profile):
    item = setup_item(profile)
    paths.TRUSTED.write_text("sites: []\n", encoding="utf-8")
    store.record_approval(item["id"], item["title"], "approve")
    _, sender, said = run_submit()
    assert not sender.sent and "not in config/trusted_sites.yaml" in said


def test_unconfirmed_profile_refused(home, profile):
    item = setup_item(profile, confirm_profile=False)
    store.record_approval(item["id"], item["title"], "approve")
    _, sender, said = run_submit()
    assert not sender.sent and "profile not confirmed" in said


def test_expired_refused(home, profile):
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve")
    item = store.load_opportunities()[item["id"]]
    assert f"deadline passed ({DEADLINE.isoformat()})" in gate.check(item, today=DEADLINE + timedelta(days=1))


def test_answer_no_does_not_send(home, profile):
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve")
    res, sender, _ = run_submit(answer="no")
    assert not sender.sent and res[0][0] == "declined"
    assert store.load_submissions()[-1]["decision"] == "no"


def test_yes_sends_exactly_once_and_logs(home, profile):
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve")
    res, sender, said = run_submit(answer="yes")
    assert len(sender.sent) == 1 and res[0][0] == "submitted"
    assert "PREVIEW" in said
    row = store.load_submissions()[-1]
    assert row["result"] == "submitted" and row["confirmation_ref"]
    # second run refuses: already submitted
    _, sender2, said2 = run_submit(answer="yes")
    assert not sender2.sent and "already submitted" in said2


def test_page_change_stops(home, profile):
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve")
    sender, said = Sender(), []
    changed = PAGE.replace(f"{DEADLINE:%d.%m.%Y}", f"{DEADLINE - timedelta(days=10):%d.%m.%Y}")
    submit.submit_all(ask=lambda q: "yes", out=said.append, interactive=True,
                      fetcher=FakeFetcher({"https://example.org/demo": changed}), sender=sender)
    assert not sender.sent and any("STOPPED" in s for s in said)


def test_failure_retries_only_once(home, profile):
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve")
    calls = []

    def bad(msg):
        calls.append(1)
        raise OSError("smtp down")
    submit.submit_all(ask=lambda q: "yes", out=lambda s: None, interactive=True,
                      fetcher=FakeFetcher({"https://example.org/demo": PAGE}), sender=bad)
    assert len(calls) == 2 and store.load_submissions()[-1]["result"] == "failed"


def test_non_interactive_refused(home, profile):
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve")
    said = []
    submit.submit_all(ask=lambda q: "yes", out=said.append, interactive=False, sender=Sender())
    assert "REFUSED" in said[0]


def test_review_never_changes_decision_without_asking(home, profile):
    import review
    item = setup_item(profile)
    store.record_approval(item["id"], item["title"], "approve", "first")
    answers = iter(["no"])              # "Change this decision?" -> no
    review.review(ask=lambda q: next(answers), out=lambda s: None)
    assert [r["decision"] for r in store.load_approvals()] == ["approve"]
    answers = iter(["yes", "h", "wait for BA marks"])
    review.review(ask=lambda q: next(answers), out=lambda s: None)
    rows = store.load_approvals()
    assert [r["decision"] for r in rows] == ["approve", "hold"] and rows[-1]["timestamp"]
