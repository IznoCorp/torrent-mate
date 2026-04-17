"""Scrape step runner: entry point for the scrape pipeline step.

Instantiates API clients, creates the Scraper orchestrator, and
processes movies and TV shows. Converts ScrapeResult list to StepReport
for the pipeline framework.

Lock is acquired at the CLI level, not here.
"""

import logging
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.models import StepReport
from personalscraper.naming_patterns import PATTERNS, SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper.scraper import Scraper, ScrapeResult
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


def _has_unscraped_items(settings: Settings) -> bool:
    """Check if any media folder needs scraping or artwork recovery.

    Returns True if at least one folder has:
    - No valid NFO (needs full scrape), OR
    - Valid NFO but missing essential artwork — poster or landscape
      (needs artwork recovery)

    Uses _parse_folder_name for consistent title extraction,
    matching the same parsing logic as Scraper.scrape_movie/scrape_tvshow.

    Args:
        settings: Pipeline configuration.

    Returns:
        True if at least one folder needs work.
    """
    from personalscraper.scraper.scraper import _parse_folder_name

    staging = settings.staging_dir
    for dir_name in (settings.movies_dir_name, settings.tvshows_dir_name):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        for folder in cat_dir.iterdir():
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            if dir_name == settings.movies_dir_name:
                title, _ = _parse_folder_name(folder.name)
                nfo_name = PATTERNS.format("movie_nfo", Title=title)
                nfo_path = folder / nfo_name
                if not _is_nfo_complete(nfo_path):
                    return True
                # Check essential artwork (poster + landscape)
                poster = PATTERNS.format("movie_poster", Title=title)
                if not (folder / poster).exists():
                    return True
                landscape = PATTERNS.format("movie_landscape", Title=title)
                if not (folder / landscape).exists():
                    return True
            else:
                nfo_path = folder / PATTERNS.tvshow_nfo
                if not _is_nfo_complete(nfo_path):
                    return True
                if not (folder / PATTERNS.tvshow_poster).exists():
                    return True
                if not (folder / PATTERNS.tvshow_landscape).exists():
                    return True
    return False


def _needs_repair(category_dir: Path) -> bool:
    """Check if any item in category needs repair beyond NFO/artwork.

    Quick filesystem-only check (no API calls). Returns True if any
    item has unorganized episodes, residual NFOs, or root-level MKV
    duplicates.

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.

    Returns:
        True if at least one item needs repair.
    """
    if not category_dir.exists():
        return False

    is_movies = "MOVIE" in category_dir.name.upper()

    for folder in category_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue

        if is_movies:
            # Detect duplicate NFOs (e.g. clean + raw release-group NFO)
            nfo_count = sum(1 for f in folder.iterdir() if f.suffix.lower() == ".nfo")
            if nfo_count > 1:
                return True
        else:
            # TV show checks
            has_season_dirs = any(
                d.is_dir() and SEASON_DIR_RE.match(d.name)
                for d in folder.iterdir()
            )

            for item in folder.iterdir():
                # Root-level video when season dirs exist → misplaced episode
                if (
                    has_season_dirs
                    and item.is_file()
                    and item.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
                ):
                    return True

                # Any non-season, non-hidden subdir is a residual torrent dir
                # (may contain videos, NFO residuals, or be empty)
                if (
                    item.is_dir()
                    and not item.name.startswith(".")
                    and not SEASON_DIR_RE.match(item.name)
                ):
                    return True

            # Residual episode NFOs at root (tvshow.nfo is expected)
            root_nfos = [
                f
                for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() == ".nfo" and f.name != "tvshow.nfo"
            ]
            if root_nfos:
                return True

    return False


def run_scrape(
    settings: Settings,
    dry_run: bool = False,
    interactive: bool = False,
    movies_only: bool = False,
    tvshows_only: bool = False,
) -> StepReport:
    """Run the scrape pipeline step.

    Instantiates API clients and Scraper, then processes movies and/or
    TV shows from the staging directory.

    Args:
        settings: Pipeline configuration with API keys and paths.
        dry_run: If True, preview operations without writing files.
        interactive: If True, prompt user for ambiguous matches.
        movies_only: If True, process only 001-MOVIES/.
        tvshows_only: If True, process only 002-TVSHOWS/.

    Returns:
        StepReport with success/skip/error counts and details.
    """
    # Fast-skip: nothing to scrape and no structural repairs needed
    staging = Path(settings.staging_dir)
    try:
        needs_movie_repair = _needs_repair(staging / settings.movies_dir_name)
    except OSError as exc:
        logger.warning("Cannot check movie repair status: %s", exc)
        needs_movie_repair = True
    try:
        needs_tvshow_repair = _needs_repair(staging / settings.tvshows_dir_name)
    except OSError as exc:
        logger.warning("Cannot check tvshow repair status: %s", exc)
        needs_tvshow_repair = True
    if not _has_unscraped_items(settings) and not needs_movie_repair and not needs_tvshow_repair:
        logger.info(
            "Scrape fast-skip: all NFOs valid, artwork present, no repairs needed"
        )
        return StepReport(name="scrape")

    scraper = Scraper(
        settings=settings,
        patterns=PATTERNS,
        dry_run=dry_run,
        interactive=interactive,
    )

    all_results: list[ScrapeResult] = []

    # Process movies
    if not tvshows_only:
        movies_dir = staging / settings.movies_dir_name
        if movies_dir.exists():
            results = scraper.process_movies(movies_dir)
            all_results.extend(results)

    # Process TV shows
    if not movies_only:
        tvshows_dir = staging / settings.tvshows_dir_name
        if tvshows_dir.exists():
            results = scraper.process_tvshows(tvshows_dir)
            all_results.extend(results)

    # Convert to StepReport
    return _to_step_report(all_results)


def _to_step_report(results: list[ScrapeResult]) -> StepReport:
    """Convert a list of ScrapeResult to a StepReport.

    Args:
        results: List of scrape results.

    Returns:
        StepReport with aggregated counts and details.
    """
    success = 0
    skipped = 0
    errors = 0
    warnings: list[str] = []
    details: list[str] = []

    for r in results:
        name = r.media_path.name
        if r.action == "scraped":
            success += 1
            parts = [f"[scraped] {name}"]
            if r.nfo_written:
                parts.append("NFO")
            if r.artwork_downloaded:
                parts.append(f"{len(r.artwork_downloaded)} artwork")
            if r.episodes_renamed > 0:
                parts.append(f"{r.episodes_renamed} episodes")
            details.append(" | ".join(parts))
        elif r.action == "artwork_recovered":
            success += 1
            parts = [f"[recovered] {name}"]
            if r.artwork_downloaded:
                parts.append(f"{len(r.artwork_downloaded)} artwork")
            details.append(" | ".join(parts))
        elif r.action == "repaired":
            success += 1
            details.append(f"[repaired] {name}")
        elif r.action.startswith("skipped"):
            skipped += 1
            details.append(f"[skipped] {name} ({r.action})")
        elif r.action == "error":
            errors += 1
            details.append(f"[error] {name}: {r.error}")
            warnings.append(f"{name}: {r.error}")

    return StepReport(
        name="scrape",
        success_count=success,
        skip_count=skipped,
        error_count=errors,
        warnings=warnings,
        details=details,
    )
