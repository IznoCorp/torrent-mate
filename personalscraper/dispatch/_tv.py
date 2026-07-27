"""TV show dispatch: merge existing or move new to best disk."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.dispatch import _transfer
from personalscraper.dispatch._identity import merge_identity_conflict
from personalscraper.dispatch._item import (
    DispatchSpec,
    _dispatch_item,
    canonical_name_from_destination,
    merge_transfer,
)
from personalscraper.dispatch._types import DispatchResult
from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.destructive_journal import OP_OVERWRITE
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.dispatch.dispatcher import Dispatcher

log = get_logger("dispatcher.tv")


def _tv_journal_detail(source_dir: Path) -> str:
    """Return the destructive-journal detail for a TV merge-overwrite.

    A TV merge journals only when it genuinely supersedes an existing episode —
    a same-filename rsync overwrite, or a re-scrape-rename purge (same
    ``(season, episode)`` key under a different filename). The detail names the
    show folder whose episode(s) were superseded (**F1**, DESIGN §6/§7).

    Args:
        source_dir: The staging show folder that supersedes on-disk episode(s).

    Returns:
        The French journal detail string.
    """
    return f"MERGE série — épisode(s) écrasé(s) par « {source_dir.name} »"


#: TV specialisation of the shared dispatch template: merge into an existing
#: on-disk show (backup/restore), gated by the §7 provider-ID identity guard so
#: a same-named but DIFFERENT series is never overwritten (``tvshow.nfo``, TVDB
#: primary; fail-open + logged when unverifiable). Journals a supersede of an
#: existing episode as one ``overwrite`` row (F1). An add-only merge destroys
#: nothing and journals nothing (see ``merge_transfer``).
_TV_SPEC = DispatchSpec(
    media_type="tvshow",
    existing_action="merged",
    transfer_fn=merge_transfer,
    identity_guard=merge_identity_conflict,
    canonical_name_rule=canonical_name_from_destination,
    journal_op=OP_OVERWRITE,
    journal_detail=_tv_journal_detail,
    bus_source="dispatch.tv",
)


def dispatch_tvshow(
    dispatcher: Dispatcher,
    show_dir: Path,
    category_id: str,
) -> DispatchResult:
    """Dispatch a TV show: merge if exists, move to best disk if new.

    Thin wrapper over :func:`personalscraper.dispatch._item._dispatch_item`
    parameterised by :data:`_TV_SPEC` (merge strategy, §7 provider-ID identity
    guard, ``overwrite`` journal on a genuine episode supersede). The shared scaffold —
    existing-copy detection, free-space + illegal-name gating, the §7.3
    seed-obligation permit consult, the transfer, the destructive journal, the
    index/outbox write-through and the ``ItemDispatched`` emit — lives in the
    template.

    Args:
        dispatcher: Dispatcher instance for config, index, and helper access.
        show_dir: Source TV show directory.
        category_id: Category ID (e.g. ``"tv_shows"``) from the classifier.

    Returns:
        DispatchResult with operation details.
    """
    return _dispatch_item(dispatcher, show_dir, category_id, _TV_SPEC)


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
