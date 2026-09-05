"""A committed checkpoint must not claim files whose rows are still in memory.

Full mode is the only mode that batches: ``FullVisitor`` passes an
``insert_buffer`` unconditionally, so ``_upsert_file_row`` appends every file it
walks — new or already known — to a Python list instead of writing it. The list
was flushed exactly once, after the whole walk returned.

Meanwhile ``_checkpoint_scan_run`` writes ``scan_run.last_path`` and **commits**
every ``checkpoint_every_n_files`` files (100 in production). So the database
durably recorded "walked as far as X" while none of the rows for those files had
been written. A hard kill loses the buffer, and the next run's
``_check_crash_resume`` returns that ``last_path``: the walker then skips every
file at or before it (``_walker.py``, the crash-resume skip), so those files are
neither indexed nor re-walked. Rows that already existed for them go unvisited
instead, which is what feeds ``mark_missed_files``.

A graceful stop — budget exhausted or SIGTERM — returns through ``walk()`` and
does reach the trailing flush, so only a hard kill (SIGKILL, OOM, power loss)
loses rows. On a machine that has run out of memory, the 37 MB the buffer
retained for this library was part of that risk rather than separate from it.

``_INSERT_BATCH_SIZE`` was declared for exactly this and read nowhere; both
docstrings claimed the caller flushed "when it reaches" it.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._checkpoint import _maybe_checkpoint
from personalscraper.indexer.scanner._db_writes import _INSERT_BATCH_SIZE, _upsert_file_row

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


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


class TestCheckpointFlushesFirst:
    """A checkpoint commits a claim about progress; the rows must back it."""

    def test_the_hook_runs_when_a_checkpoint_is_written(self) -> None:
        """The flush happens before the position is committed, not after."""
        conn = _make_conn()
        conn.execute(
            "INSERT INTO scan_run (generation, mode, started_at, status) VALUES (1, 'full', ?, 'running')",
            (int(time.time()),),
        )
        scan_run_id = int(conn.execute("SELECT id FROM scan_run").fetchone()[0])
        observed: list[Any] = []

        def _flush() -> None:
            """Read the position the hook can still see, which must be the old one."""
            observed.append(conn.execute("SELECT last_path FROM scan_run WHERE id = ?", (scan_run_id,)).fetchone()[0])

        _maybe_checkpoint(conn, scan_run_id, "BatchDisk/films/x.mkv", 100, 100, 0.0, None, before_commit=_flush)

        assert observed == [None], "the hook must run while the OLD position still stands"
        written = conn.execute("SELECT last_path FROM scan_run WHERE id = ?", (scan_run_id,)).fetchone()[0]
        assert written == "BatchDisk/films/x.mkv", "and the new position is committed after it"

    def test_the_hook_does_not_run_between_checkpoints(self) -> None:
        """Flushing on every file would defeat the batch entirely."""
        calls: list[str] = []
        conn = _make_conn()
        _maybe_checkpoint(conn, 1, "BatchDisk/films/x.mkv", 3, 100, 0.0, None, before_commit=calls.append)
        assert calls == []

    def test_no_hook_is_still_a_valid_call(self) -> None:
        """Modes that buffer nothing pass nothing, and must not break."""
        conn = _make_conn()
        conn.execute(
            "INSERT INTO scan_run (generation, mode, started_at, status) VALUES (1, 'quick', ?, 'running')",
            (int(time.time()),),
        )
        scan_run_id = int(conn.execute("SELECT id FROM scan_run").fetchone()[0])
        counter, exhausted = _maybe_checkpoint(conn, scan_run_id, "BatchDisk/films/x.mkv", 100, 100, 0.0, None)
        assert (counter, exhausted) == (0, False)
