"""Full mode must not write a walked file until the walk is over.

This reads like a performance detail and is a data-integrity guarantee. Every
scanner connection is opened with ``isolation_level=None``
(``scanner/_concurrency.py``, ``core/sqlite/_open.py``) and nothing in the
package issues a BEGIN, so **every statement commits the instant it runs** and
``worker_conn.rollback()`` on the EIO path (``_scan_orchestrator.py``) rolls
back nothing at all.

What actually implements DESIGN §15.5 for ``media_file`` — a disk that vanishes
mid-walk contributes no rows — is that full mode's rows are still in a Python
list when the ``OSError`` propagates out of :func:`walk` and skips the trailing
flush in ``_scan_disk_full``. Nothing else stops them. ``path`` rows are not
buffered and are therefore already durable when it happens, which is why the
guarantee is partial to begin with.

So ``_INSERT_BATCH_SIZE`` is deliberately NOT applied as a running ceiling.
Enforcing it was tried in this branch and withdrawn: with a fixture one batch
deep, ``test_indexer_unplug_during_scan`` leaked 5 000 rows for a disk whose
walk had been declared failed. The operator's library is ~98 500 files, so that
is roughly nineteen batches — the leak would have been the normal case rather
than the edge case.

The cost of the guarantee is the retention: 98 506 rows and 37.2 MB measured,
lost outright on a hard kill while ``scan_run.last_path`` has already recorded
those files as walked. Both are consequences of the missing transaction and
neither can be repaired from inside the buffer.

The holds below pin the SHAPE rather than the constant, so re-introducing a
mid-walk drain at any interval turns them red.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner import _db_writes
from personalscraper.indexer.scanner._modes.full import FullVisitor
from personalscraper.indexer.scanner._walker import WalkBudget, WalkCheckpoint, walk
from personalscraper.indexer.schema import DiskRow, ScanRunRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory connection with the full schema applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, mount_path: str) -> DiskRow:
    """Insert a disk rooted at *mount_path* and return the stored row."""
    row = DiskRow(
        id=0,
        uuid="uuid-buffer",
        label="BufferDisk",
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


def _rows_written(conn: sqlite3.Connection) -> int:
    """Return how many media_file rows the database actually holds."""
    return int(conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0])


def _walk_files(conn: sqlite3.Connection, root: Path, count: int, *, checkpoint_every: int = 2) -> FullVisitor:
    """Create *count* files under *root* and walk them in full mode."""
    for index in range(count):
        (root / f"Movie {index:03d}.mkv").write_bytes(b"\0" * 16)
    disk = _insert_disk(conn, str(root))
    scan_run_id = _insert_scan_run(conn)
    visitor = FullVisitor(conn, disk, generation=1, files_visited=[0], dirs_visited=[0])
    walk(
        str(root),
        visitor,
        budget=WalkBudget(budget_seconds=None, started_at_monotonic=time.monotonic(), budget_exhausted=[False]),
        shutdown=lambda: False,
        checkpoint=WalkCheckpoint(
            scan_run_id=scan_run_id,
            checkpoint_every=checkpoint_every,
            files_since_checkpoint=[0],
            resume_from=[None],
        ),
    )
    return visitor


class TestTheWalkWritesNothingUntilItEnds:
    """The rows stay in memory for the whole walk — that IS the EIO guarantee."""

    def test_nothing_is_written_even_past_several_batch_boundaries(self, tmp_path: Path) -> None:
        """A drain at any interval publishes a failed disk's rows durably.

        The batch size is patched far below the file count, so the ceiling this
        branch tried and withdrew would have fired four times here.
        """
        conn = _make_conn()
        with patch.object(_db_writes, "_INSERT_BATCH_SIZE", 3):
            visitor = _walk_files(conn, tmp_path, 12)

        assert _rows_written(conn) == 0, "a mid-walk drain publishes rows a vanished disk must not leave"
        assert len(visitor.insert_buffer) == 12, "every walked file must still be held"

    def test_the_checkpoint_commits_the_position_without_the_rows(self, tmp_path: Path) -> None:
        """The other half of the tension, pinned so it is not mistaken for safety.

        ``last_path`` IS durable — written on an autocommit connection — while
        the rows for those same files are not. A hard kill therefore resumes
        past files that were never indexed. This hold does not bless that; it
        records it, so a reader can see the gap is known and measured.
        """
        conn = _make_conn()
        _walk_files(conn, tmp_path, 6)

        last_path = conn.execute("SELECT last_path FROM scan_run").fetchone()[0]
        assert last_path is not None, "the walk was long enough to checkpoint"
        assert _rows_written(conn) == 0, "yet not one row backs the position it committed"

    def test_the_trailing_flush_is_what_writes_them(self, tmp_path: Path) -> None:
        """The single post-walk flush is the only writer, and it does write."""
        conn = _make_conn()
        visitor = _walk_files(conn, tmp_path, 5)

        _db_writes._flush_insert_buffer(conn, visitor.insert_buffer)

        assert _rows_written(conn) == 5
        assert visitor.insert_buffer == []
