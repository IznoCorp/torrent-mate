"""Episode management: season directories, file matching, and renaming.

Handles the creation of Saison XX/ directories, matching video files
to API episode data (via S/E extraction), and renaming episodes with
proper titles from TMDB/TVDB. Subtitle files (.srt, .sub, .vtt) are
renamed alongside their associated video files.

These functions are used by the TV show orchestrator (scraper.py)
to organize episodes after metadata matching.
"""

import re
from pathlib import Path
from typing import Any

from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns

log = get_logger("episode_manager")

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


def _provider_id_fields(ep_info: dict[str, Any]) -> dict[str, str]:
    """Extract the propagated per-episode provider IDs from an API episode dict.

    Returns a sparse dict (keys absent rather than empty) so the
    upstream matched dict can rely on ``.get(...)`` returning ``None``
    when a provider had no ID for this episode. Only keys with the
    ``{provider}_episode_id`` shape are forwarded — the call site is
    DEV #2-specific and must not accidentally carry unrelated fields.

    Args:
        ep_info: Single entry from the ``api_episodes`` map produced
            by :meth:`TvServiceMixin._build_episode_map`.

    Returns:
        Dict mapping ``{provider}_episode_id`` to its string value,
        skipping providers that returned an empty / missing ID.
    """
    return {key: ep_info[key] for key in ep_info if key.endswith("_episode_id") and ep_info.get(key)}


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
            log.info("season_dir_exists", directory=dir_name)
            created.append(season_dir)
            continue
        if dry_run:
            log.info("season_dir_would_create", directory=dir_name)
            created.append(season_dir)
            continue
        season_dir.mkdir(parents=True, exist_ok=True)
        log.info("season_dir_created", directory=dir_name)
        created.append(season_dir)

    return created


def match_episode_files(
    video_files: list[Path],
    api_episodes: dict[tuple[int, int], dict[str, Any]],
    episode_default_name: str = "Episode",
    allow_synthetic_rename: bool = True,
) -> dict[Path, dict[str, Any]]:
    """Match video files to API episode data by season/episode numbers.

    Resolves each file in three cascading passes:

    1. **Direct match** — the ``(season, episode)`` parsed from the filename
       exists in ``api_episodes``. Uses the provider title and still_path.
    2. **Phantom-season remap** — the filename labels a season the show's
       catalog doesn't have (common for parallel-numbering spin-offs whose
       releases mirror the main show's season, e.g. an S17 label on a show
       whose own catalog is S01..S04). When the provider's catalog does
       contain ``(max_season_in_catalog, episode)``, the file is remapped
       to that season with the provider's title.
    3. **Synthetic fallback** — no API entry available and no remap worked.
       Behavior depends on ``allow_synthetic_rename``:

       - ``True`` (legacy): the title becomes ``"{episode_default_name}
         {episode}"`` and the entry is flagged ``fallback=True`` so NFO
         generation can skip it. The file is propagated to
         ``rename_episodes`` and lands under ``Saison NN/``.
       - ``False`` (default contract per
         ``metadata.episode_scraping_policy.allow_synthetic_rename_on_unmatched``):
         the file is EXCLUDED from the result dict — no rename, no
         ``Saison NN/`` created. The file stays at the show-folder root
         with its raw filename. ``episode_unmatched_no_rename`` is logged
         for observability.

    Args:
        video_files: List of video file paths.
        api_episodes: Mapping from (season, episode) to episode info dict
            with keys "title" and "still_path".
        episode_default_name: Prefix used to forge a synthetic title when
            no API entry and no remap are available AND
            ``allow_synthetic_rename=True``. Combined with the episode
            number (e.g. ``"Episode" + " 8"`` → ``"Episode 8"``).
        allow_synthetic_rename: When ``True`` (legacy), Pass-3 synthesizes
            a title and the file is propagated for renaming. When
            ``False`` (current default contract), Pass-3 excludes the file
            entirely so it stays at its current location.

    Returns:
        Dict mapping video path to match info:
        {path: {"season": int, "episode": int, "api_title": str,
                "still_path": str, "fallback": bool}}.
        ``fallback=True`` signals synthetic data (no provider record) —
        downstream NFO generation should skip these entries. Files
        unmatched while ``allow_synthetic_rename=False`` are absent.
    """
    matched: dict[Path, dict[str, Any]] = {}
    available_seasons = {s for s, _ in api_episodes.keys()}
    max_season = max(available_seasons) if available_seasons else None

    for video_path in video_files:
        season, episode = _extract_season_episode(video_path.name)
        if season is None or episode is None:
            log.warning("episode_se_not_found", filename=video_path.name)
            continue

        # Pass 1: direct API match.
        key = (season, episode)
        if key in api_episodes:
            ep_info = api_episodes[key]
            matched[video_path] = {
                "season": season,
                "episode": episode,
                "api_title": ep_info["title"],
                "still_path": ep_info.get("still_path", ""),
                "fallback": False,
                **_provider_id_fields(ep_info),
            }
            continue

        is_phantom_season = bool(available_seasons) and season not in available_seasons

        # Pass 2: phantom-season remap via (max_season, episode).
        if is_phantom_season and max_season is not None:
            remap_key = (max_season, episode)
            if remap_key in api_episodes:
                ep_info = api_episodes[remap_key]
                log.info(
                    "episode_phantom_season_remapped",
                    filename=video_path.name,
                    labeled_season=season,
                    remapped_season=max_season,
                    episode=episode,
                    api_title=ep_info["title"],
                )
                matched[video_path] = {
                    "season": max_season,
                    "episode": episode,
                    "api_title": ep_info["title"],
                    "still_path": ep_info.get("still_path", ""),
                    "fallback": False,
                    **_provider_id_fields(ep_info),
                }
                continue

        # Pass 3: synthetic fallback OR skip (per allow_synthetic_rename).
        if not allow_synthetic_rename:
            # Contract: file stays at the show-folder root with its raw
            # filename. Nothing is added to ``matched`` so downstream
            # ``rename_episodes`` never sees it.
            log.warning(
                "episode_unmatched_no_rename",
                filename=video_path.name,
                season=season,
                episode=episode,
                phantom_season=is_phantom_season,
                available_seasons=sorted(available_seasons),
            )
            continue

        # Legacy synthetic-rename branch (allow_synthetic_rename=True).
        if is_phantom_season:
            log.warning(
                "episode_phantom_season_fallback",
                filename=video_path.name,
                labeled_season=season,
                episode=episode,
                available_seasons=sorted(available_seasons),
            )
        else:
            log.warning(
                "episode_not_in_api_fallback",
                filename=video_path.name,
                season=season,
                episode=episode,
            )
        matched[video_path] = {
            "season": season,
            "episode": episode,
            "api_title": f"{episode_default_name} {episode}",
            "still_path": "",
            "fallback": True,
        }

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
            log.info("episode_already_named", filename=dest.name)
            renamed_count += 1
            continue

        if dry_run:
            log.info("episode_would_rename", source=video_path.name, dest=str(dest))
        else:
            season_dir.mkdir(parents=True, exist_ok=True)
            video_path.rename(dest)
            log.info("episode_renamed", source=video_path.name, dest=dest.name)

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
            log.info("subtitle_would_rename", source=sub_file.name, dest=new_sub_name)
        else:
            sub_file.rename(dest)
            log.info("subtitle_renamed", source=sub_file.name, dest=new_sub_name)
