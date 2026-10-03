"""Filesystem-level cleanup for the media library — remove .actors/, empty dirs, junk files.

Dry-run by default. Requires --apply to actually delete.
Handles NTFS deletion failures gracefully (per-item error, continues).
Folder deletion goes through :func:`personalscraper.indexer.deletion.delete_media_folder`,
which tolerates NTFS ghost-dirents (macFUSE/NTFS known issue).

``clean_library`` accepts a ``Config`` object and resolves folder names
from ``config.category(id).folder_name``. Disk filter uses ``disk.id``;
category filter uses ``category_id``.

Write-through: every real deletion (not dry-run) publishes a best-effort
outbox event (folders: inside ``delete_media_folder``; junk files: here) so
the indexer can reconcile removed files at the next drain cycle (DESIGN
§10.2).  The event uses ``op='move'`` with an empty ``dst_rel_path`` to
signal removal.  On any outbox error the deletion is still reported as
successful — the indexer will reconcile the drift at the next scan.

Moved from the legacy library disk-cleaner module during lib-fold Phase 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

from personalscraper._fs_utils import is_apple_double
from personalscraper.conf.preprod_guard import PreprodGuardError
from personalscraper.core.delete_permit import ALLOW, AllowAllPermit, DeletePermit, PermitDecision
from personalscraper.core.sqlite._fs_probe import is_mounted
from personalscraper.indexer.deletion import DeleteOutcome, _publish_deleted, delete_media_folder
from personalscraper.indexer.destructive_journal import OP_DELETE, record_destruction
from personalscraper.logger import get_logger

log = get_logger("library.disk_cleaner")

# --- Orphan-detection constants -------------------------------------------
# Video extensions considered for "main video" presence — canonical SSOT from
# core.media_types. Subtitle/audio-only files do not count: a release with
# only an .mp3 or .srt is not a watchable release. Audiobook items (.m4b) are
# intentionally excluded from this check because the orphan mode targets video
# releases, not audiobook collections.
# Note: core.media_types stores extensions WITHOUT leading dot (e.g. "mkv").
# Callers must use ``path.suffix.lower().lstrip(".")`` when comparing.
from personalscraper.core.media_types import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS  # noqa: E402
from personalscraper.text_utils import JUNK_FILE_NAMES as _JUNK_FILES  # noqa: E402

# A "main" video must be at least this large. Trailers and shorts under this
# threshold do not count, even if their filename does not match the trailer
# pattern. 50 MB filters out lyric clips while still accepting low-bitrate
# 30-min episodes (~30 MB / min × 30 ≈ a comfortable margin).
_MAIN_VIDEO_MIN_BYTES: int = 50 * 1024 * 1024

# Filename markers that demote a video file to "trailer / extra" status —
# matched case-insensitively against the basename.
_TRAILER_MARKERS: tuple[str, ...] = ("trailer", "teaser", "sample", "extra")

# TV-show season folder names — canonical SSOT from naming_patterns.
from personalscraper.naming_patterns import SEASON_DIR_RE as _TV_SEASON_DIR_RE  # noqa: E402

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
        skipped_by_obligation: Number of deletions vetoed by the
            :class:`~personalscraper.core.delete_permit.DeletePermit`
            (hard-skip — counted but never deleted in both dry-run and
            apply modes).
        details: Per-item details (path + action).
        errors: Per-item error details (path + error message).
    """

    dry_run: bool = True
    deleted_count: int = 0
    error_count: int = 0
    freed_bytes: int = 0
    skipped_by_obligation: int = 0
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _delete_dir(
    path: Path,
    result: CleanResult,
    dry_run: bool,
    label: str,
    db_path: Path,
    permit: DeletePermit = AllowAllPermit(),
    config: Config | None = None,
) -> None:
    """Delete a directory through :func:`delete_media_folder` and fold its outcome into *result*.

    The primitive consults *permit*, removes the tree (tolerating NTFS ghost
    dirents), journals the deletion and publishes the best-effort outbox event
    so the indexer can reconcile removed content at drain time. A VETO is a
    hard skip, counted as ``skipped_by_obligation``; the consult runs in both
    dry-run and apply modes so a preview shows what would be skipped.

    Args:
        path: Directory to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging (e.g. ".actors", "empty dir").
        db_path: Resolved ``Config.indexer.db_path`` forwarded to
            :func:`delete_media_folder` for the journal and outbox (DESIGN §9.4).
        permit: Deletion authority (fail-open default: AllowAllPermit).
        config: Loaded configuration forwarded to :func:`delete_media_folder`, whose
            preprod guard needs it under ``staging``.

    Returns:
        None. *result* is updated in place; a deletion the preprod guard refuses is
        counted as an error.
    """
    try:
        outcome = delete_media_folder(
            path, db_path=db_path, actor="disk-clean", label=label, permit=permit, dry_run=dry_run, config=config
        )
    except PreprodGuardError as exc:
        result.error_count += 1
        result.errors.append(f"Refused to delete {label}: {path} — {exc}")
        return
    if outcome.outcome is DeleteOutcome.VETOED:
        result.skipped_by_obligation += 1
        return
    if outcome.outcome is DeleteOutcome.DELETED:
        result.deleted_count += outcome.deleted_count
        result.freed_bytes += outcome.size_bytes
        prefix = "[DRY-RUN] Would delete" if dry_run else "Deleted"
        result.details.append(f"{prefix} {label}: {path} ({outcome.size_bytes} bytes)")
        return
    result.error_count += 1
    if outcome.ghosts:
        ghost_summary = ", ".join(g.rsplit("/", 1)[-1] for g in outcome.ghosts[:3])
        extra = f" ({len(outcome.ghosts) - 3} more)" if len(outcome.ghosts) > 3 else ""
        result.errors.append(
            f"Partial delete of {label}: {path} — "
            f"{len(outcome.ghosts)} ghost dirent(s) blocking rmdir: "
            f"{ghost_summary}{extra}. NTFS NFC/NFD inconsistency; "
            "unmount + fsck required."
        )
    else:
        result.errors.append(f"Failed to delete {label}: {path} — {outcome.error}")


