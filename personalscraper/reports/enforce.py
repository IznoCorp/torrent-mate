"""Typed details payload for the enforce step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnforceDetails:
    """Structured enforce-step outcomes."""

    corrected: list[str] = field(default_factory=list)
    already_compliant: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


__all__ = ["EnforceDetails"]
