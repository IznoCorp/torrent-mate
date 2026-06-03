"""TV show dispatch: merge existing or move new to best disk."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf import resolver
from personalscraper.dispatch import _transfer
from personalscraper.dispatch._movie import _disk_root_for, _is_skipped_for_illegal_names
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

log = get_logger("dispatcher.tv")


def dispatch_tvshow(
    dispatcher: Dispatcher,
    show_dir: Path,
    category_id: str,
) -> DispatchResult:
    """Dispatch a TV show: merge if exists, move to best disk if new.

    Args:
        dispatcher: Dispatcher instance for config, index, and helper access.
        show_dir: Source TV show directory.
        category_id: Category ID (e.g. ``"tv_shows"``) from the classifier.

    Returns:
        DispatchResult with operation details.
    """
    result = DispatchResult(source=show_dir)

    disk_statuses = [get_disk_status(c) for c in dispatcher._disk_configs]
    free_space_by_id = {s.config.id: s.free_space_gb if s.is_mounted else 0.0 for s in disk_statuses}
    item_size_gb = _transfer.dir_size_gb(show_dir)

    # Check index for existing copy, validated against filesystem to avoid
    # duplicating when the user has moved the folder between disks manually.
    existing = dispatcher._resolve_existing_on_filesystem(show_dir.name, "tvshow", media_dir=show_dir)

    if existing:
        dest = Path(existing.path)
        result.disk = existing.disk
        result.destination = dest

        # Check if disk has enough space for the merge
        threshold = max(
            dispatcher.config.thresholds.min_free_space_disk_gb,
            item_size_gb * 1.5,
        )
        disk_free = free_space_by_id.get(existing.disk, 0.0)
        if disk_free < threshold:
            result.action = "skipped"
            result.reason = f"Disk {existing.disk} full, cannot merge"
            return result

        # Resolve the destination disk's capability (NTFS-safe default), then
        # gate illegal filenames against THAT capability's regex (None on POSIX
        # filesystems → no restriction → not skipped). Resolving before the
        # dry-run branch keeps dry-run a faithful preview of the real run.
        cap = dispatcher._disk_capabilities.get(existing.disk, NTFS_MACFUSE)
        if _is_skipped_for_illegal_names(result, show_dir, cap):
            return result

        if dispatcher.dry_run:
            result.action = "merged"
            result.reason = f"[DRY RUN] Would merge on {existing.disk}"
            return result
        success = merge(show_dir, dest, capability=cap)
        result.action = "merged" if success else "error"
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

        dest = resolver.folder_for(dispatcher.config, target_disk, category_id) / show_dir.name
        result.disk = target_disk.id
        result.destination = dest

        # Resolve the target disk's capability (NTFS-safe default), then gate
        # illegal filenames against THAT capability's regex (None on POSIX
        # filesystems → no restriction → not skipped). Resolving before the
        # dry-run branch keeps dry-run a faithful preview of the real run.
        cap = dispatcher._disk_capabilities.get(target_disk.id, NTFS_MACFUSE)
        if _is_skipped_for_illegal_names(result, show_dir, cap):
            return result

        if dispatcher.dry_run:
            result.action = "moved"
            result.reason = f"[DRY RUN] Would move to {target_disk.id}"
            return result
        success = dispatcher._move_new(show_dir, dest, capability=cap)
        result.action = "moved" if success else "error"

    if result.action in ("merged", "moved") and result.destination:
        # When merging into an existing on-disk folder, the destination's
        # name carries the canonical casing (NTFS is case-insensitive, so
        # rsync resolves to the pre-existing folder). Recording the
        # staging-side casing here would silently overwrite the indexer
        # title with the new spelling on every dispatch and cause the
        # next case-mismatch scan to keep flagging it. Use the
        # destination's basename as the canonical title for merges /
        # replacements; ``moved`` actions write a brand-new folder so
        # the staging name is correct in that branch.
        canonical_name = result.destination.name if result.action == "merged" else show_dir.name
        dispatcher.index.add(
            IndexEntry(
                name=canonical_name,
                disk=result.disk or "",
                category=category_id,
                path=str(result.destination),
                media_type="tvshow",
            )
        )

    # Best-effort outbox publish for the indexer (DESIGN §9.1).
    if result.action in ("merged", "moved") and result.destination is not None:
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

    # Bus emit (Sub-phase 4.3) — only on real completed transfers. Dry-run
    # is excluded by the same reasoning as dispatch_movie: ItemDispatched is
    # the record of completed transfers; dry-run never completes one.
    if not dispatcher.dry_run and result.action in ("moved", "merged") and result.destination is not None:
        target_disk_path = _disk_root_for(dispatcher, result.disk)
        dispatcher._event_bus.emit(
            ItemDispatched(
                source="dispatch.tv",
                item=show_dir.name,
                target_disk=target_disk_path,
                category_id=category_id,
                action=result.action,  # type: ignore[arg-type]  # narrowed by guard above
            ),
        )

    return result


def merge(
    source: Path,
    dest: Path,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> bool:
    """Merge TV show with backup-based rollback for existing files.

    Uses rsync --backup to preserve overwritten files in
    .merge_backup/ within the destination. On failure, originals
    are restored from the backup directory.

    Pre-step: episode-conflict resolution. The unique key for a TV
    episode file is the (season, episode) tuple, NOT the full
    filename. A re-scrape can change the title segment (e.g. EN
    ``S04E06 - YOU LOOK HORRIBLE.mkv`` vs FR ``S04E06 - T'AS UNE
    SALE GUEULE.mkv`` — same episode, different title). Plain rsync
    treats those as different files and would leave the destination
    with two copies of E06. We prune the destination of any episode
    whose (season, episode) key matches a source episode under a
    different filename, so the rsync that follows produces exactly
    one file per (season, episode) — the source version.

    Args:
        source: Source TV show directory.
        dest: Existing destination directory.
        capability: Filesystem capability for the destination volume.
            Defaults to ``NTFS_MACFUSE`` (NTFS-safe) so existing callers are
            byte-identical to the legacy behaviour.

    Returns:
        True if successful.
    """
    backup_dir = dest / ".merge_backup"

    try:
        # Resolve filename conflicts on (season, episode) key BEFORE
        # the rsync. Files moved to backup_dir here are restored on
        # rsync failure by _restore_merge_backup, same as overwrites.
        purge_episode_conflicts(source, dest, backup_dir)

        # rsync with backup for overwritten files
        if not _transfer.rsync_merge(source, dest, backup_dir, capability=capability):
            _transfer.restore_merge_backup(dest, backup_dir)
            return False

        # Verify transfer
        if _transfer.verify_transfer(source, dest):
            # Success — clean backup and source
            if backup_dir.exists():
                _transfer.force_rmtree(backup_dir)
            _transfer.force_rmtree(source)
            return True

        log.error("merge_verify_failed", source=source.name)
        _transfer.restore_merge_backup(dest, backup_dir)
        return False
    except OSError as e:
        log.error("merge_failed", error=str(e), exc_info=True)
        _transfer.restore_merge_backup(dest, backup_dir)
        return False


def purge_episode_conflicts(
    source: Path,
    dest: Path,
    backup_dir: Path,
) -> None:
    """Move dest files that conflict with source on (season, episode) key.

    The unique key for a TV episode file is the (season, episode)
    tuple parsed from the filename (``S04E06`` etc.), not the full
    filename. A re-scrape that swaps the title segment (English
    original vs French localised) would otherwise leave both copies
    on disk after a plain rsync merge.

    For every source episode file we move any destination file that
    shares the same (season, episode) key but has a different
    filename into ``backup_dir``. The companion sidecars (.nfo and
    ``-thumb.jpg``) are matched the same way. The rsync that runs
    immediately after sees a clean destination for these episodes
    and writes exactly one file per (season, episode) — the source
    version — so duplicates cannot survive.

    On rsync failure ``restore_merge_backup`` puts the moved files
    back, restoring the previous state.

    Args:
        source: Staging show directory (the new version).
        dest: On-disk show directory (the existing version).
        backup_dir: Directory where conflicting dest files are
            relocated to. Created on demand.
    """
    # Lazy-import to avoid circular module load between dispatcher
    # and scraper at package init.
    from personalscraper.scraper.episode_manager import _extract_season_episode  # noqa: PLC0415

    if not dest.is_dir():
        return

    # Collect (season, episode) → list of relative paths under source
    # so we know which keys to clean on the destination side. We only
    # care about top-level video / sidecar files in season subdirs;
    # rsync handles other tree shapes naturally.
    source_keys: set[tuple[int, int, str]] = set()
    for season_dir in source.iterdir():
        if not season_dir.is_dir():
            continue
        for f in season_dir.iterdir():
            if not f.is_file():
                continue
            season, episode = _extract_season_episode(f.name)
            if season is None or episode is None:
                continue
            source_keys.add((season, episode, season_dir.name))

    if not source_keys:
        return

    # Build the inverse lookup: for each season, which (season,
    # episode) keys does the source provide? Reduces per-file work
    # in the destination scan to a single set lookup.
    source_keys_by_season: dict[str, set[tuple[int, int]]] = {}
    for season, episode, season_dir_name in source_keys:
        source_keys_by_season.setdefault(season_dir_name, set()).add((season, episode))

    for season_dir_name, keys in source_keys_by_season.items():
        dest_season = dest / season_dir_name
        if not dest_season.is_dir():
            continue
        # Collect the source filenames so we can tell "same key,
        # same filename" (rsync will overwrite — leave alone) from
        # "same key, different filename" (must purge).
        src_filenames_for_keys: dict[tuple[int, int], set[str]] = {}
        src_season = source / season_dir_name
        for f in src_season.iterdir():
            if not f.is_file():
                continue
            s, e = _extract_season_episode(f.name)
            if s is None or e is None:
                continue
            if (s, e) in keys:
                src_filenames_for_keys.setdefault((s, e), set()).add(f.name)

        for f in dest_season.iterdir():
            if not f.is_file():
                continue
            s, e = _extract_season_episode(f.name)
            if s is None or e is None:
                continue
            if (s, e) not in keys:
                continue
            if f.name in src_filenames_for_keys.get((s, e), set()):
                # Same filename → rsync will overwrite normally.
                continue
            # Same (season, episode) under a different filename:
            # move it to backup_dir mirroring its relative path so
            # restore_merge_backup can roll it back unchanged on
            # rsync failure.
            rel = f.relative_to(dest)
            target = backup_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            f.rename(target)
            log.info(
                "merge_episode_conflict_purged",
                show=dest.name,
                season=season_dir_name,
                episode=f"S{s:02d}E{e:02d}",
                removed=f.name,
                replacements=sorted(src_filenames_for_keys.get((s, e), set())),
            )
