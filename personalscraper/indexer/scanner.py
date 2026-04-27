"""Core walk skeleton for the media indexer scanner.

Provides:
- :class:`ScanMode` — enum of the four scan modes (quick, incremental, enrich, full).
- :class:`ScanRunResult` — lightweight result returned by :func:`scan`.
- :data:`EXCLUDED_NAMES` — frozenset of system / macOS directory names to skip.
- :func:`_should_exclude` — predicate for per-entry exclusion during directory walk.
- :func:`scan` — skeleton walk function: per-disk loop with guard, scandir walk,
  path row write-through, media_file upsert, scan_run lifecycle management.

Notes on ``oshash`` sentinel:
    The ``media_file`` table declares ``oshash TEXT NOT NULL``, so this skeleton
    uses the empty string ``""`` as a deferred placeholder.  Full fingerprinting
    (OSHash / xxh3) is wired in sub-phases 2.5+.  Callers must treat ``oshash == ""``
    as "not yet computed" until those sub-phases land.

Notes on the ``path`` table:
    There is no ``path_repo`` among the seven repos created in sub-phase 1.4; the
    ``path`` CRUD lives in ``disk_repo`` (``insert_path`` / ``upsert_path`` /
    ``get_path_by_disk_and_relpath``).  This module calls those functions directly.

Notes on ``os.open`` convention:
    All actual file opens (content reads) must use ``os.open(path, os.O_RDONLY)``
    so the OS can honour ``F_RDADVISE`` sequential hints added in Phase 4.  This
    skeleton does not open file content; the convention is documented here for
    implementors of the fingerprint sub-phases (2.5+).
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum

from personalscraper.indexer.merkle import DiskMismatchError, DiskUnmountedError, guard_disk_mounted
from personalscraper.indexer.repos import disk_repo, file_repo, log_repo
from personalscraper.indexer.schema import DiskRow, MediaFileRow, PathRow, ScanRunRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

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
        error: Human-readable error message; ``None`` on success.
    """

    scan_run_id: int
    files_visited: int
    dirs_visited: int
    status: str
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
) -> None:
    """Insert or update a ``media_file`` row for a discovered file.

    Uses :func:`~personalscraper.indexer.repos.file_repo.upsert` when available;
    falls back to an INSERT-OR-REPLACE via direct SQL because ``file_repo``
    currently exposes only ``insert`` and ``find_by_path_and_filename``.

    The ``oshash`` is set to ``""`` (empty string) as a deferred sentinel —
    full fingerprinting is wired in sub-phases 2.5+.  ``release_id`` is set to
    ``0`` (a sentinel FK value) because release linkage is performed during the
    scrape phase, not the walk phase.  ``last_verified_at`` is set to the current
    epoch second.  ``enriched_at`` is left ``NULL``.

    Args:
        conn: Open SQLite connection.
        path_id: PK of the owning ``path`` row.
        filename: Bare filename (no directory component).
        size_bytes: File size in bytes from ``entry.stat()``.
        mtime_ns: File modification time in nanoseconds from ``entry.stat()``.
        ctime_ns: File change time in nanoseconds; ``None`` if unavailable.
        generation: Scan generation counter for this scan run.
    """
    now_s = int(time.time())
    existing = file_repo.find_by_path_and_filename(conn, path_id, filename)
    if existing is None:
        file_repo.insert(
            conn,
            MediaFileRow(
                id=0,
                release_id=0,  # deferred — release linkage happens in scrape phase
                path_id=path_id,
                filename=filename,
                size_bytes=size_bytes,
                mtime_ns=mtime_ns,
                ctime_ns=ctime_ns,
                oshash="",  # sentinel — full fingerprint deferred to 2.5+
                xxh3_partial=None,
                xxh3_full=None,
                scan_generation=generation,
                last_verified_at=now_s,
                enriched_at=None,
                miss_strikes=0,
                deleted_at=None,
            ),
        )
    else:
        # Update mutable columns on a revisit (size, mtime, generation, verified).
        conn.execute(
            """
            UPDATE media_file
            SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                scan_generation = ?, last_verified_at = ?
            WHERE id = ?
            """,
            (size_bytes, mtime_ns, ctime_ns, generation, now_s, existing.id),
        )


