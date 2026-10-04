"""Deletion by medium: what a deletion reports, and the steps after its folders go (K2-10).

:meth:`LibraryService.delete_media <personalscraper.app.library.service.LibraryService.delete_media>`
validates every reference, then deletes each medium's folder through the one folder-deletion
primitive (``indexer/deletion.py``). This module holds what follows a folder's deletion, each
step reported, none rolled back:

- the parent folders the deletion left empty are removed, up to and never including the
  library root (the disk's mount point the index names);
- the medium's index rows are removed, each with its ``deleted_item`` tombstone and its
  ``destructive_op`` journal row;
- Plex is told once every deletion of the request is done, per section touched (the
  section indexing the deleted folder): one partial scan per refresh path (the nearest
  ancestor of a deleted folder still standing inside the section's location, else that
  location), ONE bounded wait for that section's scan to end, one emptied trash; then ONE
  bundle clean for the whole request. The trash is kept, for a named reason, while a
  location of the section is missing or a disk is unmounted: emptying it then would purge
  the items Plex holds as unavailable. A Plex failure is reported, never undone: the files
  are gone, and Plex catches up on its next scan.

Every artwork of a medium (poster, fanart, season posters…) lives in its media folder, so
the folder's deletion takes them all.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable, Collection, Sequence
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.indexer.destructive_journal import OP_DELETE, record_destruction
from personalscraper.indexer.phantom_rows import tombstone_item
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.plex import PlexClient, PlexSection

log = get_logger("app.library.deletion")

__all__ = [
    "PLEX_SCAN_GRACE_S",
    "PLEX_SCAN_POLL_S",
    "PLEX_SCAN_WAIT_S",
    "DeletionReport",
    "MediaDeletion",
    "PlexOutcome",
    "PlexSteps",
    "TrashKept",
    "follow_up_plex",
    "remove_empty_parents",
    "remove_item_rows",
]

#: ``deleted_item.reason`` of a row removed with its medium.
TOMBSTONE_REASON: Final[str] = "media_deleted"

#: The longest a request waits for one section's scan to end, in seconds: the deletion
#: holds ``pipeline.lock`` meanwhile.
PLEX_SCAN_WAIT_S: Final[float] = 30.0

#: The pause before the first read of a section's scan state: Plex starts a requested scan
#: a moment after it answers, and a scan read idle before it starts is no scan done.
PLEX_SCAN_GRACE_S: Final[float] = 2.0

#: The pause between two reads of a section's scan state.
PLEX_SCAN_POLL_S: Final[float] = 1.0


class PlexOutcome(StrEnum):
    """How Plex was told of one medium's deletion."""

    REFRESHED = "refreshed"
    """Its section rescanned, the scan ended, the trash emptied and the bundles cleaned."""
    FAILED = "failed"
    """One step at least failed (see :class:`PlexSteps`), or no section indexes the folder."""
    NOT_CONFIGURED = "not_configured"
    """No Plex server is configured: nothing was asked."""
    NOT_NEEDED = "not_needed"
    """No folder of the medium was deleted: Plex was left alone."""
    TRASH_KEPT = "trash_kept"
    """Its section rescanned, the scan ended and the bundles cleaned, its trash kept on
    purpose (see :class:`TrashKept`): the medium leaves Plex at a later emptied trash."""
    SKIPPED_PREPROD = "skipped_preprod"
    """Under ``staging`` (preprod), Plex is never told: its bundle clean is a server-wide
    purge no preprod guard bounds (operator ruling Q7 A)."""


class TrashKept(StrEnum):
    """Why a section's trash was not emptied, though Plex answered.

    Plex's emptyTrash purges every item of the section it holds as unavailable, and the
    items of a disk that is not there are unavailable too: emptying the trash then would
    take them from Plex.
    """

    LOCATION_MISSING = "location_missing"
    """A location of the section is not an existing directory (and no deletion of the
    request removed it)."""
    DISK_UNMOUNTED = "disk_unmounted"
    """A disk the index knows is not mounted."""


@dataclass(frozen=True)
class PlexSteps:
    """Each Plex step's outcome for one section.

    Attributes:
        section: The section's key, or ``None`` when no section indexes the folder.
        refreshed: Every partial scan asked of the section was accepted.
        scan_ended: The section was read idle within :data:`PLEX_SCAN_WAIT_S`.
        trash_emptied: The section's trash emptying was accepted.
        bundles_cleaned: The request's one bundle clean was accepted.
        trash_kept: Why the trash was not asked to empty, ``None`` when it was asked.
    """

    section: str | None
    refreshed: bool
    scan_ended: bool
    trash_emptied: bool
    bundles_cleaned: bool
    trash_kept: TrashKept | None = None

    @property
    def outcome(self) -> PlexOutcome:
        """How Plex was told, from its steps.

        Returns:
            ``REFRESHED`` when every step succeeded; ``TRASH_KEPT`` when every step asked
            succeeded and the trash was kept on purpose; else ``FAILED``.
        """
        asked = self.refreshed and self.scan_ended and self.bundles_cleaned
        if asked and self.trash_kept is not None:
            return PlexOutcome.TRASH_KEPT
        return PlexOutcome.REFRESHED if asked and self.trash_emptied else PlexOutcome.FAILED


