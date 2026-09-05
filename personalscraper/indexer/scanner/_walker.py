"""Directory walk skeleton + visitor protocol for the scanner.

The scanner used to carry five near-identical recursive walkers
(``_walk_dir``, ``_walk_dir_full``, ``_walk_dir_full_buffered``,
``_walk_dir_quick`` and ``incremental._walk_dir_incremental``) that had
drifted apart on SIGTERM handling, entry sort order and stat-failure
logging.  They are collapsed into ONE traversal skeleton — :func:`walk` —
that drives per-directory / per-file :class:`ScanVisitor` callbacks and
owns the traversal control (recursion, ``os.scandir`` + sort, exclusion,
stat + error demotion, crash-resume skip, and the UNIFIED
SIGTERM / budget / checkpoint check at every file boundary, at parity with
the strictest legacy walker).

Provides:
- :func:`walk` / :class:`ScanVisitor` — the single walk skeleton + callback bundle.
- :class:`WalkBudget` / :class:`WalkCheckpoint` — traversal-control state owned by :func:`walk`.
- :class:`SkeletonVisitor` — records files with ``oshash=NULL`` (Stage-A deferred).
- :func:`_walk_dir` — thin backward-compatible wrapper over :func:`walk`.
- :func:`_list_dir_entries` — shared ``os.scandir`` listing primitive (ACC-08:
  the ONLY ``scandir`` call-site in ``scanner/``).
- :func:`_verify_dir_mtime_reliable` — one-time check that dir mtime is updated on child writes.
- :func:`_sample_fresh_fingerprints` — sample fresh tier-1 fingerprints for Merkle delta.
- :func:`_build_disk_fingerprints` — build FileFingerprint list from DB rows.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field

from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.fingerprint import round_mtime_ns
from personalscraper.indexer.merkle import FileFingerprint
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner._checkpoint import _maybe_checkpoint
from personalscraper.indexer.scanner._db_writes import (
    _safe_mtime_ns,
    _upsert_file_row,
    _upsert_path_row,
)
from personalscraper.indexer.scanner._exclusions import _relpath, _should_exclude
from personalscraper.indexer.scanner._shutdown import is_shutdown_requested
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


def _log_stat_failed(path: str, exc: OSError) -> None:
    """Log a stat() failure at the appropriate severity.

    macFUSE/NTFS-3G volumes occasionally expose ghost directory entries:
    ``os.scandir`` lists a name whose underlying inode cannot be resolved by
    ``stat()`` (errno 2 / ENOENT) regardless of Unicode normalisation. Those
    are filesystem-level inconsistencies the scanner cannot fix, so they are
    demoted to ``debug`` to keep the operational warning channel meaningful.
    Real failures (EACCES, EIO, etc.) stay at ``warning``.
    """
    if exc.errno == 2:
        log.debug("indexer.scan.stat_failed", path=path, errno=exc.errno, reason="ghost_dirent")
    else:
        log.warning("indexer.scan.stat_failed", path=path, errno=exc.errno, error_type=type(exc).__name__)


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


def _build_disk_fingerprints(
    conn: sqlite3.Connection,
    disk_id: int,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> list[FileFingerprint]:
    """Query non-deleted, fingerprinted ``media_file`` rows for *disk_id*.

    Used by the quick-mode Merkle short-circuit and incremental's mid-walk
    bulk-change guard: we recompute the Merkle root entirely from the
    database (zero filesystem reads) and compare it to the stored
    ``disk.merkle_root``. If they match, the disk is skipped entirely.

    Rows with ``oshash IS NULL`` (Stage A — file discovered but not yet
    enriched) are excluded so the merkle reflects only fully-fingerprinted
    files. This helper is the SINGLE SOURCE OF TRUTH for the fingerprint set:
    every Merkle-root consumer routes through it so a stored bucketed root is
    never compared against a raw recomputation. The consumers are
    :func:`personalscraper.indexer.scanner._scan_orchestrator._finalize_disk_after_walk` (the
    bootstrap path that writes the first-ever merkle),
    :func:`personalscraper.indexer.reconcile.detect_merkle_drift` (the
    ``library-doctor`` consistency probe), and
    :func:`personalscraper.indexer.repair._refresh_disk_merkle` (the
    ``library-repair`` post-cascade rewrite). Earlier revisions of this helper
    omitted the ``oshash IS NOT NULL`` filter, leaving the scanner-stored and
    detector-computed merkles to drift permanently against each other on every
    disk that contained any Stage-A row (DEV #14).

    The ``mtime_ns`` of each fingerprint is floored to *capability*'s
    granularity bucket via :func:`round_mtime_ns` so the Merkle root computed
    from these rows is FS-aware: on a coarse filesystem (HFS+ 1 s, exFAT 2 s)
    sub-bucket mtime jitter no longer defeats the Merkle short-circuit nor
    spuriously inflates :func:`~personalscraper.indexer.merkle.compute_merkle_delta`.
    For ``NTFS_MACFUSE`` (granularity 1, the default) the bucketing is the
    identity transform, so the resulting fingerprints — and any Merkle root or
    delta derived from them — are byte-identical to the legacy behaviour.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the disk whose files to query.
        capability: Per-disk :class:`FilesystemCapability` governing mtime
            bucketing.  Defaults to ``NTFS_MACFUSE`` (granularity 1 → identity),
            so an un-threaded caller is byte-identical to the legacy behaviour.

    Returns:
        List of :class:`~personalscraper.indexer.merkle.FileFingerprint` objects,
        one per non-deleted, fingerprinted ``media_file`` row belonging to the disk.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT mf.path_id, mf.size_bytes, mf.mtime_ns, mf.oshash
        FROM media_file mf
        JOIN path p ON mf.path_id = p.id
        WHERE p.disk_id = ?
          AND mf.deleted_at IS NULL
          AND mf.oshash IS NOT NULL
        """,
        (disk_id,),
    ).fetchall()
    return [
        FileFingerprint(
            path_id=r["path_id"],
            size=r["size_bytes"],
            mtime_ns=round_mtime_ns(r["mtime_ns"], capability),
            oshash=r["oshash"],
        )
        for r in rows
    ]


def _sample_fresh_fingerprints(
    conn: sqlite3.Connection,
    disk_id: int,
    mount: str,
    capability: FilesystemCapability = NTFS_MACFUSE,
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

    The freshly-sampled ``st_mtime_ns`` is floored to *capability*'s
    granularity bucket via :func:`round_mtime_ns` so it is comparable with the
    bucketed stored fingerprints from :func:`_build_disk_fingerprints`: BOTH
    sides bucket with the SAME capability, so
    :func:`~personalscraper.indexer.merkle.compute_merkle_delta` (bucketed-vs-
    bucketed) no longer counts sub-bucket mtime jitter on a coarse FS as a
    difference, and the bulk-change freeze guard cannot trip on a healthy disk.
    For ``NTFS_MACFUSE`` (granularity 1, the default) this is the identity
    transform — byte-identical to the legacy sample.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the disk whose files to sample.
        mount: Absolute mount point path for the disk.
        capability: Per-disk :class:`FilesystemCapability` governing mtime
            bucketing.  Defaults to ``NTFS_MACFUSE`` (granularity 1 → identity),
            so an un-threaded caller is byte-identical to the legacy behaviour.

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
          AND mf.oshash IS NOT NULL
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
                # Bucket the FS-side mtime so it matches the bucketed DB-side
                # stored fingerprint (both sides use the same capability).
                mtime_ns=round_mtime_ns(st.st_mtime_ns, capability),
                # Keep stored oshash — recomputing it defeats the purpose of a
                # lightweight sample.  Only size/mtime_ns are compared here.
                oshash=row["oshash"],
            )
        )
    return result


# ---------------------------------------------------------------------------
# Shared scandir listing primitive (ACC-08: the ONLY scandir site in scanner/)
# ---------------------------------------------------------------------------


def _list_dir_entries(dir_abs: str) -> list[os.DirEntry[str]]:
    """Materialise the directory entries of *dir_abs* via a single ``os.scandir``.

    This is the ONE ``os.scandir`` call-site in the whole ``scanner/`` package
    (DESIGN §10 ACC-08). Both the recursive :func:`walk` skeleton and the enrich
    mode's shallow NFO / artwork directory listings route through it so no other
    scanner module opens a directory handle directly.

    The scandir handle is closed before returning; the returned
    :class:`os.DirEntry` objects retain their cached type/stat info, so
    ``entry.is_file()`` / ``entry.is_dir()`` / ``entry.stat()`` remain usable by
    the caller afterwards (they lazily re-stat by path if needed).

    Args:
        dir_abs: Absolute path of the directory to list.

    Returns:
        The directory entries as a list, in raw filesystem order (callers sort
        when they need a deterministic traversal).

    Raises:
        OSError: Propagated verbatim from :func:`os.scandir` (the caller decides
            whether to swallow ``PermissionError`` / ``EIO`` / etc.).
    """
    with os.scandir(dir_abs) as it:
        return list(it)


# ---------------------------------------------------------------------------
# Walk skeleton + visitor protocol
# ---------------------------------------------------------------------------


@dataclass
class WalkBudget:
    """Time-budget state shared across the recursive walk (owned by :func:`walk`).

    ``budget_exhausted`` is a single-element list so the flag set deep in the
    recursion is visible to every enclosing frame AND to the mode driver that
    inspects it after the walk returns (it must not update the Merkle root from a
    partial snapshot).

    Attributes:
        budget_seconds: Wall-clock ceiling in seconds; ``None`` = unlimited.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_exhausted: Single-element flag set ``True`` on budget/SIGTERM cutoff.
    """

    budget_seconds: float | None = None
    started_at_monotonic: float = 0.0
    budget_exhausted: list[bool] = field(default_factory=lambda: [False])


@dataclass
class WalkCheckpoint:
    """Crash-resume + checkpoint cadence state shared across the walk.

    Attributes:
        scan_run_id: PK of the active ``scan_run`` row (checkpoint FK target).
        checkpoint_every: Files processed between ``scan_run.last_path`` writes.
        files_since_checkpoint: Single-element counter since the last checkpoint.
        resume_from: Single-element list holding the opaque path string of the
            last checkpoint (``None`` once the resume boundary is passed).
    """

    scan_run_id: int = 0
    checkpoint_every: int = 100
    files_since_checkpoint: list[int] = field(default_factory=lambda: [0])
    resume_from: list[str | None] = field(default_factory=lambda: [None])


class ScanVisitor:
    """Per-directory / per-file callback bundle consumed by :func:`walk`.

    A visitor OWNS the mode-specific DB writes and holds the mutable per-disk
    state (``conn``, ``disk``, ``generation`` and the ``files_visited`` /
    ``dirs_visited`` single-element counters). :func:`walk` OWNS the traversal
    control (recursion, ``os.scandir`` + sort, exclusion, stat + error demotion,
    crash-resume skip, and the unified SIGTERM / budget / checkpoint check).

    Sub-classes must implement :meth:`visit_file`; :meth:`enter_dir` and
    :meth:`leave_dir` carry the shared default (always recurse, write the path
    row through afterwards) which quick / incremental override for dir-mtime
    subtree skipping.

    Attributes:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being walked.
        generation: Scan generation stamped on every ``media_file`` row.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        disk: DiskRow,
        generation: int,
        files_visited: list[int],
        dirs_visited: list[int],
    ) -> None:
        """Bind the per-disk state shared with :func:`walk`."""
        assert disk.mount_path is not None  # guard: mount_path checked before walk
        self.conn = conn
        self.disk = disk
        self.generation = generation
        self.files_visited = files_visited
        self.dirs_visited = dirs_visited

    def enter_dir(self, entry: os.DirEntry[str], st: os.stat_result, rel: str) -> bool:
        """Decide whether to recurse into subdirectory *entry*.

        Args:
            entry: The :class:`os.DirEntry` of the subdirectory.
            st: Its ``lstat`` result (``follow_symlinks=False``).
            rel: The subdirectory's path relative to the disk mount.

        Returns:
            ``True`` to recurse (default); ``False`` to skip the subtree entirely
            (quick / incremental dir-mtime short-circuit).
        """
        return True

    def leave_dir(self, entry: os.DirEntry[str], st: os.stat_result, rel: str) -> None:
        """Write-through the ``path`` row after a subtree is fully visited.

        The default upserts ``dir_mtime_ns`` so the next quick/incremental scan
        can short-circuit an unchanged subtree. Only invoked when
        :meth:`enter_dir` returned ``True`` and the budget was not exhausted
        mid-subtree — identical to the legacy walkers.
        """
        _upsert_path_row(self.conn, self.disk.id, rel, st.st_mtime_ns)

    def visit_file(self, entry: os.DirEntry[str], st: os.stat_result, parent_rel: str) -> None:
        """Record one file (or symlink) entry. Mode-specific; must be overridden.

        Args:
            entry: The :class:`os.DirEntry` of the file.
            st: Its ``lstat`` result (``follow_symlinks=False``).
            parent_rel: The parent directory's path relative to the disk mount
                (pre-computed by :func:`walk` so every mode uses the same value
                the crash-resume / checkpoint path strings are built from).
        """
        raise NotImplementedError