def _walk_dir(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
) -> None:
    """Recursively walk *dir_abs*, recording path and media_file rows.

    Uses :func:`os.scandir` to iterate entries.  Each entry is stat'd via
    ``entry.stat(follow_symlinks=False)`` so symlinks are never transparently
    followed.  Symlinks are still recorded in ``media_file`` with ``oshash=""``
    (the deferred sentinel).

    After visiting all children of a directory, the ``path`` row for that
    directory is upserted with its current ``dir_mtime_ns``.  This write-through
    is the mechanism used by ``--mode quick`` (Phase 2.6) to detect changed
    subtrees without re-reading every file.

    For file opens (content reads in sub-phases 2.5+), callers must use
    ``os.open(path, os.O_RDONLY)`` — never ``open()`` / ``Path.open()`` — so
    that macOS ``F_RDADVISE`` sequential hints (Phase 4) can be applied at a
    single call site.

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
            # Symlinks are recorded but never fingerprinted (oshash stays "").
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
# Public scan function
# ---------------------------------------------------------------------------


def scan(
    disks: list[DiskRow],
    mode: ScanMode,
    generation: int,
    conn: sqlite3.Connection,
) -> ScanRunResult:
    """Walk all provided disks and record discovered files in the database.

    This is the skeleton walk implementation used by sub-phase 2.4.  Full-mode
    fingerprinting (OSHash / xxh3) and quick-mode dir-mtime short-circuits are
    wired in sub-phases 2.5 and 2.6 respectively.  The ``mode`` parameter is
    accepted but only ``full`` behaviour (walk every file) is implemented here.

    Walk strategy (per disk):
        1. Call :func:`~personalscraper.indexer.merkle.guard_disk_mounted`.  On
           :class:`~personalscraper.indexer.merkle.DiskUnmountedError` or
           :class:`~personalscraper.indexer.merkle.DiskMismatchError` the disk is
           skipped with a warning; the scan continues on remaining disks.
        2. Walk the disk root via recursive :func:`os.scandir` calls.
           - Never follow symlinks (``entry.stat(follow_symlinks=False)``).
           - Skip any entry whose name is in :data:`EXCLUDED_NAMES` or starts with ``"._"``.
           - After visiting all children of a directory, upsert the ``path`` row
             with its current ``dir_mtime_ns``.
           - For each file (or symlink) entry, insert/update a ``media_file`` row
             with ``oshash=""`` (deferred sentinel) and ``enriched_at=NULL``.
        3. Track ``files_visited`` and ``dirs_visited`` counters.

    Lifecycle:
        A ``scan_run`` row is inserted at start (``status='running'``).  On
        success the row is updated to ``status='ok'`` with ``finished_at``.  On
        any unexpected exception the row is updated to ``status='failed'`` and the
        exception is re-raised.

    Notes on the ``path`` table:
        There is no ``path_repo``; ``path`` CRUD lives in
        :mod:`personalscraper.indexer.repos.disk_repo`.

    Args:
        disks: List of :class:`~personalscraper.indexer.schema.DiskRow` objects
            representing the disks to scan.  Unmounted / mismatched disks are
            skipped without aborting the scan.
        mode: The :class:`ScanMode` to use.  Only ``full`` walk semantics are
            implemented in this skeleton; other modes fall through to the same
            walk path until sub-phases 2.5 / 2.6 extend them.
        generation: Monotonically increasing generation counter stamped on every
            ``media_file`` row visited during this scan.
        conn: Open :class:`sqlite3.Connection` with ``isolation_level=None``
            (autocommit) or an active transaction managed by the caller.

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
            disk_filter=None,
            started_at=started_at,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        ),
    )

    files_visited = [0]  # mutable counter (list avoids nonlocal in nested helper)
    dirs_visited = [0]

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

            # Walk disk root.
            _walk_dir(conn, disk, mount, files_visited, dirs_visited, generation)

            # Write-through the path row for the disk root itself.
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
            error=str(exc),
        )