@dataclass(frozen=True)
class MediaDeletion:
    """What the deletion of one medium did.

    Attributes:
        ref: The medium, as the request named it.
        folders_deleted: Its media folders deleted.
        folders_vetoed: Its media folders the deletion authority kept (a seed obligation).
        folders_failed: Its media folders whose removal failed, or that resolve outside
            their disk.
        folders_unreachable: Its media folders on a disk the index says is not mounted.
        parents_removed: The parent folders its deletion left empty, removed.
        rows_removed: Its index rows removed (none unless every folder was deleted).
        plex: How Plex was told.
        plex_steps: Each Plex step's outcome, ``None`` when Plex was not asked.
    """

    ref: MediaRef
    folders_deleted: int
    folders_vetoed: int
    folders_failed: int
    folders_unreachable: int
    parents_removed: int
    rows_removed: int
    plex: PlexOutcome
    plex_steps: PlexSteps | None = None

    @property
    def deleted(self) -> bool:
        """Whether the medium went entirely: no folder kept, its rows removed."""
        kept = self.folders_vetoed + self.folders_failed + self.folders_unreachable
        return kept == 0 and self.rows_removed > 0


@dataclass(frozen=True)
class DeletionReport:
    """What a deletion request did.

    Attributes:
        deleted: The media deleted entirely (the contract's ``{deleted}``).
        media: Each medium's deletion, in request order.
    """

    deleted: int
    media: tuple[MediaDeletion, ...]


def remove_empty_parents(folder: Path, root: Path) -> tuple[Path, ...]:
    """Remove the parents of a deleted folder that it left empty, up to *root*, never *root*.

    Only an empty directory is removed (``rmdir`` refuses any other), from the nearest
    parent up; the walk stops at the first one that is not empty or cannot be removed,
    and never climbs outside *root*.

    Args:
        folder: The folder just deleted.
        root: The library root holding it (the disk's mount point).

    Returns:
        The parents removed, nearest first.
    """
    removed: list[Path] = []
    parent = folder.parent
    while parent != root and parent.is_relative_to(root):
        try:
            os.rmdir(parent)
        except OSError:
            break
        log.info("app.library.delete_parent_removed", path=str(parent))
        removed.append(parent)
        parent = parent.parent
    return tuple(removed)


