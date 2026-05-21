"""Canonical capability protocols for the notify family (DESIGN §4).

Hosts the two notify protocols — :class:`Notifier` and
:class:`HealthChecker`. Both already existed in
``personalscraper.api.notify._base`` as plain ``Protocol`` classes (the
notify family was authored capability-first ; this sub-phase only
moves them to the cross-family contracts module and adds
``@runtime_checkable`` so consumers may use ``isinstance`` checks
consistently with the metadata / tracker / torrent families).

Names and signatures are **unchanged** : the move is purely a
reorganisation. ``_base.py`` re-exports both protocols so that future
imports work from either location.

The protocols remain fail-soft : implementations MUST NOT raise on
transport or API errors — they log and return ``False`` (for
:class:`Notifier`) or no-op (for :class:`HealthChecker`) so that
notification failures never abort the pipeline.
"""

from __future__ import annotations

from typing import ClassVar, Protocol, runtime_checkable

from personalscraper.models import PipelineReport


@runtime_checkable
class Notifier(Protocol):
    """Protocol for notification providers (Telegram, Slack, …).

    Required members:
        provider_name: Class-level provider identifier (matches every
            concrete provider declaring it as ``ClassVar[str]``).
        REQUIRED_CREDS: List of .env variable names needed by this provider.
        send(): Post a free-form message; returns True on success, False on failure.
        send_report(): Serialize and send a PipelineReport; returns success flag.
    """

    provider_name: ClassVar[str]
    REQUIRED_CREDS: ClassVar[list[str]]

    def send(self, message: str, parse_mode: str = "HTML") -> bool: ...

    def send_report(self, report: PipelineReport) -> bool: ...


@runtime_checkable
class HealthChecker(Protocol):
    """Protocol for dead-man's-switch health-check providers (healthchecks.io, …).

    Implementations are fail-soft: ping_* methods never raise, even when the
    backend is unreachable. They are pure side-effects (no return value) used
    to bracket pipeline runs so external monitoring can detect crashes.

    Required members:
        provider_name: Class-level provider identifier (matches every
            concrete provider declaring it as ``ClassVar[str]``).
        REQUIRED_CREDS: List of .env variable names needed by this provider.
        ping_start(): Signal that a pipeline run has started.
        ping_success(): Signal that a pipeline run completed successfully.
        ping_fail(): Signal that a pipeline run failed.
    """

    provider_name: ClassVar[str]
    REQUIRED_CREDS: ClassVar[list[str]]

    def ping_start(self) -> None: ...

    def ping_success(self) -> None: ...

    def ping_fail(self) -> None: ...


__all__ = ["Notifier", "HealthChecker"]
