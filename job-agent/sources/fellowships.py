"""Fellowships and grants pages (config/sources.yaml -> fellowships.pages)."""
from .base import Source, extract_notices


class FellowshipSource(Source):
    kind = "fellowship"

    def collect(self, fetcher, cfg):
        items = []
        for p in cfg["fellowships"]["pages"]:
            html = self.get(fetcher, p["url"])
            if html:
                official = "aggregator" not in p["employer"]
                for it in extract_notices(html, p["url"], p["employer"], "India / Remote", self.name, official):
                    it["remote"] = True
                    items.append(it)
        return items


SOURCE = FellowshipSource("fellowships")
