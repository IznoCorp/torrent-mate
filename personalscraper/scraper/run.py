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
from personalscraper.naming_patterns import PATTERNS
from personalscraper.scraper.scraper import Scraper, ScrapeResult

logger = logging.getLogger(__name__)


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
    scraper = Scraper(
        settings=settings,
        patterns=PATTERNS,
        dry_run=dry_run,
        interactive=interactive,
    )

    all_results: list[ScrapeResult] = []
    staging = Path(settings.staging_dir)

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
