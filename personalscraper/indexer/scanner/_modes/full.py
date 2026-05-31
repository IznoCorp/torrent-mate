"""Full scan mode driver."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from personalscraper.indexer.scanner._index_ddl import _recreate_indexes
from personalscraper.indexer.scanner._walker import (
    _walk_dir_full_buffered,
)
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("indexer.scan")

__all__ = [
    "_scan_disk_full",
    "stage_items_pass1",
]


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

    Wraps the :func:`_walk_dir_full` recursive walk.  When ``drop_indexes`` is
    ``True``, secondary indexes on ``media_file`` / ``media_stream`` are dropped
    before the walk and always recreated in a ``try/finally`` block, regardless
    of whether an exception occurs during the walk.

    New rows are accumulated in an ``insert_buffer``.  The buffer is flushed
    every :data:`_INSERT_BATCH_SIZE` rows (checked inside
    :func:`_walk_dir_full`) and once more at the end to drain any remainder.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        mount: Absolute mount point path.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation counter.
        drop_indexes: Whether to drop and recreate secondary indexes.
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Forwarded to :func:`_walk_dir_full_buffered`.
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

    insert_buffer: list[Any] = []
    try:
        _walk_dir_full_buffered(
            conn,
            disk,
            mount,
            files_visited,
            dirs_visited,
            generation,
            insert_buffer,
            resume_from,
            files_since_checkpoint,
            budget_exhausted,
            started_at_monotonic,
            budget_seconds,
            scan_run_id,
            checkpoint_every,
        )
        # Flush any remaining rows that did not fill a full batch.
        from personalscraper.indexer.scanner import _modes as modes_api  # noqa: PLC0415

        modes_api._flush_insert_buffer(conn, insert_buffer)
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
