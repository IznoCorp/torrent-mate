"""The one folder-deletion primitive: consult the permit, delete, journal, publish.

Extracted from the disk cleaner's ``_delete_dir`` so that every folder deletion
shares the same trail: a deletion-authority consult (fail-open), an
NTFS-tolerant recursive removal, one ``destructive_op`` journal row and one
best-effort outbox event the indexer drains to reconcile the removed subtree.

A journal or outbox failure never raises: the filesystem operation already
succeeded and the indexer reconciles drift at its next scan.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf.environment import is_sandboxed
from personalscraper.conf.sandbox_guard import SandboxGuardError, assert_within_sandbox
from personalscraper.core.delete_permit import ALLOW, AllowAllPermit, DeletePermit, PermitDecision
from personalscraper.core.identity import ItemId
from personalscraper.core.sqlite import refuse_newer_schema
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.indexer.destructive_journal import OP_DELETE, record_destruction
from personalscraper.indexer.migrations import MIGRATIONS_DIR as LIBRARY_MIGRATIONS_DIR
from personalscraper.indexer.phantom_rows import tombstone_item
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("library.disk_cleaner")


class DeleteOutcome(StrEnum):
    """How one folder-deletion request ended."""

    DELETED = "deleted"
    VETOED = "vetoed"
    FAILED = "failed"


@dataclass(frozen=True)
class DeleteResult:
    """What :func:`delete_media_folder` did, with what its callers report.

    Attributes:
        outcome: How the request ended.
        size_bytes: Bytes under the folder before deletion (0 when vetoed).
        deleted_count: 1 when the folder was deleted (or would be, in dry-run), else 0.
        ghosts: Paths of entries that blocked the removal (NTFS NFC/NFD ghost dirents).
        error: The OS error text when *outcome* is ``FAILED``.
    """

    outcome: DeleteOutcome
    size_bytes: int = 0
    deleted_count: int = 0
    ghosts: tuple[str, ...] = ()
    error: str | None = None


def _dir_size(path: Path) -> int:
    """Calculate total byte size of a directory recursively."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    continue
    except OSError as exc:
        log.warning("library_clean_dir_size_error", path=str(path), exc_info=True, error=str(exc))
    return total


def _publish_deleted(path: Path, label: str, db_path: Path) -> None:
    """Publish a best-effort outbox event signalling that *path* was removed.

    Uses ``op='move'`` with ``src_rel_path=<path-str>`` and an empty
    ``dst_rel_path`` as a convention understood by the drainer to mean the
    path was deleted from the filesystem.  Any exception is swallowed — the
    FS operation already succeeded; the indexer reconciles drift at the next
    scan.

    Args:
        path: Absolute path that was deleted.
        label: Human label for logging (e.g. ``".actors"``, ``"junk file"``).
        db_path: Resolved ``Config.indexer.db_path`` so the event lands in the
            user-configured DB (DESIGN §9.4).
    """
    try:
        from personalscraper.indexer.outbox._disk import disk_id_for_path  # noqa: PLC0415
        from personalscraper.indexer.outbox._publish import publish_event  # noqa: PLC0415

        resolved = disk_id_for_path(path, db_path)
        if resolved is None:
            # Path not in any mounted disk's mount_path — skip outbox publish.
            return
        disk_pk, rel_path = resolved
        publish_event(
            disk_pk,
            op="move",
            payload={
                "src_rel_path": rel_path,
                "dst_rel_path": "",
                "filename": path.name,
                "size_bytes": None,
                "mtime_ns": None,
                "_clean_label": label,
            },
            db_path=db_path,
            source="scanner",
        )
    except Exception as exc:  # noqa: BLE001
        log.debug(
            "library_clean_outbox_skipped",
            path=str(path),
            label=label,
            error=str(exc),
        )


