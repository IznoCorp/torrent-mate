"""Movie dispatch: replace existing or move new to best disk."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf import resolver
from personalscraper.core.delete_permit import ALLOW
from personalscraper.dispatch import _transfer
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.disk_scanner import get_disk_status
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.dispatch.media_index import IndexEntry
from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.outbox._disk import disk_id_for_path
from personalscraper.indexer.outbox._publish import publish_event
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.dispatch.dispatcher import Dispatcher

log = get_logger("dispatcher.movie")


def dispatch_movie(
    dispatcher: Dispatcher,
    movie_dir: Path,
    category_id: str,
) -> DispatchResult:
    """Dispatch a movie: replace if exists, move to best disk if new.

    Args:
        dispatcher: Dispatcher instance for config, index, and helper access.
        movie_dir: Source movie directory.
        category_id: Category ID (e.g. ``"movies"``) from the classifier.

    Returns:
        DispatchResult with operation details.
    """
    result = DispatchResult(source=movie_dir)

    # Get disk statuses keyed by disk ID for resolver
    disk_statuses = [get_disk_status(c) for c in dispatcher._disk_configs]
    free_space_by_id = {s.config.id: s.free_space_gb if s.is_mounted else 0.0 for s in disk_statuses}

    # Calculate source size
    item_size_gb = _transfer.dir_size_gb(movie_dir)

    # Check index for existing copy, validated against filesystem to avoid
    # duplicating when the user has moved the folder between disks manually.
    existing = dispatcher._resolve_existing_on_filesystem(movie_dir.name, "movie", media_dir=movie_dir)

    if existing:
        # Replace existing on the same disk (disk stored as disk_id in the index)
        dest = Path(existing.path)
        result.disk = existing.disk
        result.destination = dest

        # Check if disk has enough space for the replacement
        threshold = max(
            dispatcher.config.thresholds.min_free_space_disk_gb,
            item_size_gb * 1.5,
        )
        disk_free = free_space_by_id.get(existing.disk, 0.0)
        if disk_free < threshold:
            result.action = "skipped"
            result.reason = f"Disk {existing.disk} full, cannot replace"
            return result

        # Resolve the destination disk's capability (NTFS-safe default), then
        # gate illegal filenames against THAT capability's regex (None on POSIX
        # filesystems → no restriction → not skipped). Resolving before the
        # dry-run branch keeps dry-run a faithful preview of the real run.
        cap = dispatcher._disk_capabilities.get(existing.disk, NTFS_MACFUSE)
        if _is_skipped_for_illegal_names(result, movie_dir, cap):
            return result

        if dispatcher.dry_run:
            result.action = "replaced"
            result.reason = f"[DRY RUN] Would replace on {existing.disk}"
            return result
        # Three-state seedtime-aware policy (DESIGN §7.3): the replace deletes the
        # OLD on-disk content. If a live seed obligation on it is unmet, the new
        # real media still wins (O3) — but the breach is recorded, never silent.
        # Relocate-not-delete is deferred to O2/O3, so we proceed either way.
        decision = dispatcher._permit.may_delete(dest)
        if decision is not ALLOW:
            log.warning("acquire.hnr_risk", path=str(dest), reason=str(decision), action="replace")
            dispatcher._recorder.mark_breach(dest)
        # Write-before-move (DESIGN §7.2): record the obligation for the NEWLY
        # dispatched media BEFORE the FS move, so a crash mid-move never loses
        # the safety constraint. Fail-soft (never raises).
        dispatcher._recorder.record_dispatch(staging_source=movie_dir, dispatched_dest=dest)
        success = replace(movie_dir, dest, capability=cap)
        result.action = "replaced" if success else "error"
    else:
        # Move to best disk via resolver
        target_disk = resolver.pick_disk_for(
            dispatcher.config,
            category_id,
            free_space_by_id,
            dispatcher.config.thresholds.min_free_space_disk_gb,
            item_size_gb,
        )
        if not target_disk:
            result.action = "skipped"
            result.reason = f"No disk with enough space for category '{category_id}'"
            return result

        dest = resolver.folder_for(dispatcher.config, target_disk, category_id) / movie_dir.name
        result.disk = target_disk.id
        result.destination = dest

        # Resolve the target disk's capability (NTFS-safe default), then gate
        # illegal filenames against THAT capability's regex (None on POSIX
        # filesystems → no restriction → not skipped). Resolving before the
        # dry-run branch keeps dry-run a faithful preview of the real run.
        cap = dispatcher._disk_capabilities.get(target_disk.id, NTFS_MACFUSE)
        if _is_skipped_for_illegal_names(result, movie_dir, cap):
            return result

        if dispatcher.dry_run:
            result.action = "moved"
            result.reason = f"[DRY RUN] Would move to {target_disk.id}"
            return result
        # Write-before-move (DESIGN §7.2): the new media may itself be a live
        # seed, so record its obligation BEFORE the FS move. No permit consult
        # here — there is no pre-existing library content to delete (only the
        # staging copy is removed after the move, and ingest copies seeding
        # torrents, so that copy is not the qBit-seeding payload).
        dispatcher._recorder.record_dispatch(staging_source=movie_dir, dispatched_dest=dest)
        success = dispatcher._move_new(movie_dir, dest, capability=cap)
        result.action = "moved" if success else "error"

    # Update index with current IDs
    if result.action in ("replaced", "moved") and result.destination:
        # ``replaced`` writes into an existing on-disk folder whose casing
        # is canonical; record that, not the staging spelling, so the
        # indexer never drifts away from the filesystem (see the matching
        # comment in dispatch_tvshow for the rationale).
        canonical_name = result.destination.name if result.action == "replaced" else movie_dir.name
        dispatcher.index.add(
            IndexEntry(
                name=canonical_name,
                disk=result.disk or "",
                category=category_id,
                path=str(result.destination),
                media_type="movie",
            )
        )

    # Best-effort outbox publish for the indexer (DESIGN §9.1).
    if result.action in ("replaced", "moved") and result.destination is not None:
        _db_path = dispatcher.config.indexer.db_path
        assert _db_path is not None, "indexer.db_path must be resolved"
        resolved = disk_id_for_path(result.destination, _db_path)
        if resolved is not None:
            disk_id, rel_path = resolved
            size_bytes, max_mtime = _transfer.dir_stats(result.destination)
            publish_event(
                disk_id,
                op="move",
                payload={
                    "src_rel_path": "",
                    "dst_rel_path": rel_path,
                    "filename": result.destination.name,
                    "size_bytes": size_bytes,
                    "mtime_ns": max_mtime,
                },
                db_path=_db_path,
                source="dispatch",
            )

    # Bus emit (Sub-phase 4.3) — only on real completed transfers.
    # Dry-run is excluded because the catalog defines ItemDispatched as the
    # record of completed transfers; the action enum has no "skipped" value
    # so dry-run runs logically cannot emit (DESIGN §Event catalog Notes).
    if not dispatcher.dry_run and result.action in ("moved", "replaced") and result.destination is not None:
        target_disk_path = _disk_root_for(dispatcher, result.disk)
        dispatcher._event_bus.emit(
            ItemDispatched(
                source="dispatch.movie",
                item=movie_dir.name,
                target_disk=target_disk_path,
                category_id=category_id,
                action=result.action,  # type: ignore[arg-type]  # narrowed by guard above
            ),
        )

    return result


def _is_skipped_for_illegal_names(
    result: DispatchResult,
    source_dir: Path,
    capability: FilesystemCapability,
) -> bool:
    """Gate a transfer on filesystem-illegal filenames for the resolved dest.

    Run AFTER the destination disk (and thus its capability) is chosen, so the
    gate honours the per-disk ``illegal_name_regex``: ``None`` on POSIX
    filesystems (APFS/HFS+/exFAT/ext4) means no restriction, so a ``:``-titled
    item proceeds; on NTFS/unknown the restrictive regex still skips it exactly
    as before this phase. Disk selection is read-only (index lookup +
    free-space), so it is safe to resolve the capability before this gate and
    before any file transfer.

    On a hit, mutates *result* in place with the same ``skipped`` action and
    NTFS-illegal reason the legacy pre-resolution gate set, logs the event, and
    returns ``True`` so the caller returns the skipped result without
    dispatching. Returns ``False`` (no mutation) when the resolved capability
    imposes no name restriction or no illegal name is present.

    Args:
        result: DispatchResult to mutate on a skip (action/reason set in place).
        source_dir: Source media directory whose filenames are scanned.
        capability: Resolved destination-disk capability; its
            ``illegal_name_regex`` drives the gate (``None`` → never skips).

    Returns:
        True if the item is skipped (illegal name on a restricted dest FS);
        False otherwise.
    """
    if _transfer.has_ntfs_illegal_names(source_dir, pattern=capability.illegal_name_regex):
        result.action = "skipped"
        result.reason = f"NTFS-illegal filenames in {source_dir.name}. Run 'personalscraper process' to sanitize."
        log.error("dispatch_ntfs_illegal", path=str(source_dir))
        return True
    return False


def _disk_root_for(dispatcher: Dispatcher, disk_id: str | None) -> Path:
    """Return the storage-disk root path for ``disk_id`` (empty path if unknown).

    ``ItemDispatched.target_disk`` is the disk's mount point, NOT the
    per-category sub-folder. The dispatcher holds the list of resolved disk
    configs; this helper is a thin lookup used by the dispatch_movie /
    dispatch_tvshow emit sites.
    """
    if not disk_id:
        return Path("")
    for cfg in dispatcher._disk_configs:
        if cfg.id == disk_id:
            return cfg.path
    return Path("")


def replace(
    source: Path,
    dest: Path,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> bool:
    """Crash-safe cross-filesystem replace via rsync.

    Phase 1 (Transfer): rsync source → dest.new.tmp/
    Phase 2 (Atomic swap): rename dest → dest.old.tmp, rename dest.new.tmp → dest
    Phase 3 (Cleanup, non-critical): remove dest.old.tmp and source

    Phases 1-2 must succeed; Phase 3 failures are logged as warnings
    since the replace is already complete at that point. If Phase 2
    fails mid-way, the original is restored from dest.old.tmp.

    Args:
        source: Source directory.
        dest: Destination directory to replace.
        capability: Filesystem capability for the destination volume.
            Defaults to ``NTFS_MACFUSE`` (NTFS-safe) so existing callers are
            byte-identical to the legacy behaviour.

    Returns:
        True if successful.
    """
    tmp_new = dest.parent / f"{dest.name}.new.tmp"
    tmp_old = dest.parent / f"{dest.name}.old.tmp"

    # Phase 1: Transfer (critical — must succeed)
    if not _transfer.rsync(source, tmp_new, capability=capability):
        try:
            if tmp_new.exists():
                _transfer.force_rmtree(tmp_new)
        except OSError as e:
            log.warning("replace_tmp_cleanup_failed", path=str(tmp_new), error=str(e), exc_info=True)
        return False

    # Phase 2: Atomic swap (critical — rollback on failure)
    try:
        if dest.exists():
            os.rename(dest, tmp_old)
        os.rename(tmp_new, dest)
    except OSError as e:
        log.error(
            "replace_swap_failed",
            exc_info=True,
            error=str(e),
            tmp_old=str(tmp_old),
            tmp_new=str(tmp_new),
        )
        # Attempt to restore original from backup
        try:
            if tmp_old.exists() and not dest.exists():
                os.rename(tmp_old, dest)
                log.info("replace_restored_from_backup", dest=str(dest))
        except OSError as restore_err:
            log.error(
                "replace_restore_failed",
                exc_info=True,
                error=str(restore_err),
                tmp_old=str(tmp_old),
                dest=str(dest),
            )
        # Clean up the successful transfer so it is not left orphaned
        # on disk (occupies space and could be picked up by a
        # subsequent dispatch run as a stale sibling).
        try:
            if tmp_new.exists():
                _transfer.force_rmtree(tmp_new)
        except OSError as e:
            log.warning("replace_tmp_new_cleanup_failed", path=str(tmp_new), error=str(e), exc_info=True)
        return False

    # Phase 3: Cleanup (non-critical — replace already succeeded)
    try:
        if tmp_old.exists():
            _transfer.force_rmtree(tmp_old)
    except OSError as e:
        log.warning("replace_old_copy_cleanup_failed", path=str(tmp_old), error=str(e), exc_info=True)
    try:
        _transfer.force_rmtree(source)
    except OSError as e:
        log.warning("replace_source_cleanup_failed", path=str(source), error=str(e), exc_info=True)
    return True
