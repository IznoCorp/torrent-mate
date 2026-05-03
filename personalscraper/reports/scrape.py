"""Typed details payload for the scrape step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScrapeDetails:
    """Structured scrape outcomes."""

    scraped: list[str] = field(default_factory=list)
    skipped_low_confidence: list[str] = field(default_factory=list)
    existing_validated: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    unmatched_paths: list[str] = field(default_factory=list)


__all__ = ["ScrapeDetails"]