def _scandir_rmtree(path: Path, ghosts: list[str] | None = None) -> None:
    """Recursive delete that survives NTFS-via-macFUSE NFC/NFD filename quirks.

    ``shutil.rmtree`` walks the tree by re-listing each directory and then
    re-stat'ing each entry by its decoded name. macFUSE-NTFS sometimes returns
    a filename in one Unicode normalization form (NFD with combining accent)
    while the kernel inode is reachable only via the other (NFC, single
    codepoint), so the follow-up ``os.unlink(name)`` raises ``FileNotFoundError``
    even though the file was just listed.

    This walker:

    * Uses the ``os.DirEntry`` objects from :func:`os.scandir` and their
      ``.path`` attribute (no re-encoding round-trip).
    * Tolerates **ghost dirents** — entries that ``scandir`` lists but the
      kernel cannot ``stat`` / ``unlink``. These are recorded in *ghosts* and
      skipped. They typically come from filesystem-level inconsistencies that
      only an unmount + fsck can repair; we report them rather than abort the
      whole rmtree, so the caller can free what is freeable.
    * Bottom-up traversal so directories are emptied before they are removed.

    Args:
        path: Directory to remove (symlinks are unlinked, not descended).
        ghosts: Mutable list that receives the path of every entry that
            could not be removed because of a ghost-dirent inconsistency.
            Pass ``None`` (default) to disable collection. The caller may
            then decide whether the parent ``rmdir`` failure is fatal or
            should be reported as a partial cleanup.

    Raises:
        OSError: If the final ``rmdir`` of *path* itself fails for a reason
            other than ``ENOTEMPTY`` (i.e. caused by a ghost remnant). When
            ``ENOTEMPTY`` is raised the function lets it propagate so the
            caller can correlate with the ghost list.
    """
    if path.is_symlink() or not path.is_dir():
        os.unlink(path)
        return

    with os.scandir(path) as it:
        entries = list(it)
    for entry in entries:
        try:
            is_subdir = entry.is_dir(follow_symlinks=False)
        except OSError:
            # Ghost dirent: even is_dir() round-trips through stat and may
            # fail. Treat as a leaf-level ghost so we keep walking siblings.
            if ghosts is not None:
                ghosts.append(entry.path)
            continue
        try:
            if is_subdir:
                _scandir_rmtree(Path(entry.path), ghosts=ghosts)
            else:
                os.unlink(entry.path)
        except FileNotFoundError:
            # Classic NTFS-macFUSE NFC/NFD ghost: listed but unreachable.
            if ghosts is not None:
                ghosts.append(entry.path)
            # Carry on with siblings; the parent rmdir at the bottom of
            # the recursion will surface ENOTEMPTY if any ghost remains.
            continue
    os.rmdir(path)


