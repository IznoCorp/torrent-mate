"""TV show scraper service."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from personalscraper.api._contracts import ApiError, CircuitOpenError, MediaType
from personalscraper.api.metadata._base import Notations
from personalscraper.api.metadata._contracts import TvDetailsProvider
from personalscraper.api.metadata._tvdb_parsers import map_language
from personalscraper.api.metadata.registry import AttemptOutcome, RegistryProviderName
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_sample_path
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper._drift_persistence import DriftIssueStore
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper._tvdb_convert import (
    _tvdb_series_to_show_data as _tvdb_series_to_show_data,
)
from personalscraper.scraper._tvdb_convert import (
    fetch_show_data,
)
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.confidence import LOW_CONFIDENCE
from personalscraper.scraper.episode_manager import create_season_dirs, match_episode_files, rename_episodes
from personalscraper.scraper.existing_validator import _infer_year_from_child_names, _local_show_seasons
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.rename_service import (
    _cleanup_empty_release_dirs,
    _cleanup_stale_files,
    _merge_dirs,
    _rename_dir_case_safe,
)
from personalscraper.scraper.tv_service_episodes import (
    _episode_payload as _episode_payload,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.conf.models.config import Config
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper.artwork import ArtworkDownloader

log = get_logger("scraper")

# Season/episode token pattern used to strip the SxxEyy suffix from a
# guessit-extracted episode title so only the show name remains.
_SEASON_TOKEN_RE = re.compile(r"\s*-?\s*S\d+(?:E\d+)*.*$", re.IGNORECASE)


def _recover_title_from_episodes(show_dir: Path) -> str | None:
    """Recover the show title from episode filenames when the folder name is degenerate.

    When a staging folder is named with only a season token (e.g. `` S03``),
    ``_parse_folder_name`` returns that token as the title. This function
    inspects the episode files inside ``show_dir``, picks the first video
    file, runs ``NameCleaner.clean()`` on its stem, and strips the trailing
    season/episode token so only the show title remains.

    Args:
        show_dir: Path to the TV show staging directory.

    Returns:
        Recovered show title string, or None if no video files are found or
        the recovery produces an empty / token-only string.
    """
    video_files = sorted(
        f for f in show_dir.iterdir() if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
    )
    if not video_files:
        return None

    first = video_files[0]
    try:
        from personalscraper.sorter.cleaner import NameCleaner  # noqa: PLC0415

        cleaner = NameCleaner()
        raw_title = cleaner.clean(first.stem)
    except Exception:  # pragma: no cover — guard against unexpected guessit failures
        return None

    if not raw_title:
        return None

    # Strip trailing SxxEyy and everything after it (episode number, title)
    recovered = _SEASON_TOKEN_RE.sub("", raw_title).strip(" -").strip()
    return recovered if recovered else None


def _safe_get_rating(client: Any, provider_id: str) -> list[Notations]:
    """Backward-compat alias for :func:`personalscraper.scraper._xref.safe_get_rating`.

    Kept so the legacy import path (``from .tv_service import
    _safe_get_rating``) keeps working ; new code should import the
    function directly from ``personalscraper.scraper._xref``.
    """
    from personalscraper.scraper._xref import safe_get_rating  # noqa: PLC0415

    return safe_get_rating(client, provider_id)


class TvServiceMixin:
    """TV show scrape service methods.

    Provider access routes through ``self._registry`` (DESIGN §5.2). Phase 1
    uses ``self._registry.get("tmdb")`` / ``get("tvdb")`` for transitional
    direct access; Phase 2 migrates the matching path to
    ``registry.chain(Searchable | TvDetailsProvider | EpisodeFetcher)``.
    """

    patterns: "NamingPatterns"
    dry_run: bool
    _registry: "ProviderRegistry"
    _scraper_language: str
    _scraper_fallback_language: str
    _tvdb_language: str
    _tvdb_fallback_language: str
    _nfo: "NFOGenerator"
    _artwork: "ArtworkDownloader"
    config: "Config | None"
    _classify_item: "Callable[..., str | None]"
    _resolve_title: "Callable[..., str]"
    _strip_trailing_year: "Callable[[str], str]"
    _verify_existing_scrape: "Callable[..., tuple[bool, str]]"
    _check_missing_tvshow_artwork: "Callable[..., list[str]]"
    _recover_tvshow_artwork: "Callable[..., None]"
    _repair_tvshow_dir: "Callable[..., bool]"
    _generate_episode_nfos: Any  # from TvServiceNfoMixin (Phase 27.2 extraction)

    @staticmethod
    def _to_tvdb_language(language: str) -> str:
        """Convert configured scraper language to TVDB's 3-letter code."""
        code = language.split("-", 1)[0].lower()
        return map_language(code)

    def scrape_tvshow(self, show_dir: Path) -> ScrapeResult:
        """Scrape a TV show: match → NFO → artwork → seasons → episodes.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            ScrapeResult with action and details.
        """
        title, year = _parse_folder_name(show_dir.name)
        # Episode-filename fallback: if the folder title is a bare season/episode
        # token (e.g. " S03"), re-derive the show title from the first episode
        # file so the provider query uses the real title ("The Orville") instead
        # of the degenerate token.  is_degenerate_title is imported inline to
        # avoid a circular import with classifier.
        from personalscraper.scraper.classifier import is_degenerate_title  # noqa: PLC0415

        if is_degenerate_title(title):
            recovered = _recover_title_from_episodes(show_dir)
            if recovered:
                log.info(
                    "show_title_recovered_from_episodes",
                    degenerate_title=title,
                    recovered_title=recovered,
                    show_dir=str(show_dir),
                )
                title = recovered
        if year is None:
            year = _infer_year_from_child_names(show_dir, title)
        result = ScrapeResult(media_path=show_dir, media_type="tvshow")

        # Check for existing valid NFO
        nfo_path = show_dir / self.patterns.tvshow_nfo
        # ``drift_rescrape_episode_nfo`` flips True when the drift
        # validator rejects the existing scrape because of ANY
        # episode-level issue — missing canonical ``<uniqueid>`` tag
        # (provider-ids feature), non-conformant episode filename, or
        # a missing sibling episode NFO. Without this signal the full-
        # scrape path below would skip files already organized in
        # ``Saison NN/`` — exactly the DEV #2 symptom on a re-scrape
        # pass where only tvshow.nfo was regenerated but episode files
        # kept their raw release names.
        drift_rescrape_episode_nfo = False
        if _is_nfo_complete(nfo_path):
            # Fast path only when the previous scrape is still coherent with
            # the current scraper output (folder name, episode naming, NFO
            # content, artwork). Any drift → delete the NFO so the normal
            # scrape flow below rebuilds from a clean slate.
            is_valid, drift_reason = self._verify_existing_scrape(show_dir, nfo_path)
            if not is_valid:
                log.info(
                    "show_rescrape_drift",
                    directory=show_dir.name,
                    reason=drift_reason,
                )
                store = DriftIssueStore.from_config(self.config)
                if store is not None:
                    store.persist(show_dir, drift_reason)
                # Any episode-level drift reason requires sweeping into
                # ``Saison NN/`` so the rescrape path can regenerate
                # NFOs, rename episodes, or both.  The three reasons
                # match the ``verify_tvshow_scrape_drift`` return slugs.
                if drift_reason.startswith(
                    (
                        "episode_nfo_missing_canonical_uniqueid",
                        "episode_naming_drift",
                        "episode_nfo_missing",
                    )
                ):
                    drift_rescrape_episode_nfo = True
                if not self.dry_run:
                    try:
                        nfo_path.unlink()
                    except OSError as exc:
                        result.error = f"Cannot delete drifted NFO: {exc}"
                        log.error("nfo_drift_delete_failed", path=str(nfo_path), error=str(exc))
                        return result
                # Fall through to the full rescrape path below.
            else:
                # Existing fast path: artwork recovery + dir repair.
                missing_art = self._check_missing_tvshow_artwork(show_dir)
                if missing_art:
                    if self.dry_run:
                        # Surface the work the real run would do so dry-run
                        # output is not misleading (operators previously saw
                        # ``skipped_already_done`` and then watched the real
                        # run unexpectedly download artwork).
                        log.info(
                            "artwork_would_recover",
                            directory=show_dir.name,
                            missing=missing_art,
                        )
                    else:
                        self._recover_tvshow_artwork(nfo_path, show_dir, result)
                # Repair pass: remove residual NFOs, root MKV duplicates, etc.
                repaired = self._repair_tvshow_dir(show_dir)
                if repaired and result.action != "artwork_recovered":
                    result.action = "repaired"
                elif result.action != "artwork_recovered":
                    result.action = "skipped_already_done"
                log.info("nfo_valid", action=result.action, directory=show_dir.name)
                return result

        # Corrupt NFO: delete before re-scrape.  Same dry_run guard as
        # the movie branch above — a dry-run pass should not mutate
        # staging.
        if nfo_path.exists():
            if self.dry_run:
                log.info("nfo_corrupt_rescrape_would_delete", filename=nfo_path.name)
            else:
                log.warning("nfo_corrupt_rescrape", filename=nfo_path.name)
                try:
                    nfo_path.unlink()
                except OSError as exc:
                    result.error = f"Cannot delete corrupt NFO: {exc}"
                    log.error("nfo_corrupt_delete_failed", path=str(nfo_path), error=str(exc))
                    return result

        # Collect seasons present in the folder's video files — feeds
        # content-aware candidate disambiguation in match_tvshow_tvdb.
        local_seasons = _local_show_seasons(show_dir)

        # Match against TVDB/TMDB and fetch show details
        lookup = self._lookup_series(title, year, local_seasons, result)
        if lookup is None:
            return result
        match, show_data, tmdb_id, resolved_title = lookup

        # Rename folder to canonical name
        old_dir_name = show_dir.name  # Save before potential rename
        canonical = self.patterns.format(
            "movie_dir",
            Title=resolved_title,
            Year=match.api_year or year or "",
        )
        # NFC-compare: macOS stores filenames in NFD, Python strings are typically
        # NFC; a naive string compare treats them as different and triggers a
        # rename-into-self merge that empties the folder. See
        # ``verify_tvshow_scrape_drift`` for the matching normalization on the
        # read side.
        if unicodedata.normalize("NFC", show_dir.name) != unicodedata.normalize("NFC", canonical):
            new_dir = show_dir.parent / canonical
            if not self.dry_run:
                try:
                    if new_dir.exists():
                        try:
                            is_same_dir = show_dir.samefile(new_dir)
                        except OSError:
                            is_same_dir = False
                        if is_same_dir:
                            _rename_dir_case_safe(show_dir, new_dir)
                            log.info("show_folder_renamed", title=title, dest=canonical)
                        else:
                            moved, merge_failed = _merge_dirs(show_dir, new_dir)
                            log.info("show_folder_merged", title=title, dest=canonical, items=moved)
                            if merge_failed:
                                result.warnings.append(f"Partial merge: {merge_failed} item(s) failed")
                    else:
                        _rename_dir_case_safe(show_dir, new_dir)
                        log.info("show_folder_renamed", title=title, dest=canonical)
                    show_dir = new_dir
                    result.media_path = new_dir
                except OSError as exc:
                    result.error = f"Rename/merge failed: {exc}"
                    log.error("show_folder_rename_failed", title=title, dest=canonical, error=str(exc))
                    return result
                # Non-critical: clean stale files from before rename.
                # TV show artwork uses fixed names (poster.jpg, tvshow.nfo),
                # so this is a no-op for standard shows. Kept as safety net.
                try:
                    _cleanup_stale_files(show_dir, old_dir_name, canonical)
                except OSError as exc:
                    log.warning("stale_cleanup_failed", directory=show_dir.name, error=str(exc))
            else:
                action = "merge into" if new_dir.exists() else "rename"
                log.info("show_folder_would_rename", action=action, title=title, dest=canonical)

        # Classify item — must run before NFO write so the
        # category_id can be embedded in the NFO by nfo_generator.
        # For TV shows matched via TVDB the source TMDB ID may differ from
        # match.api_id — use tmdb_id which was resolved above.
        nfo_path = show_dir / self.patterns.tvshow_nfo
        category_id = self._classify_item(
            media_type=MediaType.TV,
            path=show_dir,
            title=resolved_title,
            api_data=show_data,
            tmdb_id=tmdb_id,
            nfo_path=nfo_path if nfo_path.exists() else None,
        )
        result.category_id = category_id
        if category_id is None and self.config is not None:
            # Config is present but no category matched — skip this item
            result.action = "skipped_no_category"
            return result

        # Generate tvshow.nfo
        try:
            xml = self._nfo.generate_tvshow_nfo(show_data, category_id=category_id)
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
            else:
                log.info("nfo_would_write", filename="tvshow.nfo")
        except Exception as e:
            result.error = f"tvshow.nfo failed: {e}"
            return result

        # Process episodes — rglob to find files nested in release-group subdirs,
        # but skip files already organized in Saison XX/ directories.
        # Trailers/ holds Plex-conformant trailer mp4s, never episodes.
        #
        # Episode processing must run BEFORE artwork so the Saison NN/ dirs
        # exist when ``download_tvshow_artwork`` decides which season posters
        # to fetch: that helper skips seasons whose folder is absent.
        total_renamed = 0

        # On an episode-NFO drift re-scrape, ALSO include files that
        # are already organized in ``Saison NN/`` — otherwise
        # ``_generate_episode_nfos`` never runs and the episode NFOs
        # stay broken (the very condition that triggered drift in the
        # first place, producing an infinite drift→rescrape loop with
        # no fix). ``rename_episodes`` is idempotent (skips files
        # already at their destination), so the wider sweep is safe.
        def _is_in_season_dir(path: Path) -> bool:
            return bool(SEASON_DIR_RE.match(path.parent.name))

        video_files = sorted(
            f
            for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and (drift_rescrape_episode_nfo or not _is_in_season_dir(f))
            and "Trailers" not in f.parts
            and not is_sample_path(f)
        )

        if video_files:
            # Resolve the synthetic-title prefix once per show so in-provider
            # episodes with empty names and post-facto fallbacks share the same
            # user-configurable wording (default "Episode").
            episode_default_name = self.config.scraper.episode_default_name if self.config is not None else "Episode"
            api_episodes = self._build_episode_map(show_dir, match, tmdb_id, episode_default_name)

            # Sequential xref enrichment (phase 5) — backfill the IDs of
            # the non-canonical provider into ``api_episodes`` so the
            # NFO writer can emit ``<uniqueid type=canonical>`` AND
            # ``<uniqueid type=xref>`` on every episode. Fail-soft : a
            # xref provider exception is logged, the canonical scrape
            # carries on with what it already has.
            canonical_provider = match.source
            tvdb_series_id = match.api_id if canonical_provider == "tvdb" else None
            self._xref_enrichment(
                api_episodes,
                canonical_provider=canonical_provider,
                tvdb_id=tvdb_series_id,
                tmdb_id=tmdb_id,
            )

            total_renamed, nfo_warnings = self._match_seasons(
                video_files, api_episodes, show_dir, show_data, episode_default_name
            )
            result.warnings.extend(nfo_warnings)

            # Clean empty release-group subdirectories left after episode moves
            if not self.dry_run:
                try:
                    _cleanup_empty_release_dirs(show_dir)
                except OSError as exc:
                    log.warning("show_clean_release_dirs_failed", show=show_dir.name, error=str(exc))

            # Episodes detected at the show root but none matched/moved into
            # ``Saison NN/`` — file naming and provider season layout diverge.
            # Without this signal the operator gets ``action="scraped"`` and
            # no clue that videos are still loose; verify catches the
            # filesystem shape but the scrape result itself stays opaque.
            if total_renamed == 0:
                loose = [f.name for f in video_files]
                result.warnings.append(
                    f"Episodes unmatched against {match.source} api_id={match.api_id}: {', '.join(loose)}"
                )
                log.warning(
                    "show_episodes_unmatched",
                    provider=match.source,
                    api_id=match.api_id,
                    show=show_dir.name,
                    files=loose,
                )

        # Download artwork (show-level + season posters). Runs after episode
        # processing so newly-created Saison NN/ dirs are visible to the
        # season-poster selection logic in ``download_tvshow_artwork``.
        try:
            downloaded = self._artwork.download_tvshow_artwork(
                show_data,
                show_dir,
                self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except (requests.RequestException, OSError, KeyError, AttributeError) as e:
            log.warning("show_artwork_failed", api_title=match.api_title, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork failed: {e}")

        store = DriftIssueStore.from_config(self.config)
        if store is not None:
            store.clear(show_dir)
        result.episodes_renamed = total_renamed
        result.action = "scraped"
        return result

    def _match_tvshow_candidates(
        self,
        title: str,
        year: int | None,
        local_seasons: set[int],
        result: ScrapeResult,
    ) -> Any | None:
        """Search the configured TV chain for candidates matching title + year.

        Thin delegate to
        :func:`personalscraper.scraper.tv_service_episodes.match_tvshow_candidates`
        — see that function for the full chain-iteration / fallback contract.
        """
        from personalscraper.scraper.tv_service_episodes import match_tvshow_candidates  # noqa: PLC0415

        return match_tvshow_candidates(self._registry, title, year, local_seasons, result)

    def _lookup_series(
        self,
        title: str,
        year: int | None,
        local_seasons: set[int],
        result: ScrapeResult,
    ) -> tuple[Any, dict[str, Any], int | None, str] | None:
        """Match a TV show against the TV chain and fetch full series details.

        Two-step lookup:

        1. ``_match_tvshow_candidates`` iterates
           ``registry.chain(TvDetailsProvider)`` to find the best
           :class:`MatchResult` (TVDB first then TMDB by default
           configuration, with full chain fallback semantics).
        2. Once a match is accepted (confidence ≥ ``LOW_CONFIDENCE``),
           the details fetch iterates the same chain again but filters
           to ``provider_name == match.source`` to honour the
           source-of-match invariant — cross-provider id translation
           (TVDB ↔ TMDB) is owned by ``registry.cross_ref`` and lives
           in sub-phase 7.4.

        Per-provider failures during the details step emit
        :class:`ProviderFallbackTriggered`; full exhaustion emits
        :class:`ProviderExhaustedEvent` and populates ``result.error``.

        Returns ``(match, show_data, tmdb_id, resolved_title)`` on
        success, ``None`` on failure (sets ``result.error`` /
        ``result.action``).

        Args:
            title: Parsed show title.
            year: Optional release year.
            local_seasons: Season numbers present on disk.
            result: ScrapeResult for tracking.

        Returns:
            Success tuple or ``None``.
        """
        # The chain raises ``ProviderExhausted`` when every eligible
        # provider failed with a classified error (DESIGN §6.2 line 79).
        # Catch and surface the original exception detail to preserve
        # the ACC-13 legacy contract.
        try:
            match = self._match_tvshow_candidates(title, year, local_seasons, result)
        except ProviderExhausted as exc:
            detail = exc.last_exception if exc.last_exception is not None else exc
            result.error = f"Match failed: {detail}"
            result.action = "error"
            return None
        if result.error:
            return None
        if match is None or match.confidence < LOW_CONFIDENCE:
            result.action = "skipped_low_confidence"
            log.warning(
                "show_no_confident_match",
                title=title,
                year=year,
                score=round(match.confidence if match else 0.0, 2),
            )
            return None
        result.match = match
        log.info(
            "show_matched",
            title=title,
            api_title=match.api_title,
            source=match.source,
            confidence=round(match.confidence, 2),
        )

        # Step 2 — details fetch via chain iteration (DESIGN §6.2). Mirror
        # of the movie scrape_movie details path: iterate
        # ``chain(TvDetailsProvider)`` filtering to ``match.source``;
        # ApiError / network / circuit failures emit fallback events;
        # full exhaustion emits ProviderExhaustedEvent.
        details_item_context: dict[str, Any] = {
            "title": match.api_title,
            "year": match.api_year,
            "media_type": "tvshow",
            "provider_id": match.api_id,
        }
        tmdb_id: int | None = None
        show_data: dict[str, Any] | None = None
        details_attempted: list[AttemptOutcome] = []
        details_providers = self._registry.chain(TvDetailsProvider)  # type: ignore[type-abstract]
        for provider in details_providers:
            provider_name = getattr(provider, "provider_name", "?")
            # Honour the source-of-match invariant: only consult the
            # provider that produced the MatchResult. Cross-provider
            # translation lands in sub-phase 7.4.
            if provider_name != match.source:
                continue
            try:
                # Source-aware show-data fetch — the TVDB-primary / TMDB-fallback
                # branch now lives once in fetch_show_data, shared with the
                # maintenance rescraper so the discipline cannot diverge.
                show_data, tmdb_id = fetch_show_data(
                    match.source,
                    match.api_id,
                    provider,
                    preferred_language=self._scraper_language,
                    fallback_language=self._scraper_fallback_language,
                )
                break
            except CircuitOpenError as exc:
                details_attempted.append(
                    AttemptOutcome(provider=RegistryProviderName(provider_name), reason="circuit_open")
                )
                self._registry.emit_provider_fallback(
                    capability="TvDetailsProvider",
                    from_provider=provider_name,
                    reason="circuit_open",
                    item=details_item_context,
                )
                log.warning("show_details_circuit_open", provider=provider_name, error=str(exc))
                continue
            except (ApiError, requests.RequestException, OSError) as exc:
                details_attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(provider_name),
                        reason="network",
                        detail=type(exc).__name__,
                    )
                )
                self._registry.emit_provider_fallback(
                    capability="TvDetailsProvider",
                    from_provider=provider_name,
                    reason="network",
                    exc_type=type(exc).__name__,
                    item=details_item_context,
                )
                log.warning(
                    "show_details_network_fail",
                    provider=provider_name,
                    exc_type=type(exc).__name__,
                    error=str(exc),
                )
                continue
            except Exception as e:
                # Phase 21 + 26.2: ANY unclassified exception during details
                # fetch is treated as a chain fallback per DESIGN §6.2.
                # Aligns with the broader ``except Exception`` already used
                # by movie_service.py:857.
                details_attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(provider_name),
                        reason="other",
                        detail=type(e).__name__,
                    )
                )
                self._registry.emit_provider_fallback(
                    capability="TvDetailsProvider",
                    from_provider=provider_name,
                    reason="other",
                    exc_type=type(e).__name__,
                    item=details_item_context,
                )
                log.warning(
                    "show_details_failed",
                    provider=provider_name,
                    exc_type=type(e).__name__,
                    error=str(e),
                )
                continue

        if show_data is None:
            if details_attempted:
                self._registry.emit_provider_exhausted(
                    capability="TvDetailsProvider",
                    attempted=details_attempted,
                    item=details_item_context,
                )
                log.error(
                    "registry_chain_exhausted",
                    capability="TvDetailsProvider",
                    attempted=[(a.provider, a.reason) for a in details_attempted],
                    item=details_item_context,
                )
                result.error = f"Get details failed: all providers exhausted for {TvDetailsProvider.__name__}"
            else:
                result.error = f"Get details failed: no provider available for source={match.source!r}"
                log.error("show_details_no_provider", api_title=match.api_title, source=match.source)
            return None

        resolved_title = self._strip_trailing_year(self._resolve_title(match.api_title, show_data, "tvshow"))
        return match, show_data, tmdb_id, resolved_title

    def _build_episode_map(
        self,
        show_dir: Path,
        match: Any,
        tmdb_id: int | None,
        episode_default_name: str,
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """Fetch episode data from TVDB/TMDB keyed by (season, episode).

        Discovers seasons from local filesystem directories (Saison XX/) and
        queries metadata providers in the priority order declared by
        ``config.metadata.priorities.episode_scraping``. The first provider
        that returns a non-empty episode list for a given season wins; if
        it comes back empty or raises, the next provider is tried.
        Episodes with missing titles receive a synthetic
        ``"{episode_default_name} {number}"``.

        Args:
            show_dir: Path to the TV show directory.
            match: MatchResult from the scrape step.
            tmdb_id: TMDB ID resolved at lookup time (from cross-references
                on TVDB-matched shows or ``match.api_id`` on TMDB-matched
                shows). ``None`` disables the TMDB branch.
            episode_default_name: Fallback title prefix for unnamed episodes.

        Returns:
            Dict mapping ``(season, episode)`` to ``{"title", "still_path"}``.
            Empty when every provider's catalog lacks the requested seasons.
        """
        season_nums = sorted(
            {
                int(m.group(1))
                for d in show_dir.iterdir()
                if d.is_dir() and (m := SEASON_DIR_RE.match(d.name))
                if int(m.group(1)) > 0
            }
        )
        # Bootstrap: when the show has no Saison NN/ dirs yet (fresh torrent
        # layout), discover seasons from SxxEyy patterns in nested video files
        # so the API episode map can still be built — otherwise the rescrape
        # path silently bails out and never reorganizes the show.
        if not season_nums:
            season_nums = sorted(s for s in _local_show_seasons(show_dir) if s > 0)
        if not season_nums:
            return {}

        # Derive the TVDB id when the show was matched via TVDB. TMDB-matched
        # shows currently leave ``tvdb_id`` unresolved (would require a
        # cross-reference fetch); the priority loop handles that gracefully by
        # skipping providers whose id is missing.
        tvdb_id = match.api_id if match.source == "tvdb" else None

        # Provider lock contract (DESIGN scraping.md §Episode Provider Lock).
        # When ``lock_to_series_provider`` is true (default), episodes are
        # fetched ONLY from the provider that matched the series. We neutralize
        # the other provider's id so ``_ordered_episode_providers`` won't
        # build a fallback candidate for it. Pinned by
        # ``TestEpisodeProviderLockContract`` in
        # tests/integration/test_design_scraper.py.
        lock_engaged = self.config is not None and self.config.metadata.episode_scraping_policy.lock_to_series_provider
        if lock_engaged:
            if match.source == "tvdb":
                if tmdb_id is not None:
                    log.info(
                        "provider_lock_engaged",
                        provider="tvdb",
                        show_id=match.api_id,
                        suppressed_provider="tmdb",
                        suppressed_id=tmdb_id,
                    )
                tmdb_id = None
            elif match.source == "tmdb":
                if tvdb_id is not None:
                    log.info(
                        "provider_lock_engaged",
                        provider="tmdb",
                        show_id=match.api_id,
                        suppressed_provider="tvdb",
                        suppressed_id=tvdb_id,
                    )
                tvdb_id = None

        providers = self._ordered_episode_providers(tvdb_id, tmdb_id, episode_default_name)
        if not providers:
            return {}

        api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
        for s_num in season_nums:
            api_episodes.update(self._fetch_season_with_fallback(s_num, providers))
        return api_episodes

    def _xref_enrichment(
        self,
        api_episodes: dict[tuple[int, int], dict[str, Any]],
        canonical_provider: str,
        tvdb_id: int | None,
        tmdb_id: int | None,
    ) -> None:
        """Backfill the per-episode IDs of the non-canonical provider in place.

        Thin delegate to
        :func:`personalscraper.scraper._xref.xref_enrichment` — see
        that function's docstring for the contract. The mixin wrapper
        exists so callers stay decoupled from the helper module
        location and so the TV/movie services can override the fetch
        callables (TVDB / TMDb seasons) without re-implementing the
        merge logic.
        """
        from personalscraper.scraper._xref import xref_enrichment as _xref  # noqa: PLC0415

        _xref(
            api_episodes,
            canonical_provider=canonical_provider,
            tvdb_fetcher=self._xref_fetch_tvdb_season,
            tmdb_fetcher=self._xref_fetch_tmdb_season,
            tvdb_id=tvdb_id,
            tmdb_id=tmdb_id,
        )

    def _xref_fetch_tmdb_season(self, tmdb_id: int, season: int) -> dict[int, dict[str, str]]:
        """Return ``{episode_number: external_ids}`` from a TMDb season fetch.

        Thin delegate to
        :func:`personalscraper.scraper.tv_service_episodes.xref_fetch_tmdb_season`.
        """
        from personalscraper.scraper.tv_service_episodes import xref_fetch_tmdb_season  # noqa: PLC0415

        return xref_fetch_tmdb_season(self._registry, tmdb_id, season)

    def _xref_fetch_tvdb_season(self, tvdb_id: int, season: int) -> dict[int, dict[str, str]]:
        """Return ``{episode_number: external_ids}`` from a TVDB season fetch.

        Thin delegate to
        :func:`personalscraper.scraper.tv_service_episodes.xref_fetch_tvdb_season`.
        """
        from personalscraper.scraper.tv_service_episodes import xref_fetch_tvdb_season  # noqa: PLC0415

        return xref_fetch_tvdb_season(self._registry, tvdb_id, season)

    def _resolve_external_ids(
        self,
        canonical_provider: str,
        series_ids: dict[str, str],
        expected_title: str,
        expected_year: int | None,
    ) -> tuple[dict[str, str], list[Notations]]:
        """Resolve trusted cross-provider IDs + series-level ratings (Q5=B).

        Thin delegate to
        :func:`personalscraper.scraper._xref.resolve_external_ids` —
        see that function for the full contract.
        """
        from personalscraper.scraper._xref import resolve_external_ids as _resolve  # noqa: PLC0415

        return _resolve(
            canonical_provider=canonical_provider,
            ids=series_ids,
            expected_title=expected_title,
            expected_year=expected_year,
            family_to_client=self._family_to_client,
            imdb_client=getattr(self, "_imdb", None),
            rt_client=getattr(self, "_rotten_tomatoes", None),
        )

    def _family_to_client(self, family: str) -> Any | None:
        """Map a provider family name to the wired client / façade (or ``None``).

        Transitional access via the registry (Phase 1 — DESIGN §5.2). The
        registry raises ``UnknownProviderError`` for names it does not know;
        we treat that as ``None`` to preserve the legacy fail-soft contract.
        """
        from personalscraper.api.metadata.registry._errors import UnknownProviderError  # noqa: PLC0415

        if family in {"tmdb", "tvdb"}:
            try:
                return self._registry.get(family)
            except UnknownProviderError as e:
                # If boot validation passed but we reach here, this is a runtime
                # contract violation worth a forensic anchor (the registry's
                # config should already have caught an unwired family).
                log.warning(
                    "xref_family_unwired",
                    family=family,
                    exc_type=type(e).__name__,
                )
                return None
        mapping: dict[str, Any] = {
            "imdb": getattr(self, "_imdb", None),
        }
        return mapping.get(family)

    def _ordered_episode_providers(
        self,
        tvdb_id: int | None,
        tmdb_id: int | None,
        episode_default_name: str,
    ) -> list[tuple[str, Callable[[int], list[tuple[int, dict[str, Any]]]]]]:
        """Build the per-season fetch list, ordered by ``episode_scraping`` priority.

        Thin delegate to
        :func:`personalscraper.scraper.tv_service_episodes.ordered_episode_providers`.
        """
        from personalscraper.scraper.tv_service_episodes import ordered_episode_providers  # noqa: PLC0415

        priority: dict[str, int] = self.config.metadata.priorities.episode_scraping if self.config is not None else {}
        return ordered_episode_providers(self._registry, priority, tvdb_id, tmdb_id, episode_default_name)

    def _fetch_season_with_fallback(
        self,
        season: int,
        providers: list[tuple[str, Callable[[int], list[tuple[int, dict[str, Any]]]]]],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """Iterate providers in priority order, return the first non-empty result.

        Thin delegate to
        :func:`personalscraper.scraper.tv_service_episodes.fetch_season_with_fallback`.
        """
        from personalscraper.scraper.tv_service_episodes import fetch_season_with_fallback  # noqa: PLC0415

        return fetch_season_with_fallback(season, providers)

    def _match_seasons(
        self,
        video_files: list[Path],
        api_episodes: dict[tuple[int, int], dict[str, Any]],
        show_dir: Path,
        show_data: dict[str, Any],
        episode_default_name: str,
    ) -> tuple[int, list[str]]:
        """Match local video files to API episodes and organise into season dirs.

        Uses ``match_episode_files`` to pair local files with API episode data,
        then creates the necessary season directories and renames episodes into
        place. Only seasons that will actually receive a file are created.

        Args:
            video_files: Sorted list of video file paths in the show directory.
            api_episodes: Dict from ``_build_episode_map()``.
            show_dir: Path to the TV show directory.
            show_data: Full show data dict (for NFO generation).
            episode_default_name: Fallback title prefix for unnamed episodes.

        Returns:
            Tuple of (count of episodes renamed, list of NFO write failure warnings).
        """
        # Pass the unmatched-episode policy through to ``match_episode_files``.
        # Default contract (``allow_synthetic_rename_on_unmatched=False``)
        # excludes files with no API record from the result so they stay at
        # the show-folder root with their raw filename — the user can
        # intervene manually. Set to ``True`` to restore the legacy synthetic
        # "Episode N" rename + Saison NN/ placement.
        # Pinned by ``TestUnmatchedEpisodeNoRenameContract`` in
        # tests/integration/test_design_scraper.py.
        allow_synthetic_rename = (
            self.config is None or self.config.metadata.episode_scraping_policy.allow_synthetic_rename_on_unmatched
        )
        matched = match_episode_files(
            video_files,
            api_episodes,
            episode_default_name=episode_default_name,
            allow_synthetic_rename=allow_synthetic_rename,
        )
        if not matched:
            return 0, []
        needed_seasons = sorted({info["season"] for info in matched.values()})
        ep_list = [{"season_number": s, "episode_number": 0} for s in needed_seasons]
        create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
        total = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
        nfo_warnings = self._generate_episode_nfos(matched, show_dir, show_data)
        return total, nfo_warnings
