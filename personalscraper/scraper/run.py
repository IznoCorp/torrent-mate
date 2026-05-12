"""Scrape step runner: entry point for the scrape pipeline step.

Instantiates API clients, creates the Scraper orchestrator, and
processes movies and TV shows. Converts ScrapeResult list to StepReport
for the pipeline framework.

Lock is acquired at the CLI level, not here.
"""

from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.naming_patterns import PATTERNS, SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.scraper.scraper import Scraper, ScrapeResult, verify_tvshow_scrape_drift
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS, FileType

log = get_logger("run")


def _has_unscraped_items(settings: Settings, config: Config) -> bool:
    """Check if any media folder needs scraping or artwork recovery.

    Returns True if at least one folder has:
    - No valid NFO (needs full scrape), OR
    - Valid NFO but missing essential artwork — poster or landscape
      (needs artwork recovery)

    Uses _parse_folder_name for consistent title extraction,
    matching the same parsing logic as Scraper.scrape_movie/scrape_tvshow.

    Args:
        settings: Pipeline configuration (API keys and thresholds).
        config: Application config for staging path and dir name resolution.

    Returns:
        True if at least one folder needs work.
    """
    from personalscraper.scraper.scraper import _parse_folder_name

    movies_dir_name = folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir_name = folder_name(find_by_file_type(config, FileType.TVSHOW))
    staging = config.paths.staging_dir
    for dir_name in (movies_dir_name, tvshows_dir_name):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        for folder in cat_dir.iterdir():
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            if dir_name == movies_dir_name:
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
                # Drift check: even with a complete NFO + both artworks,
                # re-scraping is required when the folder or episodes no
                # longer match what the current scraper would produce
                # (folder rename policy, legacy title-less episodes,
                # missing episode NFOs).
                is_valid, reason = verify_tvshow_scrape_drift(folder, nfo_path, PATTERNS)
                if not is_valid:
                    log.info("show_rescrape_drift_detected", directory=folder.name, reason=reason)
                    return True
    return False


def _needs_repair(category_dir: Path, file_type: FileType) -> bool:
    """Check if any item in category needs repair beyond NFO/artwork.

    Quick filesystem-only check (no API calls). Returns True if any
    item has unorganized episodes, residual NFOs, or root-level MKV
    duplicates.

    Args:
        category_dir: Path to the movies or TV shows staging directory.
        file_type: FileType.MOVIE or FileType.TVSHOW — determines which
            checks to apply. Passed explicitly by callers to avoid
            substring heuristics on directory names.

    Returns:
        True if at least one item needs repair.
    """
    if not category_dir.exists():
        return False

    is_movies = file_type == FileType.MOVIE

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
            has_season_dirs = any(d.is_dir() and SEASON_DIR_RE.match(d.name) for d in folder.iterdir())

            for item in folder.iterdir():
                # Root-level video when season dirs exist → misplaced episode
                if has_season_dirs and item.is_file() and item.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
                    return True

                # Any non-season, non-hidden subdir is a residual torrent dir
                # (may contain videos, NFO residuals, or be empty)
                if item.is_dir() and not item.name.startswith(".") and not SEASON_DIR_RE.match(item.name):
                    return True

            # Residual episode NFOs at root (tvshow.nfo is expected)
            root_nfos = [
                f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".nfo" and f.name != "tvshow.nfo"
            ]
            if root_nfos:
                return True

    return False


