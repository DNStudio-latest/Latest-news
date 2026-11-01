"""Items saved by hand or by an assistant's web search into data/snapshots/*.json.

Use this when the agent's own network access is blocked. Each snapshot item keeps its provenance.
Snapshot items are never marked VERIFIED automatically: the verify step must open the official link.
"""
import json

from lib import paths
from .base import Source


class SnapshotSource(Source):
    kind = "snapshot"

    def collect(self, fetcher, cfg, only_source=None):
        items = []
        for f in sorted(paths.SNAPSHOTS.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                self.fail(str(f), e)
                continue
            for it in data.get("items", []):
                if only_source and it.get("source") != only_source:
                    continue
                it.setdefault("provenance", data.get("provenance", f.name))
                items.append(it)
        return items


SOURCE = SnapshotSource("snapshot")