def walk(
    root: str,
    visitor: ScanVisitor,
    *,
    budget: WalkBudget,
    shutdown: Callable[[], bool],
    checkpoint: WalkCheckpoint,
) -> None:
    """Recursively walk *root*, driving *visitor* callbacks (the ONE walk skeleton).

    Traversal control lives here — the single place SIGTERM / budget /
    checkpoint are handled, at parity with the strictest legacy walker (every
    file boundary tests the budget AND the shutdown request; the incremental
    walker historically checked only the budget — that drift gap is closed
    here). Per directory the order is: ``enter_dir`` → (recurse) → ``leave_dir``;
    per file: crash-resume skip → ``visit_file`` → checkpoint/budget/shutdown.

    The disk root's own ``path`` row is NOT written here (the mode driver /
    orchestrator upserts ``"."`` after the walk) — :func:`walk` only visits the
    root's children and their subtrees, exactly like the legacy walkers.

    Args:
        root: Absolute path of the directory to start walking (the disk mount).
        visitor: The :class:`ScanVisitor` carrying the mode-specific DB writes.
        budget: Shared :class:`WalkBudget` (time ceiling + exhausted flag).
        shutdown: Zero-arg predicate returning ``True`` when a clean shutdown was
            requested (normally
            :func:`personalscraper.indexer.scanner._shutdown.is_shutdown_requested`;
            injectable so tests can drive a mid-walk SIGTERM deterministically).
        checkpoint: Shared :class:`WalkCheckpoint` (resume cursor + cadence).
    """
    _walk_subtree(root, visitor, budget=budget, shutdown=shutdown, checkpoint=checkpoint)


