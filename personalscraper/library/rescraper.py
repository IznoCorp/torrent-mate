"""Library rescraper — targeted API-based repairs for library items.

Detects what needs repair per item (NFO, artwork, episodes), resolves
TMDB/TVDB IDs from existing NFOs or re-matching, fetches API data once,
then applies only the needed fixes. Reuses existing scraper components.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.metadata.tvdb import TVDBClient
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.nfo_generator import NFOGenerator

from personalscraper.conf.ids import TV_CATEGORY_IDS
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
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
    extract_nfo_ids,
    parse_title_year,
)
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.nfo_utils import is_nfo_complete
from personalscraper.scraper.confidence import (
    HIGH_CONFIDENCE,
    match_movie,
    match_tvshow,
)
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

log = get_logger("library.rescraper")


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
        log.warning("library_rescrape_match_failed", title=title, exc_info=True, error=str(exc))
        return None, None, None

    if match is None:
        return None, None, None

    # Confidence check
    if match.confidence < HIGH_CONFIDENCE:
        if interactive:
            response = input(
                f"  Match: '{title}' → '{match.api_title}' (confidence={match.confidence:.0%}). Accept? [y/N] "
            )
            if response.lower() != "y":
                return None, None, match.confidence
        else:
            log.info(
                "library_rescrape_low_confidence",
                title=title,
                confidence=round(match.confidence * 100),
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
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not f.name.startswith("._"):
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
    episode_default_name: str = "Episode",
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
        episode_default_name: Prefix used when an episode title is missing
            from the configured scraper-language response.

    Returns:
        RescrapeAction or None if item is already OK.
    """
    needs_nfo, needs_artwork, needs_episodes = _detect_needs(media_dir, media_type, only)

    if not any([needs_nfo, needs_artwork, needs_episodes]):
        return None  # Already OK

    # Resolve TMDB ID
    tmdb_id, id_source, confidence = _resolve_tmdb_id(
        media_dir,
        media_type,
        title,
        year,
        tmdb_client,
        tvdb_client,
        interactive,
    )

    if tmdb_id is None:
        skip_reason = SKIP_LOW_CONFIDENCE if confidence is not None else SKIP_NO_MATCH
        return RescrapeAction(
            path=str(media_dir),
            title=title,
            media_type=media_type,
            disk=disk,
            category=category,
            actions_taken=[],
            actions_skipped=[skip_reason],
            errors=[],
            tmdb_id=None,
            id_source=None,
            match_confidence=confidence,
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
            path=str(media_dir),
            title=title,
            media_type=media_type,
            disk=disk,
            category=category,
            actions_taken=[],
            actions_skipped=[],
            errors=[f"API error: {exc}"],
            tmdb_id=tmdb_id,
            id_source=id_source,
            match_confidence=confidence,
            rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    actions: list[str] = []
    errors: list[str] = []

    # Fix NFO
    if needs_nfo:
        try:
            from personalscraper.scraper.movie_service import (
                _coerce_to_movie_data,
                _coerce_to_show_data,
            )

            if media_type == "movie":
                nfo_name = patterns.format("movie_nfo", Title=title)
                nfo_path = media_dir / nfo_name
                from personalscraper.scraper.mediainfo import extract_stream_info

                video_file = _find_largest_video(media_dir)
                stream_info = extract_stream_info(video_file) if video_file else None
                xml = nfo_gen.generate_movie_nfo(_coerce_to_movie_data(api_data), stream_info)
            else:
                nfo_path = media_dir / "tvshow.nfo"
                xml = nfo_gen.generate_tvshow_nfo(_coerce_to_show_data(api_data))
            if not dry_run:
                nfo_gen.write_nfo(xml, nfo_path)
            actions.append(ACTION_NFO_REGENERATED)
            log.info("library_rescrape_nfo", title=title, dry_run=dry_run)
        except Exception as exc:
            errors.append(f"NFO generation failed: {exc}")
            log.error("library_rescrape_nfo_failed", title=title, exc_info=True, error=str(exc))

    # Fix artwork
    if needs_artwork:
        try:
            if not dry_run:
                from personalscraper.scraper.movie_service import (
                    _coerce_to_movie_data,
                    _coerce_to_show_data,
                )

                if media_type == "movie":
                    artwork_dl.download_movie_artwork(_coerce_to_movie_data(api_data), media_dir, patterns)
                else:
                    artwork_dl.download_tvshow_artwork(_coerce_to_show_data(api_data), media_dir, patterns)
            actions.append(ACTION_ARTWORK_DOWNLOADED)
            log.info("library_rescrape_artwork", title=title, dry_run=dry_run)
        except Exception as exc:
            errors.append(f"Artwork download failed: {exc}")
            log.error("library_rescrape_artwork_failed", title=title, exc_info=True, error=str(exc))

    # Fix episodes (TV shows only)
    if needs_episodes and media_type == "tvshow":
        try:
            _rescrape_episodes(
                media_dir,
                api_data,
                api_id,
                tmdb_client,
                patterns,
                dry_run,
                episode_default_name=episode_default_name,
            )
            actions.append(ACTION_EPISODES_RENAMED)
            log.info("library_rescrape_episodes", title=title, dry_run=dry_run)
        except Exception as exc:
            errors.append(f"Episode rename failed: {exc}")
            log.error("library_rescrape_episodes_failed", title=title, exc_info=True, error=str(exc))

    return RescrapeAction(
        path=str(media_dir),
        title=title,
        media_type=media_type,
        disk=disk,
        category=category,
        actions_taken=actions,
        actions_skipped=[],
        errors=errors,
        tmdb_id=tmdb_id,
        id_source=id_source,
        match_confidence=confidence,
        rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def _rescrape_episodes(
    show_dir: Path,
    show_data: object,
    tmdb_id: int,
    tmdb_client: TMDBClient,
    patterns: NamingPatterns,
    dry_run: bool,
    episode_default_name: str = "Episode",
) -> None:
    """Rescrape TV show episodes: fetch season data and rename.

    Args:
        show_dir: Path to TV show directory.
        show_data: TMDB MediaDetails (typed model, not a raw dict).
        tmdb_id: TMDB show ID.
        tmdb_client: TMDB API client.
        patterns: NamingPatterns instance.
        dry_run: Preview without changes.
        episode_default_name: Prefix used when the provider has no episode
            title in the configured scraper language.
    """
    from personalscraper.naming_patterns import SEASON_DIR_RE
    from personalscraper.scraper.episode_manager import (
        create_season_dirs,
        match_episode_files,
        rename_episodes,
    )

    # Discover season numbers from local filesystem (MediaDetails has no seasons array).
    season_nums = sorted(
        {
            int(m.group(1))
            for d in show_dir.iterdir()
            if d.is_dir() and (m := SEASON_DIR_RE.match(d.name))
            if int(m.group(1)) > 0
        }
    )
    if not season_nums:
        return

    all_episodes = {}
    for season_num in season_nums:
        try:
            season_data = tmdb_client.get_tv_season(tmdb_id, season_num)
            for ep in season_data.episodes:
                ep_num = ep.episode_number
                all_episodes[(season_num, ep_num)] = {
                    "title": ep.title or f"{episode_default_name} {ep_num}",
                    "still_path": "",
                }
        except Exception as exc:
            log.warning(
                "library_rescrape_season_fetch_failed",
                season=season_num,
                show=show_dir.name,
                exc_info=True,
                error=str(exc),
            )

    if not all_episodes:
        return

    video_files = [
        f
        for f in show_dir.rglob("*")
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not f.name.startswith("._")
    ]

    # Only create season directories for seasons that actually receive
    # a local file: matching the in-scraper rule, this avoids creating
    # 16 empty Saison NN dirs for shows whose catalog spans seasons we
    # do not own locally.
    matched = match_episode_files(video_files, all_episodes)
    if matched:
        needed_seasons = sorted({info["season"] for info in matched.values()})
        season_dicts = [{"season_number": s, "episode_number": 0} for s in needed_seasons]
        create_season_dirs(show_dir, season_dicts, patterns, dry_run)
        rename_episodes(matched, show_dir, patterns, dry_run)


def _collect_rescrape_candidates(
    config: Config,
    conn: sqlite3.Connection | None,
    disk_filter: str | None,
    category_filter: str | None,
) -> list[tuple[Path, str, str, str]]:
    """Build a list of (media_dir, media_type, disk_id, category_id) candidates.

    When *conn* is provided, queries the indexer DB for items where
    ``nfo_status != 'valid'`` or ``date_metadata_refreshed IS NULL``.  Paths
    are reconstructed from the ``disk.mount_path`` + ``path.rel_path`` columns.

    When *conn* is ``None``, falls back to a direct filesystem walk of
    ``config.disks``.

    Args:
        config: Loaded pipeline :class:`~personalscraper.conf.models.Config`.
        conn: Open SQLite connection, or ``None`` to use filesystem walk.
        disk_filter: Restrict to a single disk ID, or ``None`` for all.
        category_filter: Restrict to a single category ID, or ``None`` for all.

    Returns:
        List of ``(media_dir, media_type, disk_id, category_id)`` tuples.
    """
    from personalscraper.indexer.repos import item_repo as _item_repo  # noqa: PLC0415

    candidates: list[tuple[Path, str, str, str]] = []

    if conn is not None:
        # DB-query path: find items needing rescrape by NFO / refresh status.
        db_items = _item_repo.find_items_needing_rescrape(conn)
        for item_row, mount_path, rel_path in db_items:
            if not mount_path or not rel_path:
                continue
            media_dir = Path(mount_path) / rel_path
            if not media_dir.is_dir():
                continue

            # Map category_id back to disk_id via config for filter checks.
            # disk_id (uuid/label) is stored as DiskConfig.id in the scanner.
            disk_id = ""
            for disk in config.disks:
                if disk_filter and disk.id != disk_filter:
                    continue
                if item_row.category_id in disk.categories:
                    disk_id = disk.id
                    break
            if not disk_id:
                continue

            if category_filter and item_row.category_id != category_filter:
                continue

            media_type = "tvshow" if item_row.kind == "show" else "movie"
            candidates.append((media_dir, media_type, disk_id, item_row.category_id))
    else:
        # Filesystem-walk fallback: iterate config.disks → category dirs → media dirs.
        for disk in config.disks:
            if disk_filter and disk.id != disk_filter:
                continue
            if not disk.path.exists():
                log.warning("library_rescrape_disk_not_mounted", disk=disk.id, path=str(disk.path))
                continue

            for category_id in disk.categories:
                if category_filter and category_id != category_filter:
                    continue

                cat_cfg = config.category(category_id)
                category_dir = disk.path / cat_cfg.folder_name
                if not category_dir.is_dir():
                    log.debug(
                        "library_rescrape_category_not_found",
                        category_dir=str(category_dir),
                        disk=disk.id,
                    )
                    continue

                is_series = category_id in TV_CATEGORY_IDS
                media_type = "tvshow" if is_series else "movie"

                for media_dir in sorted(category_dir.iterdir()):
                    if not media_dir.is_dir() or media_dir.name.startswith("."):
                        continue
                    candidates.append((media_dir, media_type, disk.id, category_id))

    return candidates


def rescrape_library(
    config: Config,
    settings: Settings,
    conn: sqlite3.Connection | None = None,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    only: str | None = None,
    interactive: bool = False,
    dry_run: bool = True,
    max_items: int | None = None,
    *,
    event_bus: EventBus,
) -> LibraryRescrapeResult:
    """Rescrape library items that need repair.

    Only repairs what is broken per item. Reuses existing scraper components.
    When *conn* is provided, candidate items are discovered by querying
    ``media_item WHERE nfo_status != 'valid' OR date_metadata_refreshed IS NULL``
    (indexer DB path).  When *conn* is ``None``, falls back to a filesystem walk
    of ``config.disks``.

    Args:
        config: Config with disk and category definitions.
        settings: Pipeline settings (API keys, language, paths).
        conn: Optional open SQLite connection to the indexer DB.  When supplied,
            items are found via DB query instead of a full filesystem walk.
        disk_filter: Only rescrape this disk (by disk.id). None = all.
        category_filter: Only rescrape this category_id. None = all.
        only: Only apply this action: "nfo", "artwork", "episodes". None = all.
        interactive: If True, prompt for low-confidence matches.
        dry_run: If True, preview without modifying files.
        max_items: Maximum items to process. None = unlimited.
        event_bus: Required :class:`EventBus` propagated to TMDB/TVDB
            transports so circuit-breaker trips during a long rescrape
            reach the run's Telegram / RichConsole subscribers.

    Returns:
        LibraryRescrapeResult with per-item actions.
    """
    from personalscraper.api.metadata.tmdb import TMDBClient  # noqa: PLC0415
    from personalscraper.api.metadata.tvdb import TVDBClient  # noqa: PLC0415
    from personalscraper.api.transport._http import HttpTransport  # noqa: PLC0415
    from personalscraper.scraper.artwork import ArtworkDownloader  # noqa: PLC0415
    from personalscraper.scraper.nfo_generator import NFOGenerator  # noqa: PLC0415

    scraper_config = config.scraper
    tmdb_policy = TMDBClient.policy(settings.tmdb_api_key)
    tmdb_client = TMDBClient(
        transport=HttpTransport(tmdb_policy, event_bus=event_bus),
        language=scraper_config.language,
    )
    tvdb_client = TVDBClient(settings.tvdb_api_key, event_bus=event_bus)
    # Pass db_path so write-through outbox publishes land in the user-configured
    # DB rather than the default IndexerConfig().db_path (DESIGN §9.4).
    nfo_gen = NFOGenerator(db_path=config.indexer.db_path)
    artwork_dl = ArtworkDownloader(
        dry_run=dry_run,
        artwork_language=scraper_config.artwork_language,
        db_path=config.indexer.db_path,
    )
    patterns = NamingPatterns()

    items: list[RescrapeAction] = []
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    items_processed = 0
    start = datetime.now(tz=timezone.utc).isoformat()

    candidates = _collect_rescrape_candidates(config, conn, disk_filter, category_filter)

    for media_dir, media_type, disk_id, category_id in candidates:
        if max_items and items_processed >= max_items:
            break

        title, year = parse_title_year(media_dir.name)

        try:
            action = _rescrape_item(
                media_dir=media_dir,
                media_type=media_type,
                disk=disk_id,
                category=category_id,
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
                episode_default_name=scraper_config.episode_default_name,
            )
        except Exception as exc:
            log.exception("library_rescrape_item_error", media_dir=str(media_dir), error=str(exc))
            items.append(
                RescrapeAction(
                    path=str(media_dir),
                    title=title,
                    media_type=media_type,
                    disk=disk_id,
                    category=category_id,
                    actions_taken=[],
                    actions_skipped=[],
                    errors=[str(exc)],
                    tmdb_id=None,
                    id_source=None,
                    match_confidence=None,
                    rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
                )
            )
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
