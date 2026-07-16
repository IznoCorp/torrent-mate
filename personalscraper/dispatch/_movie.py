"""Movie dispatch: replace existing or move new to best disk."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.dispatch import _transfer
from personalscraper.dispatch._identity import replace_identity_conflict
from personalscraper.dispatch._item import (
    DispatchSpec,
    _dispatch_item,
    canonical_name_from_destination,
    replace_transfer,
)
from personalscraper.dispatch._types import DispatchResult
from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.destructive_journal import OP_OVERWRITE
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.dispatch.dispatcher import Dispatcher

log = get_logger("dispatcher.movie")


def _movie_journal_detail(source_dir: Path) -> str:
    """Return the destructive-journal detail for a movie replace (byte-identical).

    Preserves the exact legacy detail string so the append-only ``overwrite``
    row shape is unchanged after routing the movie-replace path through the
    shared :func:`personalscraper.dispatch._item._dispatch_item` template.

    Args:
        source_dir: The staging movie folder that supersedes the on-disk copy.

    Returns:
        The French journal detail string.
    """
    return f"REPLACE film — écrasé par « {source_dir.name} »"


#: Movie specialisation of the shared dispatch template: supersede an existing
#: on-disk copy via the 3-phase crash-safe replace, gated by the §7 provider-ID
#: identity guard, journaling the destruction as one ``overwrite`` row (F1).
_MOVIE_SPEC = DispatchSpec(
    media_type="movie",
    existing_action="replaced",
    transfer_fn=replace_transfer,
    identity_guard=replace_identity_conflict,
    canonical_name_rule=canonical_name_from_destination,
    journal_op=OP_OVERWRITE,
    journal_detail=_movie_journal_detail,
    bus_source="dispatch.movie",
)


def dispatch_movie(
    dispatcher: Dispatcher,
    movie_dir: Path,
    category_id: str,
) -> DispatchResult:
    """Dispatch a movie: replace if exists, move to best disk if new.

    Thin wrapper over :func:`personalscraper.dispatch._item._dispatch_item`
    parameterised by :data:`_MOVIE_SPEC` (replace strategy, §7 identity guard,
    ``overwrite`` journal on a genuine destruction). The shared scaffold —
    existing-copy detection, free-space + illegal-name gating, the §7.3
    seed-obligation permit consult, the transfer, the destructive journal, the
    index/outbox write-through and the ``ItemDispatched`` emit — lives in the
    template.

    Args:
        dispatcher: Dispatcher instance for config, index, and helper access.
        movie_dir: Source movie directory.
        category_id: Category ID (e.g. ``"movies"``) from the classifier.

    Returns:
        DispatchResult with operation details.
    """
    return _dispatch_item(dispatcher, movie_dir, category_id, _MOVIE_SPEC)


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
