"""Core walk skeleton for the media indexer scanner.

Provides:
- :class:`IndexerConfigError` — raised for invalid configuration (e.g. unknown ``--disk``).
- :class:`ScanMode` — enum of the four scan modes (quick, incremental, enrich, full).
- :class:`ScanRunResult` — lightweight result returned by :func:`scan`.
- :data:`EXCLUDED_NAMES` — frozenset of system / macOS directory names to skip.
- :func:`_should_exclude` — predicate for per-entry exclusion during directory walk.
- :func:`filter_disks` — filter a disk list by label; raises :class:`IndexerConfigError` if unknown.
- :func:`scan` — walk function: per-disk loop with guard, scandir walk,
  path row write-through, media_file upsert, scan_run lifecycle management.

Sub-phase 2.5 additions:
    - Full-mode fingerprinting: ``fingerprint_tier1`` (size/mtime/ctime) for every
      non-symlink file; ``oshash`` for files whose suffix is in
      ``fingerprint.OSHASH_EXTENSIONS``.
    - Symlinks continue to receive ``oshash=None`` (NULL in DB; never fingerprinted).
    - ``drop_indexes_during_full_scan`` optimization: secondary indexes on
      ``media_file`` / ``media_stream`` are dropped before bulk inserts and
      recreated via a ``try/finally`` block after the disk is fully walked.
    - ``--disk D`` scoping via :func:`filter_disks` and the ``disk_filter`` parameter
      on :func:`scan`.

Sub-phase 2.6 additions:
    - Quick-mode path: per-disk Merkle short-circuit and dir-mtime subtree skip.
    - :func:`_verify_dir_mtime_reliable` — one-time session check that writes a temp
      file and detects whether the OS updates parent-directory mtime.  When the check
      fails, the dir-mtime optimisation is disabled for the entire scan session.
    - :func:`_build_disk_fingerprints` — query existing ``media_file`` rows for a disk
      and construct :class:`~personalscraper.indexer.merkle.FileFingerprint` objects
      for Merkle computation.
    - :func:`_walk_dir_quick` — recursive dir walk that skips unchanged subtrees by
      comparing stored ``path.dir_mtime_ns`` to the current FS value.
    - :func:`_scan_disk_quick` — per-disk quick-mode driver: Merkle short-circuit first,
      then dir-mtime walk on Merkle miss, then Merkle root update.

Notes on ``oshash`` nullability:
    The ``media_file`` table declares ``oshash TEXT`` (nullable since migration 002).
    In full mode, video files receive a real 16-char hex OSHash.  Non-video regular
    files and symlinks receive ``None`` (stored as SQL NULL) because OSHash is only
    defined for video content and symlinks are never fingerprinted.  Callers must
    treat ``oshash IS NULL`` as "not yet computed or not applicable".

Notes on the ``path`` table:
    There is no ``path_repo`` among the seven repos created in sub-phase 1.4; the
    ``path`` CRUD lives in ``disk_repo`` (``insert_path`` / ``upsert_path`` /
    ``get_path_by_disk_and_relpath``).  This module calls those functions directly.

Notes on ``os.open`` convention:
    All actual file opens (content reads) must use ``os.open(path, os.O_RDONLY)``
    so the OS can honour ``F_RDADVISE`` sequential hints added in Phase 4.  The
    ``fingerprint.oshash`` function already follows this convention.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from personalscraper.indexer import fingerprint
from personalscraper.indexer.merkle import (
    DiskMismatchError,
    DiskUnmountedError,
    FileFingerprint,
    compute_merkle_root,
    guard_disk_mounted,
)
from personalscraper.indexer.repos import disk_repo, file_repo, log_repo
from personalscraper.indexer.schema import DiskRow, MediaFileRow, PathRow, ScanRunRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

# Batch size for executemany inserts during full-mode walk (DESIGN §11.7).
_INSERT_BATCH_SIZE: int = 5000


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class IndexerConfigError(ValueError):
    """Raised when scanner configuration is invalid.

    Typical triggers:
    - ``--disk D`` references a label that is not present in the configured disk list.

    Args:
        message: Human-readable description of the configuration problem.
    """

    def __init__(self, message: str) -> None:
        """Initialize with a human-readable message."""
        super().__init__(message)


# ---------------------------------------------------------------------------
# ScanMode
# ---------------------------------------------------------------------------


class ScanMode(str, Enum):
    """Enumeration of available scan modes.

    Members:
        quick: Merkle short-circuit + dir-mtime subtree skip (Phase 2.6).
        incremental: Changed-files only based on dir-mtime deltas (Phase 4).
        enrich: Re-run mediainfo / NFO / artwork on un-enriched files (Phase 4).
        full: Walk every file on every disk and (re-)compute tier-1 fingerprints (Phase 2.5).
    """

    quick = "quick"
    incremental = "incremental"
    enrich = "enrich"
    full = "full"


# ---------------------------------------------------------------------------
# ScanRunResult
# ---------------------------------------------------------------------------


@dataclass
class ScanRunResult:
    """Summary result returned by :func:`scan`.

    Args:
        scan_run_id: PK of the ``scan_run`` row created for this scan.
        files_visited: Number of file entries visited across all disks.
        dirs_visited: Number of directory entries visited (including disk roots).
        status: Final status string — ``'ok'`` or ``'failed'``.
        disks_skipped: Number of disks short-circuited by the Merkle match in
            quick mode (Merkle root matched → zero FS reads for that disk).
        error: Human-readable error message; ``None`` on success.
    """

    scan_run_id: int
    files_visited: int
    dirs_visited: int
    status: str
    disks_skipped: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# Excluded names
# ---------------------------------------------------------------------------

#: Exact-match names that are always skipped during the directory walk.
#: These are well-known macOS / Windows system artefacts that should never
#: be indexed as media content.
EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        ".fseventsd",
        "$Recycle.Bin",
        ".Spotlight-V100",
        ".Trashes",
        "System Volume Information",
        ".DS_Store",
    }
)


# ---------------------------------------------------------------------------
# Exclusion predicate
# ---------------------------------------------------------------------------


def _should_exclude(name: str) -> bool:
    """Return True if a filesystem entry should be skipped during the walk.

    An entry is excluded if its bare name is in :data:`EXCLUDED_NAMES` or if it
    starts with the ``"._"`` prefix used by macOS for resource-fork shadow files.

    Args:
        name: The bare entry name (no directory component).

    Returns:
        ``True`` if the entry must be skipped; ``False`` if it should be walked.
    """
    return name in EXCLUDED_NAMES or name.startswith("._")


# ---------------------------------------------------------------------------
# filter_disks
# ---------------------------------------------------------------------------


def filter_disks(disks: list[DiskRow], disk_label: str | None) -> list[DiskRow]:
    """Filter a disk list to a single disk by label, or return all disks.

    When ``disk_label`` is ``None``, the full list is returned unchanged.
    When ``disk_label`` is provided, the list is filtered to disks whose
    ``label`` matches exactly.  If no match is found an
    :class:`IndexerConfigError` is raised.

    Args:
        disks: Full list of :class:`~personalscraper.indexer.schema.DiskRow`
            objects to filter.
        disk_label: Disk label to match against.  ``None`` returns all disks.

    Returns:
        Filtered list of :class:`~personalscraper.indexer.schema.DiskRow`
        objects.  Contains at most one element when ``disk_label`` is given.

    Raises:
        IndexerConfigError: When ``disk_label`` is not ``None`` and no disk
            with that label exists in ``disks``.
    """
    if disk_label is None:
        return list(disks)

    matched = [d for d in disks if d.label == disk_label]
    if not matched:
        raise IndexerConfigError(f"no disk with label '{disk_label}'")
    return matched


# ---------------------------------------------------------------------------
# Index management helpers (drop_indexes_during_full_scan, DESIGN §11.7)
# ---------------------------------------------------------------------------


def _capture_index_ddl(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Capture CREATE INDEX statements for ``media_file`` and ``media_stream``.

    Excludes SQLite auto-indexes (``sqlite_autoindex_*``) that are tied to
    ``UNIQUE`` constraints and cannot be recreated manually.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(index_name, create_sql)`` tuples for non-autoindex entries.
    """
    rows = conn.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'index'
          AND tbl_name IN ('media_file', 'media_stream')
          AND sql IS NOT NULL
          AND name NOT LIKE 'sqlite_autoindex_%'
        """
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _drop_secondary_indexes(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Drop all non-autoindex secondary indexes on ``media_file`` and ``media_stream``.

    Captures the DDL first, drops each index, and returns the captured DDL so
    the caller can recreate the indexes via :func:`_recreate_indexes`.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(index_name, create_sql)`` pairs that were dropped.
    """
    ddl_pairs = _capture_index_ddl(conn)
    for name, _ in ddl_pairs:
        conn.execute(f"DROP INDEX IF EXISTS {name}")
        log.debug("indexer.scan.index_dropped", index_name=name)
    return ddl_pairs


