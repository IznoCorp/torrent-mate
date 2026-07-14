"""Tests for the §5 truth-table facts (web/acquisition/truth.py — P0-B.2).

The named production cases pin the derivation:
- Silo: everything aired is owned, one phantom grabbed row → up_to_date facts
  (inflight 0), never « en cours d'acquisition ».
- House of the Dragon: an aired episode neither owned nor queued → missing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.truth import FollowTruth, compute_follow_truth
from personalscraper.web.models.acquisition import FollowedSeriesItem, MediaRefResponse


class _StubChecker:
    """Ownership checker stub exposing a fixed owned-pairs set."""

    def __init__(self, pairs: set[tuple[int, int]]) -> None:
        self._pairs = pairs

    def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
        return self._pairs


@pytest.fixture
def acquire_conn(tmp_path: Path):
    """Yield a read connection to a migrated temp acquire.db with one follow."""
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    # Touch a sub-store so the schema exists.
    store.wanted.list_pending()
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    conn.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, added_at, kind) "
        "VALUES (1, '{\"tvdb_id\": 403245}', 'Silo', 1, 1750000000, 'show')"
    )
    conn.commit()
    yield conn
    conn.close()
    store.close()


def _seed_aired(conn: sqlite3.Connection, pairs: list[tuple[int, int]]) -> None:
    """Insert aired-catalog rows for followed_id=1."""
    conn.executemany(
        "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) "
        "VALUES (1, ?, ?, NULL, '2026-01-01', 1750000000)",
        pairs,
    )
    conn.commit()


def _seed_wanted(conn: sqlite3.Connection, season: int, episode: int, status: str) -> None:
    """Insert one episode wanted row for followed_id=1."""
    conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, status, enqueued_at) "
        "VALUES (1, '{\"tvdb_id\": 403245}', 'episode', ?, ?, ?, 1750000000)",
        (season, episode, status),
    )
    conn.commit()


REF = MediaRef(tvdb_id=403245)


def test_no_catalog_yields_none_facts(acquire_conn: sqlite3.Connection) -> None:
    """No cached catalog → all-None facts (caller degrades to raw counters)."""
    truth = compute_follow_truth(acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF)
    assert truth == FollowTruth()


def test_silo_shape_phantom_grabbed_is_not_inflight(acquire_conn: sqlite3.Connection) -> None:
    """All aired episodes owned + one grabbed row → inflight 0, nothing missing.

    The Silo bug: the card said « En cours d'acquisition » from a raw
    ``grabbed`` counter while every episode chip was green. A grabbed row whose
    episode the library owns is a phantom, not an acquisition.
    """
    _seed_aired(acquire_conn, [(3, 1), (3, 2)])
    _seed_wanted(acquire_conn, 3, 1, "grabbed")
    truth = compute_follow_truth(acquire_conn, _StubChecker({(3, 1), (3, 2)}), followed_id=1, media_ref=REF)

    assert truth.aired_count == 2
    assert truth.owned_count == 2
    assert truth.inflight_count == 0
    assert truth.queued_count == 0
    assert truth.missing_count == 0

    # And the derived card status is « à jour », never « en cours ».
    item = _item(truth, wanted_grabbed=1)
    assert item.status == "up_to_date"


def test_hotd_shape_unqueued_missing_episode(acquire_conn: sqlite3.Connection) -> None:
    """An aired episode neither owned nor queued → missing → status incomplete."""
    _seed_aired(acquire_conn, [(3, 3), (3, 4)])
    # E3 owned; E4 has an abandoned row (not an open one) → missing.
    _seed_wanted(acquire_conn, 3, 4, "abandoned")
    truth = compute_follow_truth(acquire_conn, _StubChecker({(3, 3)}), followed_id=1, media_ref=REF)

    assert truth.missing_count == 1
    assert _item(truth, wanted_grabbed=0).status == "incomplete"


def test_real_inflight_and_queue_counts(acquire_conn: sqlite3.Connection) -> None:
    """Unowned aired episodes split between grabbed (inflight) and pending (queued)."""
    _seed_aired(acquire_conn, [(1, 1), (1, 2), (1, 3)])
    _seed_wanted(acquire_conn, 1, 2, "grabbed")
    _seed_wanted(acquire_conn, 1, 3, "pending")
    truth = compute_follow_truth(acquire_conn, _StubChecker({(1, 1)}), followed_id=1, media_ref=REF)

    assert truth.owned_count == 1
    assert truth.inflight_count == 1
    assert truth.queued_count == 1
    assert truth.missing_count == 0
    assert _item(truth, wanted_grabbed=1).status == "acquiring"


def _item(truth: FollowTruth, *, wanted_grabbed: int) -> FollowedSeriesItem:
    """Build a FollowedSeriesItem carrying the truth facts (status is computed)."""
    return FollowedSeriesItem(
        id=1,
        title="Silo",
        media_ref=MediaRefResponse(tvdb_id=403245),
        active=True,
        kind="show",
        added_at=1750000000.0,
        wanted_pending=0,
        wanted_grabbed=wanted_grabbed,
        aired_count=truth.aired_count,
        owned_count=truth.owned_count,
        inflight_count=truth.inflight_count,
        queued_count=truth.queued_count,
        missing_count=truth.missing_count,
    )
