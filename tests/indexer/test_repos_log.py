"""Repo-specific tests for log_repo: scan_run lifecycle, scan_event, deleted_item.

Covers:
- insert_scan_run returns a positive rowid
- update_scan_run_status transitions status and sets finished_at
- insert_scan_event linked to a scan_run, with payload validated
- insert_deleted_item tombstone record
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Literal

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import log_repo
from personalscraper.indexer.schema import DeletedItemRow, ScanEventRow, ScanRunRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


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


def _make_scan_run(
    generation: int = 1,
    status: Literal["running", "ok", "failed", "aborted"] = "running",
) -> ScanRunRow:
    """Return a minimal ScanRunRow ready for insertion.

    Args:
        generation: Monotonically increasing scan generation number.
        status: Initial status string.

    Returns:
        Populated :class:`ScanRunRow` with ``id=0`` (auto-assigned on insert).
    """
    return ScanRunRow(
        id=0,
        generation=generation,
        mode="quick",
        disk_filter=None,
        started_at=int(time.time()),
        finished_at=None,
        last_path=None,
        status=status,
        stats_json=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_insert_scan_run_returns_id(conn: sqlite3.Connection) -> None:
    """insert_scan_run returns a positive integer rowid on success."""
    rowid = log_repo.insert_scan_run(conn, _make_scan_run())
    assert isinstance(rowid, int)
    assert rowid > 0


def test_update_scan_run_status(conn: sqlite3.Connection) -> None:
    """update_scan_run_status transitions status and stores finished_at."""
    run_id = log_repo.insert_scan_run(conn, _make_scan_run(status="running"))

    # Sanity: row exists with status 'running'.
    row = log_repo.get_scan_run_by_id(conn, run_id)
    assert row is not None
    assert row.status == "running"
    assert row.finished_at is None

    finished = int(time.time())
    updated = log_repo.update_scan_run_status(
        conn,
        run_id,
        status="ok",
        finished_at=finished,
    )
    assert updated is True

    row = log_repo.get_scan_run_by_id(conn, run_id)
    assert row is not None
    assert row.status == "ok"
    assert row.finished_at == finished


def test_update_scan_run_status_returns_false_for_nonexistent_id(conn: sqlite3.Connection) -> None:
    """update_scan_run_status returns False when no row matches the id."""
    result = log_repo.update_scan_run_status(conn, 9999, status="completed")
    assert result is False


def test_insert_scan_event(conn: sqlite3.Connection) -> None:
    """insert_scan_event creates a row linked to an existing scan_run.

    The payload_json is stored verbatim and round-trips without corruption.
    """
    run_id = log_repo.insert_scan_run(conn, _make_scan_run())

    payload = '{"path": "/Volumes/Disk1/001-MOVIES", "files_seen": 42}'
    event = ScanEventRow(
        id=0,
        scan_id=run_id,
        ts=int(time.time()),
        item_id=None,
        file_id=None,
        event="indexer.scan.checkpoint",
        payload_json=payload,
    )
    rowid = log_repo.insert_scan_event(conn, event)
    assert isinstance(rowid, int)
    assert rowid > 0

    # Verify round-trip: fetch back and check payload.
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM scan_event WHERE id = ?", (rowid,)).fetchone()
    assert row is not None
    assert row["scan_id"] == run_id
    assert row["event"] == "indexer.scan.checkpoint"
    assert row["payload_json"] == payload
    assert row["item_id"] is None
    assert row["file_id"] is None


def test_insert_scan_event_enforces_fk(conn: sqlite3.Connection) -> None:
    """insert_scan_event raises IntegrityError when scan_id does not exist."""
    bad_event = ScanEventRow(
        id=0,
        scan_id=99999,
        ts=int(time.time()),
        item_id=None,
        file_id=None,
        event="indexer.scan.checkpoint",
        payload_json=None,
    )
    with pytest.raises(sqlite3.IntegrityError):
        log_repo.insert_scan_event(conn, bad_event)


def test_insert_deleted_item(conn: sqlite3.Connection) -> None:
    """insert_deleted_item creates a tombstone row and returns a positive rowid."""
    snapshot = '{"kind": "item", "snapshot": {"id": 7, "title": "Inception"}}'
    tombstone = DeletedItemRow(
        id=0,
        kind="item",
        original_id=7,
        deleted_at=int(time.time()),
        reason="duplicate replaced by higher-quality release",
        payload_json=snapshot,
    )
    rowid = log_repo.insert_deleted_item(conn, tombstone)
    assert isinstance(rowid, int)
    assert rowid > 0

    # Verify round-trip.
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM deleted_item WHERE id = ?", (rowid,)).fetchone()
    assert row is not None
    assert row["kind"] == "item"
    assert row["original_id"] == 7
    assert row["reason"] == "duplicate replaced by higher-quality release"
    assert row["payload_json"] == snapshot
