"""All file locations in one place. Set JOB_AGENT_HOME to point at another copy (used by tests)."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("JOB_AGENT_HOME", Path(__file__).resolve().parent.parent))
CV = ROOT / "cv" / "cv.md"
CONFIG = ROOT / "config"
PROFILE = CONFIG / "profile.yaml"
PREFERENCES = CONFIG / "preferences.yaml"
TRUSTED = CONFIG / "trusted_sites.yaml"
SCORING = CONFIG / "scoring.yaml"
SOURCES_CFG = CONFIG / "sources.yaml"
DATA = ROOT / "data"
OPPORTUNITIES = DATA / "opportunities.csv"
APPROVALS = DATA / "approvals.csv"
SUBMISSIONS = DATA / "submissions.csv"
SNAPSHOTS = DATA / "snapshots"
OUTPUT = ROOT / "output"
QUEUE = OUTPUT / "queue"
SUBMITTED = OUTPUT / "submitted"
LOGS = ROOT / "logs"


def ensure_dirs():
    for d in (DATA, SNAPSHOTS, QUEUE, SUBMITTED, LOGS):
        d.mkdir(parents=True, exist_ok=True)
