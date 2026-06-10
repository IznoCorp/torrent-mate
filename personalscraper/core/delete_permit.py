"""Neutral deletion-authority port types (RP3).

Import direction: stdlib + typing only (mirror core/_contracts.py).
Never imported by acquire/ implementation modules at the top level —
inject via the composition root.

The deleters (maintenance/disk_cleaner, dispatch/) depend ONLY on these
core port types. The concrete acquire/ implementation is injected at the
composition root. This ensures deleters never import acquire/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class _Allow:
    """Singleton sentinel meaning the deletion is permitted."""

    def __repr__(self) -> str:
        return "ALLOW"


@dataclass(frozen=True)
class _Veto:
    """A deletion veto with a human-readable reason."""

    reason: str

    def __repr__(self) -> str:
        return f"VETO({self.reason!r})"

    def __str__(self) -> str:
        return f"VETO: {self.reason}"


#: Singleton ALLOW sentinel returned by permit implementations.
ALLOW: _Allow = _Allow()

PermitDecision = _Allow | _Veto


def veto(reason: str) -> _Veto:
    """Construct a VETO decision with the given reason string.

    Args:
        reason: Human-readable explanation for the veto.

    Returns:
        A _Veto instance carrying the reason.
    """
    return _Veto(reason=reason)


@runtime_checkable
class DeletePermit(Protocol):
    """Protocol for deletion-authority implementations.

    A ``DeletePermit`` is consulted before any media deletion.
    Implementations MUST be fail-open: any lookup error → ALLOW.
    VETO is only returned on a positively-known unmet seed obligation.
    """

    def may_delete(self, path: Path) -> PermitDecision:
        """Return ALLOW or a VETO for the given path.

        Args:
            path: The filesystem path about to be deleted.

        Returns:
            ``ALLOW`` if deletion is permitted, ``veto(reason)`` if it is not.
        """
        ...


@runtime_checkable
class SeedObligationRecorder(Protocol):
    """Protocol for recording a seed obligation at dispatch time.

    Implementations MUST be fail-soft: any write error is swallowed and
    logged; the caller is never interrupted by an obligation-write failure.
    """

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> None:
        """Correlate staging_source to a live seeding torrent and record the obligation.

        Called BEFORE the FS move (write-before-move guarantee).

        Args:
            staging_source: Absolute path of the file in the staging area.
            dispatched_dest: Absolute path of the destination after dispatch.
        """
        ...

    def mark_breach(self, path: Path) -> None:
        """Mark every active obligation under *path* as breached (DESIGN §7.3).

        Called by the dispatch flow when the "real media wins" rule deletes a
        live payload before its seed obligation is met. Implementations MUST be
        fail-soft: any write error is swallowed and logged; the caller is never
        interrupted.

        Args:
            path: Absolute path whose active obligations are breached.
        """
        ...


class AllowAllPermit:
    """Fail-open no-op DeletePermit — always returns ALLOW.

    Used as the default for tests, for dispatch/maintenance when no store
    is present, and as the fallback when the store is unreadable.
    Also implements SeedObligationRecorder as a no-op.
    """

    def may_delete(self, path: Path) -> PermitDecision:
        """Always permit the deletion.

        Args:
            path: Ignored.

        Returns:
            Always ``ALLOW``.
        """
        return ALLOW

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> None:
        """No-op recorder — does nothing.

        Args:
            staging_source: Ignored.
            dispatched_dest: Ignored.
        """

    def mark_breach(self, path: Path) -> None:
        """No-op breach marker — does nothing.

        Args:
            path: Ignored.
        """


__all__ = [
    "ALLOW",
    "AllowAllPermit",
    "DeletePermit",
    "PermitDecision",
    "SeedObligationRecorder",
    "veto",
]
