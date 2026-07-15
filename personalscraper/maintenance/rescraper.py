"""Library rescraper — targeted API-based repairs for library items.

Detects what needs repair per item (NFO, artwork, episodes), resolves
TMDB/TVDB IDs from existing NFOs or re-matching, fetches API data once,
then applies only the needed fixes. Reuses existing scraper components.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.metadata.tvdb import TVDBClient
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.nfo_generator import NFOGenerator

from personalscraper._fs_utils import is_apple_double
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.conf.ids import TV_CATEGORY_IDS
from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import EventBus
from personalscraper.core.media_types import VIDEO_EXTENSIONS
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.nfo_utils import extract_nfo_metadata, is_nfo_complete, parse_title_year
from personalscraper.scraper.confidence import (
    HIGH_CONFIDENCE,
    match_movie,
    match_tvshow,
)

log = get_logger("library.rescraper")


# --- Rescrape action constants ---

ACTION_NFO_REGENERATED = "nfo_regenerated"
ACTION_ARTWORK_DOWNLOADED = "artwork_downloaded"
ACTION_EPISODES_RENAMED = "episodes_renamed"
SKIP_LOW_CONFIDENCE = "low_confidence_match"
SKIP_NO_MATCH = "no_match"
SKIP_ALREADY_OK = "already_conforming"

_VALID_ONLY_FILTERS = {"nfo", "artwork", "episodes"}
_VALID_ID_SOURCES = {"nfo", "api_match"}


@dataclass
class RescrapeAction:
    """Single repair action taken on a media item.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        title: Media title.
        media_type: "movie" or "tvshow".
        disk: Disk name.
        category: Category name.
        actions_taken: List of action constants performed.
        actions_skipped: List of skip reason constants.
        errors: Per-item errors (API failure, NTFS write error, etc.).
        tmdb_id: TMDB ID used for API calls (str for JSON, converted from int).
        id_source: How the ID was obtained: "nfo" or "api_match".
        match_confidence: Match confidence 0.0-1.0 (None if ID from NFO).
        rescraped_at: ISO 8601 timestamp of this action.
    """

    path: str
    title: str
    media_type: str
    disk: str
    category: str
    actions_taken: list[str]
    actions_skipped: list[str]
    errors: list[str]
    tmdb_id: str | None
    id_source: str | None
    match_confidence: float | None
    rescraped_at: str = ""

    def __post_init__(self) -> None:
        """Enforce media_type and confidence constraints."""
        if self.media_type not in ("movie", "tvshow"):
            raise ValueError(f"media_type must be 'movie' or 'tvshow', got '{self.media_type}'")
        if self.match_confidence is not None and not (0.0 <= self.match_confidence <= 1.0):
            raise ValueError(f"match_confidence must be 0.0-1.0, got {self.match_confidence}")
        if self.id_source is not None and self.id_source not in _VALID_ID_SOURCES:
            raise ValueError(f"id_source must be one of {_VALID_ID_SOURCES} or None, got '{self.id_source}'")
        if self.tmdb_id is None and self.match_confidence is not None:
            self.match_confidence = None


@dataclass
class LibraryRescrapeResult:
    """Top-level container for library_rescrape.json.

    Attributes:
        rescraped_at: ISO 8601 timestamp of rescrape start.
        disk_filter: Disk filter applied (None = all disks).
        category_filter: Category filter applied (None = all).
        only_filter: Action filter ("nfo", "artwork", "episodes", or None = all).
        dry_run: Whether this was a dry-run (no actual changes).
        fixed_count: Items successfully repaired.
        skipped_count: Items skipped (low confidence, already OK, etc.).
        error_count: Items with errors.
        items: List of per-item rescrape actions.
        candidate_count: Number of items the rescrape resolved and attempted
            (``len(candidates)``). Distinguishes "item not found / not on disk"
            (0 candidates) from "item found but nothing to do" (>=1 candidate,
            0 fixed/skipped/error) — the latter must not be reported as not-found.
    """

    rescraped_at: str
    disk_filter: str | None
    category_filter: str | None
    only_filter: str | None
    dry_run: bool
    fixed_count: int
    skipped_count: int
    error_count: int
    items: list[RescrapeAction] = field(default_factory=list)
    candidate_count: int = 0

    def __post_init__(self) -> None:
        """Validate only_filter."""
        if self.only_filter is not None and self.only_filter not in _VALID_ONLY_FILTERS:
            raise ValueError(f"only_filter must be one of {_VALID_ONLY_FILTERS} or None")


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
    # (ID resolution is handled separately by _resolve_tmdb_id). Canonical
    # detection (core.artwork_naming): the old exact-name checks re-downloaded
    # artwork that existed under another legitimate spelling.
    from personalscraper.core.artwork_naming import has_poster  # noqa: PLC0415

    needs_artwork = not has_poster(media_dir)

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
    registry: ProviderRegistry,
    interactive: bool,
) -> tuple[str | None, str | None, float | None, str | None]:
    """Resolve the metadata-provider ID + matched provider for a media item.

    Strategy:
    1. Extract from existing NFO (even partially valid)
    2. Re-match via TMDB/TVDB API if no ID found

    Args:
        media_dir: Path to media directory.
        media_type: "movie" or "tvshow".
        title: Parsed title from directory name.
        year: Parsed year.
        registry: ProviderRegistry for resolving metadata clients.
        interactive: If True, prompt for low-confidence matches.

    Returns:
        Tuple of (tmdb_id_str, id_source, confidence).
        tmdb_id_str is None if no match found.
    """
    tmdb_client = cast("TMDBClient", registry.get("tmdb"))
    tvdb_client = cast("TVDBClient", registry.get("tvdb"))

    # 1. Try to extract from NFO. Honour the canonical provider recorded there:
    # a TVDB-canonical show NFO must resolve to its TVDB id (so the fetch goes
    # through TVDB), not be mislabelled as a TMDB id. Provider is derived from
    # id presence (tvdb wins for TV), mirroring existing_validator.
    nfo_name = f"{title}.nfo" if media_type == "movie" else "tvshow.nfo"
    nfo_path = media_dir / nfo_name
    if nfo_path.exists():
        meta = extract_nfo_metadata(nfo_path)
        nfo_tvdb = meta.get("tvdb_id")
        nfo_tmdb = meta.get("tmdb_id")
        if nfo_tvdb and str(nfo_tvdb).isdigit():
            return str(nfo_tvdb), "nfo", None, "tvdb"
        if nfo_tmdb and str(nfo_tmdb).isdigit():
            return str(nfo_tmdb), "nfo", None, "tmdb"

    # 2. Re-match via API
    try:
        if media_type == "movie":
            match = match_movie(tmdb_client, title, year)
        else:
            match = match_tvshow(tvdb_client, tmdb_client, title, year)
    except Exception as exc:
        log.warning("library_rescrape_match_failed", title=title, exc_info=True, error=str(exc))
        return None, None, None, None

    if match is None:
        return None, None, None, None

    # Confidence check
    if match.confidence < HIGH_CONFIDENCE:
        if interactive:
            response = input(
                f"  Match: '{title}' → '{match.api_title}' (confidence={match.confidence:.0%}). Accept? [y/N] "
            )
            if response.lower() != "y":
                return None, None, match.confidence, None
        else:
            log.info(
                "library_rescrape_low_confidence",
                title=title,
                confidence=round(match.confidence * 100),
            )
            return None, None, match.confidence, None

    # Movies are TMDB-only; TV honours the matched provider (TVDB-primary).
    source = "tmdb" if media_type == "movie" else match.source
    return str(match.api_id), "api_match", match.confidence, source


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
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not is_apple_double(f.name):
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
    registry: ProviderRegistry,
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
        registry: ProviderRegistry for resolving metadata clients.
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
    provider_id, id_source, confidence, source = _resolve_tmdb_id(
        media_dir,
        media_type,
        title,
        year,
        registry,
        interactive,
    )

    if provider_id is None:
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

    # Fetch API data once, honouring the source-of-match invariant via the
    # SHARED fetch_show_data (TVDB-primary / TMDB fallback) — the SAME helper
    # the initial tv_service scrape uses, so the provider-priority discipline
    # cannot diverge between scrape and rescrape. Movies stay TMDB-only.
    # provider_id is a TVDB series id when source == "tvdb".
    api_id = int(provider_id)
    tmdb = cast("TMDBClient", registry.get("tmdb"))
    report_tmdb_id: str | None = provider_id if media_type == "movie" else None
    api_data: Any
    try:
        if media_type == "movie":
            api_data = tmdb.get_movie(api_id)
        else:
            from personalscraper.scraper._tvdb_convert import fetch_show_data

            provider = registry.get(source) if source else tmdb
            api_data, xref_tmdb = fetch_show_data(
                source or "tmdb",
                api_id,
                provider,
                preferred_language="fr-FR",
                fallback_language="en-US",
            )
            report_tmdb_id = str(xref_tmdb) if xref_tmdb else None
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
            tmdb_id=report_tmdb_id,
            id_source=id_source,
            match_confidence=confidence,
            rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    actions: list[str] = []
    errors: list[str] = []

    # Fix NFO
    if needs_nfo:
        try:
            from personalscraper.scraper._movie_convert import (
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
                from personalscraper.scraper._movie_convert import (
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
                source or "tmdb",
                api_id,
                registry,
                patterns,
                dry_run,
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
        tmdb_id=report_tmdb_id,
        id_source=id_source,
        match_confidence=confidence,
        rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def _rescrape_episodes(
    show_dir: Path,
    show_data: object,
    source: str,
    api_id: int,
    registry: ProviderRegistry,
    patterns: NamingPatterns,
    dry_run: bool,
) -> None:
    """Rescrape TV show episodes from the MATCHED provider, then rename.

    Honours the source-of-match invariant: a TVDB-matched show fetches episode
    data from TVDB (``_fetch_season_episodes_tvdb``), a TMDB-matched show from
    TMDB (``_fetch_season_episodes``) — the shared twins also used by
    ``existing_validator``. Never queries TMDB for a TVDB-matched show's
    episodes (which would 404 on the TVDB id).

    Args:
        show_dir: Path to TV show directory.
        show_data: Show metadata (TMDB MediaDetails or TVDB-derived dict).
        source: Matched provider — ``"tvdb"`` or ``"tmdb"``.
        api_id: Provider id (TVDB series id when source == 'tvdb', else TMDB id).
        registry: ProviderRegistry to resolve the matched provider's client.
        patterns: NamingPatterns instance.
        dry_run: Preview without changes.
    """
    from personalscraper.naming_patterns import SEASON_DIR_RE
    from personalscraper.scraper.episode_manager import (
        create_season_dirs,
        match_episode_files,
        rename_episodes,
    )
    from personalscraper.scraper.existing_validator_repair import (
        _fetch_season_episodes,
        _fetch_season_episodes_tvdb,
    )

    # Discover season numbers from local filesystem (show_data has no seasons array).
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

    # Source-aware episode fetch (TVDB-primary): use the shared twins, never
    # tmdb.get_tv_season on a TVDB id (the divergence that caused the 404 abort).
    try:
        if source == "tvdb":
            tvdb_client = cast("TVDBClient", registry.get("tvdb"))
            all_episodes = _fetch_season_episodes_tvdb(tvdb_client, api_id, season_nums)
        else:
            tmdb_client = cast("TMDBClient", registry.get("tmdb"))
            all_episodes = _fetch_season_episodes(tmdb_client, api_id, season_nums)
    except Exception as exc:
        log.warning(
            "library_rescrape_season_fetch_failed",
            show=show_dir.name,
            source=source,
            exc_info=True,
            error=str(exc),
        )
        all_episodes = {}

    if not all_episodes:
        return

    video_files = [
        f
        for f in show_dir.rglob("*")
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not is_apple_double(f.name)
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
    item_id: int | None = None,
) -> list[tuple[Path, str, str, str]]:
    """Build a list of (media_dir, media_type, disk_id, category_id) candidates.

    When *item_id* is provided, the function enters an **item-id fast-path**:
    it resolves exactly that item from the indexer DB via ``item_repo.get_by_id``
    and returns it as the sole candidate, **bypassing**
    ``find_items_needing_rescrape`` entirely.  This allows force-rescraping an
    item whose ``nfo_status`` is already ``'valid'``.  *item_id* is mutually
    exclusive with *disk_filter* and *category_filter*; supplying either raises a
    :exc:`ValueError`.

    When *conn* is provided (and *item_id* is ``None``), queries the indexer DB
    for items where ``nfo_status != 'valid'`` or
    ``date_metadata_refreshed IS NULL``.  Paths are reconstructed from the
    ``disk.mount_path`` + ``path.rel_path`` columns.

    When *conn* is ``None`` and *item_id* is ``None``, falls back to a direct
    filesystem walk of ``config.disks``.

    Args:
        config: Loaded pipeline :class:`~personalscraper.conf.models.Config`.
        conn: Open SQLite connection, or ``None`` to use filesystem walk.
        disk_filter: Restrict to a single disk ID, or ``None`` for all.
        category_filter: Restrict to a single category ID, or ``None`` for all.
        item_id: When set, target exactly this item by its DB primary key.
            Mutually exclusive with *disk_filter* and *category_filter*.

    Returns:
        List of ``(media_dir, media_type, disk_id, category_id)`` tuples.

    Raises:
        ValueError: If *item_id* is set together with *disk_filter* or
            *category_filter* (mutually exclusive options).
    """
    from personalscraper.indexer.repos import item_repo as _item_repo  # noqa: PLC0415

    candidates: list[tuple[Path, str, str, str]] = []

    # --- item_id fast-path: resolve a single item, bypassing the predicate ---
    if item_id is not None:
        # Mutual exclusion check: combining item_id with a filter makes no sense
        # and would produce confusing silent no-ops; fail loud instead.
        if disk_filter or category_filter:
            raise ValueError(
                f"item_id={item_id!r} is mutually exclusive with disk_filter and "
                f"category_filter. Remove disk_filter={disk_filter!r} and "
                f"category_filter={category_filter!r} when targeting a single item."
            )

        # item_id requires an open DB connection; conn is guaranteed non-None by
        # the CLI (which validates this before calling us), but guard defensively.
        if conn is None:
            log.warning("library_rescrape_item_id_no_conn", item_id=item_id)
            return []

        item = _item_repo.get_by_id(conn, item_id)
        if item is None:
            log.warning(
                "library_rescrape_item_id_not_found",
                item_id=item_id,
            )
            return []

        # Resolve the full filesystem path from the dispatch flex attribute.
        # _ATTR_DISPATCH_PATH stores the complete path as written at dispatch time
        # (e.g. "/Volumes/Disk1/films/Movie (2024)"), so no path join is needed.
        path_attr = _item_repo.get_attr(conn, item_id, _item_repo._ATTR_DISPATCH_PATH)
        if not path_attr or not path_attr.value:
            log.warning(
                "library_rescrape_item_id_no_dispatch_path",
                item_id=item_id,
                title=item.title,
            )
            return []

        media_dir = Path(path_attr.value)
        if not media_dir.is_dir():
            log.warning(
                "library_rescrape_item_id_dir_missing",
                item_id=item_id,
                title=item.title,
                path=str(media_dir),
            )
            return []

        # Retrieve the config disk_id from the dispatch disk attribute.
        # The value can be None if the attribute row has a NULL value column,
        # so we fall back to "" to satisfy the tuple[..., str, ...] contract.
        disk_attr = _item_repo.get_attr(conn, item_id, _item_repo._ATTR_DISPATCH_DISK)
        disk_id: str = (disk_attr.value or "") if disk_attr else ""

        media_type = "tvshow" if item.kind == "show" else "movie"
        return [(media_dir, media_type, disk_id, item.category_id)]

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
    conn: sqlite3.Connection | None = None,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    item_id: int | None = None,
    only: str | None = None,
    interactive: bool = False,
    dry_run: bool = True,
    max_items: int | None = None,
    *,
    event_bus: EventBus,
    registry: ProviderRegistry,
) -> LibraryRescrapeResult:
    """Rescrape library items that need repair.

    Only repairs what is broken per item. Reuses existing scraper components.
    When *conn* is provided, candidate items are discovered by querying
    ``media_item WHERE nfo_status != 'valid' OR date_metadata_refreshed IS NULL``
    (indexer DB path).  When *conn* is ``None``, falls back to a filesystem walk
    of ``config.disks``.

    When *item_id* is set, exactly that item is targeted by DB look-up,
    bypassing the needs-rescrape predicate so that items with
    ``nfo_status='valid'`` can be force-rescraped.  *item_id* is mutually
    exclusive with *disk_filter* and *category_filter* (enforced by
    :func:`_collect_rescrape_candidates`).

    Args:
        config: Config with disk and category definitions.
        conn: Optional open SQLite connection to the indexer DB.  When supplied,
            items are found via DB query instead of a full filesystem walk.
        disk_filter: Only rescrape this disk (by disk.id). None = all.
        category_filter: Only rescrape this category_id. None = all.
        item_id: Target exactly this item by its indexer DB id, bypassing the
            needs-rescrape predicate.  Mutually exclusive with *disk_filter* and
            *category_filter*.  None = use standard candidate discovery.
        only: Only apply this action: "nfo", "artwork", "episodes". None = all.
        interactive: If True, prompt for low-confidence matches.
        dry_run: If True, preview without modifying files.
        max_items: Maximum items to process. None = unlimited.
        event_bus: Required :class:`EventBus` propagated to TMDB/TVDB
            transports so circuit-breaker trips during a long rescrape
            reach the run's Telegram / RichConsole subscribers.
        registry: Configured :class:`ProviderRegistry` for resolving metadata
            clients (TMDB, TVDB).

    Returns:
        LibraryRescrapeResult with per-item actions.
    """
    from personalscraper.scraper.artwork import ArtworkDownloader  # noqa: PLC0415
    from personalscraper.scraper.nfo_generator import NFOGenerator  # noqa: PLC0415

    scraper_config = config.scraper
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

    candidates = _collect_rescrape_candidates(config, conn, disk_filter, category_filter, item_id=item_id)

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
                registry=registry,
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
        candidate_count=len(candidates),
    )
