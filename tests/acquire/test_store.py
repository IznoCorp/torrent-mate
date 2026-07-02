"""Non-vacuous tests for the concrete AcquireStore (RP3, lock-model corrected).

Covers:
- Lazy open: build_acquire_store creates NO db file / connection / lock until
  the first sub-store access (the corrected concurrency model — DESIGN §6.3).
- Migration: on first access PRAGMA user_version == 1 (001_init.sql applied).
- Protocol conformance: ConcreteAcquireStore satisfies the AcquireStore Protocol.
- CONCURRENCY REGRESSION: two stores on the SAME db_path both open + read with
  NO AcquireLockError (proves the lifetime-writer-lock regression is fixed).
- WRITE SERIALIZATION: a write through one store is visible to a second store's
  read (BEGIN IMMEDIATE commits are durable + shared cross-handle); _write_tx
  issues the BEGIN IMMEDIATE serialization primitive.
- close() fail-soft + idempotent + close-without-open no-op.
- Round-trip per sub-store with field-level frozen-VO equality (incl. MediaRef
  JSON round-trip), wanted status transition, partial-index pending query.
- CHECK-constraint liveness (mutation-proof guard).
- isinstance: Acquire* errors subclass the core Sqlite* markers.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from personalscraper.acquire._ports import AcquireStore as AcquireStoreProtocol
from personalscraper.acquire.domain import (
    FollowedSeries,
    RatioState,
    SeedObligation,
    WantedItem,
)
from personalscraper.acquire.errors import (
    AcquireCorruptError,
    AcquireLockError,
    AcquireMigrationError,
)
from personalscraper.acquire.store import (
    ConcreteAcquireStore,
    _write_tx,
    build_acquire_store,
)
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteLockError,
    SqliteMigrationError,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards.

    The store is inert until a sub-store is accessed; the tests that use this
    fixture access a sub-store, which lazily opens the connection.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A :class:`ConcreteAcquireStore` (opens on first sub-store access).
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Lazy open (corrected concurrency model — DESIGN §6.3)
# ---------------------------------------------------------------------------


def test_build_is_inert_no_db_file_until_first_access(tmp_path: Path) -> None:
    """build_acquire_store opens nothing: the db file is absent until first use.

    Proves the laziness contract: no mkdir, no connection, no lock and no
    migration happen at build.  The db file appears only after a sub-store is
    touched.
    """
    db_path = tmp_path / "subdir" / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    s = build_acquire_store(cfg)
    try:
        # Inert: file (and even the parent dir) must not exist yet.
        assert not db_path.exists()
        assert not db_path.parent.exists()
        assert s._conn is None  # type: ignore[unreachable]
        # First sub-store access opens the connection + migrates.
        _ = s.follow
        assert db_path.exists()
        assert s._conn is not None
    finally:
        s.close()


def test_build_runs_migration_user_version_on_first_access(tmp_path: Path) -> None:
    """After first sub-store access PRAGMA user_version reflects latest migration."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        _ = s.follow  # triggers open + migrate
        # Read user_version through a throwaway connection (reads are lock-free).
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        assert version >= 2  # latest migration is 002_cross_seed.sql
    finally:
        s.close()


