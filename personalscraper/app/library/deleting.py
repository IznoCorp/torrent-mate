"""``LibraryDeletion``: a medium's deletion — its folder, its index rows, its Plex entry.

The deletion is ``library.delete``: the method is authorised by ``@requires`` before it
opens anything, and ``actor`` is consulted again only to journal who deleted. The folder,
index and Plex primitives are split: the folder and index ones (``delete_media_folder``,
``remove_items``) are in ``indexer/deletion.py``; the empty-parent removal and the Plex
follow-up (``remove_empty_parents``, ``follow_up_plex``) are in ``app/library/deletion.py``. An id held by two rows,
or by one row in two media folders, is a duplicate, and the deletion refuses it (O-5 B).
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.errors import AppConflict, AppInternalError, AppNotFound, AppUnavailable, RefusalCode
from personalscraper.app.library.deletion import (
    TOMBSTONE_REASON,
    DeletionReport,
    MediaDeletion,
    PlexOutcome,
    follow_up_plex,
    remove_empty_parents,
)
from personalscraper.app.library.identity import Provider, ref_key
from personalscraper.app.library.listing import held_of, open_reader, resolve_media_folder
from personalscraper.conf.environment import is_sandboxed
from personalscraper.conf.sandbox_guard import SandboxGuardError
from personalscraper.core.delete_permit import DeletePermit, PermitDecision
from personalscraper.core.identity import ItemId, MediaRef
from personalscraper.indexer.deletion import DeleteOutcome, delete_media_folder, remove_items
from personalscraper.indexer.library_view import LibraryIndex
from personalscraper.lock import acquire_pipeline_lock, release_lock, scrape_locks_dir_for
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.plex import PlexClient
    from personalscraper.conf.models.config import Config

log = get_logger("app.library.deleting")

__all__ = ["LibraryDeletion"]


@dataclass(frozen=True)
class _DeletionPlan:
    """What one validated medium's deletion touches.

    Attributes:
        ref: The medium, as the request named it.
        item_id: The one index row holding it.
        targets: Its media folders, resolved inside their disks: ``(mount point, folder)``.
        unresolved: Its mounted media folders that do not resolve inside their disk, resolve
            through a symlink, or sit on a disk root on no mounted volume: never deleted,
            counted failed.
        unreachable: Its media folders on a disk the index says is not mounted.
    """

    ref: MediaRef
    item_id: ItemId
    targets: tuple[tuple[Path, Path], ...]
    unresolved: int
    unreachable: int


@dataclass(frozen=True)
class _Deleted:
    """One medium's deletion before Plex is told.

    Attributes:
        deletion: What was done, Plex not yet asked.
        folders: Its deleted folders.
        removed: The parent folders its deletion left empty and removed.
        item_id: Its index row, naming it in the log.
    """

    deletion: MediaDeletion
    folders: tuple[Path, ...]
    removed: tuple[Path, ...]
    item_id: int


class _Decided:
    """The permit decisions of a request's folders, read once, all before any folder goes.

    A :class:`DeletePermit` the folder-deletion primitive consults: it answers each
    folder the decision read for it. Reading them all up front is what makes R1's refusal
    whole: a deletion authority that cannot read the seed obligations refuses the request
    before its first folder is touched, never halfway through it. The decisions cannot
    go stale meanwhile: a seed obligation's path is written by the dispatch, which holds
    ``pipeline.lock``, and the request holds it too.
    """

    def __init__(self, decisions: Mapping[Path, PermitDecision]) -> None:
        """Hold the decisions read.

        Args:
            decisions: Each folder's decision.
        """
        self._decisions = dict(decisions)

    @classmethod
    def read(cls, permit: DeletePermit, plans: Sequence[_DeletionPlan]) -> _Decided:
        """Read the permit's decision for every folder the request deletes.

        Args:
            permit: The deletion authority.
            plans: The request's validated media.

        Returns:
            The decisions.

        Raises:
            AppUnavailable: ``library.obligations_unreadable`` when the permit cannot read
                the seed obligations of a folder (:class:`ObligationsUnreadable`), or fails
                in any other way: a folder whose seeding owed is unknown is never deleted.
        """
        decisions: dict[Path, PermitDecision] = {}
        for plan in plans:
            for _root, directory in plan.targets:
                try:
                    decisions[directory] = permit.may_delete(directory)
                except Exception as exc:
                    # ObligationsUnreadable, or any other failure of the lookup: unknown is refused.
                    log.error(
                        "app.library.delete_obligations_unreadable",
                        item_id=plan.item_id,
                        error=type(exc).__name__,
                        detail=str(exc),
                    )
                    raise AppUnavailable(
                        "The seed obligations cannot be read.", code=RefusalCode.LIBRARY_OBLIGATIONS_UNREADABLE
                    ) from exc
        return cls(decisions)

    def may_delete(self, path: Path) -> PermitDecision:
        """The decision read for a folder.

        Args:
            path: A folder of the request.

        Returns:
            Its decision.
        """
        return self._decisions[path]

    def owed_until(self, path: Path) -> int | None:
        """When a vetoed folder's seeding is met, as its veto says.

        Args:
            path: A vetoed folder of the request.

        Returns:
            Epoch seconds, or ``None`` when the permit does not know it.
        """
        owed: int | None = getattr(self._decisions[path], "owed_until", None)
        return owed


#: The Plex outcomes of a medium's sections, the worst first: the worst speaks for it.
_PLEX_SEVERITY: Final[tuple[PlexOutcome, ...]] = (
    PlexOutcome.FAILED,
    PlexOutcome.TRASH_KEPT,
    PlexOutcome.REFRESHED,
)


def _deletable_folder(mounted: tuple[str, str]) -> tuple[Path, Path] | None:
    """Resolve a media folder for deletion: inside a mounted disk, and reached through no symlink.

    Args:
        mounted: ``(mount path, "<category>/<media folder>")`` as the index names it.

    Returns:
        ``(mount point, folder)`` resolved, or ``None`` when the folder does not resolve
        inside its disk, when its own path or its category's is a symlink (deleting through
        a link would reach whatever it points to), or when the disk's root is on no mounted
        volume (:func:`_on_a_mounted_volume`; the index's ``is_mounted`` flag can lag: an
        unmounted disk leaves a plain folder behind, never the disk itself).
    """
    mount_path, folder = mounted
    literal = Path(mount_path) / folder
    if literal.is_symlink() or literal.parent.is_symlink():
        return None
    resolved = resolve_media_folder(mount_path, folder)
    if resolved is None or not _on_a_mounted_volume(resolved[0]):
        return None
    return resolved


def _on_a_mounted_volume(root: Path) -> bool:
    """Whether a disk root the index names sits on a mounted volume, not on the system root.

    The index's root is a folder BELOW the mount point (``/Volumes/Disk1/medias``, mounted
    at ``/Volumes/Disk1``), so it is never a mount point itself: the walk climbs to the
    nearest mount point at or above it. A disk that dropped off leaves a plain
    ``/Volumes/DiskN`` directory on the system root's device, and the walk then reaches
    ``/``.

    Args:
        root: The disk root, resolved.

    Returns:
        ``True`` when the nearest mount point at or above *root* is not ``/``.
    """
    for candidate in (root, *root.parents):
        if os.path.ismount(candidate):
            return candidate != Path("/")
    return False


def _folder_identity(folder: Path) -> tuple[int, int] | None:
    """Name a folder by its device and inode, whatever spelling reached it.

    Args:
        folder: A resolved folder.

    Returns:
        ``(st_dev, st_ino)``, or ``None`` when the folder can no longer be read.
    """
    try:
        stat = folder.stat()
    except OSError:
        return None
    return stat.st_dev, stat.st_ino


class LibraryDeletion:
    """Deletes media everywhere: their folders, their index rows, their Plex entries."""

    def __init__(
        self,
        *,
        index: LibraryIndex,
        index_db: Path,
        data_dir: Path,
        plex: PlexClient | None = None,
        delete_permit: DeletePermit | None = None,
        config: Config | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Hold the index, the clients and the authority; nothing is opened yet.

        Args:
            index: ``library.db``, read-only.
            index_db: Path of ``library.db``, which the deletion writes through the indexer.
            data_dir: The pipeline data directory holding ``pipeline.lock``.
            plex: The Plex server a deletion tells; ``None`` when none is configured.
            delete_permit: The deletion authority a deletion consults (fail-open); ``None``
                when none is wired, and then every deletion is refused (no permit, no
                deletion: a folder that still owes seeding is never deleted unasked).
            config: The loaded configuration, naming the sandbox's roots: required in
                a sandbox, where a deletion without it deletes nothing.
            sleep: Pauses a deletion's wait for a Plex scan.
            monotonic: Monotonic seconds, bounding that wait.
        """
        self._index = index
        self._index_db = index_db
        self._data_dir = data_dir
        self._plex = plex
        self._delete_permit = delete_permit
        self._config = config
        self._sleep = sleep
        self._monotonic = monotonic

    @requires("deleteLibraryItems")
    def delete_media(self, actor: Actor, refs: Sequence[MediaRef]) -> DeletionReport:
        """Delete media everywhere: their folders on the disks, their index rows, their Plex entries.

        All or nothing at the refusal: ``pipeline.lock`` is taken for the whole request,
        every reference is validated and every folder's permit decision read before any
        folder is touched. Then, per medium, each
        of its media folders (one per distinct directory on its disks) is deleted through
        the folder-deletion primitive (the deletion authority consulted, the deletion
        journaled with ``web:<account id>``, the indexer told), the parent folders each left
        empty are removed up to the library root, and its index rows are removed with their
        tombstones — only when no folder of it was kept. Plex is told last, once every
        deletion is done, per section touched (:func:`follow_up_plex`). Nothing is
        rolled back: a kept folder, a failed removal, a failed index write (the medium
        reported not deleted, its rows live, the request going on to the next) or a Plex
        failure is reported.

        Args:
            actor: Who deletes; authorised by ``@requires`` (``library.delete``).
            refs: The media, each by the one id the wire names; a medium named twice (by
                one id twice, or by two of its ids) is deleted once.

        Returns:
            The report: how many media went entirely, and what each deletion did.

        Raises:
            AppInternalError: ``internal`` when no deletion authority is wired: nothing is
                deleted, the lock is not taken.
            AppConflict: ``library.locked`` while a run holds ``pipeline.lock``;
                ``media.ambiguous`` (``params.provider`` / ``params.providerId``) when two
                or more rows, or one row's live files in two or more media folders, hold an
                id (operator ruling O-5 B), or when another row holds live files in the
                medium's media folder. Nothing is deleted.
            AppNotFound: ``media.not_found`` (``params.provider`` / ``params.providerId``)
                when no index row holds an id. Nothing is deleted.
            AppUnavailable: ``library.obligations_unreadable`` when the deletion authority
                cannot read the seed obligations of a folder (operator ruling R1): every
                folder's decision is read before any folder goes, so nothing is deleted;
                ``library.unavailable`` when ``library.db`` cannot be read.
        """
        permit = self._delete_permit
        if permit is None:
            log.error("app.library.delete_without_permit")
            raise AppInternalError("No deletion authority is wired.", code=RefusalCode.INTERNAL)
        lock_file = self._data_dir / "pipeline.lock"
        if not acquire_pipeline_lock(lock_file, scrape_locks_dir_for(self._data_dir)):
            raise AppConflict("The pipeline holds the library.", code=RefusalCode.LIBRARY_LOCKED)
        try:
            plans = self._deletion_plans(refs)
            decided = _Decided.read(permit, plans)
            done = [self._delete_one(actor, plan, decided) for plan in plans]
            return self._told_plex(done)
        finally:
            release_lock(lock_file)

    def _deletion_plans(self, refs: Sequence[MediaRef]) -> list[_DeletionPlan]:
        """Validate every reference and name what each deletion touches; refuse before anything goes.

        Args:
            refs: The media asked.

        Returns:
            One plan per distinct medium (one index row, whichever of its ids named it), in
            request order.

        Raises:
            AppNotFound: ``media.not_found`` when no row holds an id.
            AppConflict: ``media.ambiguous`` when an id is held more than once, or when
                another row holds live files in the medium's media folder.
        """
        plans: list[_DeletionPlan] = []
        seen: set[tuple[Provider, str]] = set()
        planned: set[int] = set()
        with open_reader(self._index) as reader:
            for ref in refs:
                key = ref_key(ref)
                if key in seen:
                    continue
                seen.add(key)
                provider, provider_id = key
                params = {"provider": provider.value, "providerId": provider_id}
                holders, folders = held_of(reader, ref)
                if not holders:
                    raise AppNotFound("No library row holds this id.", code=RefusalCode.MEDIA_NOT_FOUND, params=params)
                holdings = sum(max(1, len(folders.get(row.item_id, ()))) for row in holders)
                if holdings > 1:
                    raise AppConflict(
                        "Several library rows or folders hold this id.", code=RefusalCode.MEDIA_AMBIGUOUS, params=params
                    )
                [row] = holders
                if row.item_id in planned:
                    # One row named by two of its ids (its TVDB and its TMDB id): deleted once,
                    # under the first ref that named it.
                    continue
                planned.add(row.item_id)
                own = folders.get(row.item_id, set())
                if any(holders_of - {row.item_id} for holders_of in reader.folder_holders(own).values()):
                    # Another row's live files sit in this medium's folder: deleting it would
                    # take them while that row stays live.
                    raise AppConflict(
                        "Another library row holds files in this media folder.",
                        code=RefusalCode.MEDIA_AMBIGUOUS,
                        params=params,
                    )
                mounted = reader.mounted_media_folders(row.item_id)
                # Keyed by the folder's (device, inode): two spellings of one folder (NFC / NFD,
                # unequal as paths, one directory on APFS) delete it once.
                targets: dict[tuple[int, int], tuple[Path, Path]] = {}
                unresolved = 0
                for one in mounted:
                    found = _deletable_folder(one)
                    identity = _folder_identity(found[1]) if found is not None else None
                    if found is None or identity is None:
                        unresolved += 1
                        continue
                    targets.setdefault(identity, found)
                plans.append(
                    _DeletionPlan(
                        ref=ref,
                        item_id=row.item_id,
                        targets=tuple(targets.values()),
                        unresolved=unresolved,
                        unreachable=max(0, len(folders.get(row.item_id, ())) - len(mounted)),
                    )
                )
        return plans

    def _delete_one(self, actor: Actor, plan: _DeletionPlan, permit: _Decided) -> _Deleted:
        """Delete one validated medium's folders, its emptied parents and, when nothing was kept, its rows.

        An index write failure (``sqlite3.Error`` from :func:`~personalscraper.indexer.deletion.remove_items`) is logged
        and never raised: the medium is reported with ``rows_removed = 0``, so not deleted,
        and its deleted folders are still told to Plex.

        Args:
            actor: Who deletes.
            plan: What the medium's deletion touches.
            permit: The decisions read for every folder of the request, which each
                folder's deletion consults.

        Returns:
            What was done, its deleted folders and the parents their deletion removed (for
            Plex).
        """
        who = f"web:{actor.account_id}"
        provider, provider_id = ref_key(plan.ref)
        deleted = vetoed = parents_removed = 0
        failed = plan.unresolved
        if plan.unresolved:
            log.warning("app.library.delete_folder_unresolved", provider=provider.value, item_id=plan.item_id)
        folders: list[Path] = []
        removed: list[Path] = []
        owed: list[int | None] = []
        for root, directory in plan.targets:
            try:
                result = delete_media_folder(
                    directory,
                    db_path=self._index_db,
                    actor=who,
                    label=f"media {provider.value}/{provider_id}",
                    permit=permit,
                    config=self._config,
                )
            except SandboxGuardError as exc:
                log.warning("app.library.delete_preprod_refused", item_id=plan.item_id, error=str(exc))
                failed += 1
                continue
            if result.outcome is DeleteOutcome.VETOED:
                vetoed += 1
                owed.append(permit.owed_until(directory))
            elif result.outcome is DeleteOutcome.FAILED:
                failed += 1
            else:
                deleted += 1
                emptied = remove_empty_parents(directory, root)
                parents_removed += len(emptied)
                removed.extend(emptied)
                folders.append(directory)
        unreachable = plan.unreachable
        rows = 0
        if vetoed + failed + unreachable == 0:
            try:
                rows = remove_items(self._index_db, [plan.item_id], actor=who, reason=TOMBSTONE_REASON)
            except sqlite3.Error as exc:
                # The folders are gone already: the request goes on, the rows stay live
                # (the indexer's next scan sees the files gone) and the medium is reported
                # not deleted.
                log.error(
                    "app.library.delete_rows_failed",
                    provider=provider.value,
                    item_id=plan.item_id,
                    error=type(exc).__name__,
                    detail=str(exc),
                )
        # The latest moment its vetoed folders' seeding is met; unknown when any one's is.
        known = [moment for moment in owed if moment is not None]
        owed_until = max(known) if owed and len(known) == len(owed) else None
        log.info(
            "app.library.media_deleted",
            provider=provider.value,
            item_id=plan.item_id,
            folders_deleted=deleted,
            folders_vetoed=vetoed,
            folders_failed=failed,
            folders_unreachable=unreachable,
            rows_removed=rows,
        )
        return _Deleted(
            MediaDeletion(
                ref=plan.ref,
                folders_deleted=deleted,
                folders_vetoed=vetoed,
                folders_failed=failed,
                folders_unreachable=unreachable,
                parents_removed=parents_removed,
                rows_removed=rows,
                plex=PlexOutcome.NOT_NEEDED,
                owed_until=owed_until,
            ),
            tuple(folders),
            tuple(removed),
            plan.item_id,
        )

    def _disk_unmounted(self) -> bool:
        """Whether a disk the index knows is not mounted (``disk.is_mounted = 0``).

        Returns:
            ``True`` when one is; the index unreadable counts as one (the trash kept).
        """
        try:
            with open_reader(self._index) as reader:
                return reader.any_disk_unmounted()
        except (sqlite3.Error, AppUnavailable) as exc:
            log.warning("app.library.delete_disks_unreadable", error=type(exc).__name__)
            return True

    def _told_plex(self, done: Sequence[_Deleted]) -> DeletionReport:
        """Tell Plex of every deleted folder at once, and fold its steps into each medium's report.

        In a sandbox (every environment but prod) Plex is never told
        (``PlexOutcome.SKIPPED_SANDBOX``): the bundle clean purges the whole server,
        outside the sandbox guard's roots.

        Called once every deletion of the request is done, so a refresh path is never a
        parent a later deletion removed.

        Args:
            done: Each medium's deletion, its deleted folders and the parents it removed.

        Returns:
            The request's report.
        """
        deleted = [folder for one in done for folder in one.folders]
        removed = {parent for one in done for parent in one.removed}
        sandboxed = is_sandboxed()
        steps = (
            follow_up_plex(
                self._plex,
                deleted,
                removed=removed,
                disk_unmounted=self._disk_unmounted(),
                sleep=self._sleep,
                clock=self._monotonic,
            )
            if self._plex is not None and deleted and not sandboxed
            else {}
        )
        media: list[MediaDeletion] = []
        for one in done:
            report = one.deletion
            if one.folders and sandboxed:
                report = replace(report, plex=PlexOutcome.SKIPPED_SANDBOX)
            elif one.folders and self._plex is None:
                report = replace(report, plex=PlexOutcome.NOT_CONFIGURED)
            elif one.folders:
                # The worst of its folders' sections speaks for the medium.
                mine = [steps[folder] for folder in one.folders]
                chosen = min(mine, key=lambda step: _PLEX_SEVERITY.index(step.outcome))
                report = replace(report, plex=chosen.outcome, plex_steps=chosen)
            # The outcome is not on the wire: the log is where a sandbox proves Plex was left alone.
            log.info("app.library.delete_plex", item_id=one.item_id, outcome=report.plex.value)
            media.append(report)
        return DeletionReport(deleted=sum(1 for one in media if one.deleted), media=tuple(media))
