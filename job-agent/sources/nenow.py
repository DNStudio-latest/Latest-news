"""Northeast Now (nenow.in). Its 'Assam Career' section mostly reposts OTHER employers' jobs.
Those are treated as aggregator items (they must be verified on the employer's site).
Posts about Northeast Now's own vacancies are kept as official."""
import re

from .base import Source, extract_notices

OWN = re.compile(r"northeast now|nenow", re.I)


class NenowSource(Source):
    kind = "media"

    def collect(self, fetcher, cfg):
        c = cfg["media"]["nenow"]
        items = []
        for url in c["start_urls"]:
            html = self.get(fetcher, url)
            if html is None:
                continue
            for it in extract_notices(html, url, c["employer"], c["location"], self.name, True):
                if OWN.search(it["title"]):
                    items.append(it)
                elif not c.get("own_posts_only"):
                    it.update(is_official=False, official_link="", employer="(see post)")
                    items.append(it)
        return items


SOURCE = NenowSource("nenow")
