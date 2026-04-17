# Phase 12: Rescraper — Targeted API Repairs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Prerequisite:** Phases 10+11 must be completed first.

**Goal:** Implement `personalscraper library-rescrape` — targeted re-scraping of library items that need fresh metadata from TMDB/TVDB. Only repairs what is broken per item.

**Architecture:** `rescraper.py` iterates library items, detects what needs repair, resolves TMDB/TVDB IDs (from NFO or re-matching), fetches API data once per item, then applies targeted fixes (NFO, artwork, episodes). Reuses existing scraper components with zero rewrites.

**Tech Stack:** Python, Typer, TMDB/TVDB APIs, pytest

---

## Task 1: Implement rescraper core with ID resolution and detection

**Files:**

- Create: `personalscraper/library/rescraper.py`
- Create: `tests/library/test_rescraper.py`

- [ ] **Step 1: Write failing tests for detection and ID resolution**

```python
# tests/library/test_rescraper.py
"""Tests for personalscraper.library.rescraper — targeted API repairs."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.library.models import (
    ACTION_ARTWORK_DOWNLOADED,
    ACTION_NFO_REGENERATED,
    SKIP_NO_MATCH,
)


class TestDetectNeeds:
    """Tests for _detect_needs — what needs repair per item."""

    def test_missing_nfo_needs_nfo(self, tmp_path: Path) -> None:
        """Item without NFO should need NFO regeneration."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is True

    def test_missing_poster_needs_artwork(self, tmp_path: Path) -> None:
        """Item with valid NFO but no poster should need artwork."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid></movie>'
        )

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is False
        assert needs_artwork is True

    def test_complete_movie_needs_nothing(self, tmp_path: Path) -> None:
        """Complete movie should need nothing."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid></movie>'
        )
        (movie / "Movie-poster.jpg").write_bytes(b"\x00" * 100)

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", None)
        assert needs_nfo is False
        assert needs_artwork is False

    def test_only_filter_restricts(self, tmp_path: Path) -> None:
        """--only artwork should only flag artwork needs."""
        from personalscraper.library.rescraper import _detect_needs

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        # No NFO, no poster — but only=artwork

        needs_nfo, needs_artwork, needs_episodes = _detect_needs(movie, "movie", "artwork")
        assert needs_nfo is False  # Filtered out
        assert needs_artwork is True


class TestResolveId:
    """Tests for _resolve_tmdb_id — ID extraction and matching."""

    def test_id_from_valid_nfo(self, tmp_path: Path) -> None:
        """Should extract TMDB ID from valid NFO without API calls."""
        from personalscraper.library.rescraper import _resolve_tmdb_id

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.nfo").write_text(
            '<movie><uniqueid type="tmdb">12345</uniqueid></movie>'
        )

        tmdb_id, id_source, confidence = _resolve_tmdb_id(
            movie, "movie", "Movie", 2024,
            tmdb_client=MagicMock(), tvdb_client=MagicMock(), interactive=False,
        )

        assert tmdb_id == "12345"
        assert id_source == "nfo"
        assert confidence is None  # No matching needed

    def test_rematch_when_no_nfo(self, tmp_path: Path) -> None:
        """Should re-match via API when no NFO exists."""
        from personalscraper.library.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        mock_tmdb = MagicMock()
        mock_match = MatchResult(api_id=999, api_title="Movie", api_year=2024,
                                  confidence=0.95, source="tmdb")

        with patch("personalscraper.library.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie, "movie", "Movie", 2024,
                tmdb_client=mock_tmdb, tvdb_client=MagicMock(), interactive=False,
            )

        assert tmdb_id == "999"
        assert id_source == "api_match"
        assert confidence == 0.95

    def test_low_confidence_skipped(self, tmp_path: Path) -> None:
        """Low confidence match without --interactive should return None."""
        from personalscraper.library.rescraper import _resolve_tmdb_id
        from personalscraper.scraper.confidence import MatchResult

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()

        mock_match = MatchResult(api_id=999, api_title="Movie?", api_year=2024,
                                  confidence=0.4, source="tmdb")

        with patch("personalscraper.library.rescraper.match_movie", return_value=mock_match):
            tmdb_id, id_source, confidence = _resolve_tmdb_id(
                movie, "movie", "Movie", 2024,
                tmdb_client=MagicMock(), tvdb_client=MagicMock(), interactive=False,
            )

        assert tmdb_id is None
```

