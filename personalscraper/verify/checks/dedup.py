"""No-duplicate-videos check (DISPATCH stage, movie-only).

Ported verbatim from ``verify/checker.py::_check_no_duplicate_videos``.
TV shows are EXEMPT (multi-file seasons by design), so this check is
movie-only — exactly as ``check_movie`` wires it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_trailer_filename
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from pathlib import Path

    from personalscraper.verify.checks.base import CheckContext


@register_check
class NoDuplicateVideos:
    """Verify a movie directory holds at most one (non-trailer) root video."""

    name = "no_duplicate_videos"
    group = "dedup"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie"})
    default_severity = Severity.ERROR
    description = "Movie root must hold at most one feature video"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed when ≤ 1 non-trailer root video.

        The scan is non-recursive (root only): videos inside sub-dirs such
        as ``Extras/`` are legitimate and ignored. The flat Plex movie
        trailer ``{media_name}-trailer.{ext}`` is EXEMPT — filtered out
        before the count.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``no_duplicate_videos`` result.
        """
        videos = [f for f in _find_video_files(ctx.media_dir) if not is_trailer_filename(f.name)]
        passed = len(videos) <= 1
        filenames = sorted(f.name for f in videos)
        return [
            CheckResult(
                name="no_duplicate_videos",
                passed=passed,
                severity=Severity.ERROR,
                message="" if passed else f"Multiple video files at root: {filenames}",
            )
        ]


def _find_video_files(directory: "Path") -> "list[Path]":
    """Find video files in a directory (non-recursive; copied from checker.py).

    Args:
        directory: Directory to search.

    Returns:
        List of video file paths.
    """
    return [f for f in directory.iterdir() if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS]
