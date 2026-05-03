"""Typed details payload for the clean step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CleanDetails:
    """Structured clean-step filesystem changes."""

    removed_dirs: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    renamed: dict[str, str] = field(default_factory=dict)


__all__ = ["CleanDetails"]
