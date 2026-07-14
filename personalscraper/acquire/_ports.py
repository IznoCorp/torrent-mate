"""Port protocols for the acquire lobe.

RP5c established the minimal lifecycle seam (``close()``).  RP3 extends
``AcquireStore`` with the query/write surface for the five sub-stores,
exposed as attribute namespaces:

  * ``store.follow``     — ``followed_series`` writer + reader
  * ``store.wanted``     — ``wanted`` writer + reader (status transitions)
  * ``store.seed``       — ``seed_obligation`` writer + reader (deletion authority)
  * ``store.ratio``      — ``ratio_state`` reader + upsert (data-carrier)
  * ``store.cross_seed`` — ``cross_seed_history`` + ``cross_seed_quota`` (watch-seed)
  * ``store.watch``      — ``watch_state`` KV store (watcher daemon state)

All five sub-stores share a single ``acquire.db`` connection.  Cross-process
single-writer is SQLite-native (WAL + ``BEGIN IMMEDIATE`` + ``busy_timeout``):
no ``FileLock`` is held for the store's lifetime, and reads are lock-free.  The
concrete store opens lazily (on first sub-store access).  See
:mod:`personalscraper.acquire.store` for the concrete implementation.

Import direction: this module imports only from ``personalscraper.acquire``
domain VOs + stdlib — never from triage packages (layering, RP5c D3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from personalscraper.acquire.domain import (
    FollowedSeries,
    RatioState,
    SeedObligation,
    WantedItem,
    WantedKind,
    WantedStatus,
)
from personalscraper.core.identity import MediaRef


@runtime_checkable
class FollowSubStore(Protocol):
    """Writer + reader for the ``followed_series`` table."""

    def add(self, series: FollowedSeries) -> int:
        """Insert a :class:`FollowedSeries` row and return its rowid."""
        ...

    def get(self, followed_id: int) -> FollowedSeries | None:
        """Return the :class:`FollowedSeries` for *followed_id*, or ``None``."""
        ...

    def find_by_ref(self, media_ref: MediaRef) -> FollowedSeries | None:
        """Return the :class:`FollowedSeries` keyed on *media_ref*, or ``None``.

        Matches on the primary available provider ID (tvdb > tmdb > imdb),
        so a lookup matches any stored row sharing that ID regardless of
        other IDs, returning the oldest (first-by-id) on ties, or ``None``.
        """
        ...

    def list_active(self) -> list[FollowedSeries]:
        """Return all active ``followed_series`` rows, ordered by id."""
        ...

    def list_all(self) -> list[FollowedSeries]:
        """Return all ``followed_series`` rows (active and inactive), ordered by id."""
        ...

    def set_active(self, followed_id: int, active: bool) -> None:
        """Set the ``active`` flag on a ``followed_series`` row."""
        ...

    def set_kind(self, followed_id: int, kind: str) -> None:
        """Update the ``kind`` ('movie'|'show') of a ``followed_series`` row."""
        ...


@runtime_checkable
class WantedSubStore(Protocol):
    """Writer + reader for the ``wanted`` table."""

    def add(self, item: WantedItem) -> int:
        """Insert a :class:`WantedItem` row and return its rowid."""
        ...

    def get(self, wanted_id: int) -> WantedItem | None:
        """Return the :class:`WantedItem` for *wanted_id*, or ``None``."""
        ...

    def set_status(self, wanted_id: int, status: WantedStatus) -> None:
        """Transition the ``status`` column of a ``wanted`` row."""
        ...

    def list_pending(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='pending'`` (partial-index path)."""
        ...

    def claim_for_search(self, wanted_id: int, now: int) -> bool:
        """Atomically claim a pending item; return ``True`` iff this call won."""
        ...

    def mark_grabbed(self, wanted_id: int, info_hash: str) -> None:
        """Persist ``status='grabbed'`` + ``info_hash`` for the idempotence guard."""
        ...

    def list_stale_searching(self, older_than: int) -> list[WantedItem]:
        """Return ``wanted`` rows stuck in 'searching' older than the threshold."""
        ...

    def find(
        self,
        *,
        followed_id: int | None,
        kind: WantedKind,
        season: int | None,
        episode: int | None,
    ) -> WantedItem | None:
        """Return the first matching wanted row, or None (soft dedup guard).

        Uses NULL-safe comparison (``IS`` not ``=``) for ``season`` and
        ``episode`` so that a NULL episode in a future movie case does not
        accidentally match an episode row.

        Args:
            followed_id: FK to ``followed_series`` row, or ``None``.
            kind: ``"movie"`` or ``"episode"``.
            season: Season number, or ``None`` for movies.
            episode: Episode number, or ``None`` for movies.

        Returns:
            The first matching :class:`WantedItem` if found, else ``None``.
        """
        ...


