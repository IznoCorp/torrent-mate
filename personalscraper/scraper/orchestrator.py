"""Extracted scraper service module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.artwork import ArtworkDownloader
from personalscraper.scraper.classifier import ClassifierMixin
from personalscraper.scraper.existing_validator import ExistingValidatorMixin
from personalscraper.scraper.keywords_cache import KeywordsCache
from personalscraper.scraper.movie_service import MovieServiceMixin
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.tv_service import TvServiceMixin
from personalscraper.scraper.tv_service_nfo import TvServiceNfoMixin

log = get_logger("scraper")

_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


class Scraper(ClassifierMixin, ExistingValidatorMixin, MovieServiceMixin, TvServiceMixin, TvServiceNfoMixin):
    """Main scraping orchestrator.

    Coordinates TMDB/TVDB matching, NFO generation, artwork download,
    and episode management for both movies and TV shows.

    The orchestrator no longer owns provider instantiation — it receives a
    :class:`ProviderRegistry` built once at pipeline boot and routes every
    provider access through it (DESIGN §1.1, §5.2). Legacy direct
    ``self._{tmdb,tvdb}`` attributes have been removed; provider-bound code
    reads ``self._registry.get("tmdb")`` / ``self._registry.get("tvdb")`` for
    transitional direct access (Phase 1) and will move to
    ``registry.chain()`` / ``registry.locked()`` semantics in later phases.
    """

    def __init__(
        self,
        settings: Settings,
        patterns: NamingPatterns,
        dry_run: bool = False,
        interactive: bool = False,
        config: Config | None = None,
        *,
        event_bus: EventBus,
        registry: ProviderRegistry,
    ):
        """Initialize the scraper with the provider registry and helpers.

        Args:
            settings: Pipeline configuration with API keys.
            patterns: MediaElch-compatible naming patterns.
            dry_run: If True, preview operations without writing.
            interactive: If True, prompt for ambiguous matches.
            config: Config for classification rules and paths. When provided,
                classifier.classify() is called for every scraped item to assign
                a category_id. When None, classification is skipped (legacy mode).
            event_bus: Required :class:`EventBus` forwarded by ``Pipeline`` —
                kept on the orchestrator only for downstream helpers that still
                want to emit through it. Transport-level breaker events now
                originate from registry-owned ``HttpTransport`` instances.
            registry: Required :class:`ProviderRegistry` built once per process
                at pipeline boot (DESIGN §6.1). Replaces the legacy direct
                ``self._{tmdb,tvdb}`` attributes.
        """
        self.settings = settings
        self.config = config
        self.patterns = patterns
        self.dry_run = dry_run
        self.interactive = interactive
        self._event_bus = event_bus
        self._registry = registry
        scraper_config = config.scraper if config is not None else None
        self._scraper_language = scraper_config.language if scraper_config is not None else "fr-FR"
        self._scraper_fallback_language = scraper_config.fallback_language if scraper_config is not None else "en-US"
        self._prefer_local_title = scraper_config.prefer_local_title if scraper_config is not None else True
        self._tvdb_language = self._to_tvdb_language(self._scraper_language)
        self._tvdb_fallback_language = self._to_tvdb_language(self._scraper_fallback_language)

        # Provider instantiation is owned by the registry. No TMDBClient or
        # TVDBClient is constructed here anymore — the orchestrator only
        # consumes providers via ``self._registry`` (chain / get / locked).

        # Initialize helpers.  Pass db_path so write-through outbox publishes
        # land in the user-configured DB (DESIGN §9.4).  When config is None
        # (legacy/test mode) db_path is None and outbox publishing is skipped.
        _db_path = config.indexer.db_path if config is not None else None
        self._nfo = NFOGenerator(db_path=_db_path)
        artwork_lang = scraper_config.artwork_language if scraper_config is not None else "en"
        self._artwork = ArtworkDownloader(
            dry_run=dry_run,
            artwork_language=artwork_lang,
            db_path=_db_path,
        )

        # Classification helpers — only set up when config is provided.
        # _needs_keywords caches whether any category_rule uses tmdb_keyword so
        # the /keywords endpoint is only called when actually required.
        if config is not None:
            self._keywords_cache: KeywordsCache | None = KeywordsCache(config.paths.data_dir)
            self._needs_keywords: bool = any(rule.tmdb_keyword is not None for rule in config.category_rules)
        else:
            self._keywords_cache = None
            self._needs_keywords = False

    def process_movies(self, movies_dir: Path) -> list[ScrapeResult]:
        """Scrape all movies in a directory using the registry chain.

        Scans all subdirectories of ``movies_dir`` and calls ``scrape_movie()``
        on each one. The eligible-provider gate now comes from
        ``self._registry.chain(MovieDetailsProvider)``: when that list is empty
        (all circuits OPEN), the item is skipped immediately — analogous to the
        legacy "TMDB circuit OPEN" gate at orchestrator.py:150 (DESIGN §6.2).

        Args:
            movies_dir: Path to the movies directory (e.g. {movies_dir}/).

        Returns:
            List of ScrapeResult for each processed movie.
        """
        from personalscraper.api._contracts import CircuitOpenError  # noqa: PLC0415
        from personalscraper.api.metadata._contracts import MovieDetailsProvider  # noqa: PLC0415

        results: list[ScrapeResult] = []

        if not movies_dir.exists():
            log.warning("movies_dir_not_found", path=str(movies_dir))
            return results

        # Each subdirectory is a movie
        subdirs = sorted(d for d in movies_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

        log.info("movies_start", count=len(subdirs), directory=movies_dir.name)

        for movie_dir in subdirs:
            # Registry-driven eligibility gate (DESIGN §6.2). An empty chain
            # means no provider can satisfy MovieDetailsProvider right now —
            # the closest semantic equivalent of "TMDB circuit OPEN" in the
            # legacy single-provider world. The error string keeps the legacy
            # wording so downstream observers (logs, tests) keep matching.
            eligible_providers = self._registry.chain(MovieDetailsProvider)  # type: ignore[type-abstract]
            if not eligible_providers:
                log.warning("movies_tmdb_circuit_open", directory=movie_dir.name)
                results.append(
                    ScrapeResult(
                        media_path=movie_dir,
                        media_type="movie",
                        action="error",
                        error="TMDB circuit breaker OPEN",
                    )
                )
                continue

            try:
                result = self.scrape_movie(movie_dir)
                results.append(result)
            except CircuitOpenError as e:
                # Circuit opened during this item's processing
                log.warning("movies_circuit_opened", directory=movie_dir.name, error=str(e))
                results.append(
                    ScrapeResult(
                        media_path=movie_dir,
                        media_type="movie",
                        action="error",
                        error=str(e),
                    )
                )
            except Exception as e:
                log.error("movies_unexpected_error", directory=movie_dir.name, error=str(e), exc_info=True)
                results.append(
                    ScrapeResult(
                        media_path=movie_dir,
                        media_type="movie",
                        action="error",
                        error=str(e),
                    )
                )

        # Summary
        scraped = sum(1 for r in results if r.action == "scraped")
        skipped = sum(1 for r in results if r.action.startswith("skipped"))
        unmatched = sum(1 for r in results if r.action == "skipped_low_confidence")
        errors = sum(1 for r in results if r.action == "error")
        log.info("movies_done", scraped=scraped, skipped=skipped, unmatched=unmatched, errors=errors)

        return results

    def process_tvshows(self, tvshows_dir: Path) -> list[ScrapeResult]:
        """Scrape all TV shows using ``registry.chain(TvDetailsProvider)``.

        Mirror of :meth:`process_movies` for TV. When the chain of eligible
        ``TvDetailsProvider`` instances is empty, the item is skipped — the
        registry-shaped equivalent of the legacy "both TVDB and TMDB circuits
        OPEN" gate at orchestrator.py:223 (DESIGN §6.2). Partial-eligibility
        (one provider open, one closed) is no longer gated here: the chain
        loop in :meth:`tv_service.TvServiceMixin.scrape_tvshow` handles
        per-provider fallback.

        Args:
            tvshows_dir: Path to the TV shows directory (e.g. {tvshows_dir}/).

        Returns:
            List of ScrapeResult for each processed show.
        """
        from personalscraper.api._contracts import CircuitOpenError  # noqa: PLC0415
        from personalscraper.api.metadata._contracts import TvDetailsProvider  # noqa: PLC0415

        results: list[ScrapeResult] = []

        if not tvshows_dir.exists():
            log.warning("tvshows_dir_not_found", path=str(tvshows_dir))
            return results

        subdirs = sorted(d for d in tvshows_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

        log.info("tvshows_start", count=len(subdirs), directory=tvshows_dir.name)

        for show_dir in subdirs:
            # Registry-driven eligibility gate (DESIGN §6.2). The TV path
            # tolerates partial eligibility — only an empty chain means no
            # provider can satisfy TvDetailsProvider, which is the registry
            # equivalent of "both circuits open". The legacy wording is
            # preserved so log scrapers and characterization tests still match.
            eligible_providers = self._registry.chain(TvDetailsProvider)  # type: ignore[type-abstract]
            if not eligible_providers:
                log.warning("tvshows_both_circuits_open", directory=show_dir.name)
                results.append(
                    ScrapeResult(
                        media_path=show_dir,
                        media_type="tvshow",
                        action="error",
                        error="Both TVDB and TMDB circuit breakers OPEN",
                    )
                )
                continue

            try:
                result = self.scrape_tvshow(show_dir)
                results.append(result)
            except CircuitOpenError as e:
                # Both providers went down during this item
                log.warning("tvshows_circuit_opened", directory=show_dir.name, error=str(e))
                results.append(
                    ScrapeResult(
                        media_path=show_dir,
                        media_type="tvshow",
                        action="error",
                        error=str(e),
                    )
                )
            except Exception as e:
                log.error("tvshows_unexpected_error", directory=show_dir.name, error=str(e), exc_info=True)
                results.append(
                    ScrapeResult(
                        media_path=show_dir,
                        media_type="tvshow",
                        action="error",
                        error=str(e),
                    )
                )

        scraped = sum(1 for r in results if r.action == "scraped")
        skipped = sum(1 for r in results if r.action.startswith("skipped"))
        unmatched = sum(1 for r in results if r.action == "skipped_low_confidence")
        errors = sum(1 for r in results if r.action == "error")
        log.info("tvshows_done", scraped=scraped, skipped=skipped, unmatched=unmatched, errors=errors)

        return results