def remove_item_rows(db_path: Path, item_ids: Sequence[int], *, actor: str) -> int:
    """Remove index rows (their releases, files, seasons and episodes by cascade), tombstoned and journaled.

    The rows go in one transaction, each with its ``deleted_item`` tombstone; the journal
    rows (``record_destruction(op="delete", path="index:media_item/<id>")``) are written
    after it commits, through the journal's own connection, and never raise.

    Args:
        db_path: Path of ``library.db``.
        item_ids: The ``media_item`` rows to remove.
        actor: Who deletes, written to the journal (``web:<account id>``).

    Returns:
        The rows removed (a row already gone is not counted).

    Raises:
        sqlite3.Error: When the transaction fails; it is rolled back and nothing is removed.
    """
    if not item_ids:
        return 0
    now = int(time.time())
    removed: list[int] = []
    with closing(sqlite3.connect(str(db_path), isolation_level=None)) as conn:
        apply_pragmas(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            for item_id in dict.fromkeys(item_ids):
                if conn.execute("SELECT 1 FROM media_item WHERE id = ?", (item_id,)).fetchone() is None:
                    continue
                tombstone_item(conn, item_id, now, reason=TOMBSTONE_REASON)
                conn.execute("DELETE FROM media_item WHERE id = ?", (item_id,))
                removed.append(item_id)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    for item_id in removed:
        record_destruction(db_path, op=OP_DELETE, path=f"index:media_item/{item_id}", actor=actor)
        log.info("app.library.delete_row_removed", item_id=item_id, actor=actor)
    return len(removed)


def _wait_for_scan(
    plex: PlexClient,
    section: str,
    *,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> bool:
    """Wait, bounded, for a section's scan to end.

    Args:
        plex: The Plex client.
        section: The section's key.
        sleep: Pauses for a number of seconds.
        clock: Monotonic seconds.

    Returns:
        ``True`` when the section was read idle within :data:`PLEX_SCAN_WAIT_S`; ``False``
        when it still scanned at the cap, or its state could not be read.
    """
    deadline = clock() + PLEX_SCAN_WAIT_S
    sleep(PLEX_SCAN_GRACE_S)
    while True:
        refreshing = plex.section_refreshing(section)
        if refreshing is None:
            return False
        if not refreshing:
            return True
        if clock() + PLEX_SCAN_POLL_S > deadline:
            log.warning("app.library.delete_plex_scan_timeout", section=section)
            return False
        sleep(PLEX_SCAN_POLL_S)


def _location_of(section: PlexSection, folder: Path) -> Path:
    """The section location holding a folder: the deepest one that prefixes it.

    Args:
        section: The section indexing the folder.
        folder: A folder below one of its locations.

    Returns:
        That location.
    """
    target = str(folder)
    roots = [location.rstrip("/") for location in section.locations if location.rstrip("/")]
    held = [root for root in roots if target == root or target.startswith(f"{root}/")]
    return Path(max(held, key=len))


def _refresh_path(folder: Path, location: Path) -> Path:
    """The path Plex rescans for a deleted folder, read once every deletion is done.

    Args:
        folder: The deleted folder.
        location: The section location holding it.

    Returns:
        The nearest ancestor of *folder* still standing inside *location*, else
        *location* itself.
    """
    for ancestor in folder.parents:
        if not ancestor.is_relative_to(location):
            break
        if ancestor.is_dir():
            return ancestor
    return location


def _trash_kept(section: PlexSection, removed: Collection[Path], disk_unmounted: bool) -> TrashKept | None:
    """Why a section's trash must not be emptied now, if it must not.

    Args:
        section: The section.
        removed: The parent folders the request's deletions removed.
        disk_unmounted: Whether a disk the index knows is not mounted.

    Returns:
        The reason to keep the trash, or ``None`` to empty it.
    """
    if disk_unmounted:
        return TrashKept.DISK_UNMOUNTED
    for location in section.locations:
        path = Path(location.rstrip("/") or "/")
        if not path.is_dir() and path not in removed:
            return TrashKept.LOCATION_MISSING
    return None


def follow_up_plex(
    plex: PlexClient,
    deleted: Sequence[Path],
    *,
    removed: Collection[Path] = (),
    disk_unmounted: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[Path, PlexSteps]:
    """Tell Plex of deleted folders: per section, rescan, wait once, empty its trash; then clean the bundles once.

    Called once every deletion of the request is done: each folder's section is the one
    indexing the deleted folder itself, and its refresh path the nearest ancestor still
    standing inside that section's location (else the location). A section's trash is
    kept (:class:`TrashKept`) while one of its locations is missing, unless this request's
    own deletions removed it as an emptied parent, or while *disk_unmounted*.

    Args:
        plex: The Plex client.
        deleted: The folders the request deleted.
        removed: The parent folders the request's deletions removed (emptied by them).
        disk_unmounted: Whether a disk the index knows is not mounted.
        sleep: Pauses for a number of seconds (tests inject a fake).
        clock: Monotonic seconds (tests inject a fake).

    Returns:
        Each deleted folder's section steps; a folder no section indexes has
        ``section=None`` and every step false.
    """
    sections: dict[str | None, PlexSection | None] = {}
    by_section: dict[str | None, list[Path]] = {}
    for folder in dict.fromkeys(deleted):
        section = plex.section_for(folder)
        key = section.key if section is not None else None
        sections[key] = section
        by_section.setdefault(key, []).append(folder)
    done: dict[str | None, tuple[bool, bool, bool, TrashKept | None]] = {}
    for section_key, folders in by_section.items():
        section = sections[section_key]
        if section is None or section_key is None:
            log.warning("app.library.delete_plex_no_section", paths=[str(p) for p in folders])
            done[None] = (False, False, False, None)
            continue
        paths = dict.fromkeys(_refresh_path(folder, _location_of(section, folder)) for folder in folders)
        refreshed = all([plex.refresh(path) for path in paths])
        scan_ended = _wait_for_scan(plex, section_key, sleep=sleep, clock=clock)
        kept = _trash_kept(section, removed, disk_unmounted)
        if kept is not None:
            log.warning("app.library.delete_plex_trash_kept", section=section_key, reason=kept.value)
        emptied = plex.empty_trash(section_key) if kept is None else False
        done[section_key] = (refreshed, scan_ended, emptied, kept)
    bundles_cleaned = plex.clean_bundles() if any(key is not None for key in by_section) else False
    steps: dict[Path, PlexSteps] = {}
    for section_key, folders in by_section.items():
        refreshed, scan_ended, trash_emptied, kept = done[section_key]
        section_steps = PlexSteps(
            section=section_key,
            refreshed=refreshed,
            scan_ended=scan_ended,
            trash_emptied=trash_emptied,
            bundles_cleaned=bundles_cleaned and section_key is not None,
            trash_kept=kept,
        )
        for folder in folders:
            steps[folder] = section_steps
    return steps
