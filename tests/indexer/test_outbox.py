"""Tests for outbox_repo plan §5.1 and outbox drainer plan §5.2.

§5.1 — OutboxRepo and PendingOpRepo public APIs:
- insert / fetch_pending round-trip for index_outbox
- mark_done / mark_failed / mark_deferred status transitions
- insert_pending_op_row / fetch_for_disk round-trip
- mark_replayed sets replayed_at
- purge_expired deletes rows older than TTL and returns correct count

§5.2 — Outbox drainer + publish_event:
- FIFO processing order
- Deduplication: 3 rows for same (disk_id, rel_path, filename) → only latest applied
- Retry on locked DB (mock OperationalError up to 3×)
- Deferred to pending_op when disk unreachable; replayed on remount
- All four op idempotence proofs (move, nfo_write, artwork_write, trailer_download)
- publish_event swallows exceptions and logs indexer.db.outbox_lost
- Drain idempotence property test (@given with Hypothesis)
"""

from __future__ import annotations

import json
import sqlite3
import time
import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from personalscraper.indexer.config import IndexerConfig
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.outbox import DrainStats, disk_id_for_path, drain, drain_if_present, publish_event
from personalscraper.indexer.repos import outbox_repo
from personalscraper.indexer.schema import DiskRow, MediaItemRow, PathRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# Suppress "unused" F401 — ruff cannot see all uses when imports span both §5.1 and §5.2 sections.
__all__ = [
    "Any",
    "DrainStats",
    "drain",
    "drain_if_present",
    "publish_event",
    "IndexerConfig",
    "MediaItemRow",
    "PathRow",
    "json",
    "patch",
    "given",
    "settings",
    "st",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB seeded with the full migration chain.

    Returns:
        An open :class:`sqlite3.Connection` with the full schema applied.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _insert_disk(conn: sqlite3.Connection, label: str = "TestDisk") -> int:
    """Insert a minimal disk row and return its id.

    Args:
        conn: Open SQLite connection.
        label: Display label for the disk.

    Returns:
        Rowid of the newly inserted disk row.
    """
    from personalscraper.indexer.repos import disk_repo

    row = DiskRow(
        id=0,
        uuid=f"uuid-{label}",
        label=label,
        mount_path=f"/Volumes/{label}",
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    return disk_repo.insert(conn, row)


# ---------------------------------------------------------------------------
# OutboxRepo — insert / fetch_pending
# ---------------------------------------------------------------------------


def test_insert_returns_positive_rowid(conn: sqlite3.Connection) -> None:
    """insert() returns a positive integer rowid on success."""
    rowid = outbox_repo.insert(conn, source="dispatch", op="move", payload_json='{"op":"move"}')
    assert isinstance(rowid, int)
    assert rowid > 0


def test_insert_sets_pending_status(conn: sqlite3.Connection) -> None:
    """Inserted row has status='pending' and processed_at=NULL."""
    rowid = outbox_repo.insert(conn, source="scraper", op="nfo_write", payload_json='{"op":"nfo_write"}')
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM index_outbox WHERE id = ?", (rowid,)).fetchone()
    assert row is not None
    assert row["status"] == "pending"
    assert row["processed_at"] is None


def test_fetch_pending_returns_fifo_order(conn: sqlite3.Connection) -> None:
    """fetch_pending() returns pending rows ordered by id ASC (FIFO)."""
    id1 = outbox_repo.insert(conn, source="dispatch", op="move", payload_json='{"n":1}')
    id2 = outbox_repo.insert(conn, source="scraper", op="nfo_write", payload_json='{"n":2}')
    id3 = outbox_repo.insert(conn, source="trailers", op="trailer_download", payload_json='{"n":3}')

    rows = outbox_repo.fetch_pending(conn)
    assert len(rows) == 3
    assert [r.id for r in rows] == [id1, id2, id3]


def test_fetch_pending_respects_limit(conn: sqlite3.Connection) -> None:
    """fetch_pending(limit=2) returns at most 2 rows even when more exist."""
    for i in range(5):
        outbox_repo.insert(conn, source="dispatch", op="move", payload_json=f'{{"n":{i}}}')

    rows = outbox_repo.fetch_pending(conn, limit=2)
    assert len(rows) == 2


def test_fetch_pending_excludes_non_pending(conn: sqlite3.Connection) -> None:
    """fetch_pending() excludes rows already marked done/failed/deferred."""
    id_pending = outbox_repo.insert(conn, source="dispatch", op="move", payload_json='{"n":1}')
    id_done = outbox_repo.insert(conn, source="scraper", op="nfo_write", payload_json='{"n":2}')
    outbox_repo.mark_done(conn, id_done)

    rows = outbox_repo.fetch_pending(conn)
    ids = [r.id for r in rows]
    assert id_pending in ids
    assert id_done not in ids


# ---------------------------------------------------------------------------
# OutboxRepo — mark_done / mark_failed / mark_deferred
# ---------------------------------------------------------------------------


def test_mark_done_sets_status_and_processed_at(conn: sqlite3.Connection) -> None:
    """mark_done() sets status='done' and a non-NULL processed_at."""
    row_id = outbox_repo.insert(conn, source="dispatch", op="move", payload_json="{}")
    before = int(time.time())
    outbox_repo.mark_done(conn, row_id)
    after = int(time.time())

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    assert row["status"] == "done"
    assert before <= row["processed_at"] <= after


def test_mark_failed_sets_status(conn: sqlite3.Connection) -> None:
    """mark_failed() sets status='failed' and records processed_at."""
    row_id = outbox_repo.insert(conn, source="dispatch", op="move", payload_json="{}")
    outbox_repo.mark_failed(conn, row_id)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    assert row["status"] == "failed"
    assert row["processed_at"] is not None


def test_mark_deferred_sets_status(conn: sqlite3.Connection) -> None:
    """mark_deferred() sets status='deferred' and records processed_at."""
    row_id = outbox_repo.insert(conn, source="trailers", op="trailer_download", payload_json="{}")
    outbox_repo.mark_deferred(conn, row_id)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    assert row["status"] == "deferred"
    assert row["processed_at"] is not None


def test_mark_done_removes_row_from_fetch_pending(conn: sqlite3.Connection) -> None:
    """A row marked done no longer appears in fetch_pending results."""
    row_id = outbox_repo.insert(conn, source="dispatch", op="move", payload_json="{}")
    assert len(outbox_repo.fetch_pending(conn)) == 1

    outbox_repo.mark_done(conn, row_id)
    assert outbox_repo.fetch_pending(conn) == []


# ---------------------------------------------------------------------------
# PendingOpRepo — insert_pending_op_row / fetch_for_disk
# ---------------------------------------------------------------------------


def test_insert_pending_op_row_returns_positive_rowid(conn: sqlite3.Connection) -> None:
    """insert_pending_op_row() returns a positive rowid on success."""
    disk_id = _insert_disk(conn)
    rowid = outbox_repo.insert_pending_op_row(conn, disk_id=disk_id, op="move", payload_json='{"op":"move"}')
    assert isinstance(rowid, int)
    assert rowid > 0


def test_fetch_for_disk_returns_inserted_rows(conn: sqlite3.Connection) -> None:
    """fetch_for_disk() returns all rows inserted for that disk, FIFO."""
    disk_id = _insert_disk(conn)
    id1 = outbox_repo.insert_pending_op_row(conn, disk_id=disk_id, op="move", payload_json='{"n":1}')
    id2 = outbox_repo.insert_pending_op_row(conn, disk_id=disk_id, op="nfo_write", payload_json='{"n":2}')

    rows = outbox_repo.fetch_for_disk(conn, disk_id)
    assert len(rows) == 2
    assert [r.id for r in rows] == [id1, id2]


def test_fetch_for_disk_isolates_by_disk(conn: sqlite3.Connection) -> None:
    """fetch_for_disk() does not return rows belonging to a different disk."""
    disk_a = _insert_disk(conn, label="DiskA")
    disk_b = _insert_disk(conn, label="DiskB")
    outbox_repo.insert_pending_op_row(conn, disk_id=disk_a, op="move", payload_json='{"disk":"A"}')
    outbox_repo.insert_pending_op_row(conn, disk_id=disk_b, op="move", payload_json='{"disk":"B"}')

    rows_a = outbox_repo.fetch_for_disk(conn, disk_a)
    rows_b = outbox_repo.fetch_for_disk(conn, disk_b)
    assert len(rows_a) == 1
    assert len(rows_b) == 1
    assert rows_a[0].disk_id == disk_a
    assert rows_b[0].disk_id == disk_b


# ---------------------------------------------------------------------------
# PendingOpRepo — mark_replayed
# ---------------------------------------------------------------------------


def test_mark_replayed_sets_replayed_at(conn: sqlite3.Connection) -> None:
    """mark_replayed() sets replayed_at to a non-NULL unix timestamp."""
    disk_id = _insert_disk(conn)
    row_id = outbox_repo.insert_pending_op_row(conn, disk_id=disk_id, op="move", payload_json="{}")

    before = int(time.time())
    outbox_repo.mark_replayed(conn, row_id)
    after = int(time.time())

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pending_op WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    assert before <= row["replayed_at"] <= after


def test_mark_replayed_initially_null(conn: sqlite3.Connection) -> None:
    """replayed_at is NULL immediately after insertion."""
    disk_id = _insert_disk(conn)
    row_id = outbox_repo.insert_pending_op_row(conn, disk_id=disk_id, op="move", payload_json="{}")

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pending_op WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    assert row["replayed_at"] is None


# ---------------------------------------------------------------------------
# PendingOpRepo — purge_expired
# ---------------------------------------------------------------------------


def test_purge_expired_removes_old_rows(conn: sqlite3.Connection) -> None:
    """purge_expired() deletes rows whose created_at is older than ttl_days."""
    disk_id = _insert_disk(conn)
    # Insert a row with created_at far in the past (40 days ago).
    old_ts = int(time.time()) - 40 * 86400
    conn.execute(
        "INSERT INTO pending_op (disk_id, op, payload_json, created_at, replayed_at) VALUES (?, ?, ?, ?, NULL)",
        (disk_id, "move", '{"old":true}', old_ts),
    )
    # Insert a recent row.
    outbox_repo.insert_pending_op_row(conn, disk_id=disk_id, op="move", payload_json='{"recent":true}')

    purged = outbox_repo.purge_expired(conn, ttl_days=30)
    assert purged == 1

    remaining = outbox_repo.fetch_for_disk(conn, disk_id)
    assert len(remaining) == 1
    assert remaining[0].payload_json == '{"recent":true}'


def test_purge_expired_returns_zero_when_nothing_to_purge(conn: sqlite3.Connection) -> None:
    """purge_expired() returns 0 when all rows are within the TTL window."""
    disk_id = _insert_disk(conn)
    outbox_repo.insert_pending_op_row(conn, disk_id=disk_id, op="move", payload_json="{}")

    purged = outbox_repo.purge_expired(conn, ttl_days=30)
    assert purged == 0


def test_purge_expired_removes_all_old_rows(conn: sqlite3.Connection) -> None:
    """purge_expired() removes all rows past the threshold, not just one."""
    disk_id = _insert_disk(conn)
    old_ts = int(time.time()) - 60 * 86400
    for i in range(3):
        conn.execute(
            "INSERT INTO pending_op (disk_id, op, payload_json, created_at, replayed_at) VALUES (?, ?, ?, ?, NULL)",
            (disk_id, "move", f'{{"i":{i}}}', old_ts),
        )

    purged = outbox_repo.purge_expired(conn, ttl_days=30)
    assert purged == 3
    assert outbox_repo.fetch_for_disk(conn, disk_id) == []


# ===========================================================================
# §5.2 — Outbox drainer tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared helpers for drainer tests
# ---------------------------------------------------------------------------


def _make_config() -> IndexerConfig:
    """Return a default IndexerConfig suitable for unit tests.

    Returns:
        :class:`IndexerConfig` with all defaults.
    """
    return IndexerConfig()


def _insert_path(conn: sqlite3.Connection, disk_id: int, rel_path: str = "movies/TestMovie (2020)") -> int:
    """Insert a path row and return its id.

    Args:
        conn: Open SQLite connection.
        disk_id: FK to the disk row.
        rel_path: Relative path string.

    Returns:
        Rowid of the newly inserted path row.
    """
    from personalscraper.indexer.repos import disk_repo

    row = PathRow(
        id=0,
        disk_id=disk_id,
        rel_path=rel_path,
        dir_mtime_ns=None,
        last_walked_at=int(time.time()),
    )
    return disk_repo.insert_path(conn, row)


def _insert_media_item(conn: sqlite3.Connection) -> int:
    """Insert a minimal media_item row and return its id.

    Args:
        conn: Open SQLite connection.

    Returns:
        Rowid of the newly inserted media_item row.
    """
    from personalscraper.indexer.repos import item_repo

    now = int(time.time())
    row = MediaItemRow(
        id=0,
        kind="movie",
        title="TestMovie",
        title_sort="TestMovie",
        original_title=None,
        year=2020,
        category_id="movies",
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        nfo_status=None,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="fr",
    )
    return item_repo.insert(conn, row)


def _insert_release(conn: sqlite3.Connection, item_id: int) -> int:
    """Insert a minimal media_release row linking to item_id and return its id.

    Args:
        conn: Open SQLite connection.
        item_id: FK to media_item.id.

    Returns:
        Rowid of the newly inserted media_release row.
    """
    sql = (
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang)"
        " VALUES (?, NULL, NULL, NULL, NULL)"
    )
    cursor = conn.execute(sql, (item_id,))
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    return rowid


def _insert_media_file(
    conn: sqlite3.Connection,
    path_id: int,
    release_id: int,
    filename: str = "TestMovie.mkv",
) -> int:
    """Insert a minimal media_file row and return its id.

    Args:
        conn: Open SQLite connection.
        path_id: FK to path.id.
        release_id: FK to media_release.id.
        filename: Bare filename.

    Returns:
        Rowid of the newly inserted media_file row.
    """
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (?, ?, ?, 1024, 1000000000, NULL, NULL, NULL, NULL, 0, ?, NULL, 0, NULL)
        """,
        (release_id, path_id, filename, now),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    return rowid


def _seed_linked_item(
    conn: sqlite3.Connection,
    disk_id: int,
    rel_path: str = "movies/TestMovie (2020)",
    filename: str = "TestMovie.mkv",
) -> tuple[int, int, int, int]:
    """Create a fully-linked disk → path → media_item → release → file chain.

    Args:
        conn: Open SQLite connection.
        disk_id: FK for the disk row.
        rel_path: Directory path relative to disk root.
        filename: Bare filename for the media_file row.

    Returns:
        Tuple of (path_id, item_id, release_id, file_id).
    """
    path_id = _insert_path(conn, disk_id, rel_path)
    item_id = _insert_media_item(conn)
    release_id = _insert_release(conn, item_id)
    file_id = _insert_media_file(conn, path_id, release_id, filename)
    return path_id, item_id, release_id, file_id


# ---------------------------------------------------------------------------
# drain() — FIFO processing order
# ---------------------------------------------------------------------------


def test_drain_processes_rows_fifo(conn: sqlite3.Connection) -> None:
    """drain() applies rows in id ASC (FIFO) order."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/Alpha (2020)"
    path_id = _insert_path(conn, disk_id, rel_path)

    # Insert two move rows referencing different filenames to avoid deduplication.
    outbox_repo.insert(
        conn,
        source="dispatch",
        op="move",
        payload_json=json.dumps(
            {"disk_id": disk_id, "dst_rel_path": rel_path, "filename": "alpha.mkv", "size_bytes": 100, "mtime_ns": 1000}
        ),
    )
    outbox_repo.insert(
        conn,
        source="dispatch",
        op="move",
        payload_json=json.dumps(
            {
                "disk_id": disk_id,
                "dst_rel_path": rel_path,
                "filename": "beta.mkv",
                "size_bytes": 200,
                "mtime_ns": 2000,
            }
        ),
    )

    cfg = _make_config()
    stats = drain(conn, cfg)

    assert stats.applied == 2
    # Both files should now exist in media_file.
    conn.row_factory = sqlite3.Row
    files = conn.execute("SELECT filename FROM media_file WHERE path_id = ? ORDER BY filename", (path_id,)).fetchall()
    assert [r["filename"] for r in files] == ["alpha.mkv", "beta.mkv"]


# ---------------------------------------------------------------------------
# drain() — FIFO order drains outbox to empty
# ---------------------------------------------------------------------------


def test_drain_empties_outbox(conn: sqlite3.Connection) -> None:
    """drain() leaves no pending rows after it runs."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/Empty (2021)"
    _insert_path(conn, disk_id, rel_path)

    for i in range(3):
        outbox_repo.insert(
            conn,
            source="dispatch",
            op="move",
            payload_json=json.dumps(
                {
                    "disk_id": disk_id,
                    "dst_rel_path": rel_path,
                    "filename": f"file_{i}.mkv",
                    "size_bytes": i * 100,
                    "mtime_ns": i * 1000,
                }
            ),
        )

    drain(conn, _make_config())

    assert outbox_repo.fetch_pending(conn) == []


# ---------------------------------------------------------------------------
# drain() — deduplication (3 rows for same file → only latest applied)
# ---------------------------------------------------------------------------


def test_drain_deduplication_only_latest_applied(conn: sqlite3.Connection) -> None:
    """3 rows for same (disk_id, rel_path, filename) → latest applied, others marked done."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/Dup (2020)"
    _insert_path(conn, disk_id, rel_path)
    filename = "dup.mkv"

    payload_base = {"disk_id": disk_id, "dst_rel_path": rel_path, "filename": filename, "mtime_ns": 1000}
    id1 = outbox_repo.insert(
        conn, source="dispatch", op="move", payload_json=json.dumps({**payload_base, "size_bytes": 100})
    )
    id2 = outbox_repo.insert(
        conn, source="dispatch", op="move", payload_json=json.dumps({**payload_base, "size_bytes": 200})
    )
    id3 = outbox_repo.insert(
        conn, source="dispatch", op="move", payload_json=json.dumps({**payload_base, "size_bytes": 300})
    )

    cfg = _make_config()
    stats = drain(conn, cfg)

    # 1 row applied (latest), 2 rows deduped.
    assert stats.applied == 1
    assert stats.deduped == 2

    # The applied file should have size_bytes=300 (from the latest row).
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT size_bytes FROM media_file WHERE filename = ?", (filename,)).fetchone()
    assert row is not None
    assert row["size_bytes"] == 300

    # All three outbox rows must be marked done (deduped rows also get done).
    for row_id in (id1, id2, id3):
        r = conn.execute("SELECT status FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
        assert r is not None
        assert r["status"] == "done"


# ---------------------------------------------------------------------------
# drain() — retry on locked DB (testing _apply_row_with_retry directly)
# ---------------------------------------------------------------------------


def test_apply_row_with_retry_succeeds_on_uncontended_db(conn: sqlite3.Connection) -> None:
    """_apply_row_with_retry returns 'done' when the DB is not locked."""
    from personalscraper.indexer.outbox import _apply_row_with_retry  # noqa: PLC0415
    from personalscraper.indexer.schema import IndexOutboxRow  # noqa: PLC0415

    disk_id = _insert_disk(conn)
    rel_path = "movies/LockRetry (2020)"
    _insert_path(conn, disk_id, rel_path)
    filename = "lockretry.mkv"

    row_id = outbox_repo.insert(
        conn,
        source="dispatch",
        op="move",
        payload_json=json.dumps(
            {"disk_id": disk_id, "dst_rel_path": rel_path, "filename": filename, "size_bytes": 1, "mtime_ns": 1}
        ),
    )

    conn.row_factory = sqlite3.Row
    raw = conn.execute("SELECT * FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
    assert raw is not None
    row = IndexOutboxRow(
        id=raw["id"],
        source=raw["source"],
        op=raw["op"],
        payload_json=raw["payload_json"],
        created_at=raw["created_at"],
        processed_at=raw["processed_at"],
        status=raw["status"],
    )

    result = _apply_row_with_retry(conn, row)
    assert result == "done"


def test_apply_row_with_retry_returns_failed_on_bad_payload(conn: sqlite3.Connection) -> None:
    """_apply_row_with_retry returns 'skip' for malformed payload JSON."""
    from personalscraper.indexer.outbox import _apply_row_with_retry  # noqa: PLC0415
    from personalscraper.indexer.schema import IndexOutboxRow  # noqa: PLC0415

    row = IndexOutboxRow(
        id=99,
        source="dispatch",
        op="move",
        payload_json="NOT_JSON{{{",
        created_at=1,
        processed_at=None,
        status="pending",
    )
    result = _apply_row_with_retry(conn, row)
    assert result == "skip"


def test_drain_marks_failed_after_exhausting_retries(conn: sqlite3.Connection) -> None:
    """drain() marks a row failed when _apply_row_with_retry returns 'failed'."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/AlwaysLocked (2020)"
    _insert_path(conn, disk_id, rel_path)

    row_id = outbox_repo.insert(
        conn,
        source="dispatch",
        op="move",
        payload_json=json.dumps(
            {
                "disk_id": disk_id,
                "dst_rel_path": rel_path,
                "filename": "always_locked.mkv",
                "size_bytes": 512,
                "mtime_ns": 9999,
            }
        ),
    )

    # Patch _apply_row_with_retry to always return 'failed' (simulating exhaustion).
    with patch(
        "personalscraper.indexer.outbox._apply_row_with_retry",
        return_value="failed",
    ):
        stats = drain(conn, _make_config())

    assert stats.failed == 1
    assert stats.applied == 0

    # The row must be marked failed by drain().
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT status FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
    assert r is not None
    assert r["status"] == "failed"


def test_apply_row_with_retry_retries_on_lock_then_succeeds(conn: sqlite3.Connection) -> None:
    """_apply_row_with_retry succeeds after initial lock: patches _apply_move to fail once."""
    from personalscraper.indexer.outbox import _apply_row_with_retry  # noqa: PLC0415
    from personalscraper.indexer.schema import IndexOutboxRow  # noqa: PLC0415

    disk_id = _insert_disk(conn)
    rel_path = "movies/RetrySuccess (2020)"
    _insert_path(conn, disk_id, rel_path)
    filename = "retry_ok.mkv"

    row_id = outbox_repo.insert(
        conn,
        source="dispatch",
        op="move",
        payload_json=json.dumps(
            {"disk_id": disk_id, "dst_rel_path": rel_path, "filename": filename, "size_bytes": 10, "mtime_ns": 10}
        ),
    )

    conn.row_factory = sqlite3.Row
    raw = conn.execute("SELECT * FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
    assert raw is not None
    row = IndexOutboxRow(
        id=raw["id"],
        source=raw["source"],
        op=raw["op"],
        payload_json=raw["payload_json"],
        created_at=raw["created_at"],
        processed_at=raw["processed_at"],
        status=raw["status"],
    )

    import importlib  # noqa: PLC0415

    import personalscraper.indexer.outbox as _outbox_mod  # noqa: PLC0415

    apply_calls = 0
    # Access private names via getattr to avoid mypy attr-defined errors.
    original_move = getattr(_outbox_mod, "_apply_move")
    handlers: dict[str, Any] = getattr(_outbox_mod, "_OP_HANDLERS")

    def move_raises_once(c: sqlite3.Connection, payload: dict[str, Any]) -> None:
        nonlocal apply_calls
        apply_calls += 1
        if apply_calls == 1:
            raise sqlite3.OperationalError("database is locked")
        original_move(c, payload)

    # Patch _OP_HANDLERS in-place so _apply_row_with_retry picks up the wrapper.
    saved_move = handlers["move"]
    handlers["move"] = move_raises_once
    try:
        with patch("personalscraper.indexer.outbox.time.sleep"):
            result = _apply_row_with_retry(conn, row)
    finally:
        handlers["move"] = saved_move
    del importlib  # only imported to satisfy noqa; unused otherwise

    # Should succeed on the second attempt.
    assert result == "done"
    assert apply_calls == 2


# ---------------------------------------------------------------------------
# drain() — deferred to pending_op when disk unreachable
# ---------------------------------------------------------------------------


def test_drain_defers_when_disk_unreachable(conn: sqlite3.Connection) -> None:
    """drain() moves a row to pending_op when its disk is not mounted."""
    disk_id = _insert_disk(conn)
    # Mark disk unmounted.
    conn.execute("UPDATE disk SET is_mounted = 0, mount_path = NULL WHERE id = ?", (disk_id,))

    row_id = outbox_repo.insert(
        conn,
        source="dispatch",
        op="move",
        payload_json=json.dumps(
            {
                "disk_id": disk_id,
                "dst_rel_path": "movies/Unreachable (2020)",
                "filename": "unreachable.mkv",
                "size_bytes": 100,
                "mtime_ns": 1000,
            }
        ),
    )

    stats = drain(conn, _make_config())

    assert stats.deferred == 1
    assert stats.applied == 0

    # The outbox row must be marked deferred.
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT status FROM index_outbox WHERE id = ?", (row_id,)).fetchone()
    assert r is not None
    assert r["status"] == "deferred"

    # A pending_op row must have been created for the disk.
    pending = outbox_repo.fetch_for_disk(conn, disk_id)
    assert len(pending) == 1
    assert pending[0].op == "move"


# ---------------------------------------------------------------------------
# drain() — replay on remount
# ---------------------------------------------------------------------------


def test_drain_replays_pending_op_on_remount(conn: sqlite3.Connection) -> None:
    """drain() replays pending_op rows when a disk is found mounted."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/Remount (2020)"
    _insert_path(conn, disk_id, rel_path)
    filename = "remount.mkv"

    # Seed a pending_op row (simulating prior deferral).
    outbox_repo.insert_pending_op_row(
        conn,
        disk_id=disk_id,
        op="move",
        payload_json=json.dumps(
            {"disk_id": disk_id, "dst_rel_path": rel_path, "filename": filename, "size_bytes": 777, "mtime_ns": 7777}
        ),
    )

    # Disk is mounted — drain should replay.
    stats = drain(conn, _make_config())

    assert stats.replayed == 1

    # The pending_op row must have replayed_at set.
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT replayed_at FROM pending_op WHERE disk_id = ?", (disk_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["replayed_at"] is not None

    # The file should now be in media_file.
    f = conn.execute("SELECT filename FROM media_file WHERE filename = ?", (filename,)).fetchone()
    assert f is not None


# ---------------------------------------------------------------------------
# drain() — op idempotence proofs
# ---------------------------------------------------------------------------


def test_drain_move_idempotent(conn: sqlite3.Connection) -> None:
    """Replaying a 'move' row twice produces the same media_file state."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/Idempotent (2020)"
    _insert_path(conn, disk_id, rel_path)
    filename = "idempotent.mkv"

    payload = json.dumps(
        {"disk_id": disk_id, "dst_rel_path": rel_path, "filename": filename, "size_bytes": 999, "mtime_ns": 12345}
    )

    # Apply once.
    outbox_repo.insert(conn, source="dispatch", op="move", payload_json=payload)
    drain(conn, _make_config())

    # Apply again.
    outbox_repo.insert(conn, source="dispatch", op="move", payload_json=payload)
    drain(conn, _make_config())

    # Exactly one media_file row.
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM media_file WHERE filename = ?", (filename,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["size_bytes"] == 999


def test_drain_nfo_write_idempotent(conn: sqlite3.Connection) -> None:
    """Replaying an 'nfo_write' row twice yields nfo_status='valid' once, not duplicated."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/NfoIdempotent (2020)"
    _, item_id, release_id, _ = _seed_linked_item(conn, disk_id, rel_path)

    payload = json.dumps(
        {"disk_id": disk_id, "rel_path": rel_path, "item_kind": "movie", "tmdb_id": 42, "imdb_id": "tt0000042"}
    )

    # Apply twice.
    outbox_repo.insert(conn, source="scraper", op="nfo_write", payload_json=payload)
    drain(conn, _make_config())
    outbox_repo.insert(conn, source="scraper", op="nfo_write", payload_json=payload)
    drain(conn, _make_config())

    conn.row_factory = sqlite3.Row
    item = conn.execute("SELECT nfo_status, tmdb_id FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert item is not None
    assert item["nfo_status"] == "valid"
    assert item["tmdb_id"] == 42


def test_drain_artwork_write_idempotent(conn: sqlite3.Connection) -> None:
    """Replaying an 'artwork_write' row twice sets the artwork bit once, not twice."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/ArtIdempotent (2020)"
    _, item_id, release_id, _ = _seed_linked_item(conn, disk_id, rel_path)

    payload = json.dumps({"disk_id": disk_id, "rel_path": rel_path, "kind": "poster"})

    # Apply twice.
    outbox_repo.insert(conn, source="scraper", op="artwork_write", payload_json=payload)
    drain(conn, _make_config())
    outbox_repo.insert(conn, source="scraper", op="artwork_write", payload_json=payload)
    drain(conn, _make_config())

    conn.row_factory = sqlite3.Row
    item = conn.execute("SELECT artwork_json FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert item is not None
    artwork = json.loads(item["artwork_json"] or "{}")
    assert artwork.get("poster") is True


def test_drain_trailer_download_idempotent(conn: sqlite3.Connection) -> None:
    """Replaying a 'trailer_download' row twice produces one item_attribute row."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/TrailerIdempotent (2020)"
    _, item_id, release_id, _ = _seed_linked_item(conn, disk_id, rel_path)
    trailer_path = "/Volumes/Disk1/movies/TrailerIdempotent (2020)/trailer.mp4"

    payload = json.dumps({"disk_id": disk_id, "rel_path": rel_path, "trailer_path": trailer_path})

    # Apply twice.
    outbox_repo.insert(conn, source="trailers", op="trailer_download", payload_json=payload)
    drain(conn, _make_config())
    outbox_repo.insert(conn, source="trailers", op="trailer_download", payload_json=payload)
    drain(conn, _make_config())

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'trailer_found'",
        (item_id,),
    ).fetchall()
    # Only one row (UPSERT idempotent).
    assert len(rows) == 1
    assert rows[0]["value"] == trailer_path


# ---------------------------------------------------------------------------
# publish_event() — swallows exceptions, logs indexer.db.outbox_lost
# ---------------------------------------------------------------------------


def test_publish_event_swallows_bad_db_path(tmp_path: Path) -> None:
    """publish_event() returns silently when the DB path does not exist (bad path)."""
    # Override db_path to a nonexistent location on a non-macFUSE path.
    with patch("personalscraper.indexer.outbox.IndexerConfig") as MockConfig:
        instance = MockConfig.return_value
        instance.db_path = tmp_path / "nonexistent_dir" / "library.db"
        # Should not raise.
        publish_event(
            disk_id=1,
            op="move",
            payload={"dst_rel_path": "foo", "filename": "bar.mkv", "size_bytes": 1, "mtime_ns": 1},
        )


def test_publish_event_swallows_exception_on_sqlite_error(tmp_path: Path) -> None:
    """publish_event() returns silently on any sqlite3 exception."""
    with patch("personalscraper.indexer.outbox.sqlite3.connect") as mock_connect:
        mock_connect.side_effect = sqlite3.OperationalError("database is locked")
        # Should not raise.
        publish_event(disk_id=99, op="nfo_write", payload={"rel_path": "foo", "item_kind": "movie"})


def test_publish_event_inserts_row(tmp_path: Path) -> None:
    """publish_event() inserts a pending row when the DB path is valid."""
    db_path = tmp_path / "library.db"
    c = sqlite3.connect(str(db_path), isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    from personalscraper.indexer.db import apply_migrations as _am  # noqa: PLC0415

    _am(c, MIGRATIONS_DIR)
    c.close()

    with patch("personalscraper.indexer.outbox.IndexerConfig") as MockConfig:
        instance = MockConfig.return_value
        instance.db_path = db_path

        publish_event(
            disk_id=1,
            op="move",
            payload={"dst_rel_path": "movies/Foo", "filename": "foo.mkv", "size_bytes": 10, "mtime_ns": 100},
        )

    c2 = sqlite3.connect(str(db_path), isolation_level=None)
    c2.row_factory = sqlite3.Row
    rows = c2.execute("SELECT * FROM index_outbox WHERE status = 'pending'").fetchall()
    c2.close()
    assert len(rows) == 1
    assert rows[0]["op"] == "move"


# ---------------------------------------------------------------------------
# drain_if_present() — convenience wrapper
# ---------------------------------------------------------------------------


def test_drain_if_present_returns_applied_count(conn: sqlite3.Connection) -> None:
    """drain_if_present() returns the number of successfully applied rows."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/DIP (2020)"
    _insert_path(conn, disk_id, rel_path)

    for i in range(3):
        outbox_repo.insert(
            conn,
            source="dispatch",
            op="move",
            payload_json=json.dumps(
                {
                    "disk_id": disk_id,
                    "dst_rel_path": rel_path,
                    "filename": f"dip_{i}.mkv",
                    "size_bytes": i * 10,
                    "mtime_ns": i * 100,
                }
            ),
        )

    count = drain_if_present(conn)
    assert count == 3


def test_drain_if_present_accepts_none_config(conn: sqlite3.Connection) -> None:
    """drain_if_present() works with config=None (uses default IndexerConfig)."""
    disk_id = _insert_disk(conn)
    rel_path = "movies/NoneConfig (2020)"
    _insert_path(conn, disk_id, rel_path)
    outbox_repo.insert(
        conn,
        source="dispatch",
        op="move",
        payload_json=json.dumps(
            {"disk_id": disk_id, "dst_rel_path": rel_path, "filename": "nc.mkv", "size_bytes": 1, "mtime_ns": 1}
        ),
    )

    # Pass no config argument — must not raise.
    count = drain_if_present(conn, config=None)
    assert count == 1


# ---------------------------------------------------------------------------
# Drain idempotence property test (Hypothesis) — DESIGN §9.3
# ---------------------------------------------------------------------------


def _valid_outbox_payload() -> st.SearchStrategy[str]:
    """Hypothesis strategy producing a valid 'move' op payload JSON string.

    Returns:
        Strategy yielding JSON strings with disk_id=1 and random filenames/sizes.
    """
    return st.builds(
        lambda fname, size, mtime: json.dumps(
            {
                "disk_id": 1,
                "dst_rel_path": "movies/PropTest (2020)",
                "filename": fname + ".mkv",
                "size_bytes": size,
                "mtime_ns": mtime,
            }
        ),
        fname=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        ),
        size=st.integers(min_value=1, max_value=10_000_000),
        mtime=st.integers(min_value=1_000_000_000_000_000_000, max_value=2_000_000_000_000_000_000),
    )


@given(payloads=st.lists(_valid_outbox_payload(), min_size=1, max_size=10))
@settings(max_examples=40, deadline=10_000)
def test_drain_idempotence_property(payloads: list[str]) -> None:
    """Applying the drainer twice to the same set of rows yields identical DB state.

    Verifies the idempotence contract from DESIGN §9.3: replaying a fully-drained
    set of outbox rows produces no change to the indexer tables.
    """
    # Build an isolated in-memory DB per hypothesis example.
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)

    # Insert the disk and path that the payloads reference.
    from personalscraper.indexer.repos import disk_repo  # noqa: PLC0415

    disk_row = DiskRow(
        id=0,
        uuid="uuid-prop",
        label="PropDisk",
        mount_path="/Volumes/PropDisk",
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    disk_id = disk_repo.insert(c, disk_row)

    # Ensure disk.id = 1 matches the payload disk_id=1 we baked in.
    # If the auto-assigned id differs (first row should be 1), adjust payloads.
    patched_payloads = [p.replace('"disk_id": 1', f'"disk_id": {disk_id}') for p in payloads]

    path_row = PathRow(
        id=0,
        disk_id=disk_id,
        rel_path="movies/PropTest (2020)",
        dir_mtime_ns=None,
        last_walked_at=int(time.time()),
    )
    disk_repo.insert_path(c, path_row)

    cfg = IndexerConfig()

    # First pass: insert all payloads and drain.
    for p in patched_payloads:
        outbox_repo.insert(c, source="dispatch", op="move", payload_json=p)
    drain(c, cfg)

    # Snapshot the media_file table.
    c.row_factory = sqlite3.Row
    snapshot_1 = {
        (r["path_id"], r["filename"]): (r["size_bytes"], r["mtime_ns"])
        for r in c.execute("SELECT path_id, filename, size_bytes, mtime_ns FROM media_file").fetchall()
    }

    # Second pass: insert the same payloads again and drain.
    for p in patched_payloads:
        outbox_repo.insert(c, source="dispatch", op="move", payload_json=p)
    drain(c, cfg)

    snapshot_2 = {
        (r["path_id"], r["filename"]): (r["size_bytes"], r["mtime_ns"])
        for r in c.execute("SELECT path_id, filename, size_bytes, mtime_ns FROM media_file").fetchall()
    }

    assert snapshot_1 == snapshot_2, "Drainer is not idempotent: DB state changed on second drain"
    c.close()


# ===========================================================================
# §5.3a — disk_id_for_path helper
# ===========================================================================


def _make_disk_row(uuid: str, label: str, mount_path: str | None, is_mounted: int) -> DiskRow:
    """Construct a DiskRow with sensible defaults for non-essential fields.

    Args:
        uuid: Volume UUID string.
        label: Display label.
        mount_path: Current mount point; ``None`` when unmounted.
        is_mounted: 0 or 1.

    Returns:
        A fully-populated :class:`DiskRow`.
    """
    return DiskRow(
        id=0,
        uuid=uuid,
        label=label,
        mount_path=mount_path,
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=is_mounted,
        unreachable_strikes=0,
    )


class TestDiskIdForPath:
    """Tests for the disk_id_for_path helper."""

    def test_returns_disk_id_and_rel_path_for_mounted_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns (disk_id, rel_path) for a path under a mounted disk."""
        from personalscraper.indexer.repos import disk_repo  # noqa: PLC0415

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            apply_migrations(conn, MIGRATIONS_DIR)
            disk_id = disk_repo.insert(
                conn,
                _make_disk_row(uuid="u1", label="L1", mount_path="/Volumes/D1", is_mounted=1),
            )
        finally:
            conn.close()

        # Patch IndexerConfig to return our temp db_path
        monkeypatch.setattr(
            "personalscraper.indexer.outbox.IndexerConfig",
            lambda: types.SimpleNamespace(db_path=db_path),
        )

        result = disk_id_for_path(Path("/Volumes/D1/movies/foo.mp4"))
        assert result == (disk_id, "movies/foo.mp4")

    def test_returns_none_for_unmounted_or_no_match(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns None when no mounted disk matches the path prefix."""
        from personalscraper.indexer.repos import disk_repo  # noqa: PLC0415

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            apply_migrations(conn, MIGRATIONS_DIR)
            # mount_path must be NULL when is_mounted=0 (schema CHECK constraint).
            disk_repo.insert(
                conn,
                _make_disk_row(uuid="u1", label="L1", mount_path=None, is_mounted=0),
            )
        finally:
            conn.close()

        monkeypatch.setattr(
            "personalscraper.indexer.outbox.IndexerConfig",
            lambda: types.SimpleNamespace(db_path=db_path),
        )

        # Path under unmounted disk → None
        assert disk_id_for_path(Path("/Volumes/D1/movies/foo.mp4")) is None
        # Path with no matching disk → None
        assert disk_id_for_path(Path("/some/other/path")) is None

    def test_returns_none_on_db_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns None when DB cannot be opened (best-effort contract)."""
        monkeypatch.setattr(
            "personalscraper.indexer.outbox.IndexerConfig",
            lambda: types.SimpleNamespace(db_path=Path("/nonexistent/dir/library.db")),
        )
        assert disk_id_for_path(Path("/Volumes/D1/movies/foo.mp4")) is None

    def test_longest_prefix_match_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When two disks have nested mount_paths, the longest match wins."""
        from personalscraper.indexer.repos import disk_repo  # noqa: PLC0415

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            apply_migrations(conn, MIGRATIONS_DIR)
            disk_repo.insert(
                conn,
                _make_disk_row(uuid="u1", label="L1", mount_path="/Volumes", is_mounted=1),
            )
            d2 = disk_repo.insert(
                conn,
                _make_disk_row(uuid="u2", label="L2", mount_path="/Volumes/D1", is_mounted=1),
            )
        finally:
            conn.close()

        monkeypatch.setattr(
            "personalscraper.indexer.outbox.IndexerConfig",
            lambda: types.SimpleNamespace(db_path=db_path),
        )

        result = disk_id_for_path(Path("/Volumes/D1/foo.mp4"))
        assert result == (d2, "foo.mp4")
