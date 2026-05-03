"""Typed details payload for the sort step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SortResult:
    """Structured sort outcome for one source item."""

    source: str
    destination: str | None = None
    status: str = "skipped"
    media_type: str | None = None
    message: str | None = None


@dataclass
class SortDetails:
    """Structured sort outcomes grouped by status."""

    moved: list[SortResult] = field(default_factory=list)
    skipped: list[SortResult] = field(default_factory=list)
    errored: list[SortResult] = field(default_factory=list)


__all__ = ["SortDetails", "SortResult"]