def _recreate_indexes(conn: sqlite3.Connection, ddl_pairs: list[tuple[str, str]]) -> None:
    """Recreate indexes from previously captured CREATE INDEX statements.

    Args:
        conn: Open SQLite connection.
        ddl_pairs: List of ``(index_name, create_sql)`` tuples as returned by
            :func:`_drop_secondary_indexes`.
    """
    for name, sql in ddl_pairs:
        conn.execute(sql)
        log.debug("indexer.scan.index_recreated", index_name=name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _relpath(mount_path: str, abs_path: str) -> str:
    """Compute the path relative to *mount_path*, stripping any leading separator.

    Args:
        mount_path: Absolute mount point of the disk (no trailing slash).
        abs_path: Absolute path of the entry on the same disk.

    Returns:
        Relative path string, e.g. ``"001-MOVIES/Inception (2010)"``.
    """
    rel = os.path.relpath(abs_path, mount_path)
    # os.path.relpath never starts with '/' but may start with '.'; keep it clean.
    return rel.lstrip("./") if rel == "." else rel


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
    existing = file_repo.find_by_path_and_filename(conn, path_id, filename)
    if existing is None:
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
            insert_buffer.append(row_tuple)
        else:
            file_repo.insert(
                conn,
                MediaFileRow(
                    id=0,
                    release_id=row_tuple[0],
                    path_id=row_tuple[1],
                    filename=row_tuple[2],
                    size_bytes=row_tuple[3],
                    mtime_ns=row_tuple[4],
                    ctime_ns=row_tuple[5],
                    oshash=row_tuple[6],
                    xxh3_partial=row_tuple[7],
                    xxh3_full=row_tuple[8],
                    scan_generation=row_tuple[9],
                    last_verified_at=row_tuple[10],
                    enriched_at=row_tuple[11],
                    miss_strikes=row_tuple[12],
                    deleted_at=row_tuple[13],
                ),
            )
    else:
        # Update mutable columns on a revisit (size, mtime, oshash, generation, verified).
        conn.execute(
            """
            UPDATE media_file
            SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                oshash = ?, scan_generation = ?, last_verified_at = ?
            WHERE id = ?
            """,
            (size_bytes, mtime_ns, ctime_ns, oshash_value, generation, now_s, existing.id),
        )


def _flush_insert_buffer(conn: sqlite3.Connection, buffer: list[Any]) -> None:
    """Flush accumulated new-file rows to the database using ``executemany``.

    This is the batched insert path used when ``drop_indexes_during_full_scan``
    is enabled.  Rows are inserted in one ``executemany`` call, which SQLite
    processes much faster than individual ``INSERT`` statements.

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
        """,
        buffer,
    )
    log.debug("indexer.scan.batch_flushed", rows=len(buffer))
    buffer.clear()


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
        log.warning("indexer.scan.oshash_failed", path=entry_path, error=str(exc))
        return None


