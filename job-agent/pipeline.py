"""One run: collect -> verify -> score/filter -> prepare -> queue README -> summary. Never submits."""
from datetime import date

from lib import config, fetch, log, paths, store
from matcher import dedupe, scoring, verify
from sources import registry
from sources.snapshot import SOURCE as SNAPSHOT
from writer import package

L = log.get("pipeline")


def run(source_names=None, use_network=True, use_snapshots=True, today=None, fetcher=None, out=print):
    today = today or date.today()
    store.init_files()
    prof, prefs, cfg, scfg = config.profile(), config.preferences(), config.scoring(), config.sources()
    fetcher = fetcher or fetch.Fetcher()
    report = {"new": [], "failed_sources": [], "skipped_sources": [], "scams": [], "blocked": [], "queued": [],
              "expired": [], "unverified": []}

    # 1. collect
    raw = []
    if use_network:
        for src in registry.load(source_names):
            out(f"  collecting: {src.name}")
            try:
                got = src.collect(fetcher, scfg)
            except Exception as e:      # a broken module must not stop the run
                src.fail("-", f"module error {e!r}")
                got = []
            raw += got
            report["failed_sources"] += src.errors
            report["skipped_sources"] += src.skipped
            out(f"    found {len(got)}" + (f", {len(src.errors)} error(s)" if src.errors else "") + (f", {len(src.skipped)} skipped" if src.skipped else ""))
    if use_snapshots:
        only = source_names[0] if source_names and len(source_names) == 1 else None
        snap = SNAPSHOT.collect(fetcher, scfg, only_source=only)
        out(f"  snapshot items: {len(snap)}")
        raw += snap

    existing = store.load_opportunities()
    items = dedupe.dedupe(raw)
    for it in items:
        it["id"] = it.get("id") or dedupe.make_id(it)
        old = existing.get(it["id"])
        if old is None:
            it["found_at"] = store.now_iso()
            report["new"].append(it)
        else:
            it = {**old, **{k: v for k, v in it.items() if v not in (None, "")}}
        existing[it["id"]] = it

    # 2-4. verify, score, prepare
    for it in existing.values():
        if it.get("status") in ("SUBMITTED",):
            continue
        res = scoring.evaluate(it, prof, prefs, cfg, today)
        it.update(res)
        if it["status"] == "SUSPECTED SCAM":
            report["scams"].append(it)
        elif it["status"] == "EXPIRED":
            report["expired"].append(it)
        if it["status"] == "CANDIDATE":
            if use_network and it.get("verification") != "VERIFIED":
                verify.verify(it, fetcher)
                it.update(scoring.evaluate(it, prof, prefs, cfg, today))   # deadline may have changed
            it.setdefault("verification", "UNVERIFIED")
            if not it.get("verification"):
                it["verification"] = "UNVERIFIED"
            if it["status"] == "CANDIDATE":
                if cfg.get("queue_requires_verified", True) and it["verification"] != "VERIFIED":
                    it["status"] = "UNVERIFIED"
                    report["unverified"].append(it)
                else:
                    folder, status, missing = package.prepare(it, prof)
                    it["status"] = status
                    (report["blocked"] if status == "BLOCKED" else report["queued"]).append((it, folder, missing))
        if not it.get("verification"):
            it["verification"] = "UNVERIFIED"
        it["updated_at"] = store.now_iso()
    store.save_opportunities(existing)

    write_queue_readme(existing)
    write_results(existing)
    path = write_summary(report, existing, today)
    return report, path


def _active(by_id):
    return [i for i in by_id.values() if i.get("status") in ("QUEUED", "BLOCKED")]


def write_queue_readme(by_id):
    rows = sorted(_active(by_id), key=lambda i: -float(i.get("score") or 0))
    L_ = ["# Waiting for your approval", "", "Run `python run.py review` to approve, reject or hold.", "",
          "| ID | Title | Employer | Score | Deadline | Status | Needs |", "|---|---|---|---|---|---|---|"]
    for i in rows:
        f = package.folder_for(i)
        needs = ""
        try:
            import json
            j = json.loads((f / "item.json").read_text())
            needs = "; ".join(j.get("missing", []) + j.get("needs", []))
        except Exception:
            pass
        L_.append(f"| {i['id']} | {i['title'][:60]} | {i.get('employer','')[:30]} | {i.get('score')} | {i.get('deadline') or '?'} | {i['status']} | {needs} |")
    if not rows:
        L_.append("| - | Nothing queued this time | | | | | |")
    paths.QUEUE.mkdir(parents=True, exist_ok=True)
    (paths.QUEUE / "README.md").write_text("\n".join(L_) + "\n", encoding="utf-8")


def write_results(by_id):
    rows = sorted(by_id.values(), key=lambda i: -float(i.get("score") or 0))
    L_ = ["# All opportunities (ranked)", "", "| Score | Label | Status | Title | Employer | Deadline | Verified | Link |",
          "|---|---|---|---|---|---|---|---|"]
    for i in rows:
        L_.append(f"| {i.get('score')} | {i.get('label')} | {i.get('status')} | {i.get('title','')[:70]} | {i.get('employer','')[:35]} | "
                  f"{i.get('deadline') or '?'} | {i.get('verification') or '-'} | {i.get('official_link') or i.get('link')} |")
    (paths.OUTPUT / "results.md").write_text("\n".join(L_) + "\n", encoding="utf-8")


def write_summary(rep, by_id, today):
    def line(i):
        return f"- **{i.get('title')}** ({i.get('employer')}): score {i.get('score')}, deadline {i.get('deadline') or 'unknown'}, {i.get('status')}"
    live = [i for i in by_id.values() if i.get("status") not in ("EXPIRED", "EXCLUDED", "SUSPECTED SCAM")]
    top = sorted(live, key=lambda i: -float(i.get("score") or 0))[:5]
    L_ = [f"# Run summary: {today.isoformat()}", "",
          f"New items found: **{len(rep['new'])}**. Total in data: {len(by_id)}. "
          f"Queued: {len(rep['queued'])}. Blocked: {len(rep['blocked'])}. Unverified: {len(rep['unverified'])}. Expired: {len(rep['expired'])}.", "",
          "## Top 5 open items", ""] + ([line(i) for i in top] or ["- none open right now"]) + [
          "", "## BLOCKED (what you must provide)", ""] + (
          [f"- **{i['title']}**: " + "; ".join(m) for i, _, m in rep["blocked"]] or ["- none"]) + [
          "", "## Not verified on the official site (not queued)", ""] + (
          [line(i) + f"  \n  Reason: {i.get('verification_note')}" for i in rep["unverified"]] or ["- none"]) + [
          "", "## Expired", ""] + ([line(i) for i in rep["expired"]] or ["- none"]) + [
          "", "## Suspected scams (not engaged)", ""] + ([line(i) + " - " + "; ".join(i.get("flags", [])) for i in rep["scams"]] or ["- none"]) + [
          "", "## Sources that failed", ""] + ([f"- {e}" for e in rep["failed_sources"]] or ["- none"]) + [
          "", "## Sources skipped (robots.txt, block, or not configured)", ""] + ([f"- {e}" for e in rep["skipped_sources"]] or ["- none"])
    p = paths.OUTPUT / f"summary-{today.isoformat()}.md"
    p.write_text("\n".join(L_) + "\n", encoding="utf-8")
    return p
