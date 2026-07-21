"""Full scan mode driver."""

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING, Any

from personalscraper.indexer import fingerprint
from personalscraper.indexer.scanner._db_writes import (
    _compute_oshash,
    _upsert_file_row,
    _upsert_path_row,
)
from personalscraper.indexer.scanner._index_ddl import _recreate_indexes
from personalscraper.indexer.scanner._shutdown import is_shutdown_requested
from personalscraper.indexer.scanner._walker import (
    ScanVisitor,
    WalkBudget,
    WalkCheckpoint,
    walk,
)
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("indexer.scan")

__all__ = [
    "FullVisitor",
    "_scan_disk_full",
    "stage_items_pass1",
]


class FullVisitor(ScanVisitor):
    """Full-mode visitor over :func:`~personalscraper.indexer.scanner._walker.walk`.

    Fingerprints every non-symlink file at tier-1 (size, mtime_ns, ctime_ns from
    the already-performed ``stat`` — zero extra I/O) and computes ``oshash`` for
    eligible video files (128 KiB read); symlinks and non-video files get
    ``oshash=None``. New rows are appended to :attr:`insert_buffer` for the
    batched ``executemany`` flush the driver drains after the walk (DESIGN §11.7).
    Byte-identical to the legacy ``_walk_dir_full`` per-file body; the write-
    through of each subtree's ``path`` row is the inherited default
    :meth:`~personalscraper.indexer.scanner._walker.ScanVisitor.leave_dir`.

    Attributes:
        insert_buffer: Accumulation list for batched new-row inserts; the caller
            (:func:`_scan_disk_full`) flushes it once the walk returns.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        disk: DiskRow,
        generation: int,
        files_visited: list[int],
        dirs_visited: list[int],
    ) -> None:
        """Bind the per-disk state and start with an empty insert buffer."""
        super().__init__(conn, disk, generation, files_visited, dirs_visited)
        self.insert_buffer: list[Any] = []

    def visit_file(self, entry: os.DirEntry[str], st: os.stat_result, parent_rel: str) -> None:
        """Fingerprint the file (tier-1 + oshash) and buffer the new ``media_file`` row."""
        is_symlink = entry.is_symlink()

        # Tier-1 fingerprint — zero extra I/O (uses the stat already performed).
        size_bytes, mtime_ns, ctime_ns = fingerprint.fingerprint_tier1(st)

        # OSHash — 128 KiB read for eligible video files; None for all others.
        oshash_value = _compute_oshash(entry.path, entry.name, is_symlink)

        path_id = _upsert_path_row(self.conn, self.disk.id, parent_rel, 0)
        _upsert_file_row(
            self.conn,
            path_id=path_id,
            filename=entry.name,
            size_bytes=size_bytes,
            mtime_ns=mtime_ns,
            ctime_ns=ctime_ns,
            generation=self.generation,
            oshash_value=oshash_value,
            insert_buffer=self.insert_buffer,
        )


def _scan_disk_full(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    drop_indexes: bool,
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
) -> None:
    """Run the full-mode walk for a single disk with optional index management.

    Drives the shared :func:`~personalscraper.indexer.scanner._walker.walk`
    skeleton with a :class:`FullVisitor`.  When ``drop_indexes`` is ``True``,
    secondary indexes on ``media_file`` / ``media_stream`` are dropped before the
    walk and always recreated in a ``try/finally`` block, regardless of whether an
    exception occurs during the walk.

    New rows are accumulated in the visitor's ``insert_buffer`` and drained once
    the walk returns via :func:`_flush_insert_buffer` (a single ``executemany``),
    exactly like the legacy ``_walk_dir_full_buffered`` post-walk flush.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        mount: Absolute mount point path.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation counter.
        drop_indexes: Whether to drop and recreate secondary indexes.
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Forwarded to the walk skeleton.
        files_since_checkpoint: Single-element mutable counter forwarded to the walk.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded inside the walk.
        started_at_monotonic: :func:`time.monotonic` timestamp forwarded to the walk.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
    """
    ddl_pairs: list[tuple[str, str]] = []
    if drop_indexes:
        from personalscraper.indexer.scanner import _modes as modes_api  # noqa: PLC0415

        ddl_pairs = modes_api._drop_secondary_indexes(conn)

    visitor = FullVisitor(conn, disk, generation, files_visited, dirs_visited)
    try:
        walk(
            mount,
            visitor,
            budget=WalkBudget(
                budget_seconds=budget_seconds,
                started_at_monotonic=started_at_monotonic,
                budget_exhausted=budget_exhausted if budget_exhausted is not None else [False],
            ),
            shutdown=is_shutdown_requested,
            checkpoint=WalkCheckpoint(
                scan_run_id=scan_run_id,
                checkpoint_every=checkpoint_every,
                files_since_checkpoint=files_since_checkpoint if files_since_checkpoint is not None else [0],
                resume_from=resume_from if resume_from is not None else [None],
            ),
        )
        # Flush any remaining rows that did not fill a full batch.
        from personalscraper.indexer.scanner import _modes as modes_api  # noqa: PLC0415

        modes_api._flush_insert_buffer(conn, visitor.insert_buffer)
    finally:
        if drop_indexes and ddl_pairs:
            _recreate_indexes(conn, ddl_pairs)


def stage_items_pass1(conn: sqlite3.Connection, config: Config, now_s: int | None = None) -> int:
    """Pass 1 of :class:`ScanMode.full`: stage rich ``media_item`` rows for the whole library.

    DESIGN §4.1/§5: ``full.py`` invokes the item stage **before** the per-disk
    file walk so a single ``library-index --mode full`` reaches the same DB
    end-state as the legacy ``library-scan`` + ``library-index``. This is a thin
    module-level invoker — the library-wide iteration (all configured disks ×
    categories × media dirs) lives in
    :func:`personalscraper.indexer.scanner._modes._item_stage.stage_library_items`,
    to which this delegates.

    It must run **exactly once per full scan** (library-wide), not once per disk:
    :func:`stage_library_items` already iterates every configured disk, so the
    caller (:func:`personalscraper.indexer.scanner.scan` full-mode branch) invokes
    this before the per-disk walk dispatch — never inside the per-disk
    :func:`_scan_disk_full` walker.

    Args:
        conn: Open SQLite connection.
        config: Fully-loaded application config. All configured disks are staged.
        now_s: Unix epoch seconds stamped on the rows; defaults to
            ``int(time.time())`` inside the delegate.

    Returns:
        Count of media directories successfully staged.
    """
    from personalscraper.indexer.scanner._modes._item_stage import stage_library_items  # noqa: PLC0415

    staged = stage_library_items(conn, config, now_s)
    log.info("indexer.scan.full.pass1_staged", staged=staged)
    return staged
