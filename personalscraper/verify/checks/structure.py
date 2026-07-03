"""Filesystem-structure checks (DISPATCH stage).

Ported verbatim from ``verify/checker.py``:

- ``VideoPresent``    — both media types (movie non-recursive, TV recursive).
- ``NotSample``       — movie-only, conditional on at least one video file.
- ``NoEmptyDirs``     — both media types.
- ``SeasonStructure`` — TV-only.
- ``EpisodeRenamed``  — TV-only.
- ``RootVideoFiles``  — TV-only, only when ``tvshow.nfo`` exists.

Helpers (``_find_video_files``, ``_find_video_files_recursive``,
``_find_empty_dirs``, ``_find_unrenamed_episodes``) are copied verbatim;
Phase 3 consolidates the duplication.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_archive_filename
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from pathlib import Path

    from personalscraper.verify.checks.base import CheckContext, FixAction

# Minimum file size (bytes) to not be considered a sample (copied from checker.py).
_MIN_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB

# Episode file pattern (copied from checker.py _EPISODE_PATTERN).
_EPISODE_PATTERN = re.compile(r"^S\d{2}E\d{2}(?:-E\d{2})?(?: - .+)?\.\w+$")


@register_check
class VideoPresent:
    """Check that at least one video file exists."""

    name = "video_present"
    group = "structure"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "At least one video file must be present"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False when no video file exists.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``video_present`` result.
        """
        if ctx.media_type == "movie":
            video_files = _find_video_files(ctx.media_dir)
            message = "" if video_files else "No video file found"
        else:
            video_files = _find_video_files_recursive(ctx.media_dir)
            message = "" if video_files else "No video files found"
        return [
            CheckResult(
                name="video_present",
                passed=len(video_files) > 0,
                severity=Severity.ERROR,
                message=message,
            )
        ]


@register_check
class NotSample:
    """Check that the largest video is not a sample (movie-only)."""

    name = "not_sample"
    group = "structure"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie"})
    default_severity = Severity.WARNING
    description = "Largest video must not look like a sample"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[]`` when no video file exists; ``[CheckResult]`` otherwise.

        Mirrors ``check_movie``: the check is conditional on video presence.

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when no video file is present, else a single result.
        """
        video_files = _find_video_files(ctx.media_dir)
        if not video_files:
            return []
        largest = max(f.stat().st_size for f in video_files)
        is_sample = largest < _MIN_VIDEO_SIZE
        return [
            CheckResult(
                name="not_sample",
                passed=not is_sample,
                severity=Severity.WARNING,
                message=f"Largest video is {largest // (1024 * 1024)} MB (possible sample)" if is_sample else "",
            )
        ]


@register_check
class NoEmptyDirs:
    """Check that there are no empty subdirectories."""

    name = "no_empty_dirs"
    group = "structure"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "No empty subdirectories allowed"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False when empty subdirs exist.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``no_empty_dirs`` result.
        """
        empty_dirs = _find_empty_dirs(ctx.media_dir)
        return [
            CheckResult(
                name="no_empty_dirs",
                passed=len(empty_dirs) == 0,
                severity=Severity.ERROR,
                message=f"Empty subdirs: {', '.join(d.name for d in empty_dirs[:3])}" if empty_dirs else "",
                fixable=True,
            )
        ]

    def fix(self, ctx: "CheckContext") -> "list[FixAction]":
        """Remove empty subdirectories.

        Args:
            ctx: CheckContext (ctx.dry_run controls whether rmdir is applied).

        Returns:
            One FixAction per removed directory.
        """
        from personalscraper.logger import get_logger
        from personalscraper.verify.checks.base import FixAction

        log = get_logger("verify.checks.structure")
        actions = []
        try:
            # Sort so the emitted FixAction order is deterministic across
            # filesystems (APFS vs ext4 yield different iterdir/rglob order).
            for subdir in sorted(ctx.media_dir.rglob("*")):
                if subdir.is_dir() and not any(subdir.iterdir()):
                    prefix = "[DRY-RUN] Would remove" if ctx.dry_run else "Removed"
                    desc = f"{prefix} empty dir: {subdir.name}"
                    if not ctx.dry_run:
                        try:
                            subdir.rmdir()
                        except OSError as exc:
                            log.warning("no_empty_dirs_fix_failed", subdir=str(subdir), exc_info=True, error=str(exc))
                            continue
                    actions.append(FixAction(description=desc, old_path=subdir))
        except OSError as exc:
            log.warning("no_empty_dirs_fix_list_error", exc_info=True, error=str(exc))
        return actions


