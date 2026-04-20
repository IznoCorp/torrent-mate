"""Episode management: season directories, file matching, and renaming.

Handles the creation of Saison XX/ directories, matching video files
to API episode data (via S/E extraction), and renaming episodes with
proper titles from TMDB/TVDB. Subtitle files (.srt, .sub, .vtt) are
renamed alongside their associated video files.

These functions are used by the TV show orchestrator (scraper.py, Phase 12)
to organize episodes after metadata matching.
"""

import logging
import re
from pathlib import Path
from typing import Any

from personalscraper.naming_patterns import NamingPatterns

logger = logging.getLogger(__name__)

# Subtitle extensions to rename alongside video files
SUBTITLE_EXTENSIONS = frozenset({"srt", "sub", "vtt", "ass", "ssa", "idx"})

# Regex patterns for extracting season/episode from filenames
# Ordered by specificity: most specific patterns first
_SE_PATTERNS = [
    # S01E04, s01e04, S01E01E02 (captures first episode of double)
    re.compile(r"[Ss](\d{1,2})[Ee](\d{1,3})"),
    # 1x04 format
    re.compile(r"(\d{1,2})x(\d{1,3})"),
]


def _extract_season_episode(name: str) -> tuple[int | None, int | None]:
    """Extract season and episode numbers from a filename.

    Supports common patterns: S01E04, s01e04, 1x04, S01E01E02.
    For double episodes, returns the first episode number.

    Args:
        name: Raw media filename or directory name.

    Returns:
        Tuple of (season, episode), both None if not found.
    """
    for pattern in _SE_PATTERNS:
        match = pattern.search(name)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


def create_season_dirs(
    show_dir: Path,
    episodes: list[dict[str, Any]],
    patterns: NamingPatterns,
    dry_run: bool = False,
) -> list[Path]:
    """Create Saison XX/ directories for detected seasons.

    Scans the episode list for unique season numbers and creates
    the corresponding directories using NamingPatterns.season_dir.
    Skips existing directories. Season 0 (specials) is skipped.

    Args:
        show_dir: Path to the TV show root directory.
        episodes: List of episode dicts with 'season_number' key.
        patterns: Naming patterns for directory names.
        dry_run: If True, log without creating directories.

    Returns:
        List of created (or would-be-created) directory paths.
    """
    season_nums = sorted({ep.get("season_number", ep.get("seasonNumber", 0)) for ep in episodes})

    created: list[Path] = []
    for season_num in season_nums:
        if season_num == 0:
            continue
        dir_name = patterns.format("season_dir", Season=season_num)
        season_dir = show_dir / dir_name
        if season_dir.exists():
            logger.info("Season directory already exists: %s", dir_name)
            created.append(season_dir)
            continue
        if dry_run:
            logger.info("[DRY RUN] Would create directory: %s", dir_name)
            created.append(season_dir)
            continue
        season_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created season directory: %s", dir_name)
        created.append(season_dir)

    return created


def match_episode_files(
    video_files: list[Path],
    api_episodes: dict[tuple[int, int], dict[str, Any]],
) -> dict[Path, dict[str, Any]]:
    """Match video files to API episode data by season/episode numbers.

    Uses V2 NameCleaner to extract S/E numbers from filenames, then
    looks up the episode title in the API data.

    Args:
        video_files: List of video file paths.
        api_episodes: Mapping from (season, episode) to episode info dict
            with keys "title" and "still_path".

    Returns:
        Dict mapping video path to match info:
        {path: {"season": int, "episode": int, "api_title": str,
                "still_path": str}}.
        Files with no S/E match or no API match are excluded.
    """
    matched: dict[Path, dict[str, Any]] = {}

    for video_path in video_files:
        season, episode = _extract_season_episode(video_path.name)
        if season is None or episode is None:
            logger.warning(
                "Could not extract S/E from filename: %s",
                video_path.name,
            )
            continue

        key = (season, episode)
        if key in api_episodes:
            ep_info = api_episodes[key]
            matched[video_path] = {
                "season": season,
                "episode": episode,
                "api_title": ep_info["title"],
                "still_path": ep_info.get("still_path", ""),
            }
        else:
            logger.warning(
                "Episode S%02dE%02d not found in API data: %s",
                season,
                episode,
                video_path.name,
            )

    return matched


