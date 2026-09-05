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
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner._checkpoint import _maybe_checkpoint
from personalscraper.indexer.scanner._db_writes import _INSERT_BATCH_SIZE, _upsert_file_row
from personalscraper.indexer.scanner._modes.full import FullVisitor
from personalscraper.indexer.scanner._walker import WalkBudget, WalkCheckpoint, walk
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


class TestTheWalkerDrivesTheFlush:
    """The hook has to be WIRED, which testing _maybe_checkpoint alone never shows.

    The first version of these tests passed ``before_commit`` by hand, so
    removing the walker's own ``before_commit=visitor.flush_pending`` left every
    one of them green. This class drives a real :func:`walk` and reads the
    database, which is the only thing that can tell the wiring apart.
    """

    def test_rows_reach_the_database_before_the_walk_returns(self, tmp_path: Path) -> None:
        """A checkpoint mid-walk must leave written rows behind it, not a buffer."""
        conn = _make_conn()
        disk = _insert_disk(conn, str(tmp_path))
        scan_run_id = _insert_scan_run(conn)
        for index in range(6):
            (tmp_path / f"Movie {index}.mkv").write_bytes(b"\0" * 16)

        visitor = FullVisitor(conn, disk, generation=1, files_visited=[0], dirs_visited=[0])
        walk(
            str(tmp_path),
            visitor,
            budget=WalkBudget(budget_seconds=None, started_at_monotonic=time.monotonic(), budget_exhausted=[False]),
            shutdown=lambda: False,
            checkpoint=WalkCheckpoint(
                scan_run_id=scan_run_id,
                checkpoint_every=2,
                files_since_checkpoint=[0],
                resume_from=[None],
            ),
        )

        # walk() has returned but the caller's trailing flush has NOT run. Every
        # file covered by a checkpoint must already be in the database.
        assert _rows_written(conn) == 6, "the checkpoints must have drained the buffer as they went"
        assert visitor.insert_buffer == []

    def test_the_committed_position_never_outruns_the_written_rows(self, tmp_path: Path) -> None:
        """The defect itself: last_path claimed files whose rows were in memory."""
        conn = _make_conn()
        disk = _insert_disk(conn, str(tmp_path))
        scan_run_id = _insert_scan_run(conn)
        for index in range(5):
            (tmp_path / f"Movie {index}.mkv").write_bytes(b"\0" * 16)

        visitor = FullVisitor(conn, disk, generation=1, files_visited=[0], dirs_visited=[0])
        walk(
            str(tmp_path),
            visitor,
            budget=WalkBudget(budget_seconds=None, started_at_monotonic=time.monotonic(), budget_exhausted=[False]),
            shutdown=lambda: False,
            checkpoint=WalkCheckpoint(
                scan_run_id=scan_run_id,
                checkpoint_every=2,
                files_since_checkpoint=[0],
                resume_from=[None],
            ),
        )

        last_path = conn.execute("SELECT last_path FROM scan_run WHERE id = ?", (scan_run_id,)).fetchone()[0]
        assert last_path is not None, "the walk was long enough to checkpoint"
        # Every file at or before the committed position is one a resume would
        # skip, so each of them must already have its row.
        claimed = sorted(
            name for name in (f"Movie {index}.mkv" for index in range(5)) if f"{disk.label}//{name}" <= last_path
        )
        written = sorted(row[0] for row in conn.execute("SELECT filename FROM media_file ORDER BY filename").fetchall())
        assert set(claimed) <= set(written), "a committed position named files with no row"
