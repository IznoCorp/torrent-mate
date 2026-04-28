"""Directory walk helpers for the scanner.

Provides:
- :func:`_walk_dir` — skeleton walk (incremental/enrich modes).
- :func:`_walk_dir_full` — full-mode walk with fingerprinting.
- :func:`_walk_dir_full_buffered` — full-mode walk with auto-flush of insert buffer.
- :func:`_walk_dir_quick` — quick-mode walk with dir-mtime subtree skipping.
- :func:`_verify_dir_mtime_reliable` — one-time check that dir mtime is updated on child writes.
- :func:`_sample_fresh_fingerprints` — sample fresh tier-1 fingerprints for Merkle delta.
- :func:`_build_disk_fingerprints` — build FileFingerprint list from DB rows.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from typing import Any

from personalscraper.indexer import fingerprint
from personalscraper.indexer.merkle import FileFingerprint
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner._checkpoint import _maybe_checkpoint
from personalscraper.indexer.scanner._db_writes import (
    _INSERT_BATCH_SIZE,
    _compute_oshash,
    _flush_insert_buffer,
    _safe_mtime_ns,
    _upsert_file_row,
    _upsert_path_row,
)
from personalscraper.indexer.scanner._exclusions import _relpath, _should_exclude
from personalscraper.indexer.scanner._shutdown import is_shutdown_requested
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


# ---------------------------------------------------------------------------
# Quick-mode reliability check
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


# ---------------------------------------------------------------------------
# Fingerprint helpers for Merkle
# ---------------------------------------------------------------------------


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


def _sample_fresh_fingerprints(
    conn: sqlite3.Connection,
    disk_id: int,
    mount: str,
) -> list[FileFingerprint]:
    """Sample fresh tier-1 fingerprints for all known paths on *disk_id*.

    Performs a ``stat()`` call for every ``media_file`` row that belongs to
    *disk_id* in the database and is not soft-deleted.  This is used
    exclusively by the bulk-change guard in :func:`_scan_disk_quick` to compare
    the current filesystem state against the stored fingerprints without walking
    the entire directory tree.

    Files that are no longer readable (``OSError``) are silently skipped so
    that a few missing files do not inflate the delta artificially.  Deletions
    are handled by regular drift reconciliation; the delta guard is only
    concerned with mass-change events (restores, disk swaps).

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the disk whose files to sample.
        mount: Absolute mount point path for the disk.

    Returns:
        List of :class:`~personalscraper.indexer.merkle.FileFingerprint` objects
        reflecting the current filesystem state for each readable file.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT mf.path_id, p.rel_path, mf.filename, mf.oshash
        FROM media_file mf
        JOIN path p ON mf.path_id = p.id
        WHERE p.disk_id = ?
          AND mf.deleted_at IS NULL
        """,
        (disk_id,),
    ).fetchall()

    result: list[FileFingerprint] = []
    for row in rows:
        abs_path = os.path.join(mount, row["rel_path"], row["filename"])
        try:
            st = os.stat(abs_path, follow_symlinks=False)
        except OSError:
            # File unreadable or deleted — skip; delta stays conservative.
            continue
        result.append(
            FileFingerprint(
                path_id=row["path_id"],
                size=st.st_size,
                mtime_ns=st.st_mtime_ns,
                # Keep stored oshash — recomputing it defeats the purpose of a
                # lightweight sample.  Only size/mtime_ns are compared here.
                oshash=row["oshash"],
            )
        )
    return result


# ---------------------------------------------------------------------------
# Skeleton walk (_walk_dir)
# ---------------------------------------------------------------------------


def _walk_dir(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
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
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Files at or before this path are skipped;
            set to ``None`` once the resume position is passed.
        files_since_checkpoint: Single-element mutable counter for files processed
            since the last :func:`_checkpoint_scan_run` write.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded.  Callers should stop the walk when this becomes ``True``.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start,
            used to measure elapsed time against ``budget_seconds``.
        budget_seconds: Maximum wall-clock seconds for the scan; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row (needed by checkpoint helper).
        checkpoint_every: How many files to process between checkpoint writes.
    """
    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

    # Bail out early if the budget was already exhausted by a sibling subtree.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

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
            _walk_dir(
                conn,
                disk,
                entry.path,
                files_visited,
                dirs_visited,
                generation,
                resume_from,
                files_since_checkpoint,
                budget_exhausted,
                started_at_monotonic,
                budget_seconds,
                scan_run_id,
                checkpoint_every,
            )

            # Stop iterating this directory if budget was exhausted in the subtree.
            if budget_exhausted is not None and budget_exhausted[0]:
                return

            # Write-through path row for this directory.
            rel = _relpath(disk.mount_path, entry.path)
            _upsert_path_row(conn, disk.id, rel, st.st_mtime_ns)

        else:
            # Both regular files and symlinks land here.
            # Symlinks are recorded but never fingerprinted (oshash stays NULL).

            # --- crash-resume skip ---
            if resume_from is not None and resume_from[0] is not None:
                parent_rel_r = _relpath(disk.mount_path, dir_abs)
                current_path_str_r = f"{disk.label}/{parent_rel_r}/{entry.name}"
                if current_path_str_r <= resume_from[0]:
                    continue  # still before the resume position
                # Past the resume boundary — clear it so remaining files are processed.
                resume_from[0] = None

            files_visited[0] += 1
            parent_rel = _relpath(disk.mount_path, dir_abs)
            path_id = _upsert_path_row(conn, disk.id, parent_rel, 0)
            ctime_ns: int | None = st.st_ctime_ns if hasattr(st, "st_ctime_ns") else None
            _upsert_file_row(
                conn,
                path_id=path_id,
                filename=entry.name,
                size_bytes=st.st_size,
                mtime_ns=_safe_mtime_ns(st.st_mtime_ns),
                ctime_ns=ctime_ns,
                generation=generation,
            )

            # --- checkpoint / budget check ---
            if files_since_checkpoint is not None and budget_exhausted is not None:
                files_since_checkpoint[0] += 1
                parent_rel_c = _relpath(disk.mount_path, dir_abs)
                current_path_str_c = f"{disk.label}/{parent_rel_c}/{entry.name}"
                new_counter, exhausted = _maybe_checkpoint(
                    conn,
                    scan_run_id,
                    current_path_str_c,
                    files_since_checkpoint[0],
                    checkpoint_every,
                    started_at_monotonic,
                    budget_seconds,
                )
                files_since_checkpoint[0] = new_counter
                if exhausted:
                    budget_exhausted[0] = True
                    return

                # SIGTERM clean-shutdown bridge (sub-phase 4.9).  Treats a
                # shutdown request like budget exhaustion: the caller's
                # checkpoint logic will commit and update scan_run.
                if is_shutdown_requested():
                    budget_exhausted[0] = True
                    return


