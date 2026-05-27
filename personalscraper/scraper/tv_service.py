"""TV show scraper service."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from personalscraper.api._contracts import ApiError, CircuitOpenError, MediaType
from personalscraper.api.metadata._base import EpisodeInfo, Notations
from personalscraper.api.metadata._contracts import EpisodeFetcher, TvDetailsProvider
from personalscraper.api.metadata._tvdb_parsers import map_language
from personalscraper.api.metadata.registry import AttemptOutcome, RegistryProviderName
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper._drift_persistence import DriftIssueStore
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper._tvdb_convert import (
    _tvdb_series_to_show_data as _tvdb_series_to_show_data,
)
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.confidence import LOW_CONFIDENCE
from personalscraper.scraper.episode_manager import create_season_dirs, match_episode_files, rename_episodes
from personalscraper.scraper.existing_validator import _infer_year_from_child_names, _local_show_seasons
from personalscraper.scraper.models import ScraperExternalIds
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.rename_service import (
    _cleanup_empty_release_dirs,
    _cleanup_stale_files,
    _merge_dirs,
    _rename_dir_case_safe,
)
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.conf.models.config import Config
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper.artwork import ArtworkDownloader

log = get_logger("scraper")


def _safe_get_rating(client: Any, provider_id: str) -> list[Notations]:
    """Backward-compat alias for :func:`personalscraper.scraper._xref.safe_get_rating`.

    Kept so the legacy import path (``from .tv_service import
    _safe_get_rating``) keeps working ; new code should import the
    function directly from ``personalscraper.scraper._xref``.
    """
    from personalscraper.scraper._xref import safe_get_rating  # noqa: PLC0415

    return safe_get_rating(client, provider_id)


def _episode_payload(ep: EpisodeInfo, episode_default_name: str) -> dict[str, Any]:
    """Build the per-episode payload for ``_build_episode_map``.

    Translates an :class:`EpisodeInfo` from the metadata layer into the
    dict shape consumed downstream by :func:`match_episode_files` and
    :meth:`TvServiceMixin._generate_episode_nfos`. The provider-side
    IDs travel under the ``{provider}_episode_id`` keys (DEV #2 root
    cause — these keys are what reach the NFO writer as ``tvdb_id`` /
    ``tmdb_id`` / ``imdb_id``).

    Args:
        ep: Episode parsed from a TVDB / TMDB season response.
        episode_default_name: Fallback prefix when ``ep.title`` is blank.

    Returns:
        Dict carrying the display title, the still-image path
        placeholder, and the per-provider episode IDs surfaced by the
        parser.
    """
    payload: dict[str, Any] = {
        "title": ep.title or f"{episode_default_name} {ep.episode_number}",
        "still_path": "",
    }
    for provider, value in ep.external_ids.items():
        if not value:
            continue
        payload[f"{provider}_episode_id"] = value
    return payload


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

            total_renamed = self._match_seasons(video_files, api_episodes, show_dir, show_data, episode_default_name)

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

    def _augment_episode_nfo_with_xref(self, nfo_path: Path, info: dict[str, Any]) -> None:
        """Append missing xref ``<uniqueid>`` rows to an existing episode NFO.

        Thin delegate to
        :func:`personalscraper.scraper._xref.augment_episode_nfo_with_xref`.
        """
        from personalscraper.scraper._xref import augment_episode_nfo_with_xref  # noqa: PLC0415

        augment_episode_nfo_with_xref(nfo_path, info, dry_run=self.dry_run)

    def _download_episode_thumb(
        self,
        still_path: str,
        thumb_path: Path,
        season: int,
        episode: int,
    ) -> None:
        """Download an episode thumbnail from TMDB if available.

        Skips if still_path is empty, thumb already exists, or dry_run.
        Errors are logged and do not interrupt the caller.

        Args:
            still_path: TMDB still image path (e.g. "/abc123.jpg"), empty to skip.
            thumb_path: Local destination path for the thumbnail.
            season: Season number (for log messages).
            episode: Episode number (for log messages).
        """
        if not still_path or thumb_path.exists() or self.dry_run:
            return
        url = f"https://image.tmdb.org/t/p/original{still_path}"
        try:
            self._artwork.download_image(url, thumb_path)
        except requests.exceptions.RequestException:
            log.warning("episode_thumb_failed", season=season, episode=episode)

    def _match_tvshow_candidates(
        self,
        title: str,
        year: int | None,
        local_seasons: set[int],
        result: ScrapeResult,
    ) -> Any | None:
        """Search the configured TV chain for candidates matching title + year.

        Iterates ``self._registry.chain(TvDetailsProvider)`` per DESIGN §6.2
        and tries each eligible provider in priority order. Per-provider
        failures emit :class:`ProviderFallbackTriggered`; full chain
        exhaustion (every attempt errored) emits
        :class:`ProviderExhaustedEvent` and populates ``result.error``
        with the last exception's message. The legacy fail-soft contract
        is preserved: callers receive ``None`` and inspect
        ``result.error`` rather than catching a registry exception.

        Branch semantics (closed list — DESIGN §6.2):

        - ``circuit_open`` — :class:`CircuitOpenError` raised by the
          provider; record outcome, emit fallback, continue.
        - ``network`` — :class:`ApiError`, :class:`requests.RequestException`,
          or :class:`OSError`; record outcome with ``exc_type``, emit
          fallback, continue.
        - ``empty_result`` — provider returned ``None`` (no candidates);
          emit fallback, continue.
        - Any other exception — set ``result.error``, log, return ``None``
          (preserves the legacy fail-soft contract used by orchestrator).

        Returns the **first** provider's :class:`MatchResult` (even if
        low-confidence — the confidence threshold is the caller's
        responsibility, see ``_lookup_series``). Replaces the historical
        hardcoded TVDB→TMDB fallback inside :func:`match_tvshow`; the
        chain order is now declared in
        ``config.metadata.priorities.tv_match`` (default: TVDB then
        TMDB) and honoured by the registry.

        Phase 16 restores the DESIGN §6.2 line 79 contract: the chain
        now **raises** :class:`ProviderExhausted` on full failure (every
        attempt errored with ``circuit_open`` or ``network``) so the
        immediate caller (:meth:`_lookup_series`) can surface the
        original exception detail via
        :attr:`ProviderExhausted.last_exception`. The ACC-13 contract
        (``"<detail>" in result.error``) is preserved end-to-end.

        Args:
            title: Show title to search for.
            year: Optional first air date year.
            local_seasons: Season numbers observed in the folder (forwarded
                to TVDB content-aware disambiguation).
            result: ScrapeResult for error tracking.

        Returns:
            :class:`MatchResult` on the first successful provider call,
            or ``None`` when ``result.error`` was populated (unclassified
            exception) or every chain provider returned an empty result.

        Raises:
            ProviderExhausted: When at least one chain provider raised
                a classified failure (``circuit_open`` / ``network``) and
                no provider returned a match. The caller is responsible
                for catching and surfacing the error in ``result.error``.
        """
        from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

        item_context: dict[str, Any] = {"title": title, "year": year, "media_type": "tvshow"}
        providers = self._registry.chain(TvDetailsProvider)  # type: ignore[type-abstract]
        attempted: list[AttemptOutcome] = []
        last_exception: Exception | None = None

        for provider in providers:
            provider_name = getattr(provider, "provider_name", "?")
            try:
                match = scraper_api.match_tvshow_single(provider, title, year, local_seasons=local_seasons)
            except CircuitOpenError as exc:
                last_exception = exc
                attempted.append(AttemptOutcome(provider=RegistryProviderName(provider_name), reason="circuit_open"))
                log.debug(
                    "registry_provider_skip",
                    provider=provider_name,
                    capability="TvDetailsProvider",
                    reason="circuit_open",
                )
                self._registry._emit_provider_fallback(
                    capability="TvDetailsProvider",
                    from_provider=provider_name,
                    reason="circuit_open",
                    item=item_context,
                )
                continue
            except (ApiError, requests.RequestException, OSError) as exc:
                last_exception = exc
                attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(provider_name),
                        reason="network",
                        detail=type(exc).__name__,
                    )
                )
                log.warning(
                    "registry_provider_fail",
                    provider=provider_name,
                    capability="TvDetailsProvider",
                    exc_type=type(exc).__name__,
                )
                self._registry._emit_provider_fallback(
                    capability="TvDetailsProvider",
                    from_provider=provider_name,
                    reason="network",
                    exc_type=type(exc).__name__,
                    item=item_context,
                )
                continue
            except Exception as exc:
                # Unclassified provider failure — preserve legacy fail-soft
                # contract (orchestrator surfaces ``result.error`` as an
                # ``action="error"`` ScrapeResult).
                result.error = f"Match failed: {exc}"
                log.error("show_match_failed", title=title, error=str(exc), exc_info=True)
                return None

            if match is None:
                attempted.append(AttemptOutcome(provider=RegistryProviderName(provider_name), reason="empty_result"))
                log.debug(
                    "registry_provider_skip",
                    provider=provider_name,
                    capability="TvDetailsProvider",
                    reason="empty_result",
                )
                self._registry._emit_provider_fallback(
                    capability="TvDetailsProvider",
                    from_provider=provider_name,
                    reason="empty_result",
                    item=item_context,
                )
                continue

            return match

        # All providers attempted and none produced a match.
        if attempted and any(a.reason in {"circuit_open", "network"} for a in attempted):
            # At least one attempt errored. Emit the exhausted event for
            # observers, then RAISE ``ProviderExhausted`` per DESIGN §6.2.
            # The caller (:meth:`_lookup_series`) catches and surfaces a
            # legacy-shape ``result.error`` carrying the original
            # exception's detail (ACC-13 contract).
            self._registry._emit_provider_exhausted(
                capability="TvDetailsProvider",
                attempted=attempted,
                item=item_context,
            )
            log.error(
                "registry_chain_exhausted",
                capability="TvDetailsProvider",
                attempted=[(a.provider, a.reason) for a in attempted],
                item=item_context,
            )
            raise ProviderExhausted(
                capability=TvDetailsProvider,
                attempted=attempted,
                item_context=item_context,
                last_exception=last_exception,
            )
        # Empty chain or all empty_result → legacy "no confident match"
        # path (caller branches on the None return).
        return None

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
                if match.source == "tvdb":
                    tvdb_data = provider.get_series(match.api_id)  # type: ignore[attr-defined]
                    if hasattr(tvdb_data, "external_ids"):
                        remote_ids: dict[str, str] = tvdb_data.external_ids
                    else:
                        remote_ids = {}
                    raw_tmdb = remote_ids.get("tmdb")
                    tmdb_id = int(raw_tmdb) if raw_tmdb else None
                    imdb_id = remote_ids.get("imdb") or ""
                    if not tmdb_id:
                        log.info("show_tvdb_only", tvdb_id=match.api_id)
                    show_data = _tvdb_series_to_show_data(
                        tvdb_data,
                        match.api_id,
                        provider,
                        preferred_language=self._scraper_language,
                        fallback_language=self._scraper_fallback_language,
                        external_ids=ScraperExternalIds(tmdb_id=tmdb_id, imdb_id=imdb_id),
                    )
                else:
                    # Local import: avoids the movie_service ↔ tv_service
                    # circular dependency at module load.
                    from personalscraper.scraper.movie_service import _coerce_to_show_data  # noqa: PLC0415

                    tmdb_id = match.api_id
                    show_data = _coerce_to_show_data(provider.get_tv(tmdb_id))  # type: ignore[attr-defined]
                break
            except CircuitOpenError as exc:
                details_attempted.append(
                    AttemptOutcome(provider=RegistryProviderName(provider_name), reason="circuit_open")
                )
                self._registry._emit_provider_fallback(
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
                self._registry._emit_provider_fallback(
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
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                # Payload-shape / parser failures preserve the legacy
                # ``result.error`` contract — bail out without rolling on.
                result.error = f"Get details failed: {e}"
                log.error("show_details_failed", error=str(e), exc_info=True)
                return None

        if show_data is None:
            if details_attempted:
                self._registry._emit_provider_exhausted(
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

        Legitimately direct dispatch (sub-phase 7.4 carve-out): the caller
        (:func:`personalscraper.scraper._xref.xref_enrichment`) already
        knows it wants the **non-canonical** provider for the cross-
        reference backfill — there is no fallback contract here. Going
        through ``chain(EpisodeFetcher)`` would force a name filter for
        a single provider, which is exactly what direct dispatch
        already expresses. The legacy method name
        (``get_tv_season``) is retained because the
        :class:`EpisodeFetcher` Protocol surfaces ``list[EpisodeInfo]``
        while this helper consumes :class:`SeasonDetails` to keep the
        per-episode external_ids accessible without restructuring the
        xref helper API.
        """
        tmdb_client = self._registry.get("tmdb")
        detail = tmdb_client.get_tv_season(tmdb_id, season)  # type: ignore[attr-defined]
        return {ep.episode_number: dict(ep.external_ids) for ep in detail.episodes}

    def _xref_fetch_tvdb_season(self, tvdb_id: int, season: int) -> dict[int, dict[str, str]]:
        """Return ``{episode_number: external_ids}`` from a TVDB season fetch.

        Legitimately direct dispatch — see :meth:`_xref_fetch_tmdb_season`.
        """
        tvdb_client = self._registry.get("tvdb")
        detail = tvdb_client.get_series_episodes(tvdb_id, season)  # type: ignore[attr-defined]
        return {ep.episode_number: dict(ep.external_ids) for ep in detail.episodes}

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
            except UnknownProviderError:
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

        Iterates ``self._registry.chain(EpisodeFetcher)`` to enumerate the
        eligible providers (circuit CLOSED / HALF_OPEN, per DESIGN §6.2).
        Each provider is paired with the cross-reference id resolved
        upstream — providers whose id is missing (or zeroed by the
        provider-lock contract) are dropped before iteration. The
        resulting list is re-sorted by
        ``config.metadata.priorities.episode_scraping`` so the operator-
        declared priority always wins over the registry's structural
        order.

        Each entry is ``(provider_name, fetch_callable)`` where
        ``fetch_callable`` takes a season number and returns
        ``[(episode_number, payload), ...]``. Closures capture the
        provider reference directly so the chain iteration order is
        baked in at call time — no second registry lookup at fetch
        time.

        Args:
            tvdb_id: Resolved TVDB id (``None`` if unavailable).
            tmdb_id: Resolved TMDB id (``None`` if unavailable).
            episode_default_name: Title prefix for episodes whose provider
                title is empty.

        Returns:
            List of ``(name, fetch)`` pairs, lowest priority number first.
        """
        priority: dict[str, int] = self.config.metadata.priorities.episode_scraping if self.config is not None else {}

        def _rank(name: str) -> int:
            """Pull a provider rank, falling back to a sentinel for unknowns.

            Providers absent from ``episode_scraping`` are sorted last so they
            only fire when everything higher-priority is unavailable.
            """
            return priority.get(name, 99)

        # Pre-resolve the cross-reference id for each canonical name —
        # the chain iteration below filters on ``provider_name`` to
        # pair each registry-eligible provider with its resolved id.
        provider_ids: dict[str, int] = {}
        if tvdb_id is not None:
            provider_ids["tvdb"] = tvdb_id
        if tmdb_id is not None:
            provider_ids["tmdb"] = tmdb_id

        def _make_fetch(provider: Any, provider_id: int) -> Callable[[int], list[tuple[int, dict[str, Any]]]]:
            """Build a season-fetch closure bound to ``provider`` + its id.

            The closure dispatches to the per-client legacy method
            (``get_series_episodes`` on TVDB, ``get_tv_season`` on TMDB)
            so existing mock test surfaces keep working. Both legacy
            methods return :class:`SeasonDetails`, whose ``episodes``
            field carries the :class:`EpisodeInfo` payload the
            :class:`EpisodeFetcher` Protocol surfaces directly — they
            are wire-compatible. Episode payloads are rendered through
            :func:`_episode_payload` so downstream NFO + match code
            stays decoupled from the provider-specific dataclasses.
            """
            name = getattr(provider, "provider_name", "")

            def _fetch(season: int) -> list[tuple[int, dict[str, Any]]]:
                if name == "tvdb":
                    detail = provider.get_series_episodes(provider_id, season)
                elif name == "tmdb":
                    detail = provider.get_tv_season(provider_id, season)
                else:
                    # Future TV providers should be added explicitly here
                    # so the operator notices the integration gap.
                    log.warning("show_episode_provider_unknown", provider=name)
                    return []
                return [(ep.episode_number, _episode_payload(ep, episode_default_name)) for ep in detail.episodes]

            return _fetch

        candidates: list[tuple[str, int, Callable[[int], list[tuple[int, dict[str, Any]]]]]] = []
        for provider in self._registry.chain(EpisodeFetcher):  # type: ignore[type-abstract]
            name = getattr(provider, "provider_name", "")
            provider_id = provider_ids.get(name)
            if provider_id is None:
                # Either the provider has no resolved cross-reference id
                # for this show, or the lock contract neutralized it.
                continue
            candidates.append((name, _rank(name), _make_fetch(provider, provider_id)))
        candidates.sort(key=lambda c: c[1])
        return [(name, fetch) for name, _, fetch in candidates]

    def _fetch_season_with_fallback(
        self,
        season: int,
        providers: list[tuple[str, Callable[[int], list[tuple[int, dict[str, Any]]]]]],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """Iterate providers in priority order, return the first non-empty result.

        A provider is considered "successful" only when it returns at least
        one episode for the requested season. Empty responses and exceptions
        both fall through to the next provider so a stale catalog on the
        primary source does not silently lose downstream data.

        Args:
            season: Season number to fetch.
            providers: Ordered ``(name, fetch)`` list from
                :meth:`_ordered_episode_providers`.

        Returns:
            ``{(season, episode): payload}`` mapping. Empty when all
            providers came back empty or raised.
        """
        for name, fetch in providers:
            try:
                items = fetch(season)
            except Exception as e:  # noqa: BLE001 — provider clients raise a wide variety
                log.warning(
                    "show_season_fetch_failed",
                    provider=name,
                    season=season,
                    exc_info=True,
                    error=str(e),
                )
                continue
            if not items:
                log.warning("show_season_empty", provider=name, season=season)
                continue
            log.info("show_season_fetched", provider=name, season=season, count=len(items))
            return {(season, e_num): payload for e_num, payload in items}
        return {}

    def _match_seasons(
        self,
        video_files: list[Path],
        api_episodes: dict[tuple[int, int], dict[str, Any]],
        show_dir: Path,
        show_data: dict[str, Any],
        episode_default_name: str,
    ) -> int:
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
            Number of episodes renamed (0 if no matches).
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
            return 0
        needed_seasons = sorted({info["season"] for info in matched.values()})
        ep_list = [{"season_number": s, "episode_number": 0} for s in needed_seasons]
        create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
        total = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
        self._generate_episode_nfos(matched, show_dir, show_data)
        return total

    def _generate_episode_nfos(
        self,
        matched: dict[Path, dict[str, Any]],
        show_dir: Path,
        show_data: dict[str, Any],
    ) -> None:
        """Generate NFO files and download episode thumbnails.

        For each matched episode, creates an NFO file with metadata and
        downloads the TMDB still image as a thumbnail file. Episodes with
        existing NFOs only get thumbnail recovery (if missing).

        Args:
            matched: Dict from match_episode_files().
            show_dir: Path to the TV show directory.
            show_data: Full TMDB show details.
        """
        show_title = show_data.get("name", "")
        mpaa = NFOGenerator._extract_content_rating_fr(show_data)
        networks = show_data.get("networks", [])
        studio = networks[0].get("name", "") if networks else ""

        for video_path, info in matched.items():
            season = info["season"]
            episode = info["episode"]
            api_title = info["api_title"]
            still_path = info.get("still_path", "")

            # Fallback entries (no provider record — synthetic "Episode N" title)
            # skip NFO/thumb generation: the file lands as "SxxExx - Episode N.mkv"
            # under its Saison XX/ dir so verify/dispatch don't block, but we refuse
            # to fabricate episode metadata.
            if info.get("fallback"):
                continue

            season_dir_name = self.patterns.format("season_dir", Season=season)
            new_stem = self.patterns.format(
                "episode_video",
                Season=season,
                Episode=episode,
                EpisodeTitle=api_title,
            )
            nfo_path = show_dir / season_dir_name / f"{new_stem}.nfo"
            thumb_name = self.patterns.format(
                "episode_thumb",
                Season=season,
                Episode=episode,
                EpisodeTitle=api_title,
            )
            thumb_path = show_dir / season_dir_name / thumb_name

            if nfo_path.exists():
                # Phase 5.4 : upgrade-in-place. An NFO already on disk
                # may have been written by an earlier scrape that did
                # not yet have the xref IDs available — append the
                # ``<uniqueid type=xref>`` rows now without touching
                # the existing canonical (and never overwriting an
                # already-present xref value).
                self._augment_episode_nfo_with_xref(nfo_path, info)
                # Still download thumbnail if NFO exists but thumb doesn't
                self._download_episode_thumb(still_path, thumb_path, season, episode)
                continue

            # Propagate per-episode provider IDs originated by
            # ``_build_episode_map`` and surfaced via
            # ``match_episode_files`` (DEV #2 root cause). Empty values are
            # mapped to ``""`` so the NFO generator's own
            # "omit on blank" logic keeps producing well-formed XML when
            # an upstream provider had nothing to surface.
            episode_data = {
                "name": api_title,
                "showtitle": show_title,
                "id": info.get("tmdb_episode_id", ""),
                "tvdb_id": info.get("tvdb_episode_id", ""),
                "imdb_id": info.get("imdb_episode_id", ""),
                "season_number": season,
                "episode_number": episode,
                "overview": "",
                "mpaa": mpaa,
                "studio": studio,
                "crew": [],
                "still_path": still_path,
            }

            # Stream info from the renamed video
            renamed_video = show_dir / season_dir_name / f"{new_stem}{video_path.suffix}"
            stream_info = None
            if renamed_video.exists():
                from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

                stream_info = scraper_api.extract_stream_info(renamed_video)

            try:
                xml = self._nfo.generate_episode_nfo(episode_data, stream_info)
                if not self.dry_run:
                    nfo_path.parent.mkdir(parents=True, exist_ok=True)
                    self._nfo.write_nfo(xml, nfo_path)
            except Exception as e:
                log.warning("episode_nfo_failed", season=season, episode=episode, error=str(e), exc_info=True)

            # Download episode thumbnail
            self._download_episode_thumb(still_path, thumb_path, season, episode)
