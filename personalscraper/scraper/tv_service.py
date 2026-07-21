"""TV show scraper service."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from personalscraper.api.metadata._base import Notations
from personalscraper.api.metadata._contracts import TvDetailsProvider
from personalscraper.api.metadata._tvdb_parsers import map_language
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_sample_path
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper._drift_persistence import DriftIssueStore
from personalscraper.scraper._match import run_chain
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper._tvdb_convert import (
    _tvdb_series_to_show_data as _tvdb_series_to_show_data,
)
from personalscraper.scraper._tvdb_convert import (
    fetch_show_data,
)
from personalscraper.scraper._writeback import recover_artwork
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.episode_manager import (
    _file_season,
    create_season_dirs,
    match_episode_files,
    rename_episodes,
)
from personalscraper.scraper.existing_validator import _infer_year_from_child_names, _local_show_seasons
from personalscraper.scraper.nfo_generator import NFOGenerator
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

# Season/episode token pattern used to strip the trailing season/episode
# suffix from a cleaned episode title so only the show name remains.
# ``NameCleaner.clean`` appends the token at the END of the string —
# ``"{title} S{NN}"`` for a season pack or ``"{title} S{NN}E{MM}"`` for a
# single episode. The pattern is therefore END-ANCHORED with the episode
# marker OPTIONAL (so season-only packs strip correctly) and NO trailing
# ``.*`` (so a title-internal S-digit such as "S4C Documentary" — which is
# not at the end — survives).
_SEASON_TOKEN_RE = re.compile(r"\s*-?\s*S\d+(?:E\d+)?\s*$", re.IGNORECASE)

# Lowercased names of subdirectory types that contain bonus/extra content
# and must NEVER be used for title recovery, even as a fallback.
# Note: bare "specials" is intentionally absent — it is a legitimate Plex
# season-0 directory and should not be excluded.
_EXTRAS_DIR_NAMES: frozenset[str] = frozenset(
    {
        "extras",
        "featurettes",
        "featurette",
        "bonus",
        "bonuses",
        "behind the scenes",
        "deleted scenes",
        "deleted",
        "interviews",
        "making of",
        "trailers",
        "supplements",
    }
)


def _is_extras_location(path: Path, show_dir: Path) -> bool:
    """Return True if any ancestor dir between show_dir and path is an extras dir.

    Walks the chain of parent directories strictly between ``show_dir`` (exclusive)
    and the file itself (exclusive). If any intermediate directory name, lowercased
    and stripped, matches a name in ``_EXTRAS_DIR_NAMES``, the file is considered
    bonus content and must be excluded from title recovery.

    Args:
        path: Path to the candidate video file.
        show_dir: Root directory of the TV show staging folder.

    Returns:
        True when the file lives under a known extras subdirectory, False otherwise.
    """
    # Iterate ancestors from the file's immediate parent up to (but not including)
    # show_dir itself to find any intervening extras-type directory.
    current = path.parent
    while current != show_dir and current != current.parent:
        if current.name.lower().strip() in _EXTRAS_DIR_NAMES:
            return True
        current = current.parent
    return False


def _recover_title_from_episodes(show_dir: Path) -> str | None:
    """Recover the show title from episode filenames when the folder name is degenerate.

    When a staging folder is named with only a season token (e.g. `` S03``),
    ``_parse_folder_name`` returns that token as the title. This function
    inspects the episode files inside ``show_dir``, picks the first video
    file, runs ``NameCleaner.clean()`` on its stem, and strips the trailing
    season/episode token so only the show title remains.

    Two-tier candidate selection:

    1. **Restricted set** (PRIMARY): videos at the show root or in a
       ``SEASON_DIR_RE``-matching directory (``Saison NN``, ``Season NN``,
       ``Specials``), minus sample files. This is the cycle-2 behaviour and
       guarantees that an ``Extras/`` sibling never beats a proper season dir.

    2. **Fallback set**: when the restricted set is empty (e.g. all episodes
       are in exotic season dirs such as ``"Saison 3 - VOSTFR"``, ``"Staffel 3"``,
       ``"S03"``, ``"Disc 1"``), the fallback is all video files minus samples
       minus any file under an extras-type directory (``_EXTRAS_DIR_NAMES``).

    Args:
        show_dir: Path to the TV show staging directory.

    Returns:
        Recovered show title string, or None if no video files are found or
        the recovery produces an empty / token-only string.
    """

    def _is_episode_location(path: Path) -> bool:
        """True for show-root or SEASON_DIR_RE-matching parent (strict set)."""
        return path.parent == show_dir or bool(SEASON_DIR_RE.match(path.parent.name))

    def _all_videos() -> list[Path]:
        """All video files under show_dir, excluding samples."""
        return [
            f
            for f in show_dir.rglob("*")
            if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not is_sample_path(f)
        ]

    # PRIMARY — restricted to root + canonical season dirs (cycle-2 behaviour).
    # Videos under Extras/ and similar non-season dirs are implicitly excluded
    # because neither their parent == show_dir nor do they match SEASON_DIR_RE.
    restricted = sorted(f for f in _all_videos() if _is_episode_location(f))

    if restricted:
        video_files = restricted
    else:
        # FALLBACK — all videos minus extras-type locations.
        # Handles exotic season dirs (VOSTFR, Staffel, S03, Disc NN, …) that do
        # not match SEASON_DIR_RE but are not bonus content either.
        video_files = sorted(f for f in _all_videos() if not _is_extras_location(f, show_dir))

    if not video_files:
        return None

    first = video_files[0]
    try:
        from guessit.api import GuessitException  # noqa: PLC0415

        from personalscraper.sorter.cleaner import NameCleaner  # noqa: PLC0415

        cleaner = NameCleaner()
        raw_title = cleaner.clean(first.stem)
    except (
        ValueError,
        AttributeError,
        TypeError,
        GuessitException,
    ):  # pragma: no cover — guard against unexpected guessit failures
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
    _repair_tvshow_dir: "Callable[..., bool]"
    _generate_episode_nfos: "Callable[..., list[str]]"  # from TvServiceNfoMixin (Phase 27.2 extraction)
    _write_confirmed_show: "Callable[..., ScrapeResult]"  # from TvServiceWriteMixin

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
                        recover_artwork(
                            nfo_path,
                            show_dir,
                            result,
                            kind="tvshow",
                            registry=self._registry,
                            artwork=self._artwork,
                            patterns=self.patterns,
                        )
                # Repair pass: remove residual NFOs, root MKV duplicates, etc.
                repaired = self._repair_tvshow_dir(show_dir)
                if repaired and result.action != "artwork_recovered":
                    result.action = "repaired"
                elif result.action != "artwork_recovered":
                    result.action = "skipped_already_done"
                log.info("nfo_valid", action=result.action, directory=show_dir.name)
                return result

        # Corrupt/drifted NFO: do NOT delete it up front (mirrors the movie
        # branch, webui-overhaul #3). A confident re-scrape overwrites it
        # atomically below; a non-confident lookup returns early WITHOUT writing
        # a fresh NFO, so unlinking here would leave the show folder with no NFO
        # at all while a decision waits. Keeping the drifted NFO means the item
        # is never worse off than before the re-scrape.
        if nfo_path.exists() and not _is_nfo_complete(nfo_path):
            log.warning("nfo_drift_detected", filename=nfo_path.name)

        # Collect seasons present in the folder's video files — feeds
        # content-aware candidate disambiguation in match_tvshow_tvdb.
        local_seasons = _local_show_seasons(show_dir)

        # Match against TVDB/TMDB and fetch show details
        lookup = self._lookup_series(title, year, local_seasons, result)
        if lookup is None:
            return result
        match, show_data, tmdb_id, resolved_title = lookup
        return self._write_confirmed_show(
            show_dir,
            match,
            show_data,
            tmdb_id,
            resolved_title,
            title,
            year,
            result,
            drift_rescrape_episode_nfo=drift_rescrape_episode_nfo,
        )

    def _lookup_series(
        self,
        title: str,
        year: int | None,
        local_seasons: set[int],
        result: ScrapeResult,
    ) -> tuple[Any, dict[str, Any], int | None, str] | None:
        """Match a TV show against the TV chain and fetch full series details.

        Two-step lookup, both driven by
        :func:`personalscraper.scraper._match.run_chain` over
        ``registry.chain(TvDetailsProvider)`` (SCRAPER-02):

        1. **Match** — iterate the chain, matching each provider via
           :func:`~personalscraper.scraper.tv_service_episodes.match_tvshow_single_detailed`
           for the best :class:`MatchResult` + scored candidate list. TVDB is
           tried before TMDB by default configuration and run_chain's
           first-usable-result-wins semantics guarantee TVDB is never overridden
           by TMDB (the strict TV rule). A TVDB failure (circuit/network/other)
           or an empty TVDB result emits :class:`ProviderFallbackTriggered`
           before TMDB is consulted — the same fallback observability movies
           have; full exhaustion emits :class:`ProviderExhaustedEvent` and
           surfaces a fail-soft ``result.error`` (ACC-13).
        2. **Details** — once a match is accepted (confidence ≥
           ``LOW_CONFIDENCE``) the details fetch iterates the same chain again
           but filters to ``provider_name == match.source`` to honour the
           source-of-match invariant — cross-provider id translation
           (TVDB ↔ TMDB) is owned by ``registry.cross_ref``.

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
        # Scrape-arbiter DESIGN §4: call the detailed per-provider matcher to
        # get both the best match and the scored candidate list for the
        # three-tier trigger logic. run_chain owns the TVDB-first order (via
        # the registry chain), the fallback event emission, and the
        # ProviderExhausted raise on full failure (surfaced as a fail-soft
        # ``result.error`` — ACC-13).
        from personalscraper.scraper.tv_service_episodes import match_tvshow_single_detailed  # noqa: PLC0415

        item_context: dict[str, Any] = {"title": title, "year": year, "media_type": "tvshow"}

        def _attempt_match(provider: Any) -> tuple[Any, list[Any]] | None:
            """Match one TV provider; ``None`` signals an empty result."""
            best, cands = match_tvshow_single_detailed(provider, title, year, local_seasons=local_seasons)
            if best is None:
                return None
            return best, cands

        try:
            matched = run_chain(self._registry, TvDetailsProvider, _attempt_match, item_context=item_context)
        except ProviderExhausted as exc:
            # Every eligible provider errored — run_chain already emitted
            # ProviderExhaustedEvent. Preserve the legacy fail-soft shape: the
            # last underlying exception detail carries into ``result.error``.
            detail = exc.last_exception if exc.last_exception is not None else exc
            result.error = f"Match failed: {detail}"
            result.action = "error"
            return None

        match: Any
        candidates: list[Any]
        if matched is None:
            # Empty chain / every provider returned an empty result → legacy
            # "no confident match" path. ``classify_decision_trigger`` maps the
            # (None, []) pair to ``below_threshold``.
            match, candidates = None, []
        else:
            match, candidates = matched

        # Three-tier trigger logic delegates to the shared decision_triage
        # module (scrape-arbiter DESIGN §4). Only the log event names are
        # TV-specific.
        from personalscraper.scraper.decision_triage import (  # noqa: PLC0415
            apply_decision_to_result,
            classify_decision_trigger,
        )

        trigger = classify_decision_trigger(match, candidates)
        if trigger is not None:
            apply_decision_to_result(result, match, candidates, trigger)
            if trigger == "below_threshold":
                log.warning(
                    "show_no_confident_match",
                    title=title,
                    year=year,
                    score=round(match.confidence if match else 0.0, 2),
                )
                return None
            assert match is not None  # narrowed by classify_decision_trigger
            extra: dict[str, Any] = {}
            if trigger == "ambiguous" and candidates:
                extra["runner_up_score"] = round(candidates[1].score, 2)
            log.info(
                "show_queued_for_decision",
                title=title,
                api_title=match.api_title,
                source=match.source,
                confidence=round(match.confidence, 2),
                trigger=trigger,
                **extra,
            )
            return None

        # Clean >= HIGH_CONFIDENCE — proceed with full scrape path.
        assert match is not None  # narrowed by classify_decision_trigger
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

        def _fetch_details(provider: Any) -> tuple[dict[str, Any] | None, int | None]:
            """Fetch full show data from the source-of-match provider.

            The TVDB-primary / TMDB-fallback branch lives once in
            ``fetch_show_data``, shared with the maintenance rescraper so the
            discipline cannot diverge.
            """
            return fetch_show_data(
                match.source,
                match.api_id,
                provider,
                preferred_language=self._scraper_language,
                fallback_language=self._scraper_fallback_language,
            )

        def _is_source(provider: Any) -> bool:
            # Honour the source-of-match invariant: only consult the provider
            # that produced the MatchResult. Cross-provider translation is owned
            # by ``registry.cross_ref``.
            return bool(getattr(provider, "provider_name", "?") == match.source)

        try:
            fetched = run_chain(
                self._registry,
                TvDetailsProvider,
                _fetch_details,
                item_context=details_item_context,
                source_filter=_is_source,
            )
        except ProviderExhausted:
            # Every source-matching provider errored — run_chain already emitted
            # ProviderExhaustedEvent + logged ``registry_chain_exhausted``.
            result.error = f"Get details failed: all providers exhausted for {TvDetailsProvider.__name__}"
            return None

        show_data: dict[str, Any] | None = fetched[0] if fetched is not None else None
        tmdb_id: int | None = fetched[1] if fetched is not None else None
        if show_data is None:
            # No provider matched ``match.source`` (all filtered out), or the
            # source provider returned no show data.
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
        # Season-pack bootstrap: a whole-season single file (e.g. Integrale.S01)
        # carries a season token but no episode, so neither discovery above sees
        # it. When season-pack handling is enabled, discover seasons from the
        # season-only token so the provider episode map — gate 4 of
        # ``_try_season_pack_match`` — can actually be built for this show.
        if not season_nums and self.config is not None and self.config.metadata.season_pack_policy.enabled:
            season_nums = sorted(
                {
                    s
                    for f in show_dir.rglob("*")
                    if f.is_file()
                    and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
                    and not is_sample_path(f)
                    and (s := _file_season(f.name)) is not None
                    and s > 0
                }
            )
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
        # Season-pack markers (whole-season single-file handling). ``None``
        # disables the path entirely (byte-identical pre-existing behavior).
        season_pack_markers: list[str] | None = None
        if self.config is not None and self.config.metadata.season_pack_policy.enabled:
            season_pack_markers = self.config.metadata.season_pack_policy.markers
        matched = match_episode_files(
            video_files,
            api_episodes,
            episode_default_name=episode_default_name,
            allow_synthetic_rename=allow_synthetic_rename,
            season_pack_markers=season_pack_markers,
        )
        if not matched:
            return 0, []
        needed_seasons = sorted({info["season"] for info in matched.values()})
        ep_list = [{"season_number": s, "episode_number": 0} for s in needed_seasons]
        create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
        total = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
        nfo_warnings = self._generate_episode_nfos(matched, show_dir, show_data)
        return total, nfo_warnings