- [ ] **Step 2: Run to verify failures**

Run: `python -m pytest tests/library/test_rescraper.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement rescraper.py core**

```python
# personalscraper/library/rescraper.py
"""Library rescraper — targeted API-based repairs for library items.

Detects what needs repair per item (NFO, artwork, episodes), resolves
TMDB/TVDB IDs from existing NFOs or re-matching, fetches API data once,
then applies only the needed fixes. Reuses existing scraper components.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.library.models import (
    ACTION_ARTWORK_DOWNLOADED,
    ACTION_EPISODES_RENAMED,
    ACTION_NFO_REGENERATED,
    LibraryRescrapeResult,
    RescrapeAction,
    SKIP_ALREADY_OK,
    SKIP_LOW_CONFIDENCE,
    SKIP_NO_MATCH,
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
    needs_artwork = False
    needs_episodes = False

    # Artwork check (only if NFO is valid — need ID to download)
    if nfo_valid:
        if media_type == "movie":
            needs_artwork = not (media_dir / f"{title}-poster.jpg").exists()
        else:
            needs_artwork = not (media_dir / "poster.jpg").exists()

    # Episode check (TV shows only)
    if media_type == "tvshow" and nfo_valid:
        # Check if any video files are not in SxxExx format
        for f in media_dir.rglob("*"):
            if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
                import re
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
    tmdb_client: object,
    tvdb_client: object,
    interactive: bool,
) -> tuple[str | None, str | None, float | None]:
    """Resolve TMDB ID for a media item.

    Strategy:
    1. Extract from existing NFO (even partially valid)
    2. Re-match via TMDB/TVDB API if no ID found
    3. Cross-reference TVDB→TMDB if match came from TVDB

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
        tmdb_id, imdb_id = extract_nfo_ids(nfo_path)
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
            # Interactive mode: prompt user
            response = input(
                f"  Match: '{title}' → '{match.api_title}' "
                f"(confidence={match.confidence:.0%}). Accept? [y/N] "
            )
            if response.lower() != "y":
                return None, None, match.confidence
        else:
            logger.info("Low confidence match for %s: %.0f%% — skipping", title, match.confidence * 100)
            return None, None, match.confidence

    # 3. Cross-reference TVDB→TMDB if needed
    tmdb_id_str = str(match.api_id)
    if match.source == "tvdb":
        try:
            series_data = tvdb_client.get_series(match.api_id)
            from personalscraper.scraper.tvdb_client import TVDBClient
            remote_ids = TVDBClient.get_remote_ids(series_data)
            if remote_ids.get("tmdb_id"):
                tmdb_id_str = remote_ids["tmdb_id"]
            else:
                logger.warning("No TMDB cross-ref for TVDB %s (%s)", match.api_id, title)
                return None, None, match.confidence
        except Exception as exc:
            logger.warning("TVDB cross-ref failed for %s: %s", title, exc)
            return None, None, match.confidence

    return tmdb_id_str, "api_match", match.confidence