def delete_media_folder(
    path: Path,
    *,
    db_path: Path,
    actor: str,
    label: str,
    permit: DeletePermit = AllowAllPermit(),
    run_uid: str | None = None,
    dry_run: bool = False,
    config: Config | None = None,
) -> DeleteResult:
    """Consult *permit*, delete the folder, journal it and publish the outbox event.

    The permit consult is fail-open (DESIGN §7.3 / §9): a permit whose
    ``may_delete`` raises is treated as ALLOW and logged, so a faulty authority
    never fails a clean run closed. It runs in dry-run too, so a preview shows
    what would be skipped. Never raises on a journal or outbox failure.

    Args:
        path: Folder to delete.
        db_path: Resolved ``Config.indexer.db_path`` (journal and outbox target).
        actor: Who deletes (``"disk-clean"``, …), written to the journal.
        label: Human label for logs and the journal (e.g. ``".actors"``).
        permit: Deletion authority (fail-open default: ``AllowAllPermit``).
        run_uid: Optional correlating ``pipeline_run`` uid for the journal row.
        dry_run: Consult the permit and measure the folder; delete, journal and
            publish nothing.
        config: The loaded configuration, naming the sandbox's roots. Only read in
            a sandbox, where it is required (without it the roots are unknown).

    Returns:
        A :class:`DeleteResult`: ``VETOED`` when the permit refused, ``FAILED``
        when the removal raised an ``OSError`` (``ghosts`` and ``error`` filled),
        otherwise ``DELETED`` with the folder's size.

    Raises:
        SandboxGuardError: In a sandbox, *path* is outside the sandbox's marked,
            mounted roots, or no *config* was given. Nothing is deleted or journaled.
    """
    if is_sandboxed():
        if config is None:
            raise SandboxGuardError(f"cannot delete {path}: a sandbox needs the config to know its roots")
        assert_within_sandbox(config, path)
    try:
        decision: PermitDecision = permit.may_delete(path)
    except Exception as exc:
        log.warning("disk_cleaner.permit_error", path=str(path), label=label, error=str(exc))
        decision = ALLOW
    if decision is not ALLOW:
        log.info(
            "disk_cleaner.skipped_by_obligation",
            path=str(path),
            label=label,
            reason=str(decision),
        )
        return DeleteResult(DeleteOutcome.VETOED)

    size = _dir_size(path)
    if dry_run:
        return DeleteResult(DeleteOutcome.DELETED, size_bytes=size, deleted_count=1)

    ghosts: list[str] = []
    try:
        _scandir_rmtree(path, ghosts=ghosts)
    except OSError as exc:
        # Most common failure: ENOTEMPTY raised by os.rmdir(path) because at
        # least one ghost dirent (NFC/NFD inconsistency) blocked the leaf
        # walk. The caller gets the ghost list so the operator can decide on a
        # manual fix (typically unmount + fsck of the NTFS volume).
        if ghosts:
            log.warning(
                "library_clean_ghost_dirent",
                label=label,
                path=str(path),
                ghost_count=len(ghosts),
                ghost_sample=ghosts[:5],
                error=str(exc),
            )
        else:
            log.warning(
                "library_clean_ntfs_error",
                label=label,
                path=str(path),
                exc_info=True,
                error=str(exc),
            )
        return DeleteResult(DeleteOutcome.FAILED, size_bytes=size, ghosts=tuple(ghosts), error=str(exc))

    log.info("library_clean_deleted_dir", label=label, path=str(path))
    # §7 / Star City — append-only destruction trail (who/what/when/where).
    record_destruction(
        db_path,
        op=OP_DELETE,
        path=path,
        actor=actor,
        detail=f"Nettoyage disque — {label}",  # french-ok: journal detail stored verbatim in destructive_op
        run_uid=run_uid,
    )
    # Write-through: notify the indexer that this subtree was removed.
    _publish_deleted(path, label, db_path)
    return DeleteResult(DeleteOutcome.DELETED, size_bytes=size, deleted_count=1)


def remove_items(db_path: Path, item_ids: Sequence[ItemId], *, actor: str, reason: str) -> int:
    """Remove index rows (their releases, files, seasons and episodes by cascade), tombstoned and journaled.

    The rows go in one transaction, each with its ``deleted_item`` tombstone; the journal
    rows (``record_destruction(op="delete", path="index:media_item/<id>")``) are written
    after it commits, through the journal's own connection, and never raise.

    Args:
        db_path: Path of ``library.db``.
        item_ids: The ``media_item`` rows to remove.
        actor: Who deletes, written to the journal (``web:<account id>``).
        reason: The tombstones' ``deleted_item.reason``.

    Returns:
        The rows removed (a row already gone is not counted).

    Raises:
        sqlite3.Error: When the transaction fails; it is rolled back and nothing is removed.
    """
    if not item_ids:
        return 0
    now = int(time.time())
    removed: list[ItemId] = []
    with closing(sqlite3.connect(str(db_path), isolation_level=None)) as conn:
        refuse_newer_schema(conn, LIBRARY_MIGRATIONS_DIR)
        apply_pragmas(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            for item_id in dict.fromkeys(item_ids):
                if conn.execute("SELECT 1 FROM media_item WHERE id = ?", (item_id,)).fetchone() is None:
                    continue
                tombstone_item(conn, item_id, now, reason=reason)
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


__all__ = ["DeleteOutcome", "DeleteResult", "delete_media_folder", "remove_items"]
