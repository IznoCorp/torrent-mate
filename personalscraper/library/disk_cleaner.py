"""Library disk cleaner — remove .actors/, empty dirs, junk files.

Dry-run by default. Requires --apply to actually delete.
Handles NTFS deletion failures gracefully (per-item error, continues).

``clean_library`` accepts a ``Config`` object and resolves folder names
from ``config.category(id).folder_name``. Disk filter uses ``disk.id``;
category filter uses ``category_id``.

Write-through: every real deletion (not dry-run) publishes a best-effort
outbox event via :func:`personalscraper.indexer.outbox.publish_event` so
the indexer can reconcile removed files at the next drain cycle (DESIGN
§10.2).  The event uses ``op='move'`` with an empty ``dst_rel_path`` to
signal removal.  On any outbox error the deletion is still reported as
successful — the indexer will reconcile the drift at the next scan.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.conf.models import Config

from personalscraper.logger import get_logger

log = get_logger("library.disk_cleaner")

from personalscraper.text_utils import JUNK_FILE_NAMES as _JUNK_FILES  # noqa: E402


@dataclass
class CleanResult:
    """Result of a library cleanup operation.

    Attributes:
        dry_run: Whether this was a dry-run (no actual deletions).
        deleted_count: Number of items deleted (or would-be-deleted in dry-run).
        error_count: Number of deletion failures (NTFS errors, etc.).
        freed_bytes: Approximate bytes freed (or would be freed).
        details: Per-item details (path + action).
        errors: Per-item error details (path + error message).
    """

    dry_run: bool = True
    deleted_count: int = 0
    error_count: int = 0
    freed_bytes: int = 0
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


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
        from personalscraper.indexer.outbox import disk_id_for_path, publish_event  # noqa: PLC0415

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


def _delete_dir(path: Path, result: CleanResult, dry_run: bool, label: str, db_path: Path) -> None:
    """Delete a directory, handling NTFS errors gracefully.

    On a successful real deletion (not dry-run) publishes a best-effort
    outbox event so the indexer can reconcile removed content at drain time.

    Args:
        path: Directory to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging (e.g. ".actors", "empty dir").
        db_path: Resolved ``Config.indexer.db_path`` forwarded to
            :func:`_publish_deleted` (DESIGN §9.4).
    """
    size = _dir_size(path)
    if dry_run:
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"[DRY-RUN] Would delete {label}: {path} ({size} bytes)")
        return

    try:
        shutil.rmtree(path)
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"Deleted {label}: {path} ({size} bytes)")
        log.info("library_clean_deleted_dir", label=label, path=str(path))
        # Write-through: notify the indexer that this subtree was removed.
        _publish_deleted(path, label, db_path)
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Failed to delete {label}: {path} — {exc}")
        log.warning("library_clean_ntfs_error", label=label, path=str(path), exc_info=True, error=str(exc))


def _delete_file(path: Path, result: CleanResult, dry_run: bool, label: str, db_path: Path) -> None:
    """Delete a single file, handling errors gracefully.

    On a successful real deletion (not dry-run) publishes a best-effort
    outbox event so the indexer can reconcile removed content at drain time.

    Args:
        path: File to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging.
        db_path: Resolved ``Config.indexer.db_path`` forwarded to
            :func:`_publish_deleted` (DESIGN §9.4).
    """
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    if dry_run:
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"[DRY-RUN] Would delete {label}: {path}")
        return

    try:
        path.unlink()
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"Deleted {label}: {path}")
        # Write-through: notify the indexer that this file was removed.
        _publish_deleted(path, label, db_path)
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Failed to delete {label}: {path} — {exc}")
        log.warning("library_clean_file_delete_failed", label=label, path=str(path), exc_info=True, error=str(exc))


def _is_effectively_empty(directory: Path) -> bool:
    """Check if a directory is empty or contains only junk files."""
    try:
        for item in directory.iterdir():
            if item.name not in _JUNK_FILES and not item.name.startswith("._"):
                return False
        return True
    except OSError:
        return False


def clean_library(
    config: Config,
    apply: bool = False,
    only: str | None = None,
    disk_filter: str | None = None,
    category_filter: str | None = None,
) -> CleanResult:
    """Clean the media library across storage disks.

    Dry-run by default — set apply=True to actually delete.
    Iterates ``config.disks``, resolves folder names from
    ``config.category(id).folder_name``, and cleans media directories.

    On real deletions (``apply=True``) each removed file or directory is
    reported to the indexer outbox (best-effort write-through per DESIGN
    §10.2) so the indexer can reconcile removed content at drain time.

    Args:
        config: Config with disk and category definitions.
        apply: If True, actually delete files. If False, only report.
        only: Filter cleanup type: "actors", "empty", "junk", "release", or None (all).
        disk_filter: Only clean this disk (by disk.id). None = all.
        category_filter: Only clean this category_id. None = all.

    Returns:
        CleanResult with counts and details.
    """
    result = CleanResult(dry_run=not apply)

    clean_actors = only in (None, "actors")
    clean_empty = only in (None, "empty")
    clean_junk = only in (None, "junk")
    clean_release = only in (None, "release")

    for disk in config.disks:
        if disk_filter and disk.id != disk_filter:
            continue
        if not disk.path.exists():
            log.warning("library_disk_not_mounted", disk=disk.id, path=str(disk.path))
            continue

        for category_id in disk.categories:
            if category_filter and category_id != category_filter:
                continue

            # Resolve physical folder name from config
            cat_cfg = config.category(category_id)
            category_dir = disk.path / cat_cfg.folder_name
            if not category_dir.is_dir():
                log.debug("library_category_not_found", category_dir=str(category_dir), disk=disk.id)
                continue

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                _clean_media_dir(
                    media_dir,
                    result,
                    not apply,
                    clean_actors,
                    clean_empty,
                    clean_junk,
                    clean_release,
                    config.indexer.db_path,
                )

    return result


def _clean_media_dir(
    media_dir: Path,
    result: CleanResult,
    dry_run: bool,
    clean_actors: bool,
    clean_empty: bool,
    clean_junk: bool,
    clean_release: bool,
    db_path: Path,
) -> None:
    """Clean a single media directory.

    Args:
        media_dir: Path to media directory.
        result: CleanResult to update.
        dry_run: If True, only count.
        clean_actors: Whether to remove .actors/.
        clean_empty: Whether to remove empty dirs.
        clean_junk: Whether to remove junk files.
        clean_release: Whether to remove release-group artifacts.
        db_path: Resolved ``Config.indexer.db_path`` forwarded to deletion
            helpers for write-through outbox publish (DESIGN §9.4).
    """
    try:
        entries = list(media_dir.iterdir())
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Cannot list directory: {media_dir} — {exc}")
        log.warning("library_clean_list_error", media_dir=str(media_dir), exc_info=True, error=str(exc))
        return

    for item in entries:
        name = item.name

        # .actors directory
        if clean_actors and name == ".actors" and item.is_dir():
            _delete_dir(item, result, dry_run, ".actors", db_path)
            continue

        # Junk files (including macOS resource forks "._*")
        if clean_junk and (name in _JUNK_FILES or name.startswith("._")) and item.is_file():
            _delete_file(item, result, dry_run, "junk file", db_path)
            continue

        # Empty directories and release-group artifacts
        if item.is_dir() and _is_effectively_empty(item):
            # Detect release-group style names (contain dots + group suffix)
            is_release = "." in name and any(c.isupper() for c in name.split(".")[-1] if c.isalpha())
            if clean_release and is_release:
                _delete_dir(item, result, dry_run, "release artifact", db_path)
            elif clean_empty:
                _delete_dir(item, result, dry_run, "empty dir", db_path)
