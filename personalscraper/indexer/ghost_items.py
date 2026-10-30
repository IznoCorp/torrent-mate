"""Retire the ``media_item`` rows whose media folder is gone from its disk.

A file the scan no longer finds is struck, then tombstoned; an item had no such
end. When its folder was deleted or moved off the disk, its files were
tombstoned one by one and the item itself stayed forever — a ghost listed by
every view of the library.

An item is a ghost of a disk when all of these hold:

- the disk is configured and its mount is verified
  (``MOUNTED_AND_VERIFIED``: its sentinel names it) — an unmounted disk makes
  every folder look gone. The strikes go on for a disk with no readable
  sentinel (:func:`~personalscraper.indexer.drift.should_apply_drift_for_disk`);
  a hard delete does not;
- its ``dispatch_path`` lies on that disk and no longer exists (``stat``
  answers ``FileNotFoundError``; any other error freezes the disk's pass);
- none of its files is live (every one tombstoned, or none at all) — its files
  being those of its releases and those linked to no release under its folder.
  An item whose folder just vanished therefore retires only once the file
  strikes have tombstoned its files — the same three full scans a file waits;
- no ``pending`` / ``running`` repair names it, one of its releases or one of
  their files (``repair_queue.scope_id`` is a soft reference the cascade would
  leave dangling).

Retiring hard-deletes the item (the ``ON DELETE CASCADE`` removes its
attributes, seasons, episodes, releases and their tombstoned files) and records
a ``deleted_item`` tombstone holding a snapshot of the row.

The full scan applies it with a safety cap: when more than
:data:`MAX_RETIRE_SHARE` of a disk's items would go at once, something is more
likely wrong with the disk than with the library, and nothing is retired there.
The ``library-retire-ghost-items`` command applies it with no cap, as an
explicit operator action.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from personalscraper.indexer.merkle import DiskMountStatus
from personalscraper.indexer.repos.item_repo import dispatch_path_key
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("indexer.ghost_items")

#: ``deleted_item.reason`` of an item retired because its folder is gone.
GHOST_REASON = "dispatch_path_gone"

#: Largest share of a disk's items one full scan may retire; above it, none go.
MAX_RETIRE_SHARE = 0.10

_LIVE_FILES_SQL = """
SELECT COUNT(*) FROM media_file mf
JOIN media_release mr ON mr.id = mf.release_id
LEFT JOIN episode e ON e.id = mr.episode_id
LEFT JOIN season s ON s.id = e.season_id
WHERE mf.deleted_at IS NULL AND (mr.item_id = ? OR s.item_id = ?)
"""

#: Live files linked to no release whose directory is the item's folder or
#: lies under it. Paths compare on ``dispatch_path_key`` (registered on the
#: connection as ``ghost_path_key``): the walk stores what HFS+ answers (NFD),
#: the dispatch wrote the folder NFC.
_UNLINKED_LIVE_FILES_SQL = """
SELECT COUNT(*) FROM media_file mf
JOIN path p ON p.id = mf.path_id
WHERE mf.deleted_at IS NULL AND mf.release_id IS NULL AND p.disk_id = ?
AND (ghost_path_key(p.rel_path) = ? OR substr(ghost_path_key(p.rel_path), 1, ?) = ?)
"""


@dataclass(frozen=True)
class GhostItem:
    """An item whose ``dispatch_path`` no longer exists.

    Attributes:
        item_id: ``media_item.id``.
        title: Its title, for the report.
        kind: ``movie`` or ``show``.
        dispatch_path: The folder that is gone.
        reason: :data:`GHOST_REASON` for a retirable item, else why it is kept.
    """

    item_id: int
    title: str
    kind: str
    dispatch_path: str
    reason: str


@dataclass
class GhostReport:
    """What one disk's pass found and did.

    Attributes:
        disk_label: The disk's label.
        disk_items: Items whose ``dispatch_path`` lies on the disk.
        ghosts: The items retired (or, on a dry run, that would be).
        kept: Ghost folders kept: a live file (``live_files``) or an open repair
            on the item, its releases or their files (``pending_repair``).
        frozen: The mount could not be verified (or a folder could not be
            read); nothing was retired.
        capped: More than the cap would have gone; nothing was retired.
        retired: Items actually deleted.
    """

    disk_label: str
    disk_items: int = 0
    ghosts: list[GhostItem] = field(default_factory=list)
    kept: list[GhostItem] = field(default_factory=list)
    frozen: bool = False
    capped: bool = False
    retired: int = 0


def configured_disks(disks: list[DiskRow], config: Config) -> list[DiskRow]:
    """Keep the disk rows whose scan root is a disk of the configuration.

    A row left behind by a disk since removed from the configuration names a
    root nobody mounts any more: every folder on it would look gone.

    Args:
        disks: Rows of the ``disk`` table.
        config: The loaded configuration.

    Returns:
        The rows of configured disks, in their given order.
    """
    roots = {str(disk_cfg.path).rstrip("/") for disk_cfg in config.disks}
    return [d for d in disks if d.mount_path is not None and d.mount_path.rstrip("/") in roots]


def _items_on_disk(conn: sqlite3.Connection, mount_path: str) -> list[tuple[int, str, str, str]]:
    """Return ``(id, title, kind, dispatch_path)`` of every item whose folder lies on the disk.

    Args:
        conn: Open SQLite connection.
        mount_path: The disk's scan root.

    Returns:
        The items, by id.
    """
    root = mount_path.rstrip("/") + "/"
    rows = conn.execute(
        "SELECT mi.id, mi.title, mi.kind, ia.value FROM media_item mi "
        "JOIN item_attribute ia ON ia.item_id = mi.id AND ia.key = 'dispatch_path' "
        "ORDER BY mi.id"
    ).fetchall()
    # A prefix test in Python, not ``LIKE``: a folder name may hold ``%`` or ``_``.
    return [(int(r[0]), str(r[1]), str(r[2]), str(r[3])) for r in rows if str(r[3]).startswith(root)]


def _has_live_files(conn: sqlite3.Connection, item_id: int, disk: DiskRow, dispatch_path: str) -> bool:
    """Return whether a file of the item is still live.

    A file is the item's when one of its releases holds it, or — linked to no
    release yet — when it lies under the item's folder: retiring the item
    before such a file is tombstoned would break the order files-then-item.

    Args:
        conn: Open SQLite connection.
        item_id: The item.
        disk: The disk holding its folder (``mount_path`` set).
        dispatch_path: The item's folder, under the disk's root.

    Returns:
        ``True`` when at least one such file has no tombstone.
    """
    if conn.execute(_LIVE_FILES_SQL, (item_id, item_id)).fetchone()[0]:
        return True
    root = str(disk.mount_path).rstrip("/") + "/"
    folder_key = dispatch_path_key(dispatch_path[len(root) :])
    conn.create_function("ghost_path_key", 1, dispatch_path_key, deterministic=True)
    row = conn.execute(
        _UNLINKED_LIVE_FILES_SQL, (disk.id, folder_key, len(folder_key) + 1, folder_key + "/")
    ).fetchone()
    return bool(row[0])


def _folder_gone(path: str) -> bool:
    """Return whether the folder at *path* is gone.

    ``os.path.exists`` answers ``False`` on any ``OSError`` — an I/O error or a
    permission refused on a live folder would read as gone. Only
    ``FileNotFoundError`` says so.

    Args:
        path: The item's ``dispatch_path``.

    Returns:
        ``True`` when nothing is at *path*.

    Raises:
        OSError: When the folder cannot be examined (anything but not found).
    """
    try:
        os.stat(path)
    except FileNotFoundError:
        return True
    return False


_OPEN_REPAIR_SQL = """
SELECT 1 FROM repair_queue rq
WHERE rq.status IN ('pending', 'running') AND (
  (rq.scope = 'item' AND rq.scope_id = :item)
  OR (rq.scope = 'release' AND rq.scope_id IN (
    SELECT mr.id FROM media_release mr
    LEFT JOIN episode e ON e.id = mr.episode_id
    LEFT JOIN season s ON s.id = e.season_id
    WHERE mr.item_id = :item OR s.item_id = :item))
  OR (rq.scope = 'file' AND rq.scope_id IN (
    SELECT mf.id FROM media_file mf
    JOIN media_release mr ON mr.id = mf.release_id
    LEFT JOIN episode e ON e.id = mr.episode_id
    LEFT JOIN season s ON s.id = e.season_id
    WHERE mr.item_id = :item OR s.item_id = :item))
)
LIMIT 1
"""


def _has_open_repair(conn: sqlite3.Connection, item_id: int) -> bool:
    """Return whether a ``pending`` or ``running`` repair names *item_id* or a row it cascades to.

    ``repair_queue.scope_id`` is a soft reference: the cascade that deletes the
    item's releases and files would leave a repair on them dangling, so such a
    repair keeps the item exactly as an item repair does.

    Args:
        conn: Open SQLite connection.
        item_id: The item.

    Returns:
        ``True`` when the repair queue still holds work on it, its releases or
        their files.
    """
    return conn.execute(_OPEN_REPAIR_SQL, {"item": item_id}).fetchone() is not None


def _retire(conn: sqlite3.Connection, ghost: GhostItem, now_s: int) -> None:
    """Tombstone *ghost* with a snapshot of its row, then delete it.

    Args:
        conn: Open SQLite connection, inside the caller's transaction.
        ghost: The item to retire.
        now_s: Epoch seconds stamped on the tombstone.
    """
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM media_item WHERE id = ?", (ghost.item_id,)).fetchone()
    snapshot = {key: row[key] for key in row.keys()}
    conn.row_factory = None
    snapshot["dispatch_path"] = ghost.dispatch_path
    conn.execute(
        "INSERT INTO deleted_item (kind, original_id, deleted_at, reason, payload_json) VALUES ('item', ?, ?, ?, ?)",
        (ghost.item_id, now_s, GHOST_REASON, json.dumps(snapshot, default=str)),
    )
    conn.execute("DELETE FROM media_item WHERE id = ?", (ghost.item_id,))


def retire_ghost_items(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount_status: DiskMountStatus,
    *,
    dry_run: bool,
    max_share: float | None = MAX_RETIRE_SHARE,
    now_s: int | None = None,
) -> GhostReport:
    """Retire the ghost items of one configured disk.

    Args:
        conn: Open SQLite connection with no open transaction (autocommit or
            not; this function opens and commits its own when it writes).
        disk: The disk, already known to be configured.
        mount_status: A live :func:`~personalscraper.indexer.merkle.verify_disk_mounted`;
            anything but ``MOUNTED_AND_VERIFIED`` freezes the disk.
        dry_run: Report the ghosts and write nothing.
        max_share: Retire nothing when more than this share of the disk's items
            would go; ``None`` lifts the cap.
        now_s: Tombstone timestamp; defaults to now.

    Returns:
        The disk's :class:`GhostReport`.

    Raises:
        RuntimeError: When the connection has an open transaction and there are
            ghosts to retire.
        sqlite3.Error: When a write fails; the transaction is rolled back, as
            for any exception raised while retiring.
    """
    report = GhostReport(disk_label=disk.label)
    if disk.mount_path is None or mount_status is not DiskMountStatus.MOUNTED_AND_VERIFIED:
        # A hard delete needs the disk proven to be this one: ``NO_SENTINEL``
        # (absent or unreadable sentinel) lets the strikes run, not a retire.
        log.warning("indexer.ghost_items.frozen", disk=disk.label, mount_status=mount_status.value)
        report.frozen = True
        return report

    items = _items_on_disk(conn, disk.mount_path)
    report.disk_items = len(items)
    for item_id, title, kind, dispatch_path in items:
        try:
            if not _folder_gone(dispatch_path):
                continue
        except OSError as exc:
            # The disk answers but cannot be read here: nothing it says about
            # its folders can justify a hard delete.
            log.warning(
                "indexer.ghost_items.folder_unreadable",
                disk=disk.label,
                dispatch_path=dispatch_path,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            report.frozen = True
            report.ghosts.clear()
            return report
        if _has_live_files(conn, item_id, disk, dispatch_path):
            report.kept.append(GhostItem(item_id, title, kind, dispatch_path, "live_files"))
        elif _has_open_repair(conn, item_id):
            log.info(
                "indexer.ghost_items.kept_for_repair",
                item_id=item_id,
                store="library.db",
                table="repair_queue",
            )
            report.kept.append(GhostItem(item_id, title, kind, dispatch_path, "pending_repair"))
        else:
            report.ghosts.append(GhostItem(item_id, title, kind, dispatch_path, GHOST_REASON))

    if max_share is not None and report.ghosts and len(report.ghosts) > max_share * report.disk_items:
        report.capped = True
        log.warning(
            "indexer.ghost_items.capped",
            disk=disk.label,
            ghosts=len(report.ghosts),
            disk_items=report.disk_items,
            max_share=max_share,
        )
        return report
    if dry_run or not report.ghosts:
        return report

    stamp = int(time.time()) if now_s is None else now_s
    row_factory = conn.row_factory
    if conn.in_transaction:
        # Committing here would commit the caller's own pending writes along
        # with the deletes; rolling back would lose them. Neither is ours to do.
        raise RuntimeError("retire_ghost_items: the connection has an open transaction; commit it first")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for ghost in report.ghosts:
            _retire(conn, ghost, stamp)
        conn.commit()
    except Exception:
        # Whatever failed (a write, or a row gone under ``_retire``), the
        # ``BEGIN IMMEDIATE`` must not stay open on the caller's connection.
        conn.rollback()
        raise
    finally:
        conn.row_factory = row_factory
    report.retired = len(report.ghosts)
    log.info("indexer.ghost_items.retired", disk=disk.label, retired=report.retired)
    return report
