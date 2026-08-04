"""reswitch Phase 3 — tried-hashes memory + ranking exclusion.

Two independent guarantees the auto-reswitch relies on:

  * ``rank(..., exclude_hashes=…)`` never re-emits a release already tried, and
    is byte-identical to before when the set is empty (retro-compat);
  * the ``wanted`` store remembers tried hashes across a requeue — the migration
    added the column, ``append_tried_hash`` / ``list_tried_hashes`` round-trip,
    and ``requeue_for_reswitch`` atomically records the failed hash AND requeues.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import (
    RankingConfig,
    RankingCriterion,
    ThresholdEntry,
    rank,
)
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

_RANKING = RankingConfig(
    criteria=[RankingCriterion(field="seeders", thresholds=[ThresholdEntry(at=1, score=10)])],
    min_seeders=1,
)


def _result(tid: str, info_hash: str, seeders: int = 10) -> TrackerResult:
    """A minimal TrackerResult carrying an info_hash."""
    return TrackerResult(
        provider="test",
        tracker_id=tid,
        title=f"Show S03E09 {tid}",
        size=ByteSize(1_000_000_000),
        seeders=seeders,
        leechers=0,
        info_hash=info_hash,
        download_url=f"https://test/{tid}",
    )


class TestRankExclusion:
    """rank() drops excluded hashes; empty set is a no-op."""

    def test_excluded_hash_never_appears(self) -> None:
        """A hash in exclude_hashes is dropped even if it would score highest."""
        dead = _result("a", "deadbeef", seeders=100)
        alive = _result("b", "cafef00d", seeders=5)
        ranked = rank([dead, alive], _RANKING, exclude_hashes=frozenset({"deadbeef"}))
        assert [r.info_hash for r, _ in ranked] == ["cafef00d"]

    def test_exclusion_is_case_insensitive(self) -> None:
        """An uppercase result hash still matches a lowercase exclusion entry."""
        dead = _result("a", "DEADBEEF")
        ranked = rank([dead], _RANKING, exclude_hashes=frozenset({"deadbeef"}))
        assert ranked == []

    def test_empty_exclusion_is_unchanged(self) -> None:
        """Default (empty) exclusion ranks exactly as before — retro-compat."""
        a = _result("a", "aaaa", seeders=100)
        b = _result("b", "bbbb", seeders=5)
        assert [r.info_hash for r, _ in rank([a, b], _RANKING)] == ["aaaa", "bbbb"]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db (migrations applied) and close it."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _grabbed_row(store: ConcreteAcquireStore, info_hash: str) -> int:
    """Insert a wanted row, claim + grab it with *info_hash*, return its id."""
    rowid = store.wanted.add(
        WantedItem(media_ref=MediaRef(tvdb_id=42), kind="episode", status="pending", enqueued_at=1_700_000_000)
    )
    assert store.wanted.claim_for_search(rowid, 1_700_000_100) is True
    store.wanted.mark_grabbed(rowid, info_hash)
    return rowid


class TestTriedHashesStore:
    """The migration column + store methods round-trip."""

    def test_append_and_list_round_trip(self, store: ConcreteAcquireStore) -> None:
        """append_tried_hash records lowercase, dedup; list returns them."""
        rowid = _grabbed_row(store, "aaaa")
        store.wanted.append_tried_hash(rowid, "DEADBEEF")
        store.wanted.append_tried_hash(rowid, "deadbeef")  # duplicate (case) — ignored
        store.wanted.append_tried_hash(rowid, "cafe")
        assert store.wanted.list_tried_hashes(rowid) == ("deadbeef", "cafe")

    def test_get_populates_tried_hashes_field(self, store: ConcreteAcquireStore) -> None:
        """WantedItem.tried_hashes round-trips through get()."""
        rowid = _grabbed_row(store, "aaaa")
        store.wanted.append_tried_hash(rowid, "beef")
        row = store.wanted.get(rowid)
        assert row is not None
        assert row.tried_hashes == ("beef",)

    def test_requeue_for_reswitch_records_hash_and_requeues(self, store: ConcreteAcquireStore) -> None:
        """The stalled hash is remembered AND the row goes back to pending."""
        rowid = _grabbed_row(store, "deadbeef")
        assert store.wanted.requeue_for_reswitch(rowid, "deadbeef", 1_800_000_000) is True
        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "pending"
        assert row.grabbed_hash is None
        assert row.tried_hashes == ("deadbeef",)

    def test_requeue_for_reswitch_is_idempotent(self, store: ConcreteAcquireStore) -> None:
        """A second call (row no longer grabbed) is a no-op and keeps the memory."""
        rowid = _grabbed_row(store, "deadbeef")
        assert store.wanted.requeue_for_reswitch(rowid, "deadbeef", 1_800_000_000) is True
        assert store.wanted.requeue_for_reswitch(rowid, "deadbeef", 1_800_000_000) is False
        assert store.wanted.list_tried_hashes(rowid) == ("deadbeef",)

    def test_requeue_for_reswitch_resets_the_cadence_clock(self, store: ConcreteAcquireStore) -> None:
        """enqueued_at is reset to now so the cutoff cannot abandon the reswitch (review L1)."""
        rowid = _grabbed_row(store, "deadbeef")  # enqueued_at = 1_700_000_000
        assert store.wanted.requeue_for_reswitch(rowid, "deadbeef", 1_900_000_000) is True
        row = store.wanted.get(rowid)
        assert row is not None
        assert row.enqueued_at == 1_900_000_000
        assert row.attempts == 0
        assert row.last_search_at is None

    def test_tried_hashes_survive_a_second_reswitch(self, store: ConcreteAcquireStore) -> None:
        """A second dead release is appended, the first is preserved (no loop)."""
        rowid = _grabbed_row(store, "deadbeef")
        store.wanted.requeue_for_reswitch(rowid, "deadbeef", 1_800_000_000)
        # Simulate a re-grab of a different release that also stalls.
        store.wanted.claim_for_search(rowid, 1_700_000_200)
        store.wanted.mark_grabbed(rowid, "cafef00d")
        store.wanted.requeue_for_reswitch(rowid, "cafef00d", 1_800_000_100)
        assert store.wanted.list_tried_hashes(rowid) == ("deadbeef", "cafef00d")


class TestRequeueClearsTheStaleVerdict:
    """A requeued row must not keep the dead release's verdict (§2).

    Live incident 2026-08-04: the reswitch requeued American Dad S15/S17 to
    ``pending`` but left ``last_search_outcome='grabbed'`` / ``last_search_found=4``
    behind — the verdict of the release it had just declared DEAD and excluded.

    Any surface deriving state from that row would read « À récupérer », i.e.
    « a takeable candidate is known », when the only one ever tried is now on the
    exclusion list. The module's own discipline elsewhere is that status and verdict
    stay in sync; the requeue was the one place that broke it.
    """

    def test_reswitch_requeue_clears_outcome_and_found(self, store) -> None:
        """After the requeue the row states « nothing concluded since », not a stale hit."""
        wid = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=73141),
                kind="season",
                status="pending",
                enqueued_at=1_700_000_000,
                season=15,
            )
        )
        store.wanted.record_search_outcome(wid, "grabbed", 4)
        store.wanted.mark_grabbed(wid, "deadbeef" * 5)
        before = store.wanted.get(wid)
        assert before.last_search_outcome == "grabbed"
        assert before.last_search_found == 4

        assert store.wanted.requeue_for_reswitch(wid, "deadbeef" * 5, 1_700_003_600) is True

        row = store.wanted.get(wid)
        assert row.status == "pending"
        assert row.grabbed_hash is None
        assert row.last_search_outcome is None, "the dead release's verdict must not survive its own exclusion"
        assert row.last_search_found is None, "found=4 counted the release just declared dead"
        # The exclusion itself is preserved — that is the loop guard.
        assert ("deadbeef" * 5) in store.wanted.list_tried_hashes(wid)