def run_scrape(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    interactive: bool = False,
    movies_only: bool = False,
    tvshows_only: bool = False,
    *,
    event_bus: EventBus,
) -> StepReport:
    """Run the scrape pipeline step.

    Instantiates API clients and Scraper, then processes movies and/or
    TV shows from the staging directory.

    Args:
        settings: Pipeline configuration with API keys and thresholds.
        config: Config for staging path, dir name resolution, and
            classifier-based categorisation. Each scraped item is
            classified and ``ScrapeResult.category_id`` is set.
            Items with no matching category are skipped.
        dry_run: If True, preview operations without writing files.
        interactive: If True, prompt user for ambiguous matches.
        movies_only: If True, process only {movies_dir}/.
        tvshows_only: If True, process only {tvshows_dir}/.
        event_bus: Optional in-process EventBus. Each per-item
        lifecycle transition emits an ``ItemProgressed`` event on the bus.

    Returns:
        StepReport with success/skip/error counts and details.
    """
    staging = config.paths.staging_dir
    movies_dir_name = folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir_name = folder_name(find_by_file_type(config, FileType.TVSHOW))

    # Fast-skip: nothing to scrape and no structural repairs needed
    try:
        needs_movie_repair = _needs_repair(staging / movies_dir_name, FileType.MOVIE)
    except OSError as exc:
        log.warning("scrape_repair_check_failed", category="movies", error=str(exc))
        needs_movie_repair = True
    try:
        needs_tvshow_repair = _needs_repair(staging / tvshows_dir_name, FileType.TVSHOW)
    except OSError as exc:
        log.warning("scrape_repair_check_failed", category="tvshows", error=str(exc))
        needs_tvshow_repair = True
    if not _has_unscraped_items(settings, config) and not needs_movie_repair and not needs_tvshow_repair:
        log.info("scrape_fast_skip")
        return StepReport(name="scrape")

    scraper = Scraper(
        settings=settings,
        patterns=PATTERNS,
        dry_run=dry_run,
        interactive=interactive,
        config=config,
        event_bus=event_bus,
    )

    all_results: list[ScrapeResult] = []

    # Process movies
    if not tvshows_only:
        movies_dir = staging / movies_dir_name
        if movies_dir.exists():
            results = scraper.process_movies(movies_dir)
            all_results.extend(results)

    # Process TV shows
    if not movies_only:
        tvshows_dir = staging / tvshows_dir_name
        if tvshows_dir.exists():
            results = scraper.process_tvshows(tvshows_dir)
            all_results.extend(results)

    # Emit per-folder progress events
    for r in all_results:
        item_name = r.media_path.name
        event_bus.emit(ItemProgressed(step="scrape", item=item_name, status="started"))
        if r.action in ("scraped", "artwork_recovered"):
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="matched",
                    details={
                        "action": r.action,
                        "provider": r.match.source if r.match else "",
                        "confidence": r.match.confidence if r.match else 0.0,
                    },
                )
            )
        elif r.action == "skipped_low_confidence":
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="skipped_low_confidence",
                    details={
                        "provider": r.match.source if r.match else "",
                        "confidence": r.match.confidence if r.match else 0.0,
                    },
                )
            )
        elif r.action in ("skipped_already_done", "skipped_no_category"):
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="skipped",
                    details={"action": r.action},
                )
            )
        elif r.action == "error":
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="failed",
                    details={"error": r.error or ""},
                )
            )

    # Convert to StepReport
    return _to_step_report(all_results)


def _to_step_report(results: list[ScrapeResult]) -> StepReport:
    """Convert a list of ScrapeResult to a StepReport.

    Items with action ``skipped_low_confidence`` are counted separately
    in ``counts["unmatched"]`` so the caller can distinguish between
    intentional skips (already done, no category) and silent match
    failures that may indicate a scraper problem.

    Args:
        results: List of scrape results.

    Returns:
        StepReport with aggregated counts, details, and an ``unmatched``
        entry in ``counts`` when at least one item had no confident match.
    """
    success = 0
    skipped = 0
    unmatched = 0
    errors = 0
    warnings: list[str] = []
    details: list[str] = []
    unmatched_paths: list[str] = []

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
        elif r.action == "skipped_low_confidence":
            # Counted as both skipped (for backward compat) and unmatched
            # (distinct observable counter for diagnosis).
            skipped += 1
            unmatched += 1
            details.append(f"[unmatched] {name}")
            unmatched_paths.append(name)
        elif r.action.startswith("skipped"):
            skipped += 1
            details.append(f"[skipped] {name} ({r.action})")
        elif r.action == "error":
            errors += 1
            details.append(f"[error] {name}: {r.error}")
            warnings.append(f"{name}: {r.error}")

    counts: dict[str, int] = {}
    if unmatched:
        counts["unmatched"] = unmatched

    return StepReport(
        name="scrape",
        success_count=success,
        skip_count=skipped,
        error_count=errors,
        warnings=warnings,
        details=details,
        counts=counts,
        unmatched_paths=unmatched_paths,
    )
