"""Typed details payload for the cleanup step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CleanupDetails:
    """Structured cleanup outcomes."""

    removed: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)


__all__ = ["CleanupDetails"]
