"""Non-vacuous tests for the concrete AcquireStore (RP3).

Covers:
- Construction: opens acquire.db, runs 001_init.sql, holds the lifetime lock.
- Protocol conformance: ConcreteAcquireStore satisfies the AcquireStore Protocol.
- Lock contention: an explicitly-held db_lock makes build_acquire_store raise
  AcquireLockError (the planner-flagged deterministic restructure — we hold the
  lock via the core context manager, NOT a second build call).
- close() fail-soft + idempotent + lock release.
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
    build_acquire_store,
)
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite._lock import db_lock
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteLockError,
    SqliteMigrationError,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield an open store on a temp acquire.db and close it afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        An open :class:`ConcreteAcquireStore`.
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Construction + schema contract
# ---------------------------------------------------------------------------


def test_build_runs_migration_user_version(tmp_path: Path) -> None:
    """After construction PRAGMA user_version == 1 (001_init.sql applied)."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        # Read user_version through a throwaway connection (the store holds the
        # lifetime lock, but a SELECT-only connection does not need the lock).
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        assert version == 1
    finally:
        s.close()


def test_all_four_tables_exist(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """All four domain tables are present after construction."""
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
    # All four sub-store namespaces are present.
    assert all(hasattr(store, ns) for ns in ("follow", "wanted", "seed", "ratio"))


# ---------------------------------------------------------------------------
# Lock contention — deterministic restructure (planner-flagged)
# ---------------------------------------------------------------------------


def test_lock_contention_raises_acquire_lock_error(tmp_path: Path) -> None:
    """A held db_lock makes build_acquire_store raise AcquireLockError (timeout=0).

    The planner flagged the original draft (a second build on an already-open
    DB) as unreliable.  We instead hold the writer lock EXPLICITLY via the core
    ``db_lock`` context manager, then assert the build (whose own lock uses
    timeout=0 + the AcquireLockError factory) fails fast.
    """
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    # Hold the writer lock for the duration of the build attempt.
    with db_lock(db_path, timeout=0, error_factory=AcquireLockError):
        with pytest.raises(AcquireLockError) as exc_info:
            build_acquire_store(cfg)
    # The actionable message must reference the holder PID.
    assert "PID" in str(exc_info.value)
    assert exc_info.value.pid > 0


def test_lifetime_lock_blocks_second_store(tmp_path: Path) -> None:
    """An open store holds the lifetime lock; a second build raises AcquireLockError."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s1 = build_acquire_store(cfg)
    try:
        with pytest.raises(AcquireLockError):
            build_acquire_store(cfg)
    finally:
        s1.close()


# ---------------------------------------------------------------------------
# close() — fail-soft, idempotent, releases the lock
# ---------------------------------------------------------------------------


def test_close_is_idempotent_and_fail_soft(tmp_path: Path) -> None:
    """Double close() does not raise (fail-soft, idempotent)."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    s.close()
    s.close()  # must not raise


def test_close_releases_lock(tmp_path: Path) -> None:
    """After close() the writer lock is free — a fresh db_lock acquire succeeds."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    s = build_acquire_store(cfg)
    assert Path(str(db_path) + ".lock").exists()  # lock held while open
    s.close()
    # The lock sidecar/file are gone and a fresh acquire succeeds immediately.
    with db_lock(db_path, timeout=0):
        pass  # would raise if the store's lock were still held


def test_close_fail_soft_even_if_conn_already_closed(tmp_path: Path) -> None:
    """close() swallows errors when the underlying connection is already closed."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    s._conn.close()  # simulate an externally-closed connection
    s.close()  # must not raise despite the already-closed conn


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
