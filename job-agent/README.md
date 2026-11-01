# Job & Project Application Agent

Finds jobs, projects and fellowships, scores them against your CV, prepares a tailored application
for each good match, and submits **only** what you approve, **only** on sites you trust, **only** after you type `yes`.

## Safety rules built in

| Rule | Where it is enforced |
|---|---|
| No submission without your approval for that item | `submitter/gate.py` reads the latest decision in `data/approvals.csv` |
| Only trusted sites, and only entries with `status: approved` | `config/trusted_sites.yaml`, `submitter/gate.py` |
| Final "Submit this application? (yes / no)" for every item | `submitter/submit.py`, `submitter/form.py` |
| Submit never runs on a schedule (needs a keyboard) | `submitter/submit.py` refuses if not interactive |
| No passwords/keys in files; asked at runtime, never printed | SMTP password via `getpass` or `SMTP_PASSWORD` env var |
| No CAPTCHA/login/bot-check bypass | `lib/fetch.py` stops for that site and logs it |
| robots.txt respected, 3+ seconds between requests per domain | `lib/fetch.py` |
| No invented facts | `writer/cv_facts.py` checks every number and name against `cv/cv.md`; `[placeholders]` are never used |
| Missing fact needed by a notice -> item BLOCKED | `writer/tailor.py` (`required_facts`) |
| Scam signals -> SUSPECTED SCAM, not engaged | `matcher/scam.py` |
| Page changed since approval -> stop and ask | `submitter/submit.py` re-checks the official page |
| At most one retry on failure | `submitter/submit.py`, `submitter/form.py` |
| No accounts created | form filler stops on any password field |

## Setup

```bash
cd job-agent
python3 -m pip install -r requirements.txt
# put your CV at cv/cv.md, then check config/profile.yaml and set confirmed_by_user: true
python3 -m pytest -q        # all tests should pass
```

`cv/cv.md`, `config/profile.yaml`, `data/*.csv`, `output/` and `logs/` are in `.gitignore`
because this repository is public. Keep a copy of them on your own computer.

## Commands

| Command | What it does |
|---|---|
| `python run.py run` | Search all sources, verify, score, prepare packages, write the summary. **Never submits.** |
| `python run.py run --source tripura_university` | Run one source only (repeat `--source` for more). |
| `python run.py run --offline` | No network: use items saved in `data/snapshots/*.json`. |
| `python run.py review` | Go through queued items: approve / reject / hold, with a note. Asks before changing an old decision. |
| `python run.py submit` | Submit approved items (all gates must pass, then a preview, then `yes`). `--id ID` for one item. |
| `python run.py status` | Counts by status. |
| `python run.py missing` | Show the facts missing from your CV. |
| `python run.py demo` | Build a sample package from a made-up job (folder `output/demo/`, marked DEMO). |
| `python run.py reset` | Clear found items and outputs (asks first, backs up to `logs/`). `--all` also clears approvals and submissions. |

## Where things are

- `output/summary-YYYY-MM-DD.md`: read this after each run.
- `output/results.md`: every item, ranked.
- `output/queue/README.md`: items waiting for you, and what each one needs.
- `output/queue/<id>-<title>/`: `tailored_cv.md/.pdf`, `cover_letter.md`, `form_answers.md`, `checklist.md`, `item.json`.
  Put extra files (mark sheets, NET certificate) in an `attachments/` folder inside it.
- `data/opportunities.csv`, `data/approvals.csv`, `data/submissions.csv`; `output/submitted/<id>/` holds the sent email or screenshots.

## Statuses

`CANDIDATE` (scored 60+, being checked) -> `QUEUED` or `BLOCKED` (missing facts) -> after approval and `yes`: logged in `submissions.csv`.
Others: `UNVERIFIED` (could not confirm on official site, not queued), `LOW` (score under 60), `EXPIRED`, `EXCLUDED`
(eligibility clearly not met / outside locations / wrong role), `SUSPECTED SCAM`.

## Scoring (config/scoring.yaml)

Role 40, location 15, eligibility 25, deadline (5+ days) 10, source reliability 10 (aggregator = half).
80+ Strong, 60-79 Good, under 60 Weak (kept, not queued). Only **verified** items are queued.

## How to add a trusted site

Edit `config/trusted_sites.yaml`:

```yaml
sites:
  - domain: example.ac.in
    method: email          # email | form | manual
    status: approved       # only YOU set this; "pending" never submits
    note: "why you trust it"
```

For `method: email`, set `SMTP_HOST`, `SMTP_PORT` (default 587) and `SMTP_USER` in your shell.
The password is asked when sending (or read from `SMTP_PASSWORD`). Nothing is saved.
For Gmail use an App Password. `method: form` needs `pip install playwright`.

## Adding sources

URLs live in `config/sources.yaml`. Each source has its own module in `sources/`. Job boards and freelance
sites are searched through public pages only; most of them forbid automated access in robots.txt, and the agent
then skips them and says so in the summary. Aggregator results are never queued until the official notice is found.

If the agent cannot reach the web, you can save items by hand in `data/snapshots/<name>.json`
(see the existing file for the format) and run `python run.py run --offline`.

## Scheduling

Not set up. If you want it, a weekly search-only run (Monday 9 AM) on your own computer:

```
0 9 * * 1  cd /path/to/job-agent && python3 run.py run >> logs/cron.log 2>&1
```

`submit` refuses to run without a person at the keyboard, so it can never run from a schedule.
