"""Phase 1 — the advisory provenance registry: migration 010 + ProvenanceStore.

The store is ADVISORY: only ``upsert_grab`` creates a row (follow-driven grabs);
every other write is UPDATE-only (a no-op when untracked → a manual/direct grab
never gets a row, ACC-06); every write is best-effort (an error never escapes to
the pipeline step); every read is fail-soft (``None`` on error).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire._provenance_store import _ProvenanceSubStore
from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.store import ConcreteAcquireStore, _write_tx, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _a_follow(store: ConcreteAcquireStore) -> int:
    """Create a follow and return its id (for the FK on followed_id)."""
    return store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=382389), title="X", added_at=1))


class TestMigration010:
    """The staging_provenance table + index exist after migration."""

    def test_table_and_index_present(self, store: ConcreteAcquireStore) -> None:
        """A fresh store has the table and its current_path index."""
        conn = store._ensure_open()  # noqa: SLF001 — test reaches the migrated schema
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "staging_provenance" in tables
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_provenance_current_path" in indexes


class TestProvenanceCrud:
    """upsert_grab creates; the journey setters update; reads round-trip."""

    def test_upsert_grab_creates_row_with_identity(self, store: ConcreteAcquireStore) -> None:
        """A follow-driven grab creates a row carrying the identity seed + followed_id."""
        fid = _a_follow(store)
        store.provenance.upsert_grab(
            "AABBCC", followed_id=fid, media_ref=MediaRef(tvdb_id=382389), kind="episode", grabbed_at=100
        )
        row = store.provenance.by_hash("aabbcc")  # hash normalized lowercase
        assert row is not None
        assert row.followed_id == fid
        assert row.media_ref == MediaRef(tvdb_id=382389)
        assert row.kind == "episode"
        assert row.status == "grabbed"

    def test_ingest_sets_current_path_and_by_path_join(self, store: ConcreteAcquireStore) -> None:
        """set_ingest records the folder; by_path joins folder → row (the #30 seam)."""
        store.provenance.upsert_grab(
            "h1", followed_id=None, media_ref=MediaRef(tmdb_id=27205), kind="movie", grabbed_at=1
        )
        store.provenance.set_ingest("h1", ingest_path="/stage/Inception", ingested_at=2)
        row = store.provenance.by_path("/stage/Inception")
        assert row is not None and row.info_hash == "h1"
        assert row.status == "ingested"
        assert row.media_ref == MediaRef(tmdb_id=27205)

    def test_current_path_follows_a_rename(self, store: ConcreteAcquireStore) -> None:
        """set_current_path moves the join key; the old path no longer matches."""
        store.provenance.upsert_grab(
            "h2", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="episode", grabbed_at=1
        )
        store.provenance.set_ingest("h2", ingest_path="/stage/old", ingested_at=2)
        store.provenance.set_current_path("h2", path="/cat/002/New Name")
        assert store.provenance.by_path("/stage/old") is None
        assert store.provenance.by_path("/cat/002/New Name") is not None

    def test_scraped_and_dispatch_update_status(self, store: ConcreteAcquireStore) -> None:
        """set_scraped / set_dispatch advance the status and record their fields."""
        store.provenance.upsert_grab(
            "h3", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="episode", grabbed_at=1
        )
        store.provenance.set_scraped("h3", scraped_ref=MediaRef(tvdb_id=999), scraped_at=3)
        assert store.provenance.by_hash("h3").status == "scraped"  # type: ignore[union-attr]
        assert store.provenance.by_hash("h3").scraped_ref == MediaRef(tvdb_id=999)  # type: ignore[union-attr]
        store.provenance.set_dispatch("h3", dispatch_path="/Volumes/Disk/x", dispatched_at=4)
        final = store.provenance.by_hash("h3")
        assert final is not None and final.status == "dispatched" and final.dispatch_path == "/Volumes/Disk/x"

    def test_by_hash_and_by_path_miss_return_none(self, store: ConcreteAcquireStore) -> None:
        """Unknown hash / path → None (fail-soft miss)."""
        assert store.provenance.by_hash("nope") is None
        assert store.provenance.by_path("/nowhere") is None

    def test_move_path_repoints_by_path(self, store: ConcreteAcquireStore) -> None:
        """move_path (path-keyed, for sort) re-points current_path old → new."""
        store.provenance.upsert_grab("mp", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("mp", ingest_path="/097-TEMP/Rel", ingested_at=2)
        store.provenance.move_path("/097-TEMP/Rel", "/001-MOVIES/Rel")
        assert store.provenance.by_path("/097-TEMP/Rel") is None
        row = store.provenance.by_path("/001-MOVIES/Rel")
        assert row is not None and row.info_hash == "mp"

    def test_record_dispatch_by_path(self, store: ConcreteAcquireStore) -> None:
        """record_dispatch_by_path (path-keyed, for dispatch) records the destination."""
        store.provenance.upsert_grab("dp", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("dp", ingest_path="/001-MOVIES/Rel", ingested_at=2)
        store.provenance.record_dispatch_by_path(
            "/001-MOVIES/Rel", dispatch_path="/Volumes/Disk/films/Rel", dispatched_at=9
        )
        row = store.provenance.by_hash("dp")
        assert row is not None and row.status == "dispatched"
        assert row.dispatch_path == "/Volumes/Disk/films/Rel"

    def test_path_keyed_writes_noop_when_untracked(self, store: ConcreteAcquireStore) -> None:
        """move_path / record_dispatch_by_path never create a row (ACC-06)."""
        store.provenance.move_path("/x", "/y")
        store.provenance.record_dispatch_by_path("/y", dispatch_path="/z", dispatched_at=1)
        assert store.provenance.by_path("/y") is None


class TestAdvisoryInvariants:
    """ACC-06 (untracked = no row) + best-effort writes."""

    def test_setters_are_noop_when_untracked_acc06(self, store: ConcreteAcquireStore) -> None:
        """A manual/direct grab (no upsert_grab) is never given a row by any setter."""
        store.provenance.set_ingest("direct", ingest_path="/stage/Direct", ingested_at=1)
        store.provenance.set_current_path("direct", path="/x")
        store.provenance.set_scraped("direct", scraped_ref=MediaRef(tvdb_id=1), scraped_at=1)
        store.provenance.set_dispatch("direct", dispatch_path="/y", dispatched_at=1)
        assert store.provenance.by_hash("direct") is None, "an untracked hash must NEVER get a row"

    def test_write_error_is_swallowed(self) -> None:
        """A write whose execute raises is logged + swallowed (never fails a step).

        Uses a raising fake connection (a real sqlite3.Connection's C-level execute
        is not monkeypatchable) so `_write_tx`'s BEGIN raises inside `_safe_write`.
        """

        class _RaisingConn:
            def execute(self, *_a: object, **_k: object) -> object:
                raise RuntimeError("db exploded")

        sub = _ProvenanceSubStore(_RaisingConn(), _write_tx)  # type: ignore[arg-type]
        # Must NOT raise — the error is swallowed (advisory):
        sub.upsert_grab("h", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=1)

    def test_prune_stale_drops_only_missing_paths(self, store: ConcreteAcquireStore) -> None:
        """prune_stale removes rows whose current_path is gone, keeps present ones."""
        store.provenance.upsert_grab(
            "keep", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=1
        )
        store.provenance.set_ingest("keep", ingest_path="/present", ingested_at=1)
        store.provenance.upsert_grab(
            "drop", followed_id=None, media_ref=MediaRef(tvdb_id=2), kind="movie", grabbed_at=1
        )
        store.provenance.set_ingest("drop", ingest_path="/gone", ingested_at=1)
        pruned = store.provenance.prune_stale(lambda p: p == "/present")
        assert pruned == 1
        assert store.provenance.by_hash("keep") is not None
        assert store.provenance.by_hash("drop") is None
