"""Tests for the B.3 wanted ↔ library ↔ client reconciliation.

Regression suite for the frozen-`grabbed` bug: 14 production rows (Silo S3E1,
American Dad S22E5-11, FROM S4E8-10, Rick & Morty S9E5-6, Le Robot sauvage)
sat at ``grabbed`` forever because nothing ever compared them back to the
library or to the torrent client. Each rule of :func:`reconcile_wanted` gets a
red-on-old case against a REAL temp store.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


class _StubOwnership:
    """Ownership stub: owns exactly the (season, episode) pairs it was given."""

    def __init__(self, owned_pairs: set[tuple[int | None, int | None]]) -> None:
        self._owned = owned_pairs

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        return (season, episode) in self._owned


class _ExplodingOwnership:
    """Ownership stub that raises — reconcile must fail soft per row."""

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        raise RuntimeError("library.db is locked")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    yield s
    s.close()


def _grabbed(store: ConcreteAcquireStore, *, season: int, episode: int, info_hash: str) -> int:
    """Insert one grabbed episode row and return its id."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=season,
            episode=episode,
        )
    )
    store.wanted.mark_grabbed(wanted_id, info_hash)
    return wanted_id


def test_owned_grabbed_row_closes_done(store: ConcreteAcquireStore) -> None:
    """A grabbed row whose episode the library owns closes ``done`` (the Silo case)."""
    wanted_id = _grabbed(store, season=3, episode=1, info_hash="f92c7b09")

    summary = reconcile_wanted(store, _StubOwnership({(3, 1)}), {"f92c7b09"})

    assert summary.closed_owned == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_vanished_torrent_unowned_requeues_pending(store: ConcreteAcquireStore) -> None:
    """Grabbed + hash absent from the client + unowned → back to pending, hash cleared."""
    wanted_id = _grabbed(store, season=3, episode=2, info_hash="deadbeef")

    summary = reconcile_wanted(store, _StubOwnership(set()), set())

    assert summary.requeued_missing == 1
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "pending"
    assert row.grabbed_hash is None


def test_torrent_still_in_client_stays_grabbed(store: ConcreteAcquireStore) -> None:
    """Grabbed + hash still known to the client + unowned → left in flight."""
    wanted_id = _grabbed(store, season=3, episode=3, info_hash="cafebabe")

    summary = reconcile_wanted(store, _StubOwnership(set()), {"cafebabe"})

    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_client_unavailable_never_requeues(store: ConcreteAcquireStore) -> None:
    """client_hashes=None (client outage) → the requeue half is skipped (fail-soft)."""
    wanted_id = _grabbed(store, season=3, episode=4, info_hash="deadbeef")

    summary = reconcile_wanted(store, _StubOwnership(set()), None)

    assert summary.requeued_missing == 0
    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_ownership_error_fails_soft_per_row(store: ConcreteAcquireStore) -> None:
    """An ownership exception leaves the row untouched — never aborts the sweep."""
    wanted_id = _grabbed(store, season=3, episode=5, info_hash="0badf00d")

    summary = reconcile_wanted(store, _ExplodingOwnership(), {"0badf00d"})

    assert summary.checked == 1
    assert summary.closed_owned == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_reconcile_is_idempotent(store: ConcreteAcquireStore) -> None:
    """A second pass finds nothing to do (guarded SQL transitions)."""
    _grabbed(store, season=3, episode=6, info_hash="f92c7b09")
    ownership = _StubOwnership({(3, 6)})

    first = reconcile_wanted(store, ownership, {"f92c7b09"})
    second = reconcile_wanted(store, ownership, {"f92c7b09"})

    assert first.closed_owned == 1
    assert second.checked == 0
    assert second.closed_owned == 0


def test_owned_movie_row_closes_done(store: ConcreteAcquireStore) -> None:
    """The movie shape (Le Robot sauvage): grabbed + owned movie → done."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=1184918),
            kind="movie",
            status="pending",
            enqueued_at=1_750_000_000,
        )
    )
    store.wanted.mark_grabbed(wanted_id, "4bdfb777")

    summary = reconcile_wanted(store, _StubOwnership({(None, None)}), {"4bdfb777"})

    assert summary.closed_owned == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"