def _walk_dir_full(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    insert_buffer: list[Any],
) -> None:
    """Recursively walk *dir_abs* in full mode, fingerprinting every file.

    Extends the skeleton walk with:
    - ``fingerprint_tier1`` called on every non-symlink file to extract
      (size, mtime_ns, ctime_ns).
    - ``oshash`` computed for regular files with a video extension.
    - Symlinks recorded with ``oshash=None`` (NULL in DB; never fingerprinted).
    - New rows buffered for batched ``executemany`` inserts.

    Uses ``entry.stat(follow_symlinks=False)`` so symlinks are never
    transparently followed.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` owning this subtree.
        dir_abs: Absolute path of the current directory.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation stamped on every ``media_file`` row.
        insert_buffer: Accumulation list for batched inserts (flushed by caller).
    """
    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

    try:
        with os.scandir(dir_abs) as it:
            entries = list(it)
    except PermissionError:
        log.warning("indexer.scan.dir_permission_denied", path=dir_abs)
        return

    for entry in entries:
        if _should_exclude(entry.name):
            continue

        # Stat without following symlinks — this is the *only* stat call per entry.
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            log.warning("indexer.scan.stat_failed", path=entry.path)
            continue

        if entry.is_dir(follow_symlinks=False):
            dirs_visited[0] += 1
            _walk_dir_full(conn, disk, entry.path, files_visited, dirs_visited, generation, insert_buffer)

            # Write-through path row after all children have been visited.
            rel = _relpath(disk.mount_path, entry.path)
            _upsert_path_row(conn, disk.id, rel, st.st_mtime_ns)

        else:
            # Both regular files and symlinks land here.
            files_visited[0] += 1
            is_symlink = entry.is_symlink()

            # Tier-1 fingerprint — zero extra I/O (uses the stat already performed).
            size_bytes, mtime_ns, ctime_ns = fingerprint.fingerprint_tier1(st)

            # OSHash — 128 KiB read for eligible video files; "" for all others.
            oshash_value = _compute_oshash(entry.path, entry.name, is_symlink)

            parent_rel = _relpath(disk.mount_path, dir_abs)
            path_id = _upsert_path_row(conn, disk.id, parent_rel, 0)

            _upsert_file_row(
                conn,
                path_id=path_id,
                filename=entry.name,
                size_bytes=size_bytes,
                mtime_ns=mtime_ns,
                ctime_ns=ctime_ns,
                generation=generation,
                oshash_value=oshash_value,
                insert_buffer=insert_buffer,
            )


