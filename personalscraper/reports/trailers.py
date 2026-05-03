"""Typed details payload for the trailers step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrailersDetails:
    """Structured trailers-step outcomes."""

    downloaded: list[str] = field(default_factory=list)
    bot_detected: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


__all__ = ["TrailersDetails"]
