"""Incremental scan mode driver."""

from __future__ import annotations

import os
import sqlite3

from personalscraper.indexer import drift as _drift
from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.fingerprint import normalize_tier1
from personalscraper.indexer.repos import file_repo
from personalscraper.indexer.scanner._db_writes import (
    _compute_oshash,
    _safe_mtime_ns,
    _upsert_file_row,
    _upsert_path_row,
)
from personalscraper.indexer.scanner._merkle_gate import (
    guard_bulk_change,
    merkle_short_circuit,
    recompute_disk_merkle_after_walk,
)
from personalscraper.indexer.scanner._shutdown import is_shutdown_requested
from personalscraper.indexer.scanner._walker import (
    DirMtimeSkipVisitor,
    WalkBudget,
    WalkCheckpoint,
    walk,
)
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

__all__ = [
    "IncrementalVisitor",
    "_scan_disk_incremental",
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
    # --- Merkle short-circuit (shared single-impl, same gate as quick mode) ---
    # Returns the DB-side fingerprints on a miss (walk needed) or None on a match
    # (disk unchanged → skip; disks_skipped already bumped inside the helper).
    fingerprints = merkle_short_circuit(conn, disk, disks_skipped, capability)
    if fingerprints is None:
        return

    # --- Bulk-change guard (shared single-impl, on Merkle miss) ---
    guard_bulk_change(
        conn,
        disk,
        mount,
        fingerprints,
        confirm_bulk_change=confirm_bulk_change,
        merkle_delta_freeze_threshold=merkle_delta_freeze_threshold,
        capability=capability,
    )

    # --- Incremental walk ---
    visitor = IncrementalVisitor(
        conn,
        disk,
        generation,
        files_visited,
        dirs_visited,
        dir_mtime_reliable,
        capability,
    )
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

    # Skip post-walk bookkeeping if the budget was exhausted — partial state is
    # preserved for crash-resume; Merkle root must not be updated to an incomplete
    # snapshot.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

    # Write-through the disk-root path row and recompute + persist the Merkle
    # root so the next incremental scan can short-circuit (shared single-impl).
    recompute_disk_merkle_after_walk(conn, disk, mount, capability)


class IncrementalVisitor(DirMtimeSkipVisitor):
    """Incremental-mode visitor over :func:`~personalscraper.indexer.scanner._walker.walk`.

    Inherits the dir-mtime subtree short-circuit from
    :class:`~personalscraper.indexer.scanner._walker.DirMtimeSkipVisitor` and adds
    the OSHash recompute + rename/content-drift logic in :meth:`visit_file`. For a
    file whose tier-1 fingerprint (size, mtime_ns, ctime_ns — normalised via the
    disk capability) has changed, the OSHash is recomputed to distinguish cosmetic
    mtime drift (update tier-1 only), a rename (delegated to
    :func:`~personalscraper.indexer.drift.detect_rename`), an OSHash collision
    (drift module enqueues repair) and real content drift
    (:func:`~personalscraper.indexer.drift.enqueue_repair` with
    ``reason='content_drift'``). Byte-identical to the legacy
    ``_walk_dir_incremental`` per-file body.
    """

    def visit_file(self, entry: os.DirEntry[str], st: os.stat_result, parent_rel: str) -> None:
        """Apply the incremental per-file fingerprint / rename / drift logic."""
        conn = self.conn
        disk = self.disk
        generation = self.generation
        capability = self.capability

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


# Artwork filename detection is owned by ``core.artwork_naming`` (INDEXER-03);
# this scan mode does not inventory artwork itself — the enrich pass does, via
# the shared canonical union. The old ``_ARTWORK_FILENAMES`` / ``_ARTWORK_SUFFIXES``
# copies here were dead duplicates and have been removed.


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

# Categories that do not follow the Kodi NFO convention. For these,
# ``nfo_status='missing'`` is a structural false-positive — there is no
# ``movie.nfo`` / ``tvshow.nfo`` to find because the format does not
# specify one. Setting nfo_status to NULL ("not applicable") is more
# faithful than reporting them as broken in library-report.
_NFO_NA_CATEGORIES: frozenset[str] = frozenset({"audiobooks"})