def _walk_dir(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
) -> None:
    """Recursively walk *dir_abs*, recording path and media_file rows (skeleton mode).

    Used by scan modes other than ``full`` (e.g. quick, incremental) where
    fingerprinting is not yet implemented.  Records every file with
    ``oshash=None`` (NULL in DB — Stage A deferred state per migration 002).

    Uses :func:`os.scandir` to iterate entries.  Each entry is stat'd via
    ``entry.stat(follow_symlinks=False)`` so symlinks are never transparently
    followed.  Symlinks are still recorded in ``media_file`` with ``oshash=""``
    (the deferred sentinel).

    After visiting all children of a directory, the ``path`` row for that
    directory is upserted with its current ``dir_mtime_ns``.  This write-through
    is the mechanism used by ``--mode quick`` (Phase 2.6) to detect changed
    subtrees without re-reading every file.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` that owns this subtree.
        dir_abs: Absolute path of the current directory to scan.
        files_visited: Single-element list used as a mutable counter for files.
        dirs_visited: Single-element list used as a mutable counter for directories.
        generation: Scan generation for this run (stamped on every media_file row).
    """
    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

    try:
        with os.scandir(dir_abs) as it:
            entries = list(it)
    except PermissionError:
        log.warning("indexer.scan.dir_permission_denied", path=dir_abs)
        return

    for entry in entries:
        if _should_exclude(entry.name):
            continue

        # Stat without following symlinks — this is the *only* stat call per entry.
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            log.warning("indexer.scan.stat_failed", path=entry.path)
            continue

        if entry.is_dir(follow_symlinks=False):
            # Recurse first, then write-through the path row so dir_mtime_ns
            # reflects the state *after* all children have been visited.
            dirs_visited[0] += 1
            _walk_dir(conn, disk, entry.path, files_visited, dirs_visited, generation)

            # Write-through path row for this directory.
            rel = _relpath(disk.mount_path, entry.path)
            _upsert_path_row(conn, disk.id, rel, st.st_mtime_ns)

        else:
            # Both regular files and symlinks land here.
            # Symlinks are recorded but never fingerprinted (oshash stays NULL).
            files_visited[0] += 1
            parent_rel = _relpath(disk.mount_path, dir_abs)
            path_id = _upsert_path_row(conn, disk.id, parent_rel, 0)
            ctime_ns: int | None = st.st_ctime_ns if hasattr(st, "st_ctime_ns") else None
            _upsert_file_row(
                conn,
                path_id=path_id,
                filename=entry.name,
                size_bytes=st.st_size,
                mtime_ns=st.st_mtime_ns,
                ctime_ns=ctime_ns,
                generation=generation,
            )


# ---------------------------------------------------------------------------
# Quick-mode helpers (sub-phase 2.6)
# ---------------------------------------------------------------------------