@register_check
class SeasonStructure:
    """Check that season directories hold properly-named episodes (TV-only)."""

    name = "season_structure"
    group = "structure"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.ERROR
    description = "Season directories must contain properly named episodes"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` for the ``season_structure`` check.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``season_structure`` result.
        """
        show_dir = ctx.media_dir
        season_dirs = sorted(
            (d for d in show_dir.iterdir() if d.is_dir() and SEASON_DIR_RE.match(d.name)),
            key=lambda d: d.name,
        )
        has_episodes_in_seasons = (
            any(any(_EPISODE_PATTERN.match(f.name) for f in sd.iterdir() if f.is_file()) for sd in season_dirs)
            if season_dirs
            else False
        )
        return [
            CheckResult(
                name="season_structure",
                passed=has_episodes_in_seasons,
                severity=Severity.ERROR,
                message="" if has_episodes_in_seasons else "No Saison XX/ with properly named episodes",
            )
        ]


@register_check
class EpisodeRenamed:
    """Check that all videos in season dirs match the episode pattern (TV-only)."""

    name = "episode_renamed"
    group = "structure"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.ERROR
    description = "All season-dir videos must match SxxExx pattern"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` for the ``episode_renamed`` check.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``episode_renamed`` result.
        """
        show_dir = ctx.media_dir
        season_dirs = sorted(
            (d for d in show_dir.iterdir() if d.is_dir() and SEASON_DIR_RE.match(d.name)),
            key=lambda d: d.name,
        )
        unrenamed = _find_unrenamed_episodes(season_dirs)
        return [
            CheckResult(
                name="episode_renamed",
                passed=len(unrenamed) == 0,
                severity=Severity.ERROR,
                message=f"Unrenamed episodes: {', '.join(f.name for f in unrenamed[:3])}" if unrenamed else "",
            )
        ]


@register_check
class RootVideoFiles:
    """Check for stray videos at the show root (TV-only; only when scraped)."""

    name = "root_video_files"
    group = "structure"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.ERROR
    description = "No unprocessed video files at the show root"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[]`` unless ``tvshow.nfo`` exists; ``[CheckResult]`` otherwise.

        Mirrors ``check_tvshow``: the check runs only when the show has been
        scraped (i.e. ``tvshow.nfo`` is present).

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when ``tvshow.nfo`` is absent, else a single result.
        """
        show_dir = ctx.media_dir
        nfo_path = show_dir / ctx.patterns.tvshow_nfo
        if not nfo_path.exists():
            return []
        root_videos = sorted(
            f for f in show_dir.iterdir() if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        )
        if root_videos:
            names = ", ".join(f.name for f in root_videos[:3])
            suffix = f" (+{len(root_videos) - 3} more)" if len(root_videos) > 3 else ""
            message = f"Unprocessed video files at root: {names}{suffix}"
        else:
            message = ""
        return [
            CheckResult(
                name="root_video_files",
                passed=len(root_videos) == 0,
                severity=Severity.ERROR,
                message=message,
            )
        ]


@register_check
class NoArchiveFiles:
    """Check that no un-extracted archive files remain (both media types).

    Scene releases ship the real video inside a multi-part RAR set. The CLEAN
    step extracts them before scrape; if extraction failed (corrupt archive or
    missing ``unrar`` backend) the archives are deliberately preserved on disk.
    This check blocks dispatch of any item that still holds archive parts so a
    RAR set is never shipped to the library and the operator is alerted to
    extract it manually (DEV #1 safety net).
    """

    name = "no_archive_files"
    group = "structure"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "No un-extracted archive files (.rar/.r00/.zip/.7z) allowed"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False when archive files remain.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``no_archive_files`` result.
        """
        archives = sorted(f for f in ctx.media_dir.rglob("*") if f.is_file() and is_archive_filename(f.name))
        if archives:
            names = ", ".join(f.name for f in archives[:3])
            suffix = f" (+{len(archives) - 3} more)" if len(archives) > 3 else ""
            message = f"Un-extracted archives present: {names}{suffix}"
        else:
            message = ""
        return [
            CheckResult(
                name="no_archive_files",
                passed=len(archives) == 0,
                severity=Severity.ERROR,
                message=message,
            )
        ]


# --- module-level structure helpers (copied verbatim from checker.py) ---


def _find_video_files(directory: "Path") -> "list[Path]":
    """Find video files in a directory (non-recursive).

    Args:
        directory: Directory to search.

    Returns:
        List of video file paths, sorted by path for deterministic order.
    """
    return sorted(f for f in directory.iterdir() if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS)


def _find_video_files_recursive(directory: "Path") -> "list[Path]":
    """Find video files recursively in a directory tree.

    Args:
        directory: Root directory to search.

    Returns:
        List of video file paths, sorted by path for deterministic order.
    """
    results: list[Path] = []
    for ext in VIDEO_EXTENSIONS:
        results.extend(directory.rglob(f"*.{ext}"))
    return sorted(results)


def _find_empty_dirs(root: "Path") -> "list[Path]":
    """Find empty subdirectories recursively.

    A directory is considered empty if it contains no files (junk files
    like ``.DS_Store`` count as empty).

    Args:
        root: Root directory to scan.

    Returns:
        List of empty directory paths.
    """
    junk = {".DS_Store", "Thumbs.db"}
    empty = []
    # Sort so the returned empty-dir order (which feeds the result message and
    # the fix-action order) is deterministic across filesystems.
    for d in sorted(root.rglob("*")):
        if not d.is_dir():
            continue
        contents = list(d.iterdir())
        has_real_content = any(item.is_file() and item.name not in junk for item in contents)
        if not has_real_content and not any(item.is_dir() for item in contents):
            empty.append(d)
    return empty


def _find_unrenamed_episodes(season_dirs: "list[Path]") -> "list[Path]":
    """Find video files in season dirs that don't match the episode pattern.

    Args:
        season_dirs: List of ``Saison XX`` directories.

    Returns:
        List of video files that don't match ``S##E## - Title.ext``.
    """
    unrenamed = []
    for sd in season_dirs:
        # Sort within each season dir so the unrenamed-episode order (which
        # feeds the result message) is deterministic across filesystems.
        for f in sorted(sd.iterdir()):
            if not f.is_file():
                continue
            if f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                continue
            if not _EPISODE_PATTERN.match(f.name):
                unrenamed.append(f)
    return unrenamed