@runtime_checkable
class SeedSubStore(Protocol):
    """Writer + reader for the ``seed_obligation`` table (deletion authority)."""

    def add(self, obligation: SeedObligation) -> int:
        """Insert a new :class:`SeedObligation`; returns the row id."""
        ...

    def find_by_dispatched_path(self, path: Path) -> SeedObligation | None:
        """Return the active obligation for *dispatched_path*, or ``None``."""
        ...

    def find_active_under(self, path: Path) -> list[SeedObligation]:
        """Return all active obligations for *path* or any of its descendants.

        Matches obligations whose ``dispatched_path`` is either exactly *path*
        OR a descendant of *path* (boundary-safe LIKE with ESCAPE).
        Only returns obligations where ``released_at IS NULL``.
        """
        ...

    def mark_satisfied(self, obligation_id: int, satisfied_at: int) -> None:
        """Set ``satisfied_at`` on an obligation row."""
        ...

    def mark_breached(self, obligation_id: int, breached_at: int) -> None:
        """Set ``breached_at`` on an obligation row."""
        ...

    def mark_breached_under(self, path: Path, breached_at: int) -> int:
        """Breach every active obligation under *path*; return the row count.

        Matches obligations whose ``dispatched_path`` is exactly *path* OR a
        descendant (boundary-safe LIKE with ESCAPE). Only touches rows with
        ``released_at IS NULL`` that are not already breached.
        """
        ...


@runtime_checkable
class RatioSubStore(Protocol):
    """Reader + upsert for the ``ratio_state`` table (data-carrier; Ratio C1)."""

    def get(self, tracker_name: str) -> RatioState | None:
        """Return the :class:`RatioState` for *tracker_name*, or ``None``."""
        ...

    def upsert(self, state: RatioState) -> None:
        """Insert or replace the ``ratio_state`` row keyed on ``tracker_name``."""
        ...


@runtime_checkable
class WatchSubStore(Protocol):
    """Writer + reader for the ``watch_state`` key-value table."""

    def get_last_successful_run_at(self) -> float | None:
        """Return the persisted ``last_successful_run_at`` timestamp, or ``None``."""
        ...

    def set_last_successful_run_at(self, ts: float) -> None:
        """Persist the ``last_successful_run_at`` timestamp (upsert)."""
        ...


@runtime_checkable
class CrossSeedSubStore(Protocol):
    """Writer + reader for the ``cross_seed_history`` and ``cross_seed_quota`` tables."""

    def record_search(self, source_hash: str, tracker: str) -> None:
        """Record a cross-seed search attempt (upsert by source_hash+tracker)."""
        ...

    def was_searched_recently(self, source_hash: str, tracker: str, days: int) -> bool:
        """Return ``True`` if the pair was searched within *days*."""
        ...

    def daily_searches_remaining(self, max_per_day: int) -> int:
        """Return remaining quota for today (max_per_day - today's count)."""
        ...

    def increment_daily_count(self) -> None:
        """Increment today's search count (UPSERT)."""
        ...


@runtime_checkable
class AcquireStore(Protocol):
    """Full store contract for the acquisition lobe (RP3).

    Sub-stores are accessed via attribute namespaces.  Writes are serialized
    cross-process by SQLite itself (WAL + ``BEGIN IMMEDIATE`` + ``busy_timeout``);
    reads are lock-free.  The concrete store opens lazily on first access.

    The five sub-store namespaces are **read-only accessors** (the concrete
    store exposes them as ensure-open properties): callers read ``store.follow``
    but never assign it.
    """

    @property
    def follow(self) -> FollowSubStore:
        """``followed_series`` sub-store (opens the store on first access)."""
        ...

    @property
    def wanted(self) -> WantedSubStore:
        """``wanted`` sub-store (opens the store on first access)."""
        ...

    @property
    def seed(self) -> SeedSubStore:
        """``seed_obligation`` sub-store / deletion authority (opens on access)."""
        ...

    @property
    def ratio(self) -> RatioSubStore:
        """``ratio_state`` sub-store / data-carrier (opens on access)."""
        ...

    @property
    def cross_seed(self) -> CrossSeedSubStore:
        """``cross_seed_history`` + ``cross_seed_quota`` sub-store (opens on access)."""
        ...

    @property
    def watch(self) -> WatchSubStore:
        """``watch_state`` KV sub-store (opens on access)."""
        ...

    def close(self) -> None:
        """Release all resources held by the store (fail-soft — never raises)."""
        ...


__all__ = [
    "AcquireStore",
    "CrossSeedSubStore",
    "FollowSubStore",
    "RatioSubStore",
    "SeedSubStore",
    "WantedSubStore",
    "WatchSubStore",
]
