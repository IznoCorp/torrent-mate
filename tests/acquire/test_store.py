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
    """After first sub-store access PRAGMA user_version == 1 (001_init.sql)."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        _ = s.follow  # triggers open + migrate
        # Read user_version through a throwaway connection (reads are lock-free).
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        assert version == 1
    finally:
        s.close()


def test_all_four_tables_exist(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """All four domain tables are present after the store opens."""
    _ = store.follow  # ensure the store has opened + migrated
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"followed_series", "wanted", "seed_obligation", "ratio_state"} <= tables


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
        assert fetched == series
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
    assert fetched == series  # frozen dataclass field-level equality
    assert fetched is not None
    # MediaRef must round-trip identically (no provider-ID contamination).
    assert fetched.media_ref == MediaRef(tvdb_id=12345, tmdb_id=678, imdb_id="tt0011223")


def test_follow_get_missing_returns_none(store: ConcreteAcquireStore) -> None:
    """follow.get on an unknown id returns None."""
    assert store.follow.get(99999) is None


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
    assert fetched == item

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
    # Round-trip equality on the single pending item too.
    assert store.wanted.get(pid) == pending


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