def _walk_subtree(
    dir_abs: str,
    visitor: ScanVisitor,
    *,
    budget: WalkBudget,
    shutdown: Callable[[], bool],
    checkpoint: WalkCheckpoint,
) -> None:
    """Recursive body of :func:`walk` for a single directory *dir_abs*.

    See :func:`walk` for the ordering contract. Kept private and separate from
    :func:`walk` so the public entry point does not re-enter itself with a
    changing ``root`` argument.
    """
    # Bail out early if the budget was already exhausted by a sibling subtree.
    if budget.budget_exhausted[0]:
        return

    conn = visitor.conn
    disk = visitor.disk
    mount = disk.mount_path
    assert mount is not None  # guard: mount_path checked before the walk begins

    try:
        entries = sorted(_list_dir_entries(dir_abs), key=lambda e: e.name)
    except PermissionError:
        # PermissionError is swallowed (skip the unreadable dir); every other
        # OSError (EIO, ENOTCONN, …) propagates to the per-disk error handling.
        log.warning("indexer.scan.dir_permission_denied", path=dir_abs)
        return

    for entry in entries:
        if _should_exclude(entry.name):
            continue

        # Stat without following symlinks — this is the *only* stat call per entry.
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError as exc:
            _log_stat_failed(entry.path, exc)
            continue

        if entry.is_dir(follow_symlinks=False):
            visitor.dirs_visited[0] += 1
            rel = _relpath(mount, entry.path)
            if visitor.enter_dir(entry, st, rel):
                _walk_subtree(entry.path, visitor, budget=budget, shutdown=shutdown, checkpoint=checkpoint)
                # Stop iterating this directory if budget was exhausted in the
                # subtree — the parent's path row is intentionally NOT written.
                if budget.budget_exhausted[0]:
                    return
                # Write-through path row after all children have been visited.
                visitor.leave_dir(entry, st, rel)
        else:
            # Both regular files and symlinks land here.
            parent_rel = _relpath(mount, dir_abs)

            # --- crash-resume skip ---
            current_path_str = f"{disk.label}/{parent_rel}/{entry.name}"
            if checkpoint.resume_from[0] is not None:
                if current_path_str <= checkpoint.resume_from[0]:
                    continue  # still before the resume position
                # Past the resume boundary — clear it so remaining files process.
                checkpoint.resume_from[0] = None

            visitor.files_visited[0] += 1
            visitor.visit_file(entry, st, parent_rel)

            # --- unified checkpoint / budget / shutdown (strictest parity) ---
            checkpoint.files_since_checkpoint[0] += 1
            new_counter, exhausted = _maybe_checkpoint(
                conn,
                checkpoint.scan_run_id,
                current_path_str,
                checkpoint.files_since_checkpoint[0],
                checkpoint.checkpoint_every,
                budget.started_at_monotonic,
                budget.budget_seconds,
            )
            checkpoint.files_since_checkpoint[0] = new_counter
            if exhausted:
                budget.budget_exhausted[0] = True
                return

            # SIGTERM clean-shutdown bridge (sub-phase 4.9): treat a shutdown
            # request like budget exhaustion so the caller commits + checkpoints.
            if shutdown():
                budget.budget_exhausted[0] = True
                return


