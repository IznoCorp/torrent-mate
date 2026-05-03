"""Typed details payload for the dispatch step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DispatchDetails:
    """Structured dispatch outcomes."""

    moved_to_disk: dict[str, list[str]] = field(default_factory=dict)
    merged: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


__all__ = ["DispatchDetails"]
