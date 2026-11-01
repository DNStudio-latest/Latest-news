"""Freelance: internshala. Public listings only. Never logs in and never bids."""
from .base import SearchPageSource

SOURCE = SearchPageSource("internshala", section="freelance", kind="aggregator", location="Remote")
