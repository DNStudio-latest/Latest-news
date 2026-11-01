"""Freelance: upwork. Public listings only. Never logs in and never bids."""
from .base import SearchPageSource

SOURCE = SearchPageSource("upwork", section="freelance", kind="aggregator", location="Remote")