def test_all_tables_exist(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """All domain tables (including cross-seed) are present after the store opens."""
    _ = store.follow  # ensure the store has opened + migrated
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {
        "followed_series",
        "wanted",
        "seed_obligation",
        "ratio_state",
        "cross_seed_history",
        "cross_seed_quota",
        "watch_state",
    } <= tables


def test_build_requires_resolved_db_path() -> None:
    """build_acquire_store raises ValueError when db_path is unresolved (None)."""
    cfg = AcquireConfig(db_path=None)
    with pytest.raises(ValueError, match="db_path must be resolved"):
        build_acquire_store(cfg)


def test_store_satisfies_protocol(store: ConcreteAcquireStore) -> None:
    """ConcreteAcquireStore is a runtime instance of the AcquireStore Protocol."""
    assert isinstance(store, AcquireStoreProtocol)
    # All four sub-store namespaces are present (as ensure-open properties).
    assert all(hasattr(store, ns) for ns in ("follow", "wanted", "seed", "ratio"))


# ---------------------------------------------------------------------------
# Concurrency regression — two stores on one db_path coexist (lock-free reads)
# ---------------------------------------------------------------------------


def test_two_stores_same_path_both_open_and_read_no_lock_error(tmp_path: Path) -> None:
    """REGRESSION: two stores on the SAME db_path both open + read concurrently.

    The committed 3.3 store held the writer FileLock for its lifetime, so a
    second store on the same path crashed with AcquireLockError — which broke
    the shared composition root (e.g. the library-index cron during a pipeline
    run).  With the corrected model (SQLite-native single-writer, lock-free
    reads), both stores open and read with NO AcquireLockError.
    """
    db_path = tmp_path / "acquire.db"
    s1 = build_acquire_store(AcquireConfig(db_path=db_path))
    s2 = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        # Open store A (access a sub-store → opens the connection + migrates).
        assert s1.wanted.list_pending() == []
        # Build + access store B on the SAME path — must NOT raise AcquireLockError.
        assert s2.wanted.list_pending() == []
        # Both connections are independently live and lock-free for reads.
        assert s1.follow.get(123) is None
        assert s2.follow.get(123) is None
    finally:
        s1.close()
        s2.close()


def test_write_through_one_store_visible_to_another(tmp_path: Path) -> None:
    """SINGLE-WRITER CORRECTNESS: a committed write is visible across handles.

    A FollowedSeries written through store A is read back through a *separate*
    store B opened on the same db_path — proving BEGIN IMMEDIATE commits are
    durable and shared cross-process/cross-handle (the SQLite-native serializer
    that replaced the lifetime FileLock).
    """
    db_path = tmp_path / "acquire.db"
    writer = build_acquire_store(AcquireConfig(db_path=db_path))
    reader = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        series = FollowedSeries(
            media_ref=MediaRef(tvdb_id=999),
            title="Cross-Handle Show",
            added_at=1_700_000_000,
            active=True,
        )
        row_id = writer.follow.add(series)
        # A fresh handle on the same DB sees the committed row.
        fetched = reader.follow.get(row_id)
        assert fetched == replace(series, id=row_id)
    finally:
        writer.close()
        reader.close()


def test_write_tx_issues_begin_immediate(tmp_path: Path) -> None:
    """_write_tx opens an IMMEDIATE write transaction (the serialization primitive).

    Asserts the serializer directly: while a _write_tx block is open, the
    connection is in an active transaction (in_transaction True), and a SECOND
    connection with a tiny busy_timeout cannot acquire the write lock and gets
    SQLITE_BUSY (OperationalError "database is locked").  This proves BEGIN
    IMMEDIATE — not a deferred transaction — is the cross-process write gate.
    """
    db_path = tmp_path / "acquire.db"
    s = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        _ = s.follow  # open + migrate
        conn = s._conn
        assert conn is not None
        # A competing connection with a near-zero busy_timeout.
        rival = sqlite3.connect(str(db_path), timeout=0)
        try:
            with _write_tx(conn):
                assert conn.in_transaction  # IMMEDIATE took the write lock
                with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                    rival.execute("BEGIN IMMEDIATE")
            # After COMMIT the write lock is released; the rival can now write.
            rival.execute("BEGIN IMMEDIATE")
            rival.execute("ROLLBACK")
        finally:
            rival.close()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# close() — fail-soft, idempotent, no-op when never opened
# ---------------------------------------------------------------------------


def test_close_is_idempotent_and_fail_soft(tmp_path: Path) -> None:
    """Double close() does not raise (fail-soft, idempotent)."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    _ = s.follow  # open it so there is a real connection to close
    s.close()
    s.close()  # must not raise


def test_close_without_open_is_noop(tmp_path: Path) -> None:
    """close() on a never-accessed store is a pure no-op (no I/O, no raise).

    No connection was opened and no lock taken, so close() touches nothing and
    the db file is never created.
    """
    db_path = tmp_path / "acquire.db"
    s = build_acquire_store(AcquireConfig(db_path=db_path))
    s.close()  # must not raise
    assert not db_path.exists()  # nothing was ever opened


def test_close_fail_soft_even_if_conn_already_closed(tmp_path: Path) -> None:
    """close() swallows errors when the underlying connection is already closed."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    _ = s.follow  # open it
    assert s._conn is not None
    s._conn.close()  # simulate an externally-closed connection
    s.close()  # must not raise despite the already-closed conn


def test_access_after_close_raises(tmp_path: Path) -> None:
    """Accessing a sub-store after close() raises (closed handle is unusable)."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    _ = s.follow
    s.close()
    with pytest.raises(RuntimeError, match="closed"):
        _ = s.follow


# ---------------------------------------------------------------------------
# Round-trip per sub-store (field-level frozen-VO equality)
# ---------------------------------------------------------------------------


def test_follow_round_trip(store: ConcreteAcquireStore) -> None:
    """A FollowedSeries inserts and reads back as an equal frozen VO (MediaRef incl.)."""
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=12345, tmdb_id=678, imdb_id="tt0011223"),
        title="The Example Show",
        added_at=1_700_000_000,
        active=True,
        quality_profile_json='{"profile": "1080p"}',
        cadence_json='{"every": "weekly"}',
    )
    row_id = store.follow.add(series)
    fetched = store.follow.get(row_id)
    assert fetched is not None
    # fetched carries the persisted rowid; the fresh VO does not.
    assert fetched == replace(series, id=row_id)
    # MediaRef must round-trip identically (no provider-ID contamination).
    assert fetched.media_ref == MediaRef(tvdb_id=12345, tmdb_id=678, imdb_id="tt0011223")


def test_follow_get_missing_returns_none(store: ConcreteAcquireStore) -> None:
    """follow.get on an unknown id returns None."""
    assert store.follow.get(99999) is None


def test_follow_get_round_trips_id(store: ConcreteAcquireStore) -> None:
    """follow.get populates FollowedSeries.id with the rowid."""
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=10001),
        title="Id Roundtrip Show",
        added_at=1_700_000_000,
        active=True,
    )
    row_id = store.follow.add(series)
    fetched = store.follow.get(row_id)
    assert fetched is not None
    assert fetched.id == row_id, f"Expected id={row_id}, got {fetched.id}"


def test_follow_find_by_ref_returns_none_when_absent(store: ConcreteAcquireStore) -> None:
    """find_by_ref returns None when no matching row exists."""
    assert store.follow.find_by_ref(MediaRef(tvdb_id=99999)) is None


def test_follow_find_by_ref_round_trips_id(store: ConcreteAcquireStore) -> None:
    """find_by_ref locates the row and populates .id correctly (LOAD-BEARING dedup check)."""
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=55555),
        title="Dedup Show",
        added_at=1_700_000_000,
        active=True,
    )
    row_id = store.follow.add(series)
    found = store.follow.find_by_ref(MediaRef(tvdb_id=55555))
    assert found is not None
    assert found.id == row_id
    assert found.media_ref == series.media_ref

    # LOAD-BEARING: second call with the same ref finds the SAME row (1 row only).
    found2 = store.follow.find_by_ref(MediaRef(tvdb_id=55555))
    assert found2 is not None
    assert found2.id == row_id  # same rowid, no duplicate


def test_follow_find_by_ref_cross_key_tvdb_primary(store: ConcreteAcquireStore) -> None:
    """C1 REGRESSION: add tvdb+tmdb → find_by_ref(tvdb-only) matches (cross-key dedup).

    A series stored with both tvdb_id and tmdb_id MUST be found by a
    tvdb-only lookup — the primary id drives the match, not the exact tuple.
    """
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=81189, tmdb_id=1396),
        title="Breaking Bad",
        added_at=1_700_000_000,
        active=True,
    )
    store.follow.add(series)
    found = store.follow.find_by_ref(MediaRef(tvdb_id=81189))
    assert found is not None, "C1 MISS: tvdb-only lookup must match a row stored with tvdb+tmdb"
    assert found.media_ref.tvdb_id == 81189
    assert found.media_ref.tmdb_id == 1396


def test_follow_find_by_ref_cross_key_tmdb_fallback(store: ConcreteAcquireStore) -> None:
    """C1 REGRESSION: add tvdb+tmdb → find_by_ref(tmdb-only) also matches (fallback).

    When the lookup ref has only tmdb_id, it should fall back to matching on
    tmdb_id in stored rows.
    """
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=81189, tmdb_id=1396),
        title="Breaking Bad",
        added_at=1_700_000_000,
        active=True,
    )
    store.follow.add(series)
    found = store.follow.find_by_ref(MediaRef(tmdb_id=1396))
    assert found is not None, "C1 MISS: tmdb-only lookup must match a row stored with tvdb+tmdb"
    assert found.media_ref.tmdb_id == 1396


def test_follow_find_by_ref_no_false_merge(store: ConcreteAcquireStore) -> None:
    """C1 REGRESSION: two series with different tvdb_ids → find_by_ref(one) returns only that one.

    The cross-key match must NOT merge unrelated series that share no primary id.
    """
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=81189),
            title="Breaking Bad",
            added_at=1_700_000_000,
            active=True,
        )
    )
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=121361),
            title="Better Call Saul",
            added_at=1_700_000_001,
            active=True,
        )
    )
    found = store.follow.find_by_ref(MediaRef(tvdb_id=81189))
    assert found is not None
    assert found.media_ref.tvdb_id == 81189, "C1 FALSE-MERGE: find_by_ref(81189) must not return the other series"
    assert found.title == "Breaking Bad"


def test_follow_list_active_excludes_inactive(store: ConcreteAcquireStore) -> None:
    """list_active returns only active=True rows (LOAD-BEARING filter check)."""
    active_series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=1001),
        title="Active Show",
        added_at=1_700_000_001,
        active=True,
    )
    inactive_series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=1002),
        title="Inactive Show",
        added_at=1_700_000_002,
        active=False,
    )
    store.follow.add(active_series)
    store.follow.add(inactive_series)

    active_list = store.follow.list_active()
    assert len(active_list) == 1, f"Expected 1 active row, got {len(active_list)}"
    assert active_list[0].title == "Active Show"
    assert active_list[0].active is True


def test_follow_list_all_includes_both(store: ConcreteAcquireStore) -> None:
    """list_all returns all rows regardless of active flag."""
    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=2001), title="A", added_at=1, active=True))
    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=2002), title="B", added_at=2, active=False))
    all_rows = store.follow.list_all()
    assert len(all_rows) == 2
    tvdb_ids = {r.media_ref.tvdb_id for r in all_rows}
    assert tvdb_ids == {2001, 2002}


def test_follow_set_active_flips_flag(store: ConcreteAcquireStore) -> None:
    """set_active(id, False) soft-unfollows; set_active(id, True) reactivates (LOAD-BEARING)."""
    series = FollowedSeries(
        media_ref=MediaRef(tvdb_id=77777),
        title="Flip Show",
        added_at=1_700_000_000,
        active=True,
    )
    row_id = store.follow.add(series)

    # Soft unfollow.
    store.follow.set_active(row_id, False)
    after_unfollow = store.follow.get(row_id)
    assert after_unfollow is not None
    assert after_unfollow.active is False, "Expected active=False after set_active(id, False)"

    # Reactivate — must be the SAME row, not a new one.
    store.follow.set_active(row_id, True)
    after_reactivate = store.follow.get(row_id)
    assert after_reactivate is not None
    assert after_reactivate.active is True, "Expected active=True after set_active(id, True)"
    assert after_reactivate.id == row_id, "Reactivate must update the existing row, not insert a new one"

    # list_active reflects the change.
    active_list = store.follow.list_active()
    assert any(s.id == row_id for s in active_list), "Reactivated row must appear in list_active()"


def test_follow_substore_satisfies_protocol(store: ConcreteAcquireStore) -> None:
    """_FollowSubStore satisfies the FollowSubStore Protocol (all new methods present)."""
    from personalscraper.acquire._ports import FollowSubStore as FollowSubStoreProto

    follow_sub = store.follow
    expected_methods = ("add", "get", "find_by_ref", "list_active", "list_all", "set_active")
    missing = [m for m in expected_methods if not hasattr(follow_sub, m)]
    assert isinstance(follow_sub, FollowSubStoreProto), (
        f"Expected _FollowSubStore to satisfy the FollowSubStore Protocol; missing: {missing}"
    )


def test_wanted_round_trip_and_status_transition(store: ConcreteAcquireStore) -> None:
    """A WantedItem round-trips, then a status transition is observable."""
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=42),
        kind="episode",
        status="pending",
        enqueued_at=1_700_000_100,
        season=2,
        episode=5,
        attempts=0,
    )
    wid = store.wanted.add(item)
    fetched = store.wanted.get(wid)
    # The fetched item carries the persisted rowid (RP5b WantedItem.id); a fresh
    # 'pending' row has no grabbed_hash. Compare against the item with id set.
    assert fetched == replace(item, id=wid)

    store.wanted.set_status(wid, "grabbed")
    after = store.wanted.get(wid)
    assert after is not None
    assert after.status == "grabbed"
    # All other fields are unchanged by the transition.
    assert after.media_ref == item.media_ref
    assert after.season == 2
    assert after.episode == 5


def test_wanted_list_pending_partial_index_path(store: ConcreteAcquireStore) -> None:
    """list_pending returns only 'pending' rows (exercises idx_wanted_pending)."""
    pending = WantedItem(media_ref=MediaRef(tvdb_id=1), kind="movie", status="pending", enqueued_at=10)
    grabbed = WantedItem(media_ref=MediaRef(tvdb_id=2), kind="movie", status="grabbed", enqueued_at=20)
    done = WantedItem(media_ref=MediaRef(tvdb_id=3), kind="episode", status="done", enqueued_at=30, season=1, episode=1)
    pid = store.wanted.add(pending)
    store.wanted.add(grabbed)
    store.wanted.add(done)

    listed = store.wanted.list_pending()
    assert [w.media_ref.tvdb_id for w in listed] == [1]
    # Round-trip equality on the single pending item too (id now populated).
    assert store.wanted.get(pid) == replace(pending, id=pid)


def test_seed_round_trip_and_marks(store: ConcreteAcquireStore) -> None:
    """A SeedObligation round-trips and find_by_dispatched_path resolves it."""
    obligation = SeedObligation(
        info_hash="abcdef0123456789",
        source_tracker="lacale",
        min_seed_time_s=259200,
        min_ratio=1.5,
        added_at=1_700_000_200,
        dispatched_path="/Volumes/Disk1/Movies/Example (2024)",
    )
    oid = store.seed.add(obligation)
    found = store.seed.find_by_dispatched_path(Path("/Volumes/Disk1/Movies/Example (2024)"))
    assert found == obligation

    # mark_satisfied makes it inactive → no longer found.
    store.seed.mark_satisfied(oid, satisfied_at=1_700_000_999)
    assert store.seed.find_by_dispatched_path(Path("/Volumes/Disk1/Movies/Example (2024)")) is None


def test_seed_mark_breached(store: ConcreteAcquireStore) -> None:
    """mark_breached sets breached_at without satisfying the obligation."""
    obligation = SeedObligation(
        info_hash="ff00ff00",
        source_tracker="c411",
        min_seed_time_s=100,
        min_ratio=2.0,
        added_at=500,
        dispatched_path="/data/x",
    )
    oid = store.seed.add(obligation)
    store.seed.mark_breached(oid, breached_at=777)
    # Still active (not satisfied/released) so still found; breached_at is set.
    found = store.seed.find_by_dispatched_path(Path("/data/x"))
    assert found is not None
    assert found.breached_at == 777
    assert found.satisfied_at is None


def test_mark_breached_under_descendant_and_count(store: ConcreteAcquireStore) -> None:
    """mark_breached_under breaches an active descendant obligation and returns the count."""
    obligation = SeedObligation(
        info_hash="under111",
        source_tracker="lacale",
        min_seed_time_s=999999,
        min_ratio=1.0,
        added_at=1_700_000_000,
        dispatched_path="/data/tv/Show/Season 01/ep.mkv",
    )
    store.seed.add(obligation)

    # Breach by parent directory — the descendant obligation is stamped.
    count = store.seed.mark_breached_under(Path("/data/tv/Show"), breached_at=4242)
    assert count == 1

    found = store.seed.find_by_dispatched_path(Path("/data/tv/Show/Season 01/ep.mkv"))
    assert found is not None
    assert found.breached_at == 4242
    assert found.satisfied_at is None


def test_mark_breached_under_boundary_safe_no_sibling(store: ConcreteAcquireStore) -> None:
    """mark_breached_under does NOT breach a sibling-prefix obligation (boundary-safe LIKE)."""
    obligation = SeedObligation(
        info_hash="under222",
        source_tracker="c411",
        min_seed_time_s=999999,
        min_ratio=1.0,
        added_at=1_700_000_001,
        dispatched_path="/data/tv/Show-Other/stray.mkv",
    )
    store.seed.add(obligation)

    # "/data/tv/Show" must NOT match "/data/tv/Show-Other/...".
    count = store.seed.mark_breached_under(Path("/data/tv/Show"), breached_at=99)
    assert count == 0

    found = store.seed.find_by_dispatched_path(Path("/data/tv/Show-Other/stray.mkv"))
    assert found is not None
    assert found.breached_at is None


def test_mark_breached_under_excludes_released(store: ConcreteAcquireStore) -> None:
    """mark_breached_under skips already-released obligations (released_at IS NOT NULL)."""
    obligation = SeedObligation(
        info_hash="under333",
        source_tracker="lacale",
        min_seed_time_s=999999,
        min_ratio=1.0,
        added_at=1_700_000_002,
        dispatched_path="/data/movies/Film",
        released_at=1_700_000_900,
    )
    store.seed.add(obligation)

    count = store.seed.mark_breached_under(Path("/data/movies/Film"), breached_at=55)
    assert count == 0


def test_mark_breached_under_idempotent_skips_already_breached(store: ConcreteAcquireStore) -> None:
    """A second mark_breached_under on the same path is a no-op (idempotent count=0)."""
    obligation = SeedObligation(
        info_hash="under444",
        source_tracker="lacale",
        min_seed_time_s=999999,
        min_ratio=1.0,
        added_at=1_700_000_003,
        dispatched_path="/data/movies/Repeat",
    )
    store.seed.add(obligation)

    first = store.seed.mark_breached_under(Path("/data/movies/Repeat"), breached_at=10)
    assert first == 1
    # Second call must not re-stamp (breached_at IS NULL guard) → count 0.
    second = store.seed.mark_breached_under(Path("/data/movies/Repeat"), breached_at=20)
    assert second == 0
    found = store.seed.find_by_dispatched_path(Path("/data/movies/Repeat"))
    assert found is not None
    assert found.breached_at == 10


def test_find_active_under_exact_match(store: ConcreteAcquireStore) -> None:
    """find_active_under returns an obligation whose dispatched_path exactly matches path."""
    obligation = SeedObligation(
        info_hash="aaa111",
        source_tracker="lacale",
        min_seed_time_s=100,
        min_ratio=1.0,
        added_at=1_700_000_000,
        dispatched_path="/data/tv/The Show",
    )
    store.seed.add(obligation)

    results = store.seed.find_active_under(Path("/data/tv/The Show"))
    assert len(results) == 1
    assert results[0].info_hash == "aaa111"


def test_find_active_under_descendant(store: ConcreteAcquireStore) -> None:
    """find_active_under matches a dispatched_path that is a descendant of path."""
    obligation = SeedObligation(
        info_hash="bbb222",
        source_tracker="c411",
        min_seed_time_s=200,
        min_ratio=2.0,
        added_at=1_700_000_001,
        dispatched_path="/data/tv/The Show/Season 01/episode.mkv",
    )
    store.seed.add(obligation)

    # Querying the parent directory finds the file obligation underneath.
    results = store.seed.find_active_under(Path("/data/tv/The Show"))
    assert len(results) == 1
    assert results[0].info_hash == "bbb222"

    # Querying a higher ancestor also finds it.
    results = store.seed.find_active_under(Path("/data/tv"))
    assert len(results) == 1


def test_find_active_under_no_sibling_prefix_match(store: ConcreteAcquireStore) -> None:
    """find_active_under does NOT match a sibling-prefix path.

    ``/a/b`` must NOT match ``/a/bc`` or ``/a/b-other`` — the LIKE is boundary-safe.
    """
    obligation = SeedObligation(
        info_hash="ccc333",
        source_tracker="lacale",
        min_seed_time_s=300,
        min_ratio=1.0,
        added_at=1_700_000_002,
        dispatched_path="/data/tv/The Show-Other/stray.mkv",
    )
    store.seed.add(obligation)

    # /data/tv/The Show should NOT match /data/tv/The Show-Other/stray.mkv
    results = store.seed.find_active_under(Path("/data/tv/The Show"))
    assert len(results) == 0

    # /data/tv/The should NOT match /data/tv/The Show-Other/stray.mkv either
    results = store.seed.find_active_under(Path("/data/tv/The"))
    assert len(results) == 0


def test_find_active_under_excludes_released(store: ConcreteAcquireStore) -> None:
    """find_active_under excludes obligations with released_at IS NOT NULL."""
    obligation = SeedObligation(
        info_hash="ddd444",
        source_tracker="c411",
        min_seed_time_s=400,
        min_ratio=1.0,
        added_at=1_700_000_003,
        dispatched_path="/data/movies/Film",
        released_at=1_700_000_999,  # already released
    )
    store.seed.add(obligation)

    results = store.seed.find_active_under(Path("/data/movies/Film"))
    assert len(results) == 0


def test_find_active_under_returns_multiple_descendants(store: ConcreteAcquireStore) -> None:
    """find_active_under returns all active obligations under a directory."""
    obligations = [
        SeedObligation(
            info_hash="eee1",
            source_tracker="lacale",
            min_seed_time_s=100,
            min_ratio=1.0,
            added_at=1_700_000_100,
            dispatched_path="/data/tv/Show/S01/E01.mkv",
        ),
        SeedObligation(
            info_hash="eee2",
            source_tracker="lacale",
            min_seed_time_s=200,
            min_ratio=1.0,
            added_at=1_700_000_200,
            dispatched_path="/data/tv/Show/S01/E02.mkv",
        ),
        SeedObligation(
            info_hash="eee3",
            source_tracker="c411",
            min_seed_time_s=300,
            min_ratio=2.0,
            added_at=1_700_000_300,
            dispatched_path="/data/tv/Show/S02/E01.mkv",
        ),
    ]
    for obl in obligations:
        store.seed.add(obl)

    results = store.seed.find_active_under(Path("/data/tv/Show"))
    assert len(results) == 3
    info_hashes = {r.info_hash for r in results}
    assert info_hashes == {"eee1", "eee2", "eee3"}


def test_ratio_upsert_round_trip(store: ConcreteAcquireStore) -> None:
    """ratio.upsert inserts then updates the same PK row (data-carrier)."""
    initial = RatioState(
        tracker_name="lacale",
        observed_ratio=1.2,
        accumulated_seed_time_s=3600,
        hnr_count=0,
        updated_at=1000,
    )
    store.ratio.upsert(initial)
    assert store.ratio.get("lacale") == initial

    # Upsert again on the same PK must REPLACE, not duplicate.
    updated = RatioState(
        tracker_name="lacale",
        observed_ratio=1.9,
        accumulated_seed_time_s=7200,
        hnr_count=1,
        updated_at=2000,
    )
    store.ratio.upsert(updated)
    assert store.ratio.get("lacale") == updated


def test_ratio_get_missing_returns_none(store: ConcreteAcquireStore) -> None:
    """ratio.get on an unknown tracker returns None."""
    assert store.ratio.get("nonexistent") is None


# ---------------------------------------------------------------------------
# CHECK-constraint liveness (mutation-proof guard)
# ---------------------------------------------------------------------------


def test_wanted_status_check_is_live(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Writing an out-of-CHECK status via raw SQL is rejected (CHECK is live).

    Proves the schema CHECK constraints are enforced, not decorative.  We open a
    SECOND connection bypassing the store's transaction wrappers and attempt a
    direct UPDATE to an illegal status.
    """
    item = WantedItem(media_ref=MediaRef(tvdb_id=7), kind="movie", status="pending", enqueued_at=1)
    wid = store.wanted.add(item)

    raw = sqlite3.connect(str(tmp_path / "acquire.db"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute("UPDATE wanted SET status = 'bogus_status' WHERE id = ?", (wid,))
            raw.commit()
    finally:
        raw.close()
    # The stored value is still the legal one.
    fetched = store.wanted.get(wid)
    assert fetched is not None
    assert fetched.status == "pending"


def test_wanted_kind_check_is_live(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Inserting an out-of-CHECK kind via raw SQL is rejected (CHECK is live)."""
    _ = store.wanted  # ensure the schema exists before the raw connection probes it
    raw = sqlite3.connect(str(tmp_path / "acquire.db"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(
                "INSERT INTO wanted (media_ref_json, kind, status, enqueued_at) "
                "VALUES ('{}', 'bogus_kind', 'pending', 1)"
            )
            raw.commit()
    finally:
        raw.close()


# ---------------------------------------------------------------------------
# Error isinstance hierarchy
# ---------------------------------------------------------------------------


def test_acquire_errors_subclass_core_markers() -> None:
    """Each Acquire* error isinstance-matches its core Sqlite* marker."""
    assert issubclass(AcquireLockError, SqliteLockError)
    assert issubclass(AcquireCorruptError, SqliteCorruptError)
    assert issubclass(AcquireMigrationError, SqliteMigrationError)

    lock_err = AcquireLockError(4321)
    assert isinstance(lock_err, SqliteLockError)
    assert lock_err.pid == 4321
    assert "4321" in str(lock_err)

    mig_err = AcquireMigrationError(1)
    assert isinstance(mig_err, SqliteMigrationError)
    assert mig_err.version == 1
    assert "001" in str(mig_err)

    corrupt_err = AcquireCorruptError(Path("/db/acquire.db"), Path("/db/acquire.db.corrupt-1"))
    assert isinstance(corrupt_err, SqliteCorruptError)
    assert corrupt_err.db_path == Path("/db/acquire.db")
    assert corrupt_err.quarantine_path == Path("/db/acquire.db.corrupt-1")


# ---------------------------------------------------------------------------
# _WatchSubStore — real round-trip on tmp acquire.db
# ---------------------------------------------------------------------------


def test_watch_get_returns_none_when_never_set(store):
    """watch.get_last_successful_run_at returns None before any write."""
    assert store.watch.get_last_successful_run_at() is None


def test_watch_set_then_get_round_trip(store):
    """watch.set_last_successful_run_at persists a value readable by get."""
    store.watch.set_last_successful_run_at(1234.5)
    assert store.watch.get_last_successful_run_at() == 1234.5


def test_watch_set_upsert_overwrites_previous_value(store):
    """A second set_last_successful_run_at upserts (replaces, not duplicates)."""
    store.watch.set_last_successful_run_at(1234.5)
    store.watch.set_last_successful_run_at(2000.0)
    assert store.watch.get_last_successful_run_at() == 2000.0
    # Verify no duplicate rows — only one canonical key should exist.
    conn = store.watch._conn
    conn.row_factory = lambda cursor, row: row[0]
    count: int = conn.execute("SELECT COUNT(*) FROM watch_state WHERE key = 'last_successful_run_at'").fetchone()
    assert count == 1
