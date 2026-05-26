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

    In full mode the caller passes a pre-computed ``oshash_value`` and may
    optionally pass an ``insert_buffer`` list.  When a buffer is provided and
    the file is **new**, the row tuple is appended to the buffer instead of
    being inserted immediately — the caller flushes the buffer via
    :func:`_flush_insert_buffer` when it reaches :data:`_INSERT_BATCH_SIZE`.

    When the file already exists, the row is updated in-place (no buffering
    for updates; they are rare during a cold full scan).

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
        # Buffered new-row path — caller flushes via _flush_insert_buffer.
        # Used only during cold full-scan when no row collisions are expected.
        insert_buffer.append(row_tuple)
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
    # (size_bytes, mtime_ns, ctime_ns, oshash, scan_generation, last_verified_at).
    # Untouched columns (release_id, xxh3_*, enriched_at, miss_strikes,
    # deleted_at) are intentionally preserved.
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
            last_verified_at = excluded.last_verified_at
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
            last_verified_at = excluded.last_verified_at
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
