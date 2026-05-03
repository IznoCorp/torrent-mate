"""Typed details payload for the verify step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VerifyIssue:
    """Structured verify issue for one path."""

    path: str
    code: str
    message: str | None = None


@dataclass
class VerifyDetails:
    """Structured verify outcomes."""

    verified: list[str] = field(default_factory=list)
    issues: list[VerifyIssue] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)


__all__ = ["VerifyDetails", "VerifyIssue"]