def rescrape_library(
    disk_configs: list,
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

    # Initialize clients
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
                    logger.warning("Error rescaping %s: %s", media_dir, exc)
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
                    pass  # Already OK — not counted (only items needing work are tracked)
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


def _rescrape_item(
    media_dir: Path,
    media_type: str,
    disk: str,
    category: str,
    title: str,
    year: int | None,
    *,
    tmdb_client: object,
    tvdb_client: object,
    nfo_gen: object,
    artwork_dl: object,
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
                # Get stream info for streamdetails
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
            logger.warning("NFO generation failed for %s: %s", title, exc)

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
            logger.warning("Artwork download failed for %s: %s", title, exc)

    # Fix episodes (TV shows only)
    if needs_episodes and media_type == "tvshow":
        try:
            _rescrape_episodes(media_dir, api_data, api_id,
                               tmdb_client, patterns, dry_run)
            actions.append(ACTION_EPISODES_RENAMED)
            logger.info("%s episodes for %s", "Would rename" if dry_run else "Renamed", title)
        except Exception as exc:
            errors.append(f"Episode rename failed: {exc}")
            logger.warning("Episode rename failed for %s: %s", title, exc)

    return RescrapeAction(
        path=str(media_dir), title=title, media_type=media_type,
        disk=disk, category=category,
        actions_taken=actions, actions_skipped=[], errors=errors,
        tmdb_id=tmdb_id, id_source=id_source, match_confidence=confidence,
        rescraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )


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


def _rescrape_episodes(
    show_dir: Path,
    show_data: dict,
    tmdb_id: int,
    tmdb_client: object,
    patterns: NamingPatterns,
    dry_run: bool,
) -> None:
    """Rescrape TV show episodes: create season dirs, match and rename.

    Args:
        show_dir: Path to TV show directory.
        show_data: TMDB show data dict.
        tmdb_id: TMDB show ID.
        tmdb_client: TMDB API client.
        nfo_gen: NFOGenerator instance.
        patterns: NamingPatterns instance.
        dry_run: Preview without changes.
    """
    from personalscraper.scraper.episode_manager import (
        create_season_dirs,
        match_episode_files,
        rename_episodes,
    )

    # Get season data
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

    # Find video files
    video_files = [
        f for f in show_dir.rglob("*")
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not f.name.startswith("._")
    ]

    # Create season dirs (expects list[dict] with "season_number" key)
    season_dicts = [{"season_number": s, "episode_number": e} for s, e in all_episodes]
    create_season_dirs(show_dir, season_dicts, patterns, dry_run)
    matched = match_episode_files(video_files, all_episodes)
    rename_episodes(matched, show_dir, patterns, dry_run)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_rescraper.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/rescraper.py tests/library/test_rescraper.py
git commit -m "v14.12.1: Implement rescraper core with ID resolution, detection, and targeted fixes"
```

---

## Task 2: Add library-rescrape CLI command

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryRescrape:
    """Tests for library-rescrape CLI command."""

    def test_help(self) -> None:
        """library-rescrape --help should display usage."""
        result = runner.invoke(app, ["library-rescrape", "--help"])
        assert result.exit_code == 0
        assert "--only" in result.output
        assert "--disk" in result.output
        assert "--interactive" in result.output
        assert "--dry-run" in result.output
        assert "--max-items" in result.output
```

- [ ] **Step 2: Add CLI command**

Add to `personalscraper/cli.py`:

```python
@app.command()
@handle_cli_errors
def library_rescrape(
    only: str = typer.Option(None, "--only", help="Only fix: nfo, artwork, episodes"),
    disk: str = typer.Option(None, "--disk", help="Rescrape only this disk"),
    category: str = typer.Option(None, "--category", help="Rescrape only this category"),
    interactive: bool = typer.Option(False, "--interactive", help="Confirm low-confidence matches"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying files"),
    max_items: int = typer.Option(None, "--max-items", help="Limit number of items to process"),
) -> None:
    """Targeted re-scrape of library items via TMDB/TVDB.

    Only repairs what is broken per item: missing NFO, missing artwork,
    unrenamed episodes. Items already conforming are skipped.

    Examples:
        personalscraper library-rescrape --dry-run
        personalscraper library-rescrape --only artwork
        personalscraper library-rescrape --disk Disk1 --max-items 50
        personalscraper library-rescrape --interactive
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs
    from personalscraper.library.models import write_json
    from personalscraper.library.rescraper import rescrape_library

    console = state["console"]
    settings = get_settings()
    disk_configs = get_disk_configs(settings)

    # Validate --only
    valid_only = {"nfo", "artwork", "episodes"}
    if only and only not in valid_only:
        console.print(f"[red]Invalid --only value '{only}'. Valid: {', '.join(sorted(valid_only))}[/red]")
        raise typer.Exit(1)

    # Acquire lock unless dry-run
    if not dry_run:
        if not acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        mode = "[bold yellow]DRY-RUN[/bold yellow]" if dry_run else "[bold green]LIVE[/bold green]"
        console.print(f"[bold]Rescraping library ({mode})...[/bold]")

        result = rescrape_library(
            disk_configs, settings,
            disk_filter=disk, category_filter=category,
            only=only, interactive=interactive,
            dry_run=dry_run, max_items=max_items,
        )

        output_path = settings.data_dir / "library_rescrape.json"
        write_json(result, output_path)

        total = result.fixed_count + result.skipped_count + result.error_count
        console.print(
            f"[green]Fixed:[/green] {result.fixed_count}  "
            f"[yellow]Skipped:[/yellow] {result.skipped_count}  "
            f"[red]Errors:[/red] {result.error_count}  "
            f"(total: {total}) → {output_path}"
        )
    finally:
        if not dry_run:
            release_lock()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_cli.py::TestLibraryRescrape -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "v14.12.2: Add library-rescrape CLI command"
```

---

## Task 3: Add rescrape section to library-report

**Files:**

- Modify: `personalscraper/library/reporter.py`
- Modify: `tests/library/test_reporter.py`

- [ ] **Step 1: Write failing test**

Add to `tests/library/test_reporter.py`:

```python
class TestRescrapeSection:
    """Tests for rescrape section in report."""

    def test_report_with_rescrape_data(self) -> None:
        """Report should include rescrape summary."""
        rescrape_data = {
            "rescraped_at": "2026-04-17T14:00:00",
            "fixed_count": 10, "skipped_count": 5, "error_count": 2,
            "items": [
                {"actions_taken": ["nfo_regenerated"]},
                {"actions_taken": ["artwork_downloaded"]},
                {"actions_taken": ["nfo_regenerated", "artwork_downloaded"]},
            ],
        }
        report = generate_report(rescrape_data=rescrape_data)
        assert report.rescrape_fixed == 10
        assert report.rescrape_skipped == 5
        text = format_report_text(report)
        assert "RESCRAPE" in text
```

- [ ] **Step 2: Add rescrape fields to LibraryReport and generate_report**

In `personalscraper/library/reporter.py`:

Add fields to `LibraryReport`:

```python
    rescrape_fixed: int = 0
    rescrape_skipped: int = 0
    rescrape_errors: int = 0
    rescrape_nfo_count: int = 0
    rescrape_artwork_count: int = 0
    rescrape_episodes_count: int = 0
```

Add `rescrape_data` parameter to `generate_report()` and processing logic.

Add section 6 "RESCRAPE" to `format_report_text()` between TOP 20 and ACTIONS SUGGÉRÉES.

Update ACTIONS SUGGÉRÉES to reflect rescrape results.

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/library/test_reporter.py -v`
Expected: ALL PASS

```bash
git add personalscraper/library/reporter.py tests/library/test_reporter.py
git commit -m "v14.12.3: Add rescrape section to library-report"
```

---

## Task 4: Phase 12 gate

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 2: Update IMPLEMENTATION.md**

Update Phases 10-12 to DONE, update next action.

- [ ] **Step 3: Commit and push**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v14.12.4: Phase 12 gate — rescraper complete, all tests pass"
git push
```

---

## Acceptance Criteria — Phase 12

- [ ] `library-rescrape --dry-run` previews repairs without changes
- [ ] `library-rescrape` regenerates missing/broken NFOs from TMDB
- [ ] `library-rescrape` re-downloads missing artwork (skips existing)
- [ ] `library-rescrape --only artwork` only downloads artwork
- [ ] `library-rescrape --only episodes` renames unrenamed episodes
- [ ] `library-rescrape --interactive` prompts for low-confidence matches
- [ ] Low-confidence matches without --interactive are skipped
- [ ] TVDB matches are cross-referenced to TMDB ID
- [ ] Per-item error isolation
- [ ] `library-rescrape --max-items 5` limits processing
- [ ] `library_rescrape.json` saved to `.personalscraper/`
- [ ] `library-report` includes rescrape section
- [ ] Full test suite passes
