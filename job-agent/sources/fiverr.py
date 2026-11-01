"""Freelance: fiverr. Public listings only. Never logs in and never bids."""
from .base import SearchPageSource

SOURCE = SearchPageSource("fiverr", section="freelance", kind="aggregator", location="Remote")