# ---------------------------------------------------------------------------
# Full-mode walk
# ---------------------------------------------------------------------------


def _walk_dir_full(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    insert_buffer: list[Any],
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
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
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Files at or before this path are skipped;
            set to ``None`` once the resume position is passed.
        files_since_checkpoint: Single-element mutable counter for files processed
            since the last :func:`_checkpoint_scan_run` write.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded.  Callers should stop the walk when this becomes ``True``.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start,
            used to measure elapsed time against ``budget_seconds``.
        budget_seconds: Maximum wall-clock seconds for the scan; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row (needed by checkpoint helper).
        checkpoint_every: How many files to process between checkpoint writes.
    """
    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

    # Bail out early if the budget was already exhausted by a sibling subtree.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

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
            _walk_dir_full(
                conn,
                disk,
                entry.path,
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

            # Stop iterating this directory if budget was exhausted in the subtree.
            if budget_exhausted is not None and budget_exhausted[0]:
                return

            # Write-through path row after all children have been visited.
            rel = _relpath(disk.mount_path, entry.path)
            _upsert_path_row(conn, disk.id, rel, st.st_mtime_ns)

        else:
            # Both regular files and symlinks land here.

            # --- crash-resume skip ---
            if resume_from is not None and resume_from[0] is not None:
                parent_rel_r = _relpath(disk.mount_path, dir_abs)
                current_path_str_r = f"{disk.label}/{parent_rel_r}/{entry.name}"
                if current_path_str_r <= resume_from[0]:
                    continue  # still before the resume position
                # Past the resume boundary — clear it so remaining files are processed.
                resume_from[0] = None

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

            # --- checkpoint / budget check ---
            if files_since_checkpoint is not None and budget_exhausted is not None:
                files_since_checkpoint[0] += 1
                parent_rel_c = _relpath(disk.mount_path, dir_abs)
                current_path_str_c = f"{disk.label}/{parent_rel_c}/{entry.name}"
                new_counter, exhausted = _maybe_checkpoint(
                    conn,
                    scan_run_id,
                    current_path_str_c,
                    files_since_checkpoint[0],
                    checkpoint_every,
                    started_at_monotonic,
                    budget_seconds,
                )
                files_since_checkpoint[0] = new_counter
                if exhausted:
                    budget_exhausted[0] = True
                    return

                # SIGTERM clean-shutdown bridge (sub-phase 4.9).  Treats a
                # shutdown request like budget exhaustion: the caller's
                # checkpoint logic will commit and update scan_run.
                if is_shutdown_requested():
                    budget_exhausted[0] = True
                    return


def _walk_dir_full_buffered(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    insert_buffer: list[Any],
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
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
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Forwarded to :func:`_walk_dir_full`.
        files_since_checkpoint: Single-element mutable counter forwarded to the walk.
        budget_exhausted: Single-element flag; forwarded to :func:`_walk_dir_full`.
        started_at_monotonic: :func:`time.monotonic` timestamp forwarded to the walk.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
    """
    _walk_dir_full(
        conn,
        disk,
        dir_abs,
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

    # Flush whenever the buffer exceeds the batch size threshold.
    # Skip flush if budget was exhausted — partial buffer state will be discarded
    # and the rows will be re-processed after a crash-resume.
    if budget_exhausted is None or not budget_exhausted[0]:
        if len(insert_buffer) >= _INSERT_BATCH_SIZE:
            _flush_insert_buffer(conn, insert_buffer)


# ---------------------------------------------------------------------------
# Quick-mode walk
# ---------------------------------------------------------------------------


def _walk_dir_quick(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    dir_mtime_reliable: bool,
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
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
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Files at or before this path are skipped;
            set to ``None`` once the resume position is passed.
        files_since_checkpoint: Single-element mutable counter for files processed
            since the last :func:`_checkpoint_scan_run` write.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded.  Callers should stop the walk when this becomes ``True``.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start,
            used to measure elapsed time against ``budget_seconds``.
        budget_seconds: Maximum wall-clock seconds for the scan; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row (needed by checkpoint helper).
        checkpoint_every: How many files to process between checkpoint writes.
    """
    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

    # Bail out early if the budget was already exhausted by a sibling subtree.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

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
            _walk_dir_quick(
                conn,
                disk,
                entry.path,
                files_visited,
                dirs_visited,
                generation,
                dir_mtime_reliable,
                resume_from,
                files_since_checkpoint,
                budget_exhausted,
                started_at_monotonic,
                budget_seconds,
                scan_run_id,
                checkpoint_every,
            )

            # Stop iterating this directory if budget was exhausted in the subtree.
            if budget_exhausted is not None and budget_exhausted[0]:
                return

            # Update dir_mtime_ns to the current value so next scan can short-circuit.
            _upsert_path_row(conn, disk.id, rel, current_mtime_ns)

        else:
            # File (or symlink) — tier-1 fingerprint only (oshash stays NULL in quick mode).

            # --- crash-resume skip ---
            if resume_from is not None and resume_from[0] is not None:
                parent_rel_r = _relpath(disk.mount_path, dir_abs)
                current_path_str_r = f"{disk.label}/{parent_rel_r}/{entry.name}"
                if current_path_str_r <= resume_from[0]:
                    continue  # still before the resume position
                # Past the resume boundary — clear it so remaining files are processed.
                resume_from[0] = None

            files_visited[0] += 1
            parent_rel = _relpath(disk.mount_path, dir_abs)
            path_id = _upsert_path_row(conn, disk.id, parent_rel, 0)
            ctime_ns_val: int | None = st.st_ctime_ns if hasattr(st, "st_ctime_ns") else None
            _upsert_file_row(
                conn,
                path_id=path_id,
                filename=entry.name,
                size_bytes=st.st_size,
                mtime_ns=_safe_mtime_ns(st.st_mtime_ns),
                ctime_ns=ctime_ns_val,
                generation=generation,
            )

            # --- checkpoint / budget check ---
            if files_since_checkpoint is not None and budget_exhausted is not None:
                files_since_checkpoint[0] += 1
                parent_rel_c = _relpath(disk.mount_path, dir_abs)
                current_path_str_c = f"{disk.label}/{parent_rel_c}/{entry.name}"
                new_counter, exhausted = _maybe_checkpoint(
                    conn,
                    scan_run_id,
                    current_path_str_c,
                    files_since_checkpoint[0],
                    checkpoint_every,
                    started_at_monotonic,
                    budget_seconds,
                )
                files_since_checkpoint[0] = new_counter
                if exhausted:
                    budget_exhausted[0] = True
                    return

                # SIGTERM clean-shutdown bridge (sub-phase 4.9).  Treats a
                # shutdown request like budget exhaustion: the caller's
                # checkpoint logic will commit and update scan_run.
                if is_shutdown_requested():
                    budget_exhausted[0] = True
                    return
