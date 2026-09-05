"""Database write helpers for the scanner.

Provides:
- :func:`_safe_mtime_ns` — clamp raw mtime to ``[0, now_ns]``.
- :func:`_upsert_path_row` — upsert a ``path`` row.
- :func:`_upsert_file_row` — insert or update a ``media_file`` row.
- :func:`_flush_insert_buffer` — flush accumulated new-file rows via executemany.
- :func:`_compute_oshash` — compute OSHash for eligible video files.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from personalscraper.indexer import fingerprint
from personalscraper.indexer.drift import clamp_mtime_ns
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.schema import PathRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

# Batch size for executemany inserts during full-mode walk (DESIGN §11.7).
_INSERT_BATCH_SIZE: int = 5000


# ---------------------------------------------------------------------------
# mtime sanitiser
# ---------------------------------------------------------------------------


def _safe_mtime_ns(mtime_ns: int) -> int:
    """Return *mtime_ns* clamped to ``[0, now_ns]`` via :func:`clamp_mtime_ns`.

    Thin wrapper so walk helpers can sanitise raw ``st_mtime_ns`` values
    without needing to capture ``now_ns`` individually.

    Args:
        mtime_ns: Raw ``st_mtime_ns`` from ``entry.stat()``.

    Returns:
        Sanitised mtime value in ``[0, time.time_ns()]``.
    """
    return clamp_mtime_ns(mtime_ns, time.time_ns())


# ---------------------------------------------------------------------------
# Path row upsert
# ---------------------------------------------------------------------------


def _upsert_path_row(conn: sqlite3.Connection, disk_id: int, rel: str, dir_mtime_ns: int) -> int:
    """Upsert a ``path`` row and return its primary key.

    Uses :func:`~personalscraper.indexer.repos.disk_repo.upsert_path` which
    performs an ``INSERT … ON CONFLICT DO UPDATE`` so callers never need to
    check whether the row already exists.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the owning disk row.
        rel: Relative path string (no leading separator).
        dir_mtime_ns: Directory mtime in nanoseconds from ``entry.stat()``.

    Returns:
        The PK of the upserted ``path`` row.
    """
    now_s = int(time.time())
    return disk_repo.upsert_path(
        conn,
        PathRow(
            id=0,
            disk_id=disk_id,
            rel_path=rel,
            dir_mtime_ns=dir_mtime_ns,
            last_walked_at=now_s,
        ),
    )


# ---------------------------------------------------------------------------
# File row upsert
# ---------------------------------------------------------------------------


def _upsert_file_row(
    conn: sqlite3.Connection,
    path_id: int,
    filename: str,
    size_bytes: int,
    mtime_ns: int,
    ctime_ns: int | None,
    generation: int,
    oshash_value: str | None = None,
    insert_buffer: list[Any] | None = None,
) -> None:
    """Insert or update a ``media_file`` row for a discovered file.

    In full mode the caller passes a pre-computed ``oshash_value`` and an
    ``insert_buffer`` list.  When a buffer is provided the row tuple is appended
    to it instead of being written immediately, and this function drains it
    through :func:`_flush_insert_buffer` as soon as it reaches
    :data:`_INSERT_BATCH_SIZE`.  The ceiling used to be the caller's to enforce
    and no caller did, so the buffer grew for the length of the walk.

    That is a ceiling, not the usual trigger: :func:`walk` drains the buffer
    before every checkpoint (100 files in production), so the batch normally
    ends there.  Both matter — the checkpoint keeps the committed walk position
    honest, the ceiling bounds memory when checkpoints are far apart or off.

    Without a buffer the row is written immediately, upserted in place.

    The ``oshash`` is set to ``oshash_value`` (``None`` for non-video or symlink
    files — stored as SQL NULL, see migration 002).  ``release_id`` is ``None``
    (NULL) during Stage A; release linkage is populated by the scraper phase
    (Stage B).  ``enriched_at`` is left ``NULL``.

    Args:
        conn: Open SQLite connection.
        path_id: PK of the owning ``path`` row.
        filename: Bare filename (no directory component).
        size_bytes: File size in bytes from ``entry.stat()``.
        mtime_ns: File modification time in nanoseconds from ``entry.stat()``.
        ctime_ns: File change time in nanoseconds; ``None`` if unavailable.
        generation: Scan generation counter for this scan run.
        oshash_value: Pre-computed OSHash hex string; ``None`` if not applicable
            (non-video files, symlinks, or files whose hash computation failed).
        insert_buffer: Optional accumulation list for batched inserts.  When
            provided, new rows are appended rather than inserted individually.
    """
    now_s = int(time.time())
    row_tuple = (
        None,  # release_id — NULL during Stage A; release linkage in scrape phase
        path_id,
        filename,
        size_bytes,
        mtime_ns,
        ctime_ns,
        oshash_value,  # NULL for non-video/symlink files (Stage A); hex string for video
        None,  # xxh3_partial
        None,  # xxh3_full
        generation,
        now_s,  # last_verified_at
        None,  # enriched_at — mediainfo extraction is in a later sub-phase
        0,  # miss_strikes
        None,  # deleted_at
    )
    if insert_buffer is not None:
        # Buffered path, taken by full mode for EVERY file it walks (new or
        # already known — the flush carries an ON CONFLICT clause for that).
        # The ceiling is enforced here rather than left to the caller: for as
        # long as it was not, the buffer grew for the whole walk, which for
        # this library meant 98 000 tuples and 37 MB retained until the walk
        # returned, and lost outright if the process was killed.
        insert_buffer.append(row_tuple)
        if len(insert_buffer) >= _INSERT_BATCH_SIZE:
            _flush_insert_buffer(conn, insert_buffer)
        return

    # Atomic INSERT-OR-UPDATE: relies on UNIQUE(path_id, filename) constraint
    # added by migration 002. Eliminates the SELECT-then-INSERT/UPDATE TOCTOU
    # window where two concurrent walkers (or a walker + enrich pass) could
    # both observe "row missing" and race a duplicate INSERT.
    #
    # DEV #52 (preserved): oshash uses COALESCE(excluded.oshash, oshash) so a
    # freshly-computed oshash fills NULL rows (retry succeeds), but a failed
    # recomputation (oshash_value=None due to OSError) never wipes a previously
    # -good hash value.
    #
    # On conflict, we update only the columns the previous UPDATE branch did
    # (size_bytes, mtime_ns, ctime_ns, oshash, scan_generation, last_verified_at)
    # — plus ``miss_strikes``, see below. Untouched columns (release_id, xxh3_*,
    # enriched_at, deleted_at) are intentionally preserved.
    #
    # ``miss_strikes = 0`` because THIS CALL IS THE SIGHTING. Reaching here means
    # the walk stat'd the file and it is there, which is precisely the event both
    # the schema docstring (« Consecutive scans where this file was not found »)
    # and docs/production/indexer.md (« the counter is reset to 0 the moment the
    # file is observed again ») describe — and which only a RENAME performed
    # (``drift.detect_rename``). ``reset_strikes_on_reappearance`` was written for
    # the general case, is tested, and is reachable only through
    # ``reconcile_file``, which has no production caller.
    #
    # Preserving the counter here made it a LIFETIME total rather than a
    # consecutive one: three absences months apart, with complete scans in between
    # that saw the file every time, still add up to the tombstone threshold. On
    # 2026-06-30 that cost the operator 49 553 rows — three truncated runs struck
    # disk_1, and the complete 49 476-file walk sitting between the second and the
    # third cleared nothing.
    #
    # This is ONE of three writes a sighting can take. The other two are
    # ``_flush_insert_buffer`` below and ``IncrementalVisitor.visit_file``'s own
    # four UPDATEs; all three carry the reset, because a counter that resets on
    # some sightings is not a consecutive counter.
    #
    # ``deleted_at`` is deliberately NOT cleared. Restoring tombstoned rows in
    # bulk is what the Merkle bulk-change freeze exists to arbitrate, and it is a
    # different decision from this one. Resetting the counter can only ever
    # PREVENT a tombstone, never cause one.
    conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path_id, filename) DO UPDATE SET
            size_bytes = excluded.size_bytes,
            mtime_ns = excluded.mtime_ns,
            ctime_ns = excluded.ctime_ns,
            oshash = COALESCE(excluded.oshash, oshash),
            scan_generation = excluded.scan_generation,
            last_verified_at = excluded.last_verified_at,
            miss_strikes = 0
        """,
        row_tuple,
    )


