"""Port protocols for the acquire lobe.

RP5c established the minimal lifecycle seam (``close()``).  RP3 extends
``AcquireStore`` with the query/write surface for the four sub-stores,
exposed as attribute namespaces:

  * ``store.follow``  — ``followed_series`` writer + reader
  * ``store.wanted``  — ``wanted`` writer + reader (status transitions)
  * ``store.seed``    — ``seed_obligation`` writer + reader (deletion authority)
  * ``store.ratio``   — ``ratio_state`` reader + upsert (data-carrier)

All four sub-stores share a single ``acquire.db`` connection serialized by a
single ``acquire.db`` writer lock held for the store's lifetime (single-writer
per ROADMAP).  See :mod:`personalscraper.acquire.store` for the concrete
implementation.

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
    WantedStatus,
)


@runtime_checkable
class FollowSubStore(Protocol):
    """Writer + reader for the ``followed_series`` table."""

    def add(self, series: FollowedSeries) -> int:
        """Insert a :class:`FollowedSeries` row and return its rowid."""
        ...

    def get(self, followed_id: int) -> FollowedSeries | None:
        """Return the :class:`FollowedSeries` for *followed_id*, or ``None``."""
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


@runtime_checkable
class SeedSubStore(Protocol):
    """Writer + reader for the ``seed_obligation`` table (deletion authority)."""

    def add(self, obligation: SeedObligation) -> int:
        """Insert a new :class:`SeedObligation`; returns the row id."""
        ...

    def find_by_dispatched_path(self, path: Path) -> SeedObligation | None:
        """Return the active obligation for *dispatched_path*, or ``None``."""
        ...

    def mark_satisfied(self, obligation_id: int, satisfied_at: int) -> None:
        """Set ``satisfied_at`` on an obligation row."""
        ...

    def mark_breached(self, obligation_id: int, breached_at: int) -> None:
        """Set ``breached_at`` on an obligation row."""
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
class AcquireStore(Protocol):
    """Full store contract for the acquisition lobe (RP3).

    Sub-stores are accessed via attribute namespaces.  All operations are
    serialized by the single ``acquire.db`` writer lock held by the concrete
    store for its lifetime.

    Attributes:
        follow: ``followed_series`` sub-store.
        wanted: ``wanted`` sub-store.
        seed: ``seed_obligation`` sub-store (the deletion-authority table).
        ratio: ``ratio_state`` sub-store (data-carrier, dormant writer).
    """

    follow: FollowSubStore
    wanted: WantedSubStore
    seed: SeedSubStore
    ratio: RatioSubStore

    def close(self) -> None:
        """Release all resources held by the store (fail-soft — never raises)."""
        ...


__all__ = [
    "AcquireStore",
    "FollowSubStore",
    "RatioSubStore",
    "SeedSubStore",
    "WantedSubStore",
]
