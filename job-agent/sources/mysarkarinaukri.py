"""Job board: mysarkarinaukri. Public search pages only, no login. Results are aggregator items and must be
verified on the employer's official site before they can be queued."""
from .base import SearchPageSource

SOURCE = SearchPageSource("mysarkarinaukri", section="boards", kind="aggregator")
