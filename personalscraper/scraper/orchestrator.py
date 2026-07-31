"""Extracted scraper service module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.provenance_port import StagingProvenanceWriter
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
from personalscraper.scraper.tv_service_write import TvServiceWriteMixin

log = get_logger("scraper")

_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2}(?:-E\d{2,})? - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


class Scraper(
    ClassifierMixin,
    ExistingValidatorMixin,
    MovieServiceMixin,
    TvServiceMixin,
    TvServiceNfoMixin,
    TvServiceWriteMixin,
):
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
        follow_tvdb_resolver: "Callable[[Path], int | None] | None" = None,
        follow_movie_resolver: "Callable[[Path], int | None] | None" = None,
        provenance: "StagingProvenanceWriter | None" = None,
        run_uid: str | None = None,
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
            follow_tvdb_resolver: Optional provenance hook (scrape-follow-id).
                Given a staging show directory, returns the followed series'
                TVDB id so the scrape forces that id (``scrape_tvshow_forced``)
                instead of re-matching a duplicate TVDB entry. ``None`` (default)
                keeps the legacy free-match behaviour — fully retro-compatible.
            follow_movie_resolver: Optional provenance hook for MOVIES (#30 /
                ACC-05). Given a staging movie directory, returns the followed
                movie's TMDB id so the scrape forces that id
                (``scrape_movie_forced``) instead of free-matching by title+year.
                ``None`` (default) keeps the legacy free-match behaviour.
            provenance: Optional advisory provenance writer. When a scrape renames a
                tracked folder to its canonical name, ``move_path`` keeps the
                registry's ``current_path`` live so the later dispatch record matches
                (review A/B). Best-effort; ``None`` (default) ⇒ no rename tracking.
            run_uid: The scraping run's ``pipeline_run.run_uid`` (hex), stamped onto each
                scraped item's provenance row via ``set_scrape_run`` (F3). ``None``
                (default) ⇒ no run stamp.
        """
        self.settings = settings
        self.config = config
        self.patterns = patterns
        self.dry_run = dry_run
        self.interactive = interactive
        self._event_bus = event_bus
        self._registry = registry
        # Optional provenance hook (scrape-follow-id): given a staging show dir,
        # returns the followed series' TVDB id so the scrape forces that id
        # instead of re-matching a duplicate TVDB entry. None ⇒ free match
        # (retro-compatible: legacy callers pass nothing).
        self._follow_tvdb_resolver = follow_tvdb_resolver
        # Optional provenance hook for MOVIES (#30 / ACC-05): given a staging movie
        # dir, returns the TMDB id recorded at grab so the scrape forces that id
        # (``scrape_movie_forced``) instead of free-matching by title+year. None ⇒
        # free match (retro-compatible).
        self._follow_movie_resolver = follow_movie_resolver
        # Advisory provenance writer (feature provenance / #30). When a scrape renames
        # a tracked folder to its canonical name, move_path keeps current_path live so
        # the DISPATCH record (record_dispatch_by_path) matches and the row reaches
        # status='dispatched' (review A/B). Best-effort; None ⇒ not tracked.
        self._provenance = provenance
        # F3 run-linkage: the run that is scraping (hex pipeline_run.run_uid), stamped
        # onto each scraped item's provenance row via set_scrape_run. None ⇒ no stamp.
        self._run_uid = run_uid
        scraper_config = config.scraper if config is not None else None
        self._scraper_language = scraper_config.language if scraper_config is not None else "fr-FR"
        self._scraper_fallback_language = scraper_config.fallback_language if scraper_config is not None else "en-US"
        self._prefer_local_title = scraper_config.prefer_local_title if scraper_config is not None else True
        self._tvdb_language = self._to_tvdb_language(self._scraper_language)
        self._tvdb_fallback_language = self._to_tvdb_language(self._scraper_fallback_language)

        # Provider instantiation is owned by the registry. No TMDBClient or
        # TVDBClient is constructed here anymore — the orchestrator only
        # consumes providers via ``self._registry`` (chain / get / locked).

        # IMDb / Rotten-Tomatoes façades for the Q5=B external-ids pass
        # (provider-ids DESIGN §5). Both are OMDb façades gated on a single
        # ``OMDB_API_KEY`` and disabled by default, so they may not be
        # registered — resolve them fail-soft to ``None``. When ``None`` the
        # confirmed-write pass skips id re-validation + rating fetch silently
        # (DESIGN error table: "OMDb API key absent → IMDb + RT skip silencieux").
        self._imdb = self._optional_provider("imdb")
        self._rotten_tomatoes = self._optional_provider("rotten_tomatoes")

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

    def _optional_provider(self, name: str) -> Any | None:
        """Return the registry provider ``name``, or ``None`` when it is not wired.

        The IMDb / Rotten-Tomatoes rating façades are optional (gated on
        ``OMDB_API_KEY`` and off by default), so the registry raises
        :class:`UnknownProviderError` for them when OMDb is not provisioned.
        Swallow that into ``None`` — the caller (the confirmed-write external-ids
        pass) treats a missing façade as "skip validation + ratings silently".

        Args:
            name: Provider name to resolve (``"imdb"`` / ``"rotten_tomatoes"``).

        Returns:
            The wired provider instance, or ``None`` when it is not registered.
        """
        from personalscraper.api.metadata.registry._errors import UnknownProviderError  # noqa: PLC0415

        try:
            return self._registry.get(name)
        except UnknownProviderError:
            return None

    def _track_scrape_rename(self, input_dir: Path, result: ScrapeResult) -> None:
        """Keep ``current_path`` live across the scrape rename + stamp the scraping run.

        The scrape renames a folder to ``Title (Year)`` AFTER the identity resolver
        ran; without ``move_path``, ``current_path`` would stay the sorted release name
        and the dispatch record (keyed on ``current_path``) would never match (review
        A/B). After the folder is live at its final path, ``set_scrape_run`` records the
        run that scraped this item (F3). Advisory + best-effort — a provenance error
        never affects the scrape.

        Args:
            input_dir: The folder the scrape started from (the sorted path).
            result: The scrape result (``media_path`` is the FINAL, possibly-renamed
                folder — set by ``apply_canonical_dir_rename`` on a successful move).
        """
        if self._provenance is None:
            return
        final = result.media_path
        if final is not None and final != input_dir:
            try:
                self._provenance.move_path(str(input_dir), str(final))
            except Exception as exc:  # noqa: BLE001 — advisory: never fails the scrape
                log.warning("scrape_provenance_move_failed", directory=input_dir.name, error=str(exc))
        # F3: stamp the scraping run onto the (now live-at-``final``) row — for every
        # scraped item, renamed or not. No-op when run_uid is None or the item is untracked.
        stamp_path = final if final is not None else input_dir
        try:
            self._provenance.set_scrape_run(str(stamp_path), run_uid=self._run_uid)
        except Exception as exc:  # noqa: BLE001 — advisory: never fails the scrape
            log.warning("scrape_provenance_run_stamp_failed", directory=stamp_path.name, error=str(exc))

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
                # scrape-follow-id (#30 / ACC-05): if this folder came from a
                # follow-driven grab, force the recorded TMDB id (deterministic)
                # instead of free-matching. Fail-soft → free match on any error.
                forced_tmdb: int | None = None
                if self._follow_movie_resolver is not None:
                    try:
                        forced_tmdb = self._follow_movie_resolver(movie_dir)
                    except Exception as exc:  # noqa: BLE001 — never block the scrape
                        log.warning("scrape_movie_resolver_failed", directory=movie_dir.name, error=str(exc))
                if forced_tmdb is not None:
                    log.info("scrape_follow_forced_tmdb", directory=movie_dir.name, tmdb_id=forced_tmdb)
                    result = self.scrape_movie_forced(movie_dir, forced_tmdb)
                else:
                    result = self.scrape_movie(movie_dir)
                self._track_scrape_rename(movie_dir, result)
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
                # scrape-follow-id: if this folder came from a followed series,
                # force the follow's TVDB id (anti-split) instead of re-matching.
                # Fail-soft: a resolver error falls back to the free match.
                forced_tvdb: int | None = None
                if self._follow_tvdb_resolver is not None:
                    try:
                        forced_tvdb = self._follow_tvdb_resolver(show_dir)
                    except Exception as exc:  # noqa: BLE001 — never block the scrape
                        log.warning("scrape_follow_resolver_failed", directory=show_dir.name, error=str(exc))
                if forced_tvdb is not None:
                    log.info("scrape_follow_forced_tvdb", directory=show_dir.name, tvdb_id=forced_tvdb)
                    result = self.scrape_tvshow_forced(show_dir, "tvdb", forced_tvdb)
                else:
                    result = self.scrape_tvshow(show_dir)
                self._track_scrape_rename(show_dir, result)
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
