"""The full-scan insert buffer must stop growing without bound.

Full mode is the only mode that batches: ``FullVisitor`` passes an
``insert_buffer`` unconditionally, so ``_upsert_file_row`` appends every file it
walks — new or already known — to a Python list instead of writing it. The list
was flushed exactly once, after the whole walk returned, which for this library
meant 98 506 rows and 37.2 MB retained until then.

``_INSERT_BATCH_SIZE`` was declared for exactly this and read nowhere; two
docstrings claimed the caller flushed "when it reaches" it, and no caller did.

The flush does not commit, so what it writes stays inside the per-disk
transaction that DESIGN §15.5 rolls back when a disk raises ``EIO`` mid-walk.
That is deliberate and it is the whole shape of this repair. A checkpoint,
which DOES commit, would be the honest place to drain the buffer — it publishes
a ``last_path`` that a resumed scan skips past, and today that position can name
files whose rows are still in memory. But draining there makes those rows
survive the EIO rollback, and ``test_indexer_unplug_during_scan.py`` refuses
exactly that. The two guarantees are in tension; the ceiling improves the
window by 20x without touching either.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner._db_writes import _INSERT_BATCH_SIZE, _upsert_file_row
from personalscraper.indexer.schema import DiskRow, ScanRunRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _insert_disk(conn: sqlite3.Connection, mount_path: str) -> DiskRow:
    """Insert a disk rooted at *mount_path* and return the stored row."""
    row = DiskRow(
        id=0,
        uuid="uuid-wiring",
        label="WiringDisk",
        mount_path=mount_path,
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    disk_id = disk_repo.insert(conn, row)
    return DiskRow(
        id=disk_id,
        uuid=row.uuid,
        label=row.label,
        mount_path=row.mount_path,
        last_seen_at=row.last_seen_at,
        merkle_root=row.merkle_root,
        is_mounted=row.is_mounted,
        unreachable_strikes=row.unreachable_strikes,
    )


def _insert_scan_run(conn: sqlite3.Connection) -> int:
    """Insert a running full-mode scan_run row and return its PK."""
    return log_repo.insert_scan_run(
        conn,
        ScanRunRow(
            id=0,
            generation=1,
            mode="full",
            disk_filter=None,
            started_at=int(time.time()),
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        ),
    )


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _seed_path(conn: sqlite3.Connection) -> int:
    """Insert a disk and a path row; return the path id."""
    now = int(time.time())
    disk_id: int = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES ('uuid-batch', 'BatchDisk', '/mnt/batch', ?, 1, 0)",
        (now,),
    ).lastrowid  # type: ignore[assignment]
    return conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, 'films/Movie (2020)')",
        (disk_id,),
    ).lastrowid  # type: ignore[assignment]


def _append_files(conn: sqlite3.Connection, path_id: int, buffer: list[Any], count: int) -> None:
    """Walk *count* files into *buffer*, exactly as FullVisitor does."""
    for index in range(count):
        _upsert_file_row(
            conn,
            path_id=path_id,
            filename=f"Movie - S01E{index:03d}.mkv",
            size_bytes=1024,
            mtime_ns=1_700_000_000_000_000_000,
            ctime_ns=None,
            generation=1,
            oshash_value=None,
            insert_buffer=buffer,
        )


def _rows_written(conn: sqlite3.Connection) -> int:
    """Return how many media_file rows the database actually holds."""
    return int(conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0])


class TestInsertBatchCeiling:
    """The buffer stops growing without bound, which is what the constant declared."""

    def test_the_buffer_flushes_when_it_reaches_the_batch_size(self) -> None:
        """The defect: _INSERT_BATCH_SIZE was read nowhere and bounded nothing."""
        conn = _make_conn()
        path_id = _seed_path(conn)
        buffer: list[Any] = []

        _append_files(conn, path_id, buffer, _INSERT_BATCH_SIZE)

        assert buffer == [], "reaching the batch size must drain the buffer"
        assert _rows_written(conn) == _INSERT_BATCH_SIZE

    def test_a_partial_batch_stays_buffered(self) -> None:
        """Below the ceiling nothing is written — the trailing flush still owns it."""
        conn = _make_conn()
        path_id = _seed_path(conn)
        buffer: list[Any] = []

        _append_files(conn, path_id, buffer, 10)

        assert len(buffer) == 10
        assert _rows_written(conn) == 0