def rename_episodes(
    matched: dict[Path, dict[str, Any]],
    show_dir: Path,
    patterns: NamingPatterns,
    dry_run: bool = False,
) -> int:
    """Rename matched episodes and their subtitles to standard format.

    Moves video files into the correct Saison XX/ directory and renames
    them using the pattern S01E01 - Episode Title.ext. Associated subtitle
    files (same stem, subtitle extension) are renamed and moved alongside.

    Args:
        matched: Dict from match_episode_files() mapping video paths
            to {season, episode, api_title}.
        show_dir: Path to the TV show root directory.
        patterns: Naming patterns for episode filenames.
        dry_run: If True, log without renaming/moving files.

    Returns:
        Number of episodes successfully renamed.
    """
    renamed_count = 0

    for video_path, info in matched.items():
        season = info["season"]
        episode = info["episode"]
        api_title = info["api_title"]

        # Build destination path: show_dir/Saison XX/S01E01 - Title.ext
        season_dir_name = patterns.format("season_dir", Season=season)
        season_dir = show_dir / season_dir_name

        new_stem = patterns.format(
            "episode_video",
            Season=season,
            Episode=episode,
            EpisodeTitle=api_title,
        )
        new_video_name = f"{new_stem}{video_path.suffix}"
        dest = season_dir / new_video_name

        # Skip if already correctly named and in the right place
        if video_path == dest:
            logger.info("Episode already correctly named: %s", dest.name)
            renamed_count += 1
            continue

        if dry_run:
            logger.info("[DRY RUN] Would rename: %s → %s", video_path.name, dest)
        else:
            season_dir.mkdir(parents=True, exist_ok=True)
            video_path.rename(dest)
            logger.info("Renamed: %s → %s", video_path.name, dest.name)

        renamed_count += 1

        # Rename associated subtitle files
        _rename_subtitles(video_path, new_stem, season_dir, dry_run)

    return renamed_count


def _rename_subtitles(
    video_path: Path,
    new_stem: str,
    dest_dir: Path,
    dry_run: bool,
) -> None:
    """Rename subtitle files associated with a video file.

    Looks for files with the same stem as the video file but with
    subtitle extensions (.srt, .sub, .vtt, etc.). Handles language
    suffixes like .en.srt or .fra.srt.

    Args:
        video_path: Original video file path (to find sibling subtitles).
        new_stem: New base filename stem (without extension).
        dest_dir: Destination directory for renamed subtitles.
        dry_run: If True, log without renaming.
    """
    video_stem = video_path.stem
    parent = video_path.parent

    for sub_file in parent.iterdir():
        if not sub_file.is_file():
            continue

        ext = sub_file.suffix.lstrip(".").lower()
        if ext not in SUBTITLE_EXTENSIONS:
            continue

        # Check if this subtitle belongs to the video file
        # Handles: video.srt, video.en.srt, video.fra.srt
        sub_stem = sub_file.stem
        if not sub_stem.startswith(video_stem):
            continue

        # Preserve language suffix if present (e.g. ".en", ".fra")
        lang_suffix = sub_stem[len(video_stem) :]
        new_sub_name = f"{new_stem}{lang_suffix}.{ext}"
        dest = dest_dir / new_sub_name

        if sub_file == dest:
            continue

        if dry_run:
            logger.info("[DRY RUN] Would rename subtitle: %s → %s", sub_file.name, new_sub_name)
        else:
            sub_file.rename(dest)
            logger.info("Renamed subtitle: %s → %s", sub_file.name, new_sub_name)