class SkeletonVisitor(ScanVisitor):
    """Records every file with ``oshash=NULL`` (Stage-A deferred, migration 002).

    The default visitor used by any scan mode that does not fingerprint at walk
    time. Symlinks are recorded but never fingerprinted (``oshash`` stays NULL).
    """

    def visit_file(self, entry: os.DirEntry[str], st: os.stat_result, parent_rel: str) -> None:
        """Upsert a tier-0 ``media_file`` row (no oshash, no stream extraction)."""
        path_id = _upsert_path_row(self.conn, self.disk.id, parent_rel, 0)
        ctime_ns: int | None = st.st_ctime_ns if hasattr(st, "st_ctime_ns") else None
        _upsert_file_row(
            self.conn,
            path_id=path_id,
            filename=entry.name,
            size_bytes=st.st_size,
            mtime_ns=_safe_mtime_ns(st.st_mtime_ns),
            ctime_ns=ctime_ns,
            generation=self.generation,
        )


class DirMtimeSkipVisitor(SkeletonVisitor):
    """Adds the dir-mtime subtree short-circuit shared by quick + incremental.

    An unchanged directory — the stored ``path.dir_mtime_ns`` equals the live
    value, both floored to the disk capability's granularity bucket — is skipped
    entirely (zero file reads in that subtree). This is the ONE implementation of
    the dir-mtime skip that ``_walk_dir_quick`` and ``_walk_dir_incremental``
    used to carry as byte-identical copies. Quick mode uses this visitor directly
    (inheriting the Stage-A :meth:`SkeletonVisitor.visit_file`); incremental mode
    subclasses it and overrides :meth:`visit_file` with its drift/rename logic.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being walked.
        generation: Scan generation stamped on every ``media_file`` row.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        dir_mtime_reliable: When ``False`` the skip is disabled and every subtree
            is walked (fallback to per-file fingerprinting).
        capability: Per-disk :class:`FilesystemCapability` governing the mtime
            granularity bucketing of the stored-vs-live comparison.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        disk: DiskRow,
        generation: int,
        files_visited: list[int],
        dirs_visited: list[int],
        dir_mtime_reliable: bool,
        capability: FilesystemCapability = NTFS_MACFUSE,
    ) -> None:
        """Bind the per-disk state plus the dir-mtime skip configuration."""
        super().__init__(conn, disk, generation, files_visited, dirs_visited)
        self.dir_mtime_reliable = dir_mtime_reliable
        self.capability = capability

    def enter_dir(self, entry: os.DirEntry[str], st: os.stat_result, rel: str) -> bool:
        """Skip an unchanged subtree (dir-mtime match) or recurse into it."""
        if self.dir_mtime_reliable:
            # Both the stored and live dir mtimes are bucketed via the disk
            # capability so sub-bucket jitter on a coarse FS does not force a
            # spurious re-walk (NTFS granularity 1 → identity → exact compare).
            existing_path = disk_repo.get_path_by_disk_and_relpath(self.conn, self.disk.id, rel)
            if (
                existing_path is not None
                and existing_path.dir_mtime_ns is not None
                and round_mtime_ns(existing_path.dir_mtime_ns, self.capability)
                == round_mtime_ns(st.st_mtime_ns, self.capability)
            ):
                log.debug("indexer.scan.dir_unchanged", path=entry.path, dir_mtime_ns=st.st_mtime_ns)
                return False
        return True


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
    """Backward-compatible skeleton walk — a thin wrapper over :func:`walk`.

    Preserves the historical positional signature (still re-exported from the
    ``scanner`` package and used by the orchestrator's fallback branch for any
    future mode) while delegating the traversal to the unified :func:`walk`
    skeleton driving a :class:`SkeletonVisitor`. Behaviour is byte-identical:
    every file is recorded with ``oshash=NULL`` and the path row is written
    through after each subtree.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` that owns this subtree.
        dir_abs: Absolute path of the current directory to scan.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation stamped on every ``media_file`` row.
        resume_from: Single-element crash-resume cursor (or ``None``).
        files_since_checkpoint: Single-element counter since the last checkpoint.
        budget_exhausted: Single-element budget/SIGTERM flag.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_seconds: Maximum wall-clock seconds for the scan; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
    """
    visitor = SkeletonVisitor(conn, disk, generation, files_visited, dirs_visited)
    walk(
        dir_abs,
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
