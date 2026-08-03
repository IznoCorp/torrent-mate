"""Unit tests for DownloadMarksStore (migration 014 — download_marks table, O4/D7)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.acquire._download_marks import DownloadMark, DownloadMarksStore

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "migrations"


def _setup_db(conn: sqlite3.Connection) -> None:
    """Create the download_marks table from migration 014 SQL."""
    sql = (_MIGRATIONS_DIR / "014_download_marks.sql").read_text(encoding="utf-8")
    conn.executescript(sql)


@pytest.fixture
def conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the download_marks table."""
    c = sqlite3.connect(":memory:")
    _setup_db(c)
    return c


@pytest.fixture
def store(conn: sqlite3.Connection) -> DownloadMarksStore:
    """Return a DownloadMarksStore bound to the in-memory connection."""
    return DownloadMarksStore(conn)


class TestDownloadMarkDataclass:
    """DownloadMark is a frozen dataclass with four fields."""

    def test_fields(self) -> None:
        """All four fields are accessible by name."""
        mark = DownloadMark(
            info_hash="abc123",
            started_emitted=True,
            last_threshold=50,
            completed_emitted=False,
        )
        assert mark.info_hash == "abc123"
        assert mark.started_emitted is True
        assert mark.last_threshold == 50
        assert mark.completed_emitted is False

    def test_frozen(self) -> None:
        """DownloadMark is immutable."""
        mark = DownloadMark("abc", False, 0, False)
        with pytest.raises(Exception):
            mark.info_hash = "xyz"  # type: ignore[misc]


class TestGet:
    """get(info_hash) retrieves a mark or returns None."""

    def test_nonexistent_returns_none(self, store: DownloadMarksStore) -> None:
        """Get on a hash that was never upserted returns None."""
        assert store.get("nonexistent") is None

    def test_retrieves_inserted_mark(self, store: DownloadMarksStore) -> None:
        """Get returns the mark previously set via upsert."""
        store.upsert("aabbcc", started=True, threshold=25)
        mark = store.get("aabbcc")
        assert mark is not None
        assert mark.info_hash == "aabbcc"
        assert mark.started_emitted is True
        assert mark.last_threshold == 25
        assert mark.completed_emitted is False  # default

    def test_case_insensitive_get(self, store: DownloadMarksStore) -> None:
        """Get normalizes the info-hash to lowercase."""
        store.upsert("AABBCCDD", started=True)
        mark = store.get("aabbccdd")
        assert mark is not None
        assert mark.info_hash == "aabbccdd"

    def test_case_insensitive_upsert(self, store: DownloadMarksStore) -> None:
        """Upsert with uppercase stores lowercase, get with mixed case works."""
        store.upsert("DEADBEEF", started=True)
        mark = store.get("DeadBeef")
        assert mark is not None
        assert mark.info_hash == "deadbeef"


class TestUpsert:
    """upsert inserts a new row or partially updates an existing one."""

    def test_insert_then_get(self, store: DownloadMarksStore) -> None:
        """A fresh upsert creates a row with the given values."""
        store.upsert("hash1", started=True, threshold=0)
        mark = store.get("hash1")
        assert mark is not None
        assert mark.started_emitted is True
        assert mark.last_threshold == 0
        assert mark.completed_emitted is False

    def test_partial_update_threshold_only(self, store: DownloadMarksStore) -> None:
        """Updating only threshold leaves started and completed unchanged."""
        store.upsert("hash2", started=True, threshold=0)
        store.upsert("hash2", threshold=50)
        mark = store.get("hash2")
        assert mark is not None
        assert mark.started_emitted is True  # unchanged
        assert mark.last_threshold == 50  # updated
        assert mark.completed_emitted is False  # unchanged

    def test_partial_update_completed_only(self, store: DownloadMarksStore) -> None:
        """Updating only completed leaves started and threshold unchanged."""
        store.upsert("hash3", started=True, threshold=75)
        store.upsert("hash3", completed=True)
        mark = store.get("hash3")
        assert mark is not None
        assert mark.started_emitted is True  # unchanged
        assert mark.last_threshold == 75  # unchanged
        assert mark.completed_emitted is True  # updated

    def test_completed_flag(self, store: DownloadMarksStore) -> None:
        """The completed flag can be set and read back."""
        store.upsert("hash4", started=True, threshold=75, completed=True)
        mark = store.get("hash4")
        assert mark is not None
        assert mark.completed_emitted is True

    def test_idempotent_upsert_same_values(self, store: DownloadMarksStore) -> None:
        """Repeating the same upsert does not change the row."""
        store.upsert("hash5", started=True, threshold=50, completed=False)
        store.upsert("hash5", started=True, threshold=50)
        mark = store.get("hash5")
        assert mark is not None
        assert mark.started_emitted is True
        assert mark.last_threshold == 50
        assert mark.completed_emitted is False

    def test_upsert_no_kwargs_still_inserts(self, store: DownloadMarksStore) -> None:
        """Upsert with no kwargs creates a row with all defaults."""
        store.upsert("hash6")
        mark = store.get("hash6")
        assert mark is not None
        assert mark.started_emitted is False
        assert mark.last_threshold == 0
        assert mark.completed_emitted is False


