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

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.conf.models import Config

from personalscraper.logger import get_logger

log = get_logger("library.disk_cleaner")

from personalscraper.text_utils import JUNK_FILE_NAMES as _JUNK_FILES  # noqa: E402

# --- Orphan-detection constants -------------------------------------------

# Video extensions considered for "main video" presence. Subtitle/audio-only
# files do not count: a release with only an .mp3 or .srt is not a watchable
# release. Audiobook items (.m4b) are intentionally excluded from this check
# because the orphan mode targets video releases, not audiobook collections.
_VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mkv", ".mp4", ".avi", ".m4v", ".webm", ".mov", ".ts", ".m2ts", ".mpg", ".mpeg",
})

# A "main" video must be at least this large. Trailers and shorts under this
# threshold do not count, even if their filename does not match the trailer
# pattern. 50 MB filters out lyric clips while still accepting low-bitrate
# 30-min episodes (~30 MB / min × 30 ≈ a comfortable margin).
_MAIN_VIDEO_MIN_BYTES: int = 50 * 1024 * 1024

# Filename markers that demote a video file to "trailer / extra" status —
# matched case-insensitively against the basename.
_TRAILER_MARKERS: tuple[str, ...] = ("trailer", "teaser", "sample", "extra")

# TV-show season folder names (re-using the same regex as the indexer).
_TV_SEASON_DIR_RE = re.compile(
    r"^(?:saison|season)\s*\d+$|^specials?$",
    re.IGNORECASE,
)

# Categories whose "main content" is not a video file. ``orphans`` mode
# always skips these because its definition of orphan ("no main video") is
# meaningless for them. An audiobook with only the cover image left is also
# an orphan, but identifying that requires inspecting .m4b / .mp3 presence,
# which is out of scope for this video-centric mode. Use --category-specific
# tooling for those instead.
_ORPHAN_NON_VIDEO_CATEGORIES: frozenset[str] = frozenset({"audiobooks"})


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

    ghosts: list[str] = []
    try:
        _scandir_rmtree(path, ghosts=ghosts)
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"Deleted {label}: {path} ({size} bytes)")
        log.info("library_clean_deleted_dir", label=label, path=str(path))
        # Write-through: notify the indexer that this subtree was removed.
        _publish_deleted(path, label, db_path)
    except OSError as exc:
        # Most common failure: ENOTEMPTY raised by os.rmdir(path) because at
        # least one ghost dirent (NFC/NFD inconsistency) blocked the leaf
        # walk. Surface that as a precise error message and list the ghost
        # paths so the operator can decide on a manual fix (typically
        # unmount + fsck of the NTFS volume).
        if ghosts:
            ghost_summary = ", ".join(g.rsplit("/", 1)[-1] for g in ghosts[:3])
            extra = f" ({len(ghosts) - 3} more)" if len(ghosts) > 3 else ""
            result.error_count += 1
            result.errors.append(
                f"Partial delete of {label}: {path} — "
                f"{len(ghosts)} ghost dirent(s) blocking rmdir: "
                f"{ghost_summary}{extra}. NTFS NFC/NFD inconsistency; "
                "unmount + fsck required."
            )
            log.warning(
                "library_clean_ghost_dirent",
                label=label,
                path=str(path),
                ghost_count=len(ghosts),
                ghost_sample=ghosts[:5],
                error=str(exc),
            )
        else:
            result.error_count += 1
            result.errors.append(f"Failed to delete {label}: {path} — {exc}")
            log.warning(
                "library_clean_ntfs_error",
                label=label,
                path=str(path),
                exc_info=True,
                error=str(exc),
            )


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


def _has_main_video(directory: Path) -> bool:
    """Return True if *directory* contains at least one main video file.

    A "main" video is any file whose extension is in :data:`_VIDEO_EXTENSIONS`,
    whose size is at least :data:`_MAIN_VIDEO_MIN_BYTES`, and whose basename
    does not contain a trailer / extra marker (``trailer``, ``teaser``,
    ``sample``, ``extra``). For TV shows, ``Saison NN/`` and ``Season NN/``
    sub-folders are descended into one level — the orphan check must consider
    episodes, not just files at the show root.

    The function returns on the first match (short-circuit). On any OSError
    listing the directory it conservatively returns True, because we never
    want to delete a directory we cannot inspect.

    Args:
        directory: Absolute path to the release / show root to inspect.

    Returns:
        True if a main video is present (or the directory is unreadable),
        False otherwise.
    """
    try:
        entries = list(directory.iterdir())
    except OSError:
        return True

    for entry in entries:
        if entry.is_file() and _looks_like_main_video(entry):
            return True
        if entry.is_dir() and _TV_SEASON_DIR_RE.match(entry.name):
            try:
                for sub in entry.iterdir():
                    if sub.is_file() and _looks_like_main_video(sub):
                        return True
            except OSError:
                return True
    return False


def _looks_like_main_video(path: Path) -> bool:
    """Return True if *path* is a substantial video file (not a trailer/sample)."""
    if path.suffix.lower() not in _VIDEO_EXTENSIONS:
        return False
    stem_lower = path.stem.lower()
    if any(marker in stem_lower for marker in _TRAILER_MARKERS):
        return False
    try:
        return path.stat().st_size >= _MAIN_VIDEO_MIN_BYTES
    except OSError:
        return False


def _is_orphan_release_dir(media_dir: Path) -> bool:
    """Return True if *media_dir* looks like a stale release with no main video.

    A release directory is considered an orphan when it has no main video
    file at the root and no episode in any season sub-folder. Such directories
    typically result from a manual delete of the video file that left behind
    the ``.actors/`` thumbnails, the ``-trailer.mp4`` extra, the ``.nfo``,
    and the artwork — a real-world residue pattern observed across this
    project's library after partial migrations.

    The directory must contain something (an empty dir is handled by the
    existing ``--only empty`` mode, not this one).

    Args:
        media_dir: Absolute path to the candidate release directory.

    Returns:
        True if the directory is non-empty AND contains no main video.
    """
    if _is_effectively_empty(media_dir):
        return False
    return not _has_main_video(media_dir)


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
        only: Filter cleanup type: "actors", "empty", "junk", "release",
            "orphans", or None (all). ``orphans`` removes release dirs that
            have no main video file (typical residue: ``.actors/`` + trailer
            + NFO left behind after a manual video delete) and is opt-in:
            it is NEVER part of the default "all" run because deletion is
            irreversible at the release-dir granularity.
        disk_filter: Only clean this disk (by disk.id). None = all.
        category_filter: Only clean this category_id. None = all.

    Returns:
        CleanResult with counts and details.
    """
    result = CleanResult(dry_run=not apply)

    # Orphans is opt-in: only triggered when the user passes --only orphans.
    # All other modes keep their default "include in all" behaviour.
    clean_actors = only in (None, "actors")
    clean_empty = only in (None, "empty")
    clean_junk = only in (None, "junk")
    clean_release = only in (None, "release")
    clean_orphans = only == "orphans"

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

            # Orphan mode targets video releases only — audiobooks and any
            # future non-video category have a different "main content"
            # definition and would otherwise be flagged as orphans because
            # their .m4b / .mp3 / etc. files are not in _VIDEO_EXTENSIONS.
            skip_orphans_for_category = (
                clean_orphans and category_id in _ORPHAN_NON_VIDEO_CATEGORIES
            )

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                if clean_orphans:
                    if skip_orphans_for_category:
                        continue
                    if _is_orphan_release_dir(media_dir):
                        _delete_dir(
                            media_dir,
                            result,
                            not apply,
                            "orphan release",
                            config.indexer.db_path,
                        )
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
