"""Incremental scan mode driver."""

from __future__ import annotations

import os
import re
import sqlite3

from personalscraper.indexer import drift as _drift
from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.fingerprint import normalize_tier1
from personalscraper.indexer.merkle import (
    DiskBulkChangeDetected,
    compute_merkle_delta,
    compute_merkle_root,
)
from personalscraper.indexer.repos import disk_repo, file_repo
from personalscraper.indexer.scanner._db_writes import (
    _compute_oshash,
    _safe_mtime_ns,
    _upsert_file_row,
    _upsert_path_row,
)
from personalscraper.indexer.scanner._exclusions import _relpath, _should_exclude
from personalscraper.indexer.scanner._walker import (
    _build_disk_fingerprints,
    _sample_fresh_fingerprints,
)
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

__all__ = [
    "_scan_disk_incremental",
    "_walk_dir_incremental",
]


def _scan_disk_incremental(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    disks_skipped: list[int],
    dir_mtime_reliable: bool,
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
    confirm_bulk_change: bool = False,
    merkle_delta_freeze_threshold: float = 0.50,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> None:
    """Run the incremental-mode walk for a single disk.

    Incremental mode builds on quick-mode semantics (Merkle short-circuit +
    dir-mtime subtree skip) but adds an OSHash recompute step for every file
    whose tier-1 fingerprint (size, mtime_ns, ctime_ns) differs from the stored
    value.  This allows the scanner to distinguish:

    - **Mtime/size drift only** (content unchanged): update tier-1 fields, no
      repair enqueue.
    - **Rename** (same content, different path): delegate to
      :func:`~personalscraper.indexer.drift.detect_rename`; the drift module
      updates the ``path_id`` / ``filename`` in-place.
    - **OSHash collision** (multiple candidates with the same hash): the drift
      module enqueues repair for the ambiguous rows.
    - **Real content drift** (oshash changed): call
      :func:`~personalscraper.indexer.drift.enqueue_repair` with
      ``reason='content_drift'``.

    The incremental walk uses the same Merkle short-circuit guard as quick mode:
    if the DB-computed Merkle root matches ``disk.merkle_root`` the entire disk
    is skipped.  On Merkle miss, a bulk-change check samples fresh fingerprints
    to protect against accidental mass-restores.

    After a successful walk, the disk's Merkle root is recomputed from the
    updated ``media_file`` state and stored so the next scan can short-circuit.

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
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).
        files_since_checkpoint: Single-element mutable counter forwarded to
            the inner walk.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded inside the walk.
        started_at_monotonic: :func:`time.monotonic` timestamp forwarded to the walk.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
        confirm_bulk_change: When ``True``, bypass the Merkle delta freeze guard
            and proceed with the walk even when the delta exceeds
            *merkle_delta_freeze_threshold*.
        merkle_delta_freeze_threshold: Halt if the Merkle delta exceeds this
            fraction (0.0–1.0).
        capability: Per-disk :class:`FilesystemCapability` governing tier-1
            normalisation at the comparison site (ctime drop / mtime bucketing).
            Defaults to ``NTFS_MACFUSE`` so an un-threaded caller is byte-identical
            to the legacy behaviour.

    Raises:
        DiskBulkChangeDetected: When the Merkle delta exceeds
            *merkle_delta_freeze_threshold* and *confirm_bulk_change* is ``False``.
    """
    # --- Merkle short-circuit (same as quick mode) ---
    fingerprints = _build_disk_fingerprints(conn, disk.id)
    current_root = compute_merkle_root(fingerprints)

    if disk.merkle_root is not None and current_root == disk.merkle_root:
        log.info(
            "indexer.scan.merkle_match",
            disk_uuid=disk.uuid,
            label=disk.label,
            merkle_root=current_root,
        )
        disks_skipped[0] += 1
        return

    log.info(
        "indexer.scan.merkle_miss",
        disk_uuid=disk.uuid,
        label=disk.label,
        stored_root=disk.merkle_root,
        computed_root=current_root,
    )

    # --- Bulk-change guard (same as quick mode, on Merkle miss) ---
    if not confirm_bulk_change and disk.merkle_root is not None:
        fresh_fps = _sample_fresh_fingerprints(conn, disk.id, mount)
        delta = compute_merkle_delta(fingerprints, fresh_fps)
        if delta > merkle_delta_freeze_threshold:
            log.warning(
                "indexer.merkle.delta_freeze",
                disk_uuid=disk.uuid,
                label=disk.label,
                delta=delta,
                threshold=merkle_delta_freeze_threshold,
            )
            raise DiskBulkChangeDetected(delta=delta, disk_uuid=disk.uuid)

    # --- Incremental walk ---
    _walk_dir_incremental(
        conn,
        disk,
        mount,
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
        capability,
    )

    # Skip post-walk bookkeeping if the budget was exhausted — partial state is
    # preserved for crash-resume; Merkle root must not be updated to an incomplete
    # snapshot.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

    # Write-through the path row for the disk root itself.
    try:
        root_st = os.stat(mount, follow_symlinks=False)
        _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
    except OSError:
        log.warning("indexer.scan.root_stat_failed", mount_path=mount)

    # Recompute and persist the updated Merkle root.
    updated_fingerprints = _build_disk_fingerprints(conn, disk.id)
    new_root = compute_merkle_root(updated_fingerprints)
    disk_repo.update_merkle_root(conn, disk.id, new_root)
    log.debug("indexer.scan.merkle_root_updated", disk_id=disk.id, merkle_root=new_root)


def _walk_dir_incremental(
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
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> None:
    """Recursively walk *dir_abs* in incremental mode.

    Incremental mode extends quick-mode dir-mtime subtree skipping with an
    OSHash recompute step for files whose tier-1 fingerprint has changed.  The
    OSHash comparison enables accurate rename detection and distinguishes
    cosmetic mtime drift from real content changes.

    Per-file logic for files with a tier-1 mismatch against the stored row:

    1. Recompute OSHash for video files (non-video/symlinks skip this step).
    2. Compare the recomputed hash to the stored ``oshash`` column:

       a. **Match** — content is unchanged (mtime/size drift only): update tier-1
          fields in place, no repair enqueue.
       b. **Mismatch and oshash is not empty** — call
          :func:`~personalscraper.indexer.drift.detect_rename`:

          - ``rename_applied`` → drift module already updated the row.
          - ``oshash_collision`` → drift module already enqueued repair.
          - ``no_match`` → real content drift; call
            :func:`~personalscraper.indexer.drift.enqueue_repair` with
            ``reason='content_drift'``.

       c. **Mismatch and no oshash** (non-video file) — treat as content drift
          and enqueue repair directly.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` owning this subtree.
        dir_abs: Absolute path of the current directory.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation stamped on every ``media_file`` row.
        dir_mtime_reliable: When ``False``, dir-mtime skip is disabled.
        resume_from: Single-element list holding the opaque path string of the
            last checkpoint (or ``None``).
        files_since_checkpoint: Single-element mutable counter.
        budget_exhausted: Single-element flag; set to ``True`` when budget exceeded.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
        capability: Per-disk :class:`FilesystemCapability` used to normalise the
            tier-1 fingerprints before comparison.  Defaults to ``NTFS_MACFUSE``
            (legacy behaviour: ctime kept, mtime unrounded).
    """
    from personalscraper.indexer.scanner._checkpoint import _maybe_checkpoint  # noqa: PLC0415

    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

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
                # Check stored dir_mtime_ns — skip unchanged subtrees.
                existing_path = disk_repo.get_path_by_disk_and_relpath(conn, disk.id, rel)
                if existing_path is not None and existing_path.dir_mtime_ns == current_mtime_ns:
                    log.debug(
                        "indexer.scan.dir_unchanged",
                        path=entry.path,
                        dir_mtime_ns=current_mtime_ns,
                    )
                    continue

            # Recurse into changed (or all, when dir-mtime is unreliable) subtrees.
            _walk_dir_incremental(
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
                capability,
            )

            if budget_exhausted is not None and budget_exhausted[0]:
                return

            # Update dir_mtime_ns so next scan can short-circuit.
            _upsert_path_row(conn, disk.id, rel, current_mtime_ns)

        else:
            # File (or symlink) — incremental fingerprint logic.

            # --- crash-resume skip ---
            if resume_from is not None and resume_from[0] is not None:
                parent_rel_r = _relpath(disk.mount_path, dir_abs)
                current_path_str_r = f"{disk.label}/{parent_rel_r}/{entry.name}"
                if current_path_str_r <= resume_from[0]:
                    continue
                resume_from[0] = None

            files_visited[0] += 1
            parent_rel = _relpath(disk.mount_path, dir_abs)
            path_id = _upsert_path_row(conn, disk.id, parent_rel, 0)
            ctime_ns_val: int | None = st.st_ctime_ns if hasattr(st, "st_ctime_ns") else None
            mtime_ns_val = _safe_mtime_ns(st.st_mtime_ns)
            is_symlink = entry.is_symlink()

            existing = file_repo.find_by_path_and_filename(conn, path_id, entry.name)

            if existing is None:
                # New file — compute oshash.  For video files attempt rename
                # detection before inserting a fresh row.  A rename appears as
                # a new path whose oshash matches an existing DB row at a
                # different location (the old location is now gone from disk).
                oshash_value = _compute_oshash(entry.path, entry.name, is_symlink)

                if oshash_value is not None:
                    # Check whether a candidate with this oshash already exists
                    # on the disk at a different path.  If so, try rename
                    # detection first so we don't hit the UNIQUE constraint
                    # (path_id, filename) when the old row is updated in place.
                    conn.row_factory = sqlite3.Row
                    candidate = conn.execute(
                        """
                        SELECT mf.id
                          FROM media_file mf
                          JOIN path p ON p.id = mf.path_id
                         WHERE mf.oshash = ?
                           AND p.disk_id = ?
                           AND NOT (mf.path_id = ? AND mf.filename = ?)
                           AND mf.deleted_at IS NULL
                         LIMIT 1
                        """,
                        (oshash_value, disk.id, path_id, entry.name),
                    ).fetchone()
                    conn.row_factory = None

                    if candidate is not None:
                        # There is at least one existing row with this oshash —
                        # insert a temporary stub row so detect_rename can use
                        # the current (path_id, filename, size) for its size guard
                        # and old-path-existence check.
                        _upsert_file_row(
                            conn,
                            path_id=path_id,
                            filename=entry.name,
                            size_bytes=st.st_size,
                            mtime_ns=mtime_ns_val,
                            ctime_ns=ctime_ns_val,
                            generation=generation,
                            oshash_value=oshash_value,
                        )
                        # Now detect_rename can query (path_id, filename) to get
                        # current size. If it applies a rename, it UPDATES the old
                        # row to (path_id, filename) — but that would collide with
                        # the stub row we just inserted.  To avoid the UNIQUE
                        # constraint, delete the stub first then let detect_rename
                        # update the old row.
                        conn.execute(
                            "DELETE FROM media_file WHERE path_id = ? AND filename = ? AND oshash = ?",
                            (path_id, entry.name, oshash_value),
                        )
                        outcome = _drift.detect_rename(
                            conn,
                            disk.id,
                            path_id,
                            entry.name,
                            oshash_value,
                        )
                        if outcome == "rename_applied":
                            # The old row was updated in-place to (path_id, entry.name).
                            # Update its tier-1 fields to reflect the current stat.
                            conn.execute(
                                """
                                UPDATE media_file
                                   SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                       scan_generation = ?
                                 WHERE path_id = ? AND filename = ?
                                """,
                                (st.st_size, mtime_ns_val, ctime_ns_val, generation, path_id, entry.name),
                            )
                            log.info(
                                "indexer.scan.incremental.rename_applied",
                                new_path_id=path_id,
                                new_filename=entry.name,
                            )
                        else:
                            # no_match or oshash_collision — insert as a new file.
                            _upsert_file_row(
                                conn,
                                path_id=path_id,
                                filename=entry.name,
                                size_bytes=st.st_size,
                                mtime_ns=mtime_ns_val,
                                ctime_ns=ctime_ns_val,
                                generation=generation,
                                oshash_value=oshash_value,
                            )
                    else:
                        # No candidate with this oshash on this disk — genuinely
                        # new file, plain insert.
                        _upsert_file_row(
                            conn,
                            path_id=path_id,
                            filename=entry.name,
                            size_bytes=st.st_size,
                            mtime_ns=mtime_ns_val,
                            ctime_ns=ctime_ns_val,
                            generation=generation,
                            oshash_value=oshash_value,
                        )
                else:
                    # Non-video file (no oshash) — plain insert, no rename detection.
                    _upsert_file_row(
                        conn,
                        path_id=path_id,
                        filename=entry.name,
                        size_bytes=st.st_size,
                        mtime_ns=mtime_ns_val,
                        ctime_ns=ctime_ns_val,
                        generation=generation,
                        oshash_value=None,
                    )
            else:
                # Existing file — compare tier-1 fingerprint (FS-aware).  The
                # capability decides whether ctime participates and whether the
                # mtime is bucketed; for NTFS this is byte-identical to the
                # legacy ``(size, mtime_ns, ctime_ns)`` tuples.  Storage of the
                # tier-1 fields below stays raw — only the comparison normalises.
                t1_stored = normalize_tier1(existing.size_bytes, existing.mtime_ns, existing.ctime_ns or 0, capability)
                t1_current = normalize_tier1(st.st_size, mtime_ns_val, ctime_ns_val or 0, capability)

                if t1_current == t1_stored:
                    # Tier-1 unchanged — bump generation only (cheap skip).
                    conn.execute(
                        "UPDATE media_file SET scan_generation = ? WHERE id = ?",
                        (generation, existing.id),
                    )
                else:
                    # Tier-1 mismatch — recompute OSHash for video files to determine
                    # whether the content actually changed or just the metadata.
                    new_oshash = _compute_oshash(entry.path, entry.name, is_symlink)

                    if new_oshash is not None and new_oshash == existing.oshash:
                        # OSHash matches stored value: content unchanged (mtime drift
                        # only).  Update tier-1 fields; no repair enqueue needed.
                        conn.execute(
                            """
                            UPDATE media_file
                               SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                   scan_generation = ?
                             WHERE id = ?
                            """,
                            (st.st_size, mtime_ns_val, ctime_ns_val, generation, existing.id),
                        )
                        log.debug(
                            "indexer.scan.incremental.tier1_drift_only",
                            file_id=existing.id,
                            filename=entry.name,
                        )
                    elif new_oshash is not None:
                        # OSHash changed — attempt rename detection via drift module.
                        # First persist updated tier-1 and the new oshash so
                        # detect_rename can find the current row by path.
                        conn.execute(
                            """
                            UPDATE media_file
                               SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                   oshash = ?, scan_generation = ?
                             WHERE id = ?
                            """,
                            (st.st_size, mtime_ns_val, ctime_ns_val, new_oshash, generation, existing.id),
                        )
                        outcome = _drift.detect_rename(
                            conn,
                            disk.id,
                            path_id,
                            entry.name,
                            new_oshash,
                        )
                        if outcome == "no_match":
                            # No rename candidate found — this is real content drift.
                            _drift.enqueue_repair(conn, existing.id, "content_drift")
                            log.info(
                                "indexer.scan.incremental.content_drift",
                                file_id=existing.id,
                                filename=entry.name,
                            )
                        # rename_applied and oshash_collision are handled by drift module.
                    else:
                        # Non-video file (no oshash available) with tier-1 mismatch —
                        # treat as content drift; update tier-1 and enqueue repair.
                        conn.execute(
                            """
                            UPDATE media_file
                               SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                   scan_generation = ?
                             WHERE id = ?
                            """,
                            (st.st_size, mtime_ns_val, ctime_ns_val, generation, existing.id),
                        )
                        _drift.enqueue_repair(conn, existing.id, "content_drift")
                        log.info(
                            "indexer.scan.incremental.content_drift_no_oshash",
                            file_id=existing.id,
                            filename=entry.name,
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


# ---------------------------------------------------------------------------
# Artwork filename constants
# ---------------------------------------------------------------------------

# Canonical artwork filenames checked during enrich (Kodi convention).
# Matched lowercase against entry.name.lower() to handle case-insensitive FS.
_ARTWORK_FILENAMES: dict[str, str] = {
    "poster.jpg": "poster",
    "poster.png": "poster",
    "fanart.jpg": "fanart",
    "fanart.png": "fanart",
    "banner.jpg": "banner",
    "banner.png": "banner",
    "landscape.jpg": "landscape",
    "landscape.png": "landscape",
    "clearlogo.png": "clearlogo",
    "clearlogo.jpg": "clearlogo",
    "clearart.png": "clearart",
    "clearart.jpg": "clearart",
    "discart.png": "discart",
    "discart.jpg": "discart",
    "characterart.png": "characterart",
    "characterart.jpg": "characterart",
}

# MediaElch / Plex local-artwork suffixes. Matched against the trailing portion
# of the filename (e.g. "Movie Title (2020)-poster.jpg" → suffix "-poster.jpg").
# This is the format produced by MediaElch (the project's manual scraper
# fallback) and used by Plex local-art agents, both very common in real
# libraries. Without these the canonical-only pattern misses the artwork even
# though it sits next to the video file.
_ARTWORK_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("-poster.jpg", "poster"),
    ("-poster.png", "poster"),
    ("-fanart.jpg", "fanart"),
    ("-fanart.png", "fanart"),
    ("-banner.jpg", "banner"),
    ("-banner.png", "banner"),
    ("-landscape.jpg", "landscape"),
    ("-landscape.png", "landscape"),
    ("-clearlogo.png", "clearlogo"),
    ("-clearlogo.jpg", "clearlogo"),
    ("-logo.png", "clearlogo"),  # MediaElch alternative
    ("-logo.jpg", "clearlogo"),
    ("-clearart.png", "clearart"),
    ("-clearart.jpg", "clearart"),
    ("-discart.png", "discart"),
    ("-discart.jpg", "discart"),
    ("-disc.png", "discart"),  # MediaElch alternative
    ("-disc.jpg", "discart"),
    ("-characterart.png", "characterart"),
    ("-characterart.jpg", "characterart"),
)


# Subfolders whose contents must NEVER drive the parent item's NFO/artwork
# state. ``.actors`` (Kodi actor thumbnails) and Plex extras folders contain
# only sidecars; scanning them returns "missing" / empty-inventory and would
# silently overwrite the correct values written by the actual release dir.
_ITEM_ROOT_SKIP_DIRS: frozenset[str] = frozenset(
    {
        # Kodi / Plex sentinel sub-folders (English convention).
        ".actors",
        "extras",
        "behind the scenes",
        "deleted scenes",
        "featurettes",
        "interviews",
        "scenes",
        "shorts",
        "trailers",
        "other",
        # French equivalents commonly used in this project's library.
        # ``Bonus`` / ``Boni`` / ``Inédits`` hold show extras and must
        # not drive the item's NFO/artwork state — the show-level NFO
        # lives at the show root, not inside the bonus folder.
        # ``Films`` is used to nest a movie sub-collection under a
        # show root (e.g. Lucky Luke spin-off films inside the series
        # directory) — same skip rationale.
        "bonus",
        "boni",
        "inédits",
        "inedits",
        "films",
    }
)

# TV-show season folder names. When an episode file's parent matches this,
# the show's tvshow.nfo and root artwork live one level up (the show dir),
# not in the season dir.
_TV_SEASON_DIR_RE = re.compile(
    r"^(?:saison|season)\s*\d+$|^specials?$",
    re.IGNORECASE,
)

# Categories that do not follow the Kodi NFO convention. For these,
# ``nfo_status='missing'`` is a structural false-positive — there is no
# ``movie.nfo`` / ``tvshow.nfo`` to find because the format does not
# specify one. Setting nfo_status to NULL ("not applicable") is more
# faithful than reporting them as broken in library-report.
_NFO_NA_CATEGORIES: frozenset[str] = frozenset({"audiobooks"})
