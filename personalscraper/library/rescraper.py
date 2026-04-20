"""Library rescraper — targeted API-based repairs for library items.

Detects what needs repair per item (NFO, artwork, episodes), resolves
TMDB/TVDB IDs from existing NFOs or re-matching, fetches API data once,
then applies only the needed fixes. Reuses existing scraper components.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.dispatch.disk_scanner import DiskConfig
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.nfo_generator import NFOGenerator
    from personalscraper.scraper.tmdb_client import TMDBClient
    from personalscraper.scraper.tvdb_client import TVDBClient

from personalscraper.config import Settings
from personalscraper.library.models import (
    ACTION_ARTWORK_DOWNLOADED,
    ACTION_EPISODES_RENAMED,
    ACTION_NFO_REGENERATED,
    SKIP_LOW_CONFIDENCE,
    SKIP_NO_MATCH,
    LibraryRescrapeResult,
    RescrapeAction,
)
from personalscraper.library.scanner import (
    _SERIES_CATEGORIES,
    extract_nfo_ids,
    parse_title_year,
)
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.nfo_utils import is_nfo_complete
from personalscraper.scraper.confidence import (
    HIGH_CONFIDENCE,
    match_movie,
    match_tvshow,
)
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


def _detect_needs(
    media_dir: Path,
    media_type: str,
    only: str | None,
) -> tuple[bool, bool, bool]:
    """Detect what needs repair for a media item.

    Args:
        media_dir: Path to media directory.
        media_type: "movie" or "tvshow".
        only: Filter to specific action ("nfo", "artwork", "episodes") or None.

    Returns:
        Tuple of (needs_nfo, needs_artwork, needs_episodes).
    """
    title = parse_title_year(media_dir.name)[0]

    # NFO check
    if media_type == "movie":
        nfo_path = media_dir / f"{title}.nfo"
    else:
        nfo_path = media_dir / "tvshow.nfo"
    nfo_valid = is_nfo_complete(nfo_path)

    needs_nfo = not nfo_valid

    # Artwork check — flag missing poster regardless of NFO state
    # (ID resolution is handled separately by _resolve_tmdb_id)
    if media_type == "movie":
        needs_artwork = not (media_dir / f"{title}-poster.jpg").exists()
    else:
        needs_artwork = not (media_dir / "poster.jpg").exists()

    # Episode check (TV shows only)
    needs_episodes = False
    if media_type == "tvshow":
        for f in media_dir.rglob("*"):
            if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
                if not re.search(r"S\d+E\d+", f.name, re.IGNORECASE):
                    needs_episodes = True
                    break

    # Apply --only filter
    if only == "nfo":
        return needs_nfo, False, False
    if only == "artwork":
        return False, needs_artwork, False
    if only == "episodes":
        return False, False, needs_episodes

    return needs_nfo, needs_artwork, needs_episodes


def _resolve_tmdb_id(
    media_dir: Path,
    media_type: str,
    title: str,
    year: int | None,
    tmdb_client: TMDBClient,
    tvdb_client: TVDBClient,
    interactive: bool,
) -> tuple[str | None, str | None, float | None]:
    """Resolve TMDB ID for a media item.

    Strategy:
    1. Extract from existing NFO (even partially valid)
    2. Re-match via TMDB/TVDB API if no ID found

    Args:
        media_dir: Path to media directory.
        media_type: "movie" or "tvshow".
        title: Parsed title from directory name.
        year: Parsed year.
        tmdb_client: TMDB API client.
        tvdb_client: TVDB API client.
        interactive: If True, prompt for low-confidence matches.

    Returns:
        Tuple of (tmdb_id_str, id_source, confidence).
        tmdb_id_str is None if no match found.
    """
    # 1. Try to extract from NFO
    nfo_name = f"{title}.nfo" if media_type == "movie" else "tvshow.nfo"
    nfo_path = media_dir / nfo_name
    if nfo_path.exists():
        tmdb_id, _imdb_id = extract_nfo_ids(nfo_path)
        if tmdb_id:
            return tmdb_id, "nfo", None

    # 2. Re-match via API
    try:
        if media_type == "movie":
            match = match_movie(tmdb_client, title, year)
        else:
            match = match_tvshow(tvdb_client, tmdb_client, title, year)
    except Exception as exc:
        logger.warning("Match failed for %s: %s", title, exc)
        return None, None, None

    if match is None:
        return None, None, None

    # Confidence check
    if match.confidence < HIGH_CONFIDENCE:
        if interactive:
            response = input(
                f"  Match: '{title}' → '{match.api_title}' "
                f"(confidence={match.confidence:.0%}). Accept? [y/N] "
            )
            if response.lower() != "y":
                return None, None, match.confidence
        else:
            logger.info(
                "Low confidence match for %s: %.0f%% — skipping",
                title, match.confidence * 100,
            )
            return None, None, match.confidence

    return str(match.api_id), "api_match", match.confidence


def _find_largest_video(media_dir: Path) -> Path | None:
    """Find the largest video file in a directory.

    Args:
        media_dir: Path to search.

    Returns:
        Path to largest video file, or None.
    """
    largest = None
    largest_size = 0
    for f in media_dir.rglob("*"):
        if (
            f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not f.name.startswith("._")
        ):
            try:
                size = f.stat().st_size
                if size > largest_size:
                    largest = f
                    largest_size = size
            except OSError:
                continue
    return largest


def _rescrape_item(
    media_dir: Path,
    media_type: str,
    disk: str,
    category: str,
    title: str,
    year: int | None,
    *,
    tmdb_client: TMDBClient,
    tvdb_client: TVDBClient,
    nfo_gen: NFOGenerator,
    artwork_dl: ArtworkDownloader,
    patterns: NamingPatterns,
    only: str | None,
    interactive: bool,
    dry_run: bool,
) -> RescrapeAction | None:
    """Rescrape a single media item.

    Args:
        media_dir: Path to media directory.
        media_type: "movie" or "tvshow".
        disk: Disk name.
        category: Category name.
        title: Parsed title.
        year: Parsed year.
        tmdb_client: TMDB API client.
        tvdb_client: TVDB API client.
        nfo_gen: NFOGenerator instance.
        artwork_dl: ArtworkDownloader instance.
        patterns: NamingPatterns instance.
        only: Action filter.
        interactive: Prompt for low-confidence matches.
        dry_run: Preview without changes.

    Returns:
        RescrapeAction or None if item is already OK.
    """
    needs_nfo, needs_artwork, needs_episodes = _detect_needs(media_dir, media_type, only)

    if not any([needs_nfo, needs_artwork, needs_episodes]):
        return None  # Already OK

    # Resolve TMDB ID
    tmdb_id, id_source, confidence = _resolve_tmdb_id(
        media_dir, media_type, title, year,
        tmdb_client, tvdb_client, interactive,
    )

    if tmdb_id is None:
        skip_reason = SKIP_LOW_CONFIDENCE if confidence is not None else SKIP_NO_MATCH
        return RescrapeAction(
            path=str(media_dir), title=title, media_type=media_type,
            disk=disk, category=category,
            actions_taken=[], actions_skipped=[skip_reason], errors=[],
            tmdb_id=None, id_source=None, match_confidence=confidence,
            rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    # Fetch API data (once)
    api_id = int(tmdb_id)
    try:
        if media_type == "movie":
            api_data = tmdb_client.get_movie(api_id)
        else:
            api_data = tmdb_client.get_tv(api_id)
    except Exception as exc:
        return RescrapeAction(
            path=str(media_dir), title=title, media_type=media_type,
            disk=disk, category=category,
            actions_taken=[], actions_skipped=[], errors=[f"API error: {exc}"],
            tmdb_id=tmdb_id, id_source=id_source, match_confidence=confidence,
            rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    actions: list[str] = []
    errors: list[str] = []

    # Fix NFO
    if needs_nfo:
        try:
            if media_type == "movie":
                nfo_name = patterns.format("movie_nfo", Title=title)
                nfo_path = media_dir / nfo_name
                from personalscraper.scraper.mediainfo import extract_stream_info
                video_file = _find_largest_video(media_dir)
                stream_info = extract_stream_info(video_file) if video_file else None
                xml = nfo_gen.generate_movie_nfo(api_data, stream_info)
            else:
                nfo_path = media_dir / "tvshow.nfo"
                xml = nfo_gen.generate_tvshow_nfo(api_data)
            if not dry_run:
                nfo_gen.write_nfo(xml, nfo_path)
            actions.append(ACTION_NFO_REGENERATED)
            logger.info("%s NFO for %s", "Would regenerate" if dry_run else "Regenerated", title)
        except Exception as exc:
            errors.append(f"NFO generation failed: {exc}")
            logger.error("NFO generation failed for %s: %s", title, exc)

    # Fix artwork
    if needs_artwork:
        try:
            if not dry_run:
                if media_type == "movie":
                    artwork_dl.download_movie_artwork(api_data, media_dir, patterns)
                else:
                    artwork_dl.download_tvshow_artwork(api_data, media_dir, patterns)
            actions.append(ACTION_ARTWORK_DOWNLOADED)
            logger.info("%s artwork for %s", "Would download" if dry_run else "Downloaded", title)
        except Exception as exc:
            errors.append(f"Artwork download failed: {exc}")
            logger.error("Artwork download failed for %s: %s", title, exc)

    # Fix episodes (TV shows only)
    if needs_episodes and media_type == "tvshow":
        try:
            _rescrape_episodes(media_dir, api_data, api_id, tmdb_client, patterns, dry_run)
            actions.append(ACTION_EPISODES_RENAMED)
            logger.info("%s episodes for %s", "Would rename" if dry_run else "Renamed", title)
        except Exception as exc:
            errors.append(f"Episode rename failed: {exc}")
            logger.error("Episode rename failed for %s: %s", title, exc)

    return RescrapeAction(
        path=str(media_dir), title=title, media_type=media_type,
        disk=disk, category=category,
        actions_taken=actions, actions_skipped=[], errors=errors,
        tmdb_id=tmdb_id, id_source=id_source, match_confidence=confidence,
        rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def _rescrape_episodes(
    show_dir: Path,
    show_data: dict[str, Any],
    tmdb_id: int,
    tmdb_client: TMDBClient,
    patterns: NamingPatterns,
    dry_run: bool,
) -> None:
    """Rescrape TV show episodes: fetch season data and rename.

    Args:
        show_dir: Path to TV show directory.
        show_data: TMDB show data dict.
        tmdb_id: TMDB show ID.
        tmdb_client: TMDB API client.
        patterns: NamingPatterns instance.
        dry_run: Preview without changes.
    """
    from personalscraper.scraper.episode_manager import (
        create_season_dirs,
        match_episode_files,
        rename_episodes,
    )

    seasons = show_data.get("seasons", [])
    all_episodes = {}
    for season in seasons:
        season_num = season.get("season_number", 0)
        if season_num == 0:
            continue  # Skip specials
        try:
            season_data = tmdb_client.get_tv_season(tmdb_id, season_num)
            for ep in season_data.get("episodes", []):
                ep_num = ep.get("episode_number", 0)
                all_episodes[(season_num, ep_num)] = {
                    "title": ep.get("name", f"Episode {ep_num}"),
                    "still_path": ep.get("still_path"),
                }
        except Exception as exc:
            logger.warning("Cannot fetch season %d for %s: %s", season_num, show_dir.name, exc)

    if not all_episodes:
        return

    video_files = [
        f for f in show_dir.rglob("*")
        if f.is_file()
        and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not f.name.startswith("._")
    ]

    season_dicts = [{"season_number": s, "episode_number": e} for s, e in all_episodes]
    create_season_dirs(show_dir, season_dicts, patterns, dry_run)
    matched = match_episode_files(video_files, all_episodes)
    rename_episodes(matched, show_dir, patterns, dry_run)


def rescrape_library(
    disk_configs: list[DiskConfig],
    settings: Settings,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    only: str | None = None,
    interactive: bool = False,
    dry_run: bool = True,
    max_items: int | None = None,
) -> LibraryRescrapeResult:
    """Rescrape library items that need repair.

    Only repairs what is broken per item. Reuses existing scraper components.

    Args:
        disk_configs: List of DiskConfig objects.
        settings: Pipeline settings (API keys, language, paths).
        disk_filter: Only rescrape this disk. None = all.
        category_filter: Only rescrape this category. None = all.
        only: Only apply this action: "nfo", "artwork", "episodes". None = all.
        interactive: If True, prompt for low-confidence matches.
        dry_run: If True, preview without modifying files.
        max_items: Maximum items to process. None = unlimited.

    Returns:
        LibraryRescrapeResult with per-item actions.
    """
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.nfo_generator import NFOGenerator
    from personalscraper.scraper.tmdb_client import TMDBClient
    from personalscraper.scraper.tvdb_client import TVDBClient

    tmdb_client = TMDBClient(settings.tmdb_api_key, language=settings.scraper_language)
    tvdb_client = TVDBClient(settings.tvdb_api_key)
    nfo_gen = NFOGenerator()
    artwork_dl = ArtworkDownloader(dry_run=dry_run, artwork_language=settings.artwork_language)
    patterns = NamingPatterns()

    items: list[RescrapeAction] = []
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    items_processed = 0
    start = datetime.now(tz=timezone.utc).isoformat()

    for config in disk_configs:
        if disk_filter and config.name != disk_filter:
            continue
        if not config.path.exists():
            logger.warning("Disk not mounted: %s (%s)", config.name, config.path)
            continue

        for category_dir in sorted(config.path.iterdir()):
            if not category_dir.is_dir():
                continue
            if category_dir.name not in config.categories:
                continue
            if category_filter and category_dir.name != category_filter:
                continue

            is_series = category_dir.name in _SERIES_CATEGORIES
            media_type = "tvshow" if is_series else "movie"

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                if max_items and items_processed >= max_items:
                    break

                title, year = parse_title_year(media_dir.name)

                try:
                    action = _rescrape_item(
                        media_dir=media_dir,
                        media_type=media_type,
                        disk=config.name,
                        category=category_dir.name,
                        title=title,
                        year=year,
                        tmdb_client=tmdb_client,
                        tvdb_client=tvdb_client,
                        nfo_gen=nfo_gen,
                        artwork_dl=artwork_dl,
                        patterns=patterns,
                        only=only,
                        interactive=interactive,
                        dry_run=dry_run,
                    )
                except Exception as exc:
                    logger.exception("Error rescaping %s", media_dir)
                    items.append(RescrapeAction(
                        path=str(media_dir), title=title, media_type=media_type,
                        disk=config.name, category=category_dir.name,
                        actions_taken=[], actions_skipped=[], errors=[str(exc)],
                        tmdb_id=None, id_source=None, match_confidence=None,
                        rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
                    ))
                    error_count += 1
                    items_processed += 1
                    continue

                if action is None:
                    pass  # Already OK — not tracked
                elif action.errors:
                    items.append(action)
                    error_count += 1
                elif action.actions_skipped:
                    items.append(action)
                    skipped_count += 1
                else:
                    items.append(action)
                    fixed_count += 1

                items_processed += 1

            if max_items and items_processed >= max_items:
                break
        if max_items and items_processed >= max_items:
            break

    return LibraryRescrapeResult(
        rescraped_at=start,
        disk_filter=disk_filter,
        category_filter=category_filter,
        only_filter=only,
        dry_run=dry_run,
        fixed_count=fixed_count,
        skipped_count=skipped_count,
        error_count=error_count,
        items=items,
    )
