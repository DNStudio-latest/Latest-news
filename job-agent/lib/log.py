import logging
from datetime import date
from . import paths

_configured = False


def get(name="job-agent"):
    global _configured
    if not _configured:
        paths.LOGS.mkdir(parents=True, exist_ok=True)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        fh = logging.FileHandler(paths.LOGS / f"run-{date.today().isoformat()}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        root = logging.getLogger("job-agent")
        root.setLevel(logging.INFO)
        root.addHandler(fh)
        _configured = True
    return logging.getLogger("job-agent").getChild(name) if name != "job-agent" else logging.getLogger("job-agent")
