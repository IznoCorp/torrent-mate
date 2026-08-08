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

    def test_list_journeys_most_recent_first(self, store: ConcreteAcquireStore) -> None:
        """F1: list_journeys returns rows most-recent (grabbed_at) first."""
        store.provenance.upsert_grab(
            "old", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=100
        )
        store.provenance.upsert_grab(
            "new", followed_id=None, media_ref=MediaRef(tvdb_id=2), kind="movie", grabbed_at=200
        )
        journeys = store.provenance.list_journeys()
        assert [j.info_hash for j in journeys] == ["new", "old"]
        assert journeys[0].media_ref == MediaRef(tvdb_id=2)

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

    def test_scrape_rename_then_dispatch_records_and_prune_keeps(self, store: ConcreteAcquireStore) -> None:
        """Review A/B regression: the sort→scrape-rename→dispatch chain reaches 'dispatched'.

        Before the fix, the scrape's canonical rename left current_path at the sorted
        name while dispatch keyed on the canonical name → record_dispatch_by_path
        matched 0 rows (never 'dispatched'), and the prune then deleted the completed
        journey. With move_path tracking the rename, dispatch matches and the row is
        kept.
        """
        store.provenance.upsert_grab(
            "h", followed_id=None, media_ref=MediaRef(tmdb_id=27205), kind="movie", grabbed_at=1
        )
        # ingest/sort → current_path is the sorted release name.
        store.provenance.set_ingest("h", ingest_path="/001-MOVIES/Some.Movie.2020.1080p.WEB", ingested_at=2)
        # scrape renames the folder to its canonical name (the orchestrator's move_path).
        store.provenance.move_path("/001-MOVIES/Some.Movie.2020.1080p.WEB", "/001-MOVIES/Some Movie (2020)")
        # dispatch keys on the (now current) canonical staging path.
        store.provenance.record_dispatch_by_path(
            "/001-MOVIES/Some Movie (2020)", dispatch_path="/Volumes/Disk/films/Some Movie (2020)", dispatched_at=3
        )
        row = store.provenance.by_hash("h")
        assert row is not None and row.status == "dispatched", "the dispatch record must now match (review A)"
        assert row.dispatch_path == "/Volumes/Disk/films/Some Movie (2020)"
        # The prune KEEPS the completed journey even though its staging path is gone.
        assert store.provenance.prune_stale(lambda _p: False) == 0, "a dispatched row must not be pruned (review B)"
        assert store.provenance.by_hash("h") is not None


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

    def test_prune_keeps_dispatched_rows(self, store: ConcreteAcquireStore) -> None:
        """A DISPATCHED row with a vanished current_path is KEPT (completed journey)."""
        store.provenance.upsert_grab("d", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("d", ingest_path="/gone", ingested_at=1)
        store.provenance.record_dispatch_by_path("/gone", dispatch_path="/Volumes/Disk/x", dispatched_at=2)
        pruned = store.provenance.prune_stale(lambda _p: False)  # treat every path as missing
        assert pruned == 0, "a dispatched row (completed journey) must never be pruned"
        assert store.provenance.by_hash("d") is not None


class TestMigration011ResolutionColumns:
    """The F2 resolution-projection columns + partial index exist after migration 011."""

    def test_resolution_columns_and_index_present(self, store: ConcreteAcquireStore) -> None:
        """A fresh store carries the resolution_* columns and their partial index."""
        conn = store._ensure_open()  # noqa: SLF001 — test reaches the migrated schema
        cols = {r[1] for r in conn.execute("PRAGMA table_info('staging_provenance')")}
        assert {"resolution_state", "decision_id", "resolution_trigger", "resolution_at"} <= cols
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_provenance_resolution_state" in indexes

    def test_user_version_at_least_11(self, store: ConcreteAcquireStore) -> None:
        """Migration 011 (and any later) has been applied — user_version >= 11."""
        conn = store._ensure_open()  # noqa: SLF001
        assert conn.execute("PRAGMA user_version").fetchone()[0] >= 11


class TestResolutionProjection:
    """set_resolution projects the decision lifecycle onto a tracked folder (F2, advisory)."""

    def test_awaiting_round_trips_on_tracked_row(self, store: ConcreteAcquireStore) -> None:
        """An enqueued item's folder gets resolution_state='awaiting' + trigger + decision_id."""
        store.provenance.upsert_grab(
            "h1", followed_id=None, media_ref=MediaRef(tmdb_id=27205), kind="movie", grabbed_at=1
        )
        store.provenance.set_ingest("h1", ingest_path="/stage/Item", ingested_at=2)
        store.provenance.set_resolution(
            "/stage/Item", state="awaiting", resolved_at=3, decision_id=42, trigger="mid_band"
        )
        row = store.provenance.by_path("/stage/Item")
        assert row is not None
        assert row.resolution_state == "awaiting"
        assert row.decision_id == 42
        assert row.resolution_trigger == "mid_band"
        assert row.resolution_at == 3

    def test_resolved_then_dismissed_transition(self, store: ConcreteAcquireStore) -> None:
        """A later verdict overwrites the projection (awaiting → resolved)."""
        store.provenance.upsert_grab("h2", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("h2", ingest_path="/stage/B", ingested_at=2)
        store.provenance.set_resolution("/stage/B", state="awaiting", resolved_at=3, decision_id=7, trigger="ambiguous")
        store.provenance.set_resolution("/stage/B", state="resolved", resolved_at=9)
        row = store.provenance.by_path("/stage/B")
        assert row is not None
        assert row.resolution_state == "resolved"
        assert row.resolution_at == 9

    def test_untracked_folder_is_a_noop(self, store: ConcreteAcquireStore) -> None:
        """set_resolution on an untracked (manual-item) path changes nothing, never raises."""
        # No upsert_grab → no row. The manual/direct item lives only in scrape_decision.
        store.provenance.set_resolution(
            "/stage/manual-item", state="awaiting", resolved_at=1, decision_id=99, trigger="mid_band"
        )
        assert store.provenance.by_path("/stage/manual-item") is None
        conn = store._ensure_open()  # noqa: SLF001
        assert conn.execute("SELECT COUNT(*) FROM staging_provenance").fetchone()[0] == 0

    def test_set_resolution_swallows_db_error(self) -> None:
        """A DB error inside set_resolution is swallowed (advisory — never fails a step)."""

        class _RaisingConn:
            def execute(self, *_a: object, **_k: object) -> object:
                raise RuntimeError("db exploded")

        sub = _ProvenanceSubStore(_RaisingConn(), _write_tx)  # type: ignore[arg-type]
        sub.set_resolution("/x", state="awaiting", resolved_at=1)  # must NOT raise

    def test_set_resolution_matches_across_unicode_normalization(self, store: ConcreteAcquireStore) -> None:
        """A row stored under its NFD path is still hit when keyed with the NFC form (F2 #2).

        The dismiss route keys on ``scrape_decision.staging_path`` (NFC-normalized), while
        ``current_path`` is stored raw (NFD from ``iterdir`` on macOS). The projection must
        match regardless of normalization, else an accented-title dismiss silently misses.
        """
        import unicodedata

        nfd_path = unicodedata.normalize("NFD", "/stage/Amélie (2001)")
        nfc_path = unicodedata.normalize("NFC", "/stage/Amélie (2001)")
        assert nfd_path != nfc_path  # the title actually decomposes (guards the test)

        store.provenance.upsert_grab("h", followed_id=None, media_ref=MediaRef(tmdb_id=194), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("h", ingest_path=nfd_path, ingested_at=2)  # stored NFD
        # Key with the NFC form (as the dismiss route would):
        store.provenance.set_resolution(nfc_path, state="dismissed", resolved_at=3)
        row = store.provenance.by_hash("h")
        assert row is not None
        assert row.resolution_state == "dismissed"
        # by_path is likewise normalization-robust.
        assert store.provenance.by_path(nfc_path) is not None


class TestMigration012RunLinkage:
    """The F3 per-stage run-uid columns exist after migration 012."""

    def test_run_columns_present_and_version_12(self, store: ConcreteAcquireStore) -> None:
        """A fresh store carries the four *_run_uid columns and the latest user_version."""
        conn = store._ensure_open()  # noqa: SLF001 — test reaches the migrated schema
        cols = {r[1] for r in conn.execute("PRAGMA table_info('staging_provenance')")}
        assert {"grab_run_uid", "ingest_run_uid", "scrape_run_uid", "dispatch_run_uid"} <= cols
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 20  # latest chain: 020 wanted last_grab_failure


class TestRunLinkage:
    """Each stage stamps its run_uid; the converse query answers 'items in run X' (F3)."""

    def test_each_stage_stamps_its_run_uid(self, store: ConcreteAcquireStore) -> None:
        """grab/ingest/scrape/dispatch each record their own run on the row."""
        store.provenance.upsert_grab(
            "h1", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1, run_uid="grabRUN"
        )
        store.provenance.set_ingest("h1", ingest_path="/stage/Item", ingested_at=2, run_uid="ingRUN")
        store.provenance.set_scrape_run("/stage/Item", run_uid="scrRUN", scraped_at=3)
        store.provenance.record_dispatch_by_path(
            "/stage/Item", dispatch_path="/Volumes/D/Item", dispatched_at=4, run_uid="dispRUN"
        )
        row = store.provenance.by_hash("h1")
        assert row is not None
        assert row.grab_run_uid == "grabRUN"
        assert row.ingest_run_uid == "ingRUN"
        assert row.scrape_run_uid == "scrRUN"
        assert row.dispatch_run_uid == "dispRUN"

    def test_run_uids_default_none_when_omitted(self, store: ConcreteAcquireStore) -> None:
        """Omitting run_uid (grab via qBit-direct / no run) leaves the columns NULL."""
        store.provenance.upsert_grab("h2", followed_id=None, media_ref=MediaRef(tmdb_id=2), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("h2", ingest_path="/stage/B", ingested_at=2)
        row = store.provenance.by_hash("h2")
        assert row is not None
        assert row.grab_run_uid is None
        assert row.ingest_run_uid is None

    def test_set_scrape_run_marks_stage_even_without_run_uid(self, store: ConcreteAcquireStore) -> None:
        """set_scrape_run with run_uid=None still advances the scrape STAGE (scraped_at + status)."""
        store.provenance.upsert_grab("h3", followed_id=None, media_ref=MediaRef(tmdb_id=3), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("h3", ingest_path="/stage/C", ingested_at=2)
        store.provenance.set_scrape_run("/stage/C", run_uid=None, scraped_at=5)
        row = store.provenance.by_hash("h3")
        assert row is not None
        assert row.scrape_run_uid is None  # no run stamp (standalone scrape)
        assert row.scraped_at == 5  # but the stage IS recorded (chip lights up)
        assert row.status == "scraped"

    def test_set_scrape_run_noop_when_untracked(self, store: ConcreteAcquireStore) -> None:
        """set_scrape_run on an untracked (manual) folder never creates a row (ACC-06)."""
        store.provenance.set_scrape_run("/stage/manual", run_uid="scrRUN", scraped_at=1)
        assert store.provenance.by_path("/stage/manual") is None

    def test_list_journeys_for_run_matches_any_stage(self, store: ConcreteAcquireStore) -> None:
        """The converse query returns items a run touched at ANY stage, and excludes others."""
        # Item A: scraped by RUN_X.
        store.provenance.upsert_grab("a", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=10)
        store.provenance.set_ingest("a", ingest_path="/s/A", ingested_at=11)
        store.provenance.set_scrape_run("/s/A", run_uid="RUN_X", scraped_at=12)
        # Item B: dispatched by RUN_X (different stage).
        store.provenance.upsert_grab("b", followed_id=None, media_ref=MediaRef(tmdb_id=2), kind="movie", grabbed_at=20)
        store.provenance.set_ingest("b", ingest_path="/s/B", ingested_at=21)
        store.provenance.record_dispatch_by_path("/s/B", dispatch_path="/D/B", dispatched_at=22, run_uid="RUN_X")
        # Item C: untouched by RUN_X.
        store.provenance.upsert_grab(
            "c", followed_id=None, media_ref=MediaRef(tmdb_id=3), kind="movie", grabbed_at=30, run_uid="RUN_Y"
        )
        hashes = {r.info_hash for r in store.provenance.list_journeys_for_run("RUN_X")}
        assert hashes == {"a", "b"}


class TestStuckDetection:
    """F4 substrate: list_stuck + provenance_row_is_stuck identify in-flight, on-disk, aged items."""

    def _seed(self, store: ConcreteAcquireStore, h: str, path: str, status_at: dict) -> None:
        store.provenance.upsert_grab(h, followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1)
        if "ingested_at" in status_at:
            store.provenance.set_ingest(h, ingest_path=path, ingested_at=status_at["ingested_at"])
        if "dispatched_at" in status_at:
            store.provenance.record_dispatch_by_path(
                path, dispatch_path="/D/x", dispatched_at=status_at["dispatched_at"]
            )

    def test_list_stuck_returns_aged_on_disk_in_flight_only(self, store: ConcreteAcquireStore) -> None:
        """Aged + on-disk + in-flight → stuck; dispatched / vanished / fresh → excluded."""
        # A: ingested long ago, folder exists → STUCK.
        self._seed(store, "a", "/stage/A", {"ingested_at": 100})
        # B: ingested recently → not aged.
        self._seed(store, "b", "/stage/B", {"ingested_at": 10_000})
        # C: ingested long ago but folder gone → not stuck (prune candidate, not resume).
        self._seed(store, "c", "/stage/C", {"ingested_at": 100})
        # D: dispatched (terminal) → excluded even if aged.
        self._seed(store, "d", "/stage/D", {"ingested_at": 100, "dispatched_at": 200})

        present = {"/stage/A", "/stage/B", "/stage/D"}  # C's folder vanished
        stuck = store.provenance.list_stuck(older_than=5_000, exists_fn=lambda p: p in present)
        assert {r.info_hash for r in stuck} == {"a"}

    def test_provenance_row_is_stuck_predicate(self, store: ConcreteAcquireStore) -> None:
        """The shared predicate mirrors list_stuck (used by the journeys endpoint's stuck flag)."""
        from personalscraper.acquire._provenance_store import provenance_row_is_stuck

        self._seed(store, "a", "/stage/A", {"ingested_at": 100})
        row = store.provenance.by_hash("a")
        assert row is not None
        # Aged + exists → stuck.
        assert provenance_row_is_stuck(row, now=10_000, idle_seconds=1_000, exists_fn=lambda _p: True) is True
        # Folder gone → not stuck.
        assert provenance_row_is_stuck(row, now=10_000, idle_seconds=1_000, exists_fn=lambda _p: False) is False
        # Not yet idle → not stuck.
        assert provenance_row_is_stuck(row, now=500, idle_seconds=1_000, exists_fn=lambda _p: True) is False

    def test_list_stuck_fail_soft(self) -> None:
        """A DB error yields an empty list (never raises)."""

        class _RaisingConn:
            row_factory = None

            def execute(self, *_a: object, **_k: object) -> object:
                raise RuntimeError("db exploded")

        sub = _ProvenanceSubStore(_RaisingConn(), _write_tx)  # type: ignore[arg-type]
        assert sub.list_stuck(older_than=1, exists_fn=lambda _p: True) == []


class TestStageCounts:
    """F5 overview: stage_counts returns the uncapped per-status GROUP BY rollup."""

    def test_counts_by_status(self, store: ConcreteAcquireStore) -> None:
        """Each status is counted; dispatched/reconciled distinguished from in-flight."""
        # 2 grabbed, 1 ingested, 1 dispatched.
        for h in ("g1", "g2"):
            store.provenance.upsert_grab(h, followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1)
        store.provenance.upsert_grab("i1", followed_id=None, media_ref=MediaRef(tmdb_id=2), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("i1", ingest_path="/s/i1", ingested_at=2)
        store.provenance.upsert_grab("d1", followed_id=None, media_ref=MediaRef(tmdb_id=3), kind="movie", grabbed_at=1)
        store.provenance.set_ingest("d1", ingest_path="/s/d1", ingested_at=2)
        store.provenance.record_dispatch_by_path("/s/d1", dispatch_path="/D/d1", dispatched_at=3)
        counts = store.provenance.stage_counts()
        assert counts.get("grabbed") == 2
        assert counts.get("ingested") == 1
        assert counts.get("dispatched") == 1

    def test_stage_counts_fail_soft(self) -> None:
        """A DB error yields an empty dict (never raises)."""

        class _RaisingConn:
            row_factory = None

            def execute(self, *_a: object, **_k: object) -> object:
                raise RuntimeError("db exploded")

        sub = _ProvenanceSubStore(_RaisingConn(), _write_tx)  # type: ignore[arg-type]
        assert sub.stage_counts() == {}