def _delete_file(
    path: Path,
    result: CleanResult,
    dry_run: bool,
    label: str,
    db_path: Path,
    permit: DeletePermit = AllowAllPermit(),
) -> None:
    """Delete a single file, handling errors gracefully.

    On a successful real deletion (not dry-run) publishes a best-effort
    outbox event so the indexer can reconcile removed content at drain time.

    Consults *permit* before any deletion (VETO → hard-skip, counted as
    ``skipped_by_obligation``). The consult runs in both dry-run and apply
    modes so a dry-run preview correctly shows what would be skipped.

    Args:
        path: File to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging.
        db_path: Resolved ``Config.indexer.db_path`` forwarded to
            :func:`_publish_deleted` (DESIGN §9.4).
        permit: Deletion authority (fail-open default: AllowAllPermit).
    """
    # F2: the consult itself is fail-open (DESIGN §7.3 / §9). A permit whose
    # may_delete raises must NOT abort cleanup — treat the error as ALLOW (the
    # deletion proceeds) and log it.
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
        result.skipped_by_obligation += 1
        return

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
        # §7 / Star City — append-only destruction trail.
        record_destruction(db_path, op=OP_DELETE, path=path, actor="disk-clean", detail=f"Nettoyage disque — {label}")
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
            if item.name not in _JUNK_FILES and not is_apple_double(item.name):
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
    if path.suffix.lower().lstrip(".") not in _VIDEO_EXTENSIONS:
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
    permit: DeletePermit = AllowAllPermit(),
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
        permit: Deletion authority consulted before each deletion.
            Defaults to :class:`~personalscraper.core.delete_permit.AllowAllPermit`
            (fail-open — always ALLOW). Inject a real ``DeletePermit``
            via the command boundary when seed-safety is desired.

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
        if not is_mounted(disk.path):
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
            skip_orphans_for_category = clean_orphans and category_id in _ORPHAN_NON_VIDEO_CATEGORIES

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                if clean_orphans:
                    if skip_orphans_for_category:
                        continue
                    if _is_orphan_release_dir(media_dir):
                        db_path = config.indexer.db_path
                        assert db_path is not None, "indexer.db_path must be resolved"
                        _delete_dir(
                            media_dir,
                            result,
                            not apply,
                            "orphan release",
                            db_path,
                            permit=permit,
                            config=config,
                        )
                    continue
                db_path = config.indexer.db_path
                assert db_path is not None, "indexer.db_path must be resolved"
                _clean_media_dir(
                    media_dir,
                    result,
                    not apply,
                    clean_actors,
                    clean_empty,
                    clean_junk,
                    clean_release,
                    db_path,
                    permit=permit,
                    config=config,
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
    permit: DeletePermit = AllowAllPermit(),
    config: Config | None = None,
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
        permit: Deletion authority forwarded to ``_delete_dir`` / ``_delete_file``
            (fail-open default: AllowAllPermit).
        config: Loaded configuration forwarded to ``_delete_dir`` for the preprod guard.
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
            _delete_dir(item, result, dry_run, ".actors", db_path, permit=permit, config=config)
            continue

        # Junk files (including macOS resource forks "._*")
        if clean_junk and (name in _JUNK_FILES or is_apple_double(name)) and item.is_file():
            _delete_file(item, result, dry_run, "junk file", db_path, permit=permit)
            continue

        # Empty directories and release-group artifacts
        if item.is_dir() and _is_effectively_empty(item):
            # Detect release-group style names (contain dots + group suffix)
            is_release = "." in name and any(c.isupper() for c in name.split(".")[-1] if c.isalpha())
            if clean_release and is_release:
                _delete_dir(item, result, dry_run, "release artifact", db_path, permit=permit, config=config)
            elif clean_empty:
                _delete_dir(item, result, dry_run, "empty dir", db_path, permit=permit, config=config)
