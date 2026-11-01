#!/usr/bin/env python3
"""Job & Project Application Agent - single entry point.

  python run.py run [--source NAME ...] [--offline]   search, verify, score, prepare, summarise (never submits)
  python run.py review                                 approve / reject / hold queued items
  python run.py submit [--id ID ...]                   submit APPROVED items on TRUSTED sites, with a final yes/no
  python run.py status                                 counts and latest summary path
  python run.py missing                                show missing CV fields
  python run.py demo                                   build a sample package (clearly marked DEMO) in output/demo/
  python run.py reset [--all]                          clear found items and outputs (asks first; backs up)
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import paths, store  # noqa: E402


def cmd_run(a):
    import pipeline
    from sources import registry
    names = a.source or None
    if names:
        bad = [n for n in names if n not in registry.ALL and n != "snapshot"]
        if bad:
            sys.exit(f"Unknown source(s): {bad}. Choose from: {', '.join(registry.ALL)}")
        names = [n for n in names if n != "snapshot"] or None
        if not names:
            a.offline = True
    print("Running (search + prepare only; nothing is submitted)...")
    rep, path = pipeline.run(source_names=names, use_network=not a.offline, use_snapshots=not a.no_snapshots)
    print(f"\nNew: {len(rep['new'])} | Queued: {len(rep['queued'])} | Blocked: {len(rep['blocked'])} | "
          f"Unverified: {len(rep['unverified'])} | Expired: {len(rep['expired'])} | Scams: {len(rep['scams'])} | "
          f"Source errors: {len(rep['failed_sources'])}")
    print(f"Summary: {path}\nRanked list: {paths.OUTPUT / 'results.md'}\nQueue: {paths.QUEUE / 'README.md'}")


def cmd_review(a):
    import review
    review.review()


def cmd_submit(a):
    from submitter import submit
    submit.submit_all(item_ids=a.id or None)


def cmd_status(a):
    store.init_files()
    items = store.load_opportunities()
    from collections import Counter
    c = Counter(i.get("status") for i in items.values())
    print(f"{len(items)} items: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    print(f"Approvals logged: {len(store.load_approvals())}  Submissions logged: {len(store.load_submissions())}")
    s = sorted(paths.OUTPUT.glob("summary-*.md"))
    if s:
        print("Latest summary:", s[-1])


def cmd_missing(a):
    print((paths.CONFIG / "missing_fields.md").read_text(encoding="utf-8"))


def cmd_demo(a):
    import json
    from lib import config
    from writer import package
    it = json.loads((paths.ROOT / "tests" / "fixtures" / "sample_item.json").read_text())
    folder, status, missing = package.prepare(it, config.profile(), base=paths.OUTPUT / "demo")
    (folder / "DEMO_NOT_A_REAL_JOB.txt").write_text("This package was built from a made-up test item to show the format.\n")
    print(f"DEMO package (made-up job, for format only): {folder}\nStatus: {status}" + (f"\nMissing: {missing}" if missing else ""))


def cmd_reset(a):
    what = "found items, queue, results and summaries" + (", AND approvals + submissions history" if a.all else "")
    if input(f"This clears {what}. A backup goes to logs/. Type RESET to continue: ").strip() != "RESET":
        print("Cancelled.")
        return
    bk = paths.LOGS / f"backup-{datetime.now():%Y%m%d-%H%M%S}"
    bk.mkdir(parents=True)
    for p in (paths.OPPORTUNITIES, paths.APPROVALS, paths.SUBMISSIONS):
        if p.exists():
            shutil.copy2(p, bk / p.name)
    if paths.QUEUE.exists():
        shutil.copytree(paths.QUEUE, bk / "queue")
    paths.OPPORTUNITIES.unlink(missing_ok=True)
    shutil.rmtree(paths.QUEUE, ignore_errors=True)
    for p in list(paths.OUTPUT.glob("summary-*.md")) + [paths.OUTPUT / "results.md"]:
        p.unlink(missing_ok=True)
    if a.all:
        paths.APPROVALS.unlink(missing_ok=True)
        paths.SUBMISSIONS.unlink(missing_ok=True)
    store.init_files()
    print(f"Done. Backup: {bk}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--source", action="append", help="run only this source (repeatable)")
    r.add_argument("--offline", action="store_true", help="no network: use data/snapshots only")
    r.add_argument("--no-snapshots", action="store_true")
    sub.add_parser("review")
    s = sub.add_parser("submit")
    s.add_argument("--id", action="append")
    sub.add_parser("status")
    sub.add_parser("missing")
    sub.add_parser("demo")
    rs = sub.add_parser("reset")
    rs.add_argument("--all", action="store_true")
    a = ap.parse_args()
    {"run": cmd_run, "review": cmd_review, "submit": cmd_submit, "status": cmd_status, "missing": cmd_missing,
     "demo": cmd_demo, "reset": cmd_reset}[a.cmd](a)


if __name__ == "__main__":
    main()
