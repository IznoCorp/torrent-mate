"""Verify-step event catalog.

Hosts :class:`VerifyItemDone`, emitted by
:func:`personalscraper.verify.run.run_verify` once per media item after
the check → fix → re-check → classify cycle completes.

The event carries both the item outcome (``status``, ``errors``) and
telemetry counts (``checks_passed``, ``checks_total``) so downstream
consumers — the pipeline-monitor host process in particular — can produce
structured per-item observability without re-parsing log files.

The module is imported by :mod:`personalscraper.verify.run` so
``Event.__init_subclass__`` registers ``VerifyItemDone`` before any
consumer calls ``event_from_envelope``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from personalscraper.core.event_bus import Event


@dataclass(frozen=True, kw_only=True)
class VerifyItemDone(Event):
    """Emitted once per media item after the full verify cycle completes.

    Attributes:
        item: Media folder basename (e.g. ``"Inception (2010)"``).
        status: Outcome — ``"valid"``, ``"fixed"``, or ``"blocked"``.
        errors: List of blocking error messages (empty when status is
            ``"valid"`` or ``"fixed"``).
        checks_passed: Number of individual quality checks that passed.
        checks_total: Total number of individual quality checks run.
    """

    item: str
    status: str
    errors: list[str] = field(default_factory=list)
    checks_passed: int = 0
    checks_total: int = 0


__all__ = ["VerifyItemDone"]