class TestGuardedTransitions:
    """try_* transitions follow the mark_done rowcount discipline (review MINOR-6).

    The plain ``upsert`` is unconditional: two concurrent passes that both
    read « no mark » would both write and both emit. The guarded writers
    answer ``True`` to exactly ONE caller per transition.
    """

    def test_try_mark_started_first_wins_second_loses(self, store: DownloadMarksStore) -> None:
        """First claim returns True; the second attempt returns False."""
        assert store.try_mark_started("aaaa0001") is True
        assert store.try_mark_started("aaaa0001") is False
        mark = store.get("aaaa0001")
        assert mark is not None and mark.started_emitted is True

    def test_try_mark_started_creates_the_row_when_absent(self, store: DownloadMarksStore) -> None:
        """The guard materialises a fresh row (INSERT OR IGNORE) before claiming."""
        assert store.get("fresh001") is None
        assert store.try_mark_started("fresh001") is True
        mark = store.get("fresh001")
        assert mark is not None
        assert mark.started_emitted is True
        assert mark.last_threshold == 0
        assert mark.completed_emitted is False

    def test_try_mark_completed_first_wins_second_loses(self, store: DownloadMarksStore) -> None:
        """First claim returns True (and subsumes started); the second returns False."""
        assert store.try_mark_completed("bbbb0002") is True
        assert store.try_mark_completed("bbbb0002") is False
        mark = store.get("bbbb0002")
        assert mark is not None
        assert mark.completed_emitted is True
        assert mark.started_emitted is True, "completion subsumes the start"

    def test_try_advance_threshold_forward_only(self, store: DownloadMarksStore) -> None:
        """Advance claims move forward only; repeats and regressions answer False."""
        assert store.try_advance_threshold("cccc0003", 25) is True
        assert store.try_advance_threshold("cccc0003", 25) is False, "same threshold twice must lose"
        assert store.try_advance_threshold("cccc0003", 50) is True
        assert store.try_advance_threshold("cccc0003", 25) is False, "the mark never moves backwards"
        mark = store.get("cccc0003")
        assert mark is not None and mark.last_threshold == 50

    def test_guards_are_case_insensitive(self, store: DownloadMarksStore) -> None:
        """Claims normalise the hash to lowercase like every other accessor."""
        assert store.try_mark_started("DDDD0004") is True
        assert store.try_mark_started("dddd0004") is False


class TestPruneStale:
    """prune_stale removes marks not in the active set."""

    def test_keeps_active_hashes(self, store: DownloadMarksStore) -> None:
        """Marks whose hash is in active_hashes are preserved."""
        store.upsert("keep1", started=True)
        store.upsert("keep2", started=True)
        count = store.prune_stale(["keep1", "keep2", "extra"])
        assert count == 0
        assert store.get("keep1") is not None
        assert store.get("keep2") is not None

    def test_removes_closed_hashes(self, store: DownloadMarksStore) -> None:
        """Marks whose hash is NOT in active_hashes are deleted."""
        store.upsert("keep", started=True)
        store.upsert("stale1", started=True)
        store.upsert("stale2", started=True)
        count = store.prune_stale(["keep"])
        assert count == 2
        assert store.get("keep") is not None
        assert store.get("stale1") is None
        assert store.get("stale2") is None

    def test_empty_active_set_deletes_all(self, store: DownloadMarksStore) -> None:
        """An empty active_hashes set removes every mark."""
        store.upsert("a", started=True)
        store.upsert("b", started=True)
        store.upsert("c", completed=True)
        count = store.prune_stale([])
        assert count == 3
        assert store.get("a") is None
        assert store.get("b") is None
        assert store.get("c") is None

    def test_empty_active_set_on_empty_table_returns_zero(self, store: DownloadMarksStore) -> None:
        """prune_stale with empty active set on empty table returns 0."""
        count = store.prune_stale([])
        assert count == 0

    def test_prune_stale_with_empty_table_active_hashes(self, store: DownloadMarksStore) -> None:
        """prune_stale on empty table with active hashes returns 0."""
        count = store.prune_stale(["somehash"])
        assert count == 0

    def test_case_insensitive_active_matching(self, store: DownloadMarksStore) -> None:
        """prune_stale matches case-insensitively."""
        store.upsert("abcdef01", started=True)
        # Active set has uppercase version — should still be kept.
        count = store.prune_stale(["ABCDEF01"])
        assert count == 0
        assert store.get("abcdef01") is not None
