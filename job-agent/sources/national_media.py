"""Careers pages of national digital outlets you add in config/sources.yaml (media.national_media.entries)."""
from .base import OfficialPageSource

SOURCE = OfficialPageSource("national_media", section="media", kind="media")
