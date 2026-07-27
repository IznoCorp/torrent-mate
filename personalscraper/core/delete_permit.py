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
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Type-only import (no runtime coupling): record_dispatch returns opaque
    # bus events for the dispatch layer to emit — the events are constructed by
    # the concrete acquire/ recorder, so dispatch/ never references acquire/.
    from personalscraper.core.event_bus import Event


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
    ) -> list[Event]:
        """Correlate staging_source to a live seeding torrent and record the obligation.

        Called BEFORE the FS move (write-before-move guarantee).

        Args:
            staging_source: Absolute path of the file in the staging area.
            dispatched_dest: Absolute path of the destination after dispatch.

        Returns:
            Bus events the caller should emit once the move succeeds, opaque to
            the dispatch layer (which emits them without referencing
            ``acquire/``). Empty when there is nothing to announce — the current
            recorder records only the seed obligation (the wanted-row closure +
            followed-film retirement moved to the post-dispatch reconcile
            subscriber, ACQUIRE-02), so it always returns an empty list; the
            ``list[Event]`` shape is kept so the dispatch emit loop is unchanged.
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


@runtime_checkable
class SeedObligationChecker(Protocol):
    """Protocol for checking a live seed obligation by torrent info-hash.

    Consulted by ingest BEFORE the copy-vs-move decision. Unlike
    :class:`DeletePermit` (which matches on a library ``dispatched_path``), the
    ingest source lives in the download dir keyed by info-hash, so the check is
    by hash. Fail-SAFE for ingest: implementations return ``True`` when an
    active obligation is positively known — ingest then COPIES (preserves the
    seed) rather than moving (which would break a hit-and-run torrent). An
    unknown/unreadable state returns ``False`` (no positive obligation), and
    ingest falls back to its live seeding probe.
    """

    def has_active_obligation(self, info_hash: str) -> bool:
        """Return ``True`` when *info_hash* has a live, unmet seed obligation.

        Args:
            info_hash: The torrent info-hash to check.

        Returns:
            ``True`` when a positively-known active obligation exists.
        """
        ...


class AllowAllPermit:
    """Fail-open no-op DeletePermit — always returns ALLOW.

    Used as the default for tests, for dispatch/maintenance when no store
    is present, and as the fallback when the store is unreadable.
    Also implements SeedObligationRecorder and SeedObligationChecker as no-ops.
    """

    def has_active_obligation(self, info_hash: str) -> bool:
        """No-op checker — reports no obligation.

        Args:
            info_hash: Ignored.

        Returns:
            Always ``False`` (ingest then relies on its live seeding probe).
        """
        return False

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
    ) -> list[Event]:
        """No-op recorder — records nothing and announces nothing.

        Args:
            staging_source: Ignored.
            dispatched_dest: Ignored.

        Returns:
            An empty list (no events to emit).
        """
        return []

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
    "SeedObligationChecker",
    "SeedObligationRecorder",
    "veto",
]
