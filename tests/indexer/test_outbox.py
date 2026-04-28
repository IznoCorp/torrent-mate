"""Tests for outbox_repo plan §5.1 — OutboxRepo and PendingOpRepo public APIs.

Covers:
- insert / fetch_pending round-trip for index_outbox
- mark_done / mark_failed / mark_deferred status transitions
- insert_pending_op_row / fetch_for_disk round-trip
- mark_replayed sets replayed_at
- purge_expired deletes rows older than TTL and returns correct count
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import outbox_repo
from personalscraper.indexer.schema import DiskRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


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
