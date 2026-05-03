"""Typed details payload for the ingest step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IngestDetails:
    """Structured ingest outcomes."""

    copied: list[str] = field(default_factory=list)
    skipped_already_present: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


__all__ = ["IngestDetails"]
