import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A throw-away copy of the agent (config + CV), so tests never touch real data."""
    from lib import paths
    if not (ROOT / "cv" / "cv.md").exists() or not (ROOT / "config" / "profile.yaml").exists():
        pytest.skip("put your CV at cv/cv.md and keep config/profile.yaml to run these tests")
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "cv").mkdir()
    shutil.copy(ROOT / "cv" / "cv.md", tmp_path / "cv" / "cv.md")
    new = {
        "ROOT": tmp_path, "CV": tmp_path / "cv" / "cv.md", "CONFIG": tmp_path / "config",
        "PROFILE": tmp_path / "config" / "profile.yaml", "PREFERENCES": tmp_path / "config" / "preferences.yaml",
        "TRUSTED": tmp_path / "config" / "trusted_sites.yaml", "SCORING": tmp_path / "config" / "scoring.yaml",
        "SOURCES_CFG": tmp_path / "config" / "sources.yaml", "DATA": tmp_path / "data",
        "OPPORTUNITIES": tmp_path / "data" / "opportunities.csv", "APPROVALS": tmp_path / "data" / "approvals.csv",
        "SUBMISSIONS": tmp_path / "data" / "submissions.csv", "SNAPSHOTS": tmp_path / "data" / "snapshots",
        "OUTPUT": tmp_path / "output", "QUEUE": tmp_path / "output" / "queue",
        "SUBMITTED": tmp_path / "output" / "submitted", "LOGS": tmp_path / "logs",
    }
    for k, v in new.items():
        monkeypatch.setattr(paths, k, v)
    paths.ensure_dirs()
    return tmp_path


@pytest.fixture
def profile(home):
    from lib import config
    return config.profile()


@pytest.fixture
def cfgs(home):
    from lib import config
    return config.preferences(), config.scoring()


class NoNetwork:
    """Fetcher stand-in: any network call fails, like the real blocked sandbox."""
    blocked_domains = {}

    def get(self, url):
        raise ConnectionError("network disabled in tests")


class FakeFetcher:
    """Returns canned pages by URL."""
    def __init__(self, pages):
        self.pages = pages
        self.blocked_domains = {}

    def get(self, url):
        if url not in self.pages:
            raise ConnectionError("not found")

        class R:
            pass
        r = R()
        r.text = self.pages[url]
        r.content = r.text.encode()
        r.headers = {"content-type": "text/html"}
        r.url = url
        return r


@pytest.fixture
def no_net():
    return NoNetwork()
