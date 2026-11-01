"""python run.py review: approve / reject / hold each queued item. Decisions go to data/approvals.csv."""
from lib import store


def review(ask=input, out=print):
    store.init_files()
    items = [i for i in store.load_opportunities().values() if i.get("status") in ("QUEUED", "BLOCKED")]
    if not items:
        out("Nothing waiting for review.")
        return 0
    decided = store.latest_decisions()
    n = 0
    for i in sorted(items, key=lambda x: -float(x.get("score") or 0)):
        out("\n" + "-" * 70)
        out(f"[{i['id']}] {i['title']}\n  Employer: {i.get('employer')}\n  Score: {i.get('score')} ({i.get('label')})  "
            f"Deadline: {i.get('deadline') or 'unknown'}  Status: {i['status']}\n  Link: {i.get('official_link') or i.get('link')}")
        prev = decided.get(i["id"])
        if prev:
            out(f"  Already decided: {prev['decision'].upper()} on {prev['timestamp']}" + (f" ({prev['note']})" if prev["note"] else ""))
            if ask("  Change this decision? (yes / no): ").strip().lower() != "yes":
                continue
        while True:
            a = ask("  Decision: [a]pprove / [r]eject / [h]old / [s]kip: ").strip().lower()
            dec = {"a": "approve", "approve": "approve", "r": "reject", "reject": "reject", "h": "hold", "hold": "hold"}.get(a)
            if a in ("s", "skip", ""):
                break
            if dec:
                if dec == "approve" and i["status"] == "BLOCKED":
                    out("  Note: this item is BLOCKED. Approval is recorded, but submit will refuse until the missing items are fixed.")
                note = ask("  Note (optional): ").strip()
                store.record_approval(i["id"], i["title"], dec, note)
                out(f"  Recorded: {dec}")
                n += 1
                break
            out("  Please type a, r, h or s.")
    return n