def _verify_dir_mtime_reliable() -> bool:
    """Check whether the OS updates a directory's mtime when a child file is written.

    Creates a temporary directory, records the parent-dir mtime before and after
    writing a temp file inside it, and returns ``True`` only if the mtime changed.

    This one-time check guards the dir-mtime subtree-skip optimisation: on some
    filesystems (e.g. ``noatime`` / ``nodiratime`` mounts, certain network shares)
    the directory mtime is not updated on child creation, which would cause the
    scanner to silently skip changed subtrees.  When the check fails, we fall back
    to per-file fingerprinting throughout the quick-mode walk.

    Returns:
        ``True`` if the OS reliably updates directory mtime on child write;
        ``False`` if the optimisation should be disabled for this scan session.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Capture parent-dir mtime before the write.
            mtime_before = os.stat(tmp_dir).st_mtime_ns

            # Write a child file — this should bump the parent's mtime.
            test_file = os.path.join(tmp_dir, "_mtime_probe")
            with open(test_file, "w") as fh:
                fh.write("probe")

            # Capture parent-dir mtime after the write.
            mtime_after = os.stat(tmp_dir).st_mtime_ns

        if mtime_before == mtime_after:
            log.warning("indexer.scan.dir_mtime_unreliable", reason="mtime unchanged after child write")
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — deliberately broad; any failure disables opt
        log.warning("indexer.scan.dir_mtime_unreliable", reason=str(exc))
        return False


def _build_disk_fingerprints(conn: sqlite3.Connection, disk_id: int) -> list[FileFingerprint]:
    """Query all non-deleted ``media_file`` rows for *disk_id* and build fingerprint objects.

    Used by the quick-mode Merkle short-circuit: we recompute the Merkle root
    entirely from the database (zero filesystem reads) and compare it to the
    stored ``disk.merkle_root``.  If they match, the disk is skipped entirely.

    The join walks ``media_file → path`` to filter by ``path.disk_id``.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the disk whose files to query.

    Returns:
        List of :class:`~personalscraper.indexer.merkle.FileFingerprint` objects,
        one per non-deleted ``media_file`` row belonging to the disk.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT mf.path_id, mf.size_bytes, mf.mtime_ns, mf.oshash
        FROM media_file mf
        JOIN path p ON mf.path_id = p.id
        WHERE p.disk_id = ?
          AND mf.deleted_at IS NULL
        """,
        (disk_id,),
    ).fetchall()
    return [
        FileFingerprint(path_id=r["path_id"], size=r["size_bytes"], mtime_ns=r["mtime_ns"], oshash=r["oshash"])
        for r in rows
    ]


def _walk_dir_quick(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    dir_mtime_reliable: bool,
) -> None:
    """Recursively walk *dir_abs* in quick mode with dir-mtime subtree skipping.

    For each subdirectory visited, the stored ``path.dir_mtime_ns`` is compared
    to the current filesystem value.  When they match *and* ``dir_mtime_reliable``
    is ``True``, the entire subtree is skipped (zero file reads in that subtree).
    On a mismatch, the subtree is walked and files are fingerprinted at tier-1
    only (no oshash recompute in quick mode).

    After visiting a subtree (or deciding to skip it), the ``path`` row's
    ``dir_mtime_ns`` is updated to the current value so the next quick scan can
    benefit from the optimisation.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` owning this subtree.
        dir_abs: Absolute path of the current directory to scan.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation stamped on every ``media_file`` row.
        dir_mtime_reliable: When ``False``, the dir-mtime skip is disabled and
            every subdirectory is fully walked (fallback to per-file fingerprinting).
    """
    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

    try:
        with os.scandir(dir_abs) as it:
            entries = list(it)
    except PermissionError:
        log.warning("indexer.scan.dir_permission_denied", path=dir_abs)
        return

    for entry in entries:
        if _should_exclude(entry.name):
            continue

        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            log.warning("indexer.scan.stat_failed", path=entry.path)
            continue

        if entry.is_dir(follow_symlinks=False):
            dirs_visited[0] += 1
            rel = _relpath(disk.mount_path, entry.path)
            current_mtime_ns: int = st.st_mtime_ns

            if dir_mtime_reliable:
                # Check whether the stored dir_mtime_ns matches the live FS value.
                existing_path = disk_repo.get_path_by_disk_and_relpath(conn, disk.id, rel)
                if existing_path is not None and existing_path.dir_mtime_ns == current_mtime_ns:
                    # Subtree unchanged — skip recursion entirely (zero file reads).
                    log.debug("indexer.scan.dir_unchanged", path=entry.path, dir_mtime_ns=current_mtime_ns)
                    continue

            # Subtree changed (or dir-mtime unreliable) — recurse and re-fingerprint.
            _walk_dir_quick(conn, disk, entry.path, files_visited, dirs_visited, generation, dir_mtime_reliable)

            # Update dir_mtime_ns to the current value so next scan can short-circuit.
            _upsert_path_row(conn, disk.id, rel, current_mtime_ns)

        else:
            # File (or symlink) — tier-1 fingerprint only (oshash stays NULL in quick mode).
            files_visited[0] += 1
            parent_rel = _relpath(disk.mount_path, dir_abs)
            path_id = _upsert_path_row(conn, disk.id, parent_rel, 0)
            ctime_ns_val: int | None = st.st_ctime_ns if hasattr(st, "st_ctime_ns") else None
            _upsert_file_row(
                conn,
                path_id=path_id,
                filename=entry.name,
                size_bytes=st.st_size,
                mtime_ns=st.st_mtime_ns,
                ctime_ns=ctime_ns_val,
                generation=generation,
            )


def _scan_disk_quick(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    disks_skipped: list[int],
    dir_mtime_reliable: bool,
) -> None:
    """Run the quick-mode walk for a single disk.

    Implements two levels of short-circuiting:

    1. **Merkle short-circuit** (cheapest): recompute the Merkle root from the
       existing ``media_file`` rows in the database.  If it equals
       ``disk.merkle_root``, the disk has not changed since the last scan —
       skip all filesystem access for this disk.

    2. **Dir-mtime walk** (on Merkle miss): walk the disk using
       :func:`_walk_dir_quick`, which skips unchanged subtrees by comparing
       the stored ``path.dir_mtime_ns`` to the current filesystem value.

    After a successful dir-mtime walk, the disk's Merkle root is recomputed
    from the updated ``media_file`` state and stored on ``disk.merkle_root``
    so the *next* quick scan can use the short-circuit.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        mount: Absolute mount point path.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation counter.
        disks_skipped: Single-element mutable counter for Merkle-hit skips.
        dir_mtime_reliable: Whether the dir-mtime skip optimisation is enabled
            for this scan session (from :func:`_verify_dir_mtime_reliable`).
    """
    # --- Merkle short-circuit ---
    fingerprints = _build_disk_fingerprints(conn, disk.id)
    current_root = compute_merkle_root(fingerprints)

    if disk.merkle_root is not None and current_root == disk.merkle_root:
        # DB-computed root matches stored root → disk unchanged, skip walk.
        log.info("indexer.scan.merkle_match", disk_uuid=disk.uuid, label=disk.label, merkle_root=current_root)
        disks_skipped[0] += 1
        return

    log.info(
        "indexer.scan.merkle_miss",
        disk_uuid=disk.uuid,
        label=disk.label,
        stored_root=disk.merkle_root,
        computed_root=current_root,
    )

    # --- Dir-mtime walk ---
    _walk_dir_quick(conn, disk, mount, files_visited, dirs_visited, generation, dir_mtime_reliable)

    # Write-through the path row for the disk root itself.
    try:
        root_st = os.stat(mount, follow_symlinks=False)
        _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
    except OSError:
        log.warning("indexer.scan.root_stat_failed", mount_path=mount)

    # Recompute and persist the updated Merkle root so the next quick scan
    # can short-circuit if the FS state is unchanged.
    updated_fingerprints = _build_disk_fingerprints(conn, disk.id)
    new_root = compute_merkle_root(updated_fingerprints)
    disk_repo.update_merkle_root(conn, disk.id, new_root)
    log.debug("indexer.scan.merkle_root_updated", disk_id=disk.id, merkle_root=new_root)


# ---------------------------------------------------------------------------
# Public scan function
# ---------------------------------------------------------------------------


def scan(
    disks: list[DiskRow],
    mode: ScanMode,
    generation: int,
    conn: sqlite3.Connection,
    disk_filter: str | None = None,
    drop_indexes: bool = False,
) -> ScanRunResult:
    """Walk all provided disks and record discovered files in the database.

    Sub-phase 2.5 extends the skeleton walk with full-mode fingerprinting:

    * ``mode == ScanMode.full``: For each file, ``fingerprint_tier1`` extracts
      (size, mtime_ns, ctime_ns) from the already-computed ``stat`` result
      (zero extra I/O).  For files whose lowercase extension is in
      :data:`~personalscraper.indexer.fingerprint.OSHASH_EXTENSIONS`, ``oshash``
      is also computed (128 KiB read).  Symlinks and non-video files receive
      ``oshash=None`` (stored as SQL NULL per migration 002).
    * ``drop_indexes=True``: Secondary indexes on ``media_file`` / ``media_stream``
      are dropped before bulk inserts and recreated in a ``try/finally`` block.
      New rows are buffered in memory (up to :data:`_INSERT_BATCH_SIZE`) and
      flushed via ``executemany`` for faster throughput.
    * ``disk_filter``: When not ``None``, the ``scan_run.disk_filter`` column is
      set to this value to record which single disk was scoped.

    Sub-phase 2.6 extends the function with quick-mode:

    * ``mode == ScanMode.quick``: Before walking any disk, :func:`_verify_dir_mtime_reliable`
      runs a one-time check to confirm the OS updates directory mtime on child writes.
      For each disk, :func:`_scan_disk_quick` attempts a Merkle short-circuit first
      (zero FS reads on match), then falls back to a dir-mtime subtree walk.

    Walk strategy (per disk):
        1. Call :func:`~personalscraper.indexer.merkle.guard_disk_mounted`.  On
           :class:`~personalscraper.indexer.merkle.DiskUnmountedError` or
           :class:`~personalscraper.indexer.merkle.DiskMismatchError` the disk is
           skipped with a warning; the scan continues on remaining disks.
        2. If ``mode == ScanMode.full`` and ``drop_indexes`` is ``True``, drop
           secondary indexes and use ``executemany`` batches for inserts.  Always
           recreate the indexes in a ``try/finally`` block.
        3. Walk the disk root via recursive :func:`os.scandir` calls.
           - Never follow symlinks (``entry.stat(follow_symlinks=False)``).
           - Skip any entry whose name is in :data:`EXCLUDED_NAMES` or starts with ``"._"``.
           - After visiting all children of a directory, upsert the ``path`` row
             with its current ``dir_mtime_ns``.
           - For each file (or symlink) entry, insert/update a ``media_file`` row.
             In full mode, ``oshash`` is populated for eligible video files.
        4. Track ``files_visited`` and ``dirs_visited`` counters.

    Lifecycle:
        A ``scan_run`` row is inserted at start (``status='running'``).  On
        success the row is updated to ``status='ok'`` with ``finished_at``.  On
        any unexpected exception the row is updated to ``status='failed'`` and the
        exception is re-raised.

    Args:
        disks: List of :class:`~personalscraper.indexer.schema.DiskRow` objects
            representing the disks to scan.  Unmounted / mismatched disks are
            skipped without aborting the scan.
        mode: The :class:`ScanMode` to use.  ``full`` enables fingerprinting;
            ``quick`` uses Merkle + dir-mtime short-circuits; other modes fall
            back to the skeleton walk.
        generation: Monotonically increasing generation counter stamped on every
            ``media_file`` row visited during this scan.
        conn: Open :class:`sqlite3.Connection` with ``isolation_level=None``
            (autocommit) or an active transaction managed by the caller.
        disk_filter: Disk label when scoped to a single disk (``--disk D``);
            ``None`` = all disks.  Stored in ``scan_run.disk_filter``.
        drop_indexes: When ``True`` and ``mode == ScanMode.full``, drop and
            recreate secondary indexes around bulk inserts (DESIGN §11.7).
            Only activated when ``IndexerConfig.scan.drop_indexes_during_full_scan``
            is true; callers should pass this value from the config.

    Returns:
        :class:`ScanRunResult` with the assigned ``scan_run_id``, visit counts,
        and final status.

    Raises:
        Exception: Any unexpected exception from the walk loop is re-raised after
            the ``scan_run`` row is updated to ``status='failed'``.
    """
    started_at = int(time.time())

    # Insert scan_run row with status=running.
    scan_run_id = log_repo.insert_scan_run(
        conn,
        ScanRunRow(
            id=0,
            generation=generation,
            mode=mode.value,
            disk_filter=disk_filter,
            started_at=started_at,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        ),
    )

    files_visited = [0]  # mutable counter (list avoids nonlocal in nested helper)
    dirs_visited = [0]
    disks_skipped = [0]  # quick-mode Merkle-hit counter

    # One-time dir-mtime reliability check for quick mode (before any disk walk).
    dir_mtime_reliable: bool = True
    if mode == ScanMode.quick:
        dir_mtime_reliable = _verify_dir_mtime_reliable()

    try:
        for disk in disks:
            if disk.mount_path is None:
                log.warning(
                    "indexer.scan.disk_skipped",
                    disk_id=disk.id,
                    label=disk.label,
                    reason="no mount_path",
                )
                continue

            # Guard: verify disk is mounted and identity sentinel matches.
            try:
                guard_disk_mounted(disk)
            except (DiskUnmountedError, DiskMismatchError) as exc:
                log.warning(
                    "indexer.scan.disk_skipped",
                    disk_id=disk.id,
                    label=disk.label,
                    reason=str(exc),
                )
                continue

            mount = disk.mount_path
            log.info("indexer.scan.disk_start", disk_id=disk.id, label=disk.label, mount_path=mount)

            if mode == ScanMode.full:
                # Full-mode walk with optional index drop + batched inserts.
                _scan_disk_full(conn, disk, mount, files_visited, dirs_visited, generation, drop_indexes)
                # Write-through the path row for the disk root.
                try:
                    root_st = os.stat(mount, follow_symlinks=False)
                    _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
                    dirs_visited[0] += 1
                except OSError:
                    log.warning("indexer.scan.root_stat_failed", mount_path=mount)
            elif mode == ScanMode.quick:
                # Quick-mode: Merkle short-circuit then dir-mtime walk.
                _scan_disk_quick(
                    conn,
                    disk,
                    mount,
                    files_visited,
                    dirs_visited,
                    generation,
                    disks_skipped,
                    dir_mtime_reliable,
                )
            else:
                # Skeleton walk for modes not yet fully implemented (incremental, enrich).
                _walk_dir(conn, disk, mount, files_visited, dirs_visited, generation)
                # Write-through the path row for the disk root.
                try:
                    root_st = os.stat(mount, follow_symlinks=False)
                    _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
                    dirs_visited[0] += 1
                except OSError:
                    log.warning("indexer.scan.root_stat_failed", mount_path=mount)

            log.info(
                "indexer.scan.disk_done",
                disk_id=disk.id,
                label=disk.label,
                files_visited=files_visited[0],
                dirs_visited=dirs_visited[0],
            )

        # All disks processed — mark scan_run ok.
        finished_at = int(time.time())
        log_repo.update_scan_run_status(conn, scan_run_id, "ok", finished_at=finished_at)
        return ScanRunResult(
            scan_run_id=scan_run_id,
            files_visited=files_visited[0],
            dirs_visited=dirs_visited[0],
            status="ok",
            disks_skipped=disks_skipped[0],
        )

    except Exception as exc:
        # Unexpected failure — record it and re-raise.
        finished_at = int(time.time())
        log_repo.update_scan_run_status(
            conn,
            scan_run_id,
            "failed",
            finished_at=finished_at,
        )
        return ScanRunResult(
            scan_run_id=scan_run_id,
            files_visited=files_visited[0],
            dirs_visited=dirs_visited[0],
            status="failed",
            disks_skipped=disks_skipped[0],
            error=str(exc),
        )


def _scan_disk_full(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    drop_indexes: bool,
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
    """
    ddl_pairs: list[tuple[str, str]] = []
    if drop_indexes:
        ddl_pairs = _drop_secondary_indexes(conn)

    insert_buffer: list[Any] = []
    try:
        _walk_dir_full_buffered(conn, disk, mount, files_visited, dirs_visited, generation, insert_buffer)
        # Flush any remaining rows that did not fill a full batch.
        _flush_insert_buffer(conn, insert_buffer)
    finally:
        if drop_indexes and ddl_pairs:
            _recreate_indexes(conn, ddl_pairs)


def _walk_dir_full_buffered(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    insert_buffer: list[Any],
) -> None:
    """Recursive full-mode walk that auto-flushes the insert buffer every N rows.

    Calls :func:`_walk_dir_full` and then checks whether the buffer has
    reached :data:`_INSERT_BATCH_SIZE`.  The flush happens *after* every
    directory completes to keep the buffer management at the top level of
    the recursion stack.

    Because :func:`_walk_dir_full` is itself recursive (it descends into
    subdirectories), each file appended to ``insert_buffer`` by a nested call
    will be visible here via the shared reference.  We flush after processing
    each directory subtree rather than after every single file to reduce the
    number of flush calls while still bounding memory usage.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` owning this subtree.
        dir_abs: Absolute path of the directory to walk.
        files_visited: Single-element mutable counter.
        dirs_visited: Single-element mutable counter.
        generation: Scan generation counter.
        insert_buffer: Shared accumulation list for new-row tuples.
    """
    _walk_dir_full(conn, disk, dir_abs, files_visited, dirs_visited, generation, insert_buffer)

    # Flush whenever the buffer exceeds the batch size threshold.
    if len(insert_buffer) >= _INSERT_BATCH_SIZE:
        _flush_insert_buffer(conn, insert_buffer)