# ---------------------------------------------------------------------------
# Batch insert flush
# ---------------------------------------------------------------------------


def _flush_insert_buffer(conn: sqlite3.Connection, buffer: list[Any]) -> None:
    """Flush accumulated new-file rows to the database using ``executemany``.

    This is the batched insert path used when ``drop_indexes_during_full_scan``
    is enabled.  Rows are inserted in one ``executemany`` call, which SQLite
    processes much faster than individual ``INSERT`` statements.

    Uses the same ``INSERT ... ON CONFLICT(path_id, filename) DO UPDATE`` shape
    as :func:`_upsert_file_row` so that re-scans of already-indexed disks (which
    still go through the buffered path when ``drop_indexes_during_full_scan`` is
    enabled) do not crash with a UNIQUE-constraint violation.

    « The same shape » includes the ``miss_strikes = 0`` sighting reset, and that
    is not incidental: which write a walk takes is decided by its MODE — full
    always batches through here (``FullVisitor`` passes ``insert_buffer``
    unconditionally; ``drop_indexes_during_full_scan`` only governs the index
    DDL), while quick, the ``_walk_dir`` fallback and incremental's new-file
    branch take :func:`_upsert_file_row` directly. A reset on only some of them
    would make a data-integrity guarantee depend on which mode happened to run.

    Args:
        conn: Open SQLite connection.
        buffer: List of row tuples as produced by :func:`_upsert_file_row`.
            Cleared in-place after the flush.
    """
    if not buffer:
        return
    conn.executemany(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path_id, filename) DO UPDATE SET
            size_bytes = excluded.size_bytes,
            mtime_ns = excluded.mtime_ns,
            ctime_ns = excluded.ctime_ns,
            oshash = COALESCE(excluded.oshash, oshash),
            scan_generation = excluded.scan_generation,
            last_verified_at = excluded.last_verified_at,
            miss_strikes = 0
        """,
        buffer,
    )
    log.debug("indexer.scan.batch_flushed", rows=len(buffer))
    buffer.clear()


# ---------------------------------------------------------------------------
# OSHash computation
# ---------------------------------------------------------------------------


def _compute_oshash(entry_path: str, filename: str, is_symlink: bool) -> str | None:
    """Compute OSHash for a file entry if applicable.

    OSHash is only computed for regular (non-symlink) files whose suffix
    (without leading dot, lowercased) is in
    :data:`~personalscraper.indexer.fingerprint.OSHASH_EXTENSIONS`.
    All other files (non-video extensions, symlinks) receive ``None`` (stored
    as SQL NULL per migration 002).

    Args:
        entry_path: Absolute path of the file entry.
        filename: Bare filename used to extract the suffix.
        is_symlink: Whether the entry is a symlink (symlinks never get OSHash).

    Returns:
        16-character lowercase hex OSHash string, or ``None`` if not applicable
        (non-video file, symlink, or OSError during hash computation).
    """
    if is_symlink:
        return None
    suffix = Path(filename).suffix.lstrip(".").lower()
    if suffix not in fingerprint.OSHASH_EXTENSIONS:
        return None
    try:
        return fingerprint.oshash(Path(entry_path))
    except OSError as exc:
        log.warning(
            "indexer.scan.oshash_failed",
            path=entry_path,
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,
        )
        return None
