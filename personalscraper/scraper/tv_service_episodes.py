"""Free-function helpers for the TV scrape flow (chain iteration + episode fetch).

Extracted from :mod:`personalscraper.scraper.tv_service` in Phase 18 to bring
the parent module below the 1000 non-blank LOC hard ceiling
(``scripts/check-module-size.py``). The helpers were added in Phase 7.2 of the
registry feature (chain iteration over ``TvDetailsProvider`` / ``EpisodeFetcher``
plus per-season fallback logic) and account for the bulk of the module's
post-7.2 weight.

Behaviour is unchanged: the public mixin methods on
:class:`TvServiceMixin` delegate to these free functions, preserving every
external import path and call signature. The original docstrings are kept
verbatim so the contract documentation stays close to the implementation.

Direct imports from :mod:`personalscraper.scraper.tv_service` continue to
work for symbols that were previously module-level (e.g. ``_episode_payload``)
via re-exports in the parent module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from personalscraper.api.metadata._base import EpisodeInfo
from personalscraper.api.metadata._contracts import EpisodeFetcher, TvDetailsProvider
from personalscraper.logger import get_logger
from personalscraper.scraper._shared import ScrapeResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.registry import ProviderRegistry

log = get_logger("scraper")


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


def match_tvshow_candidates(
    registry: "ProviderRegistry",
    title: str,
    year: int | None,
    local_seasons: set[int],
    result: ScrapeResult,
) -> Any | None:
    """Search the configured TV chain for candidates matching title + year.

    Iterates ``registry.chain(TvDetailsProvider)`` per DESIGN §6.2
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
        registry: Provider registry from which the TV details chain
            is iterated.
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
    from personalscraper.scraper._match import run_chain  # noqa: PLC0415

    item_context: dict[str, Any] = {"title": title, "year": year, "media_type": "tvshow"}

    def _attempt(provider: Any) -> Any | None:
        """Match one TV provider; ``None`` signals an empty result."""
        return scraper_api.match_tvshow_single(provider, title, year, local_seasons=local_seasons)

    return run_chain(registry, TvDetailsProvider, _attempt, item_context=item_context)


def ordered_episode_providers(
    registry: "ProviderRegistry",
    priority: dict[str, int],
    tvdb_id: int | None,
    tmdb_id: int | None,
    episode_default_name: str,
) -> "list[tuple[str, Callable[[int], list[tuple[int, dict[str, Any]]]]]]":
    """Build the per-season fetch list, ordered by ``episode_scraping`` priority.

    Iterates ``registry.chain(EpisodeFetcher)`` to enumerate the
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
        registry: Provider registry to iterate.
        priority: ``config.metadata.priorities.episode_scraping`` mapping
            (empty dict when no config is loaded).
        tvdb_id: Resolved TVDB id (``None`` if unavailable).
        tmdb_id: Resolved TMDB id (``None`` if unavailable).
        episode_default_name: Title prefix for episodes whose provider
            title is empty.

    Returns:
        List of ``(name, fetch)`` pairs, lowest priority number first.
    """

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
    for provider in registry.chain(EpisodeFetcher):  # type: ignore[type-abstract]
        name = getattr(provider, "provider_name", "")
        provider_id = provider_ids.get(name)
        if provider_id is None:
            # Either the provider has no resolved cross-reference id
            # for this show, or the lock contract neutralized it.
            continue
        candidates.append((name, _rank(name), _make_fetch(provider, provider_id)))
    candidates.sort(key=lambda c: c[1])
    return [(name, fetch) for name, _, fetch in candidates]


def fetch_season_with_fallback(
    season: int,
    providers: "list[tuple[str, Callable[[int], list[tuple[int, dict[str, Any]]]]]]",
) -> dict[tuple[int, int], dict[str, Any]]:
    """Iterate providers in priority order, return the first non-empty result.

    A provider is considered "successful" only when it returns at least
    one episode for the requested season. Empty responses and exceptions
    both fall through to the next provider so a stale catalog on the
    primary source does not silently lose downstream data.

    Args:
        season: Season number to fetch.
        providers: Ordered ``(name, fetch)`` list from
            :func:`ordered_episode_providers`.

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


def xref_fetch_tmdb_season(registry: "ProviderRegistry", tmdb_id: int, season: int) -> dict[int, dict[str, str]]:
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
    tmdb_client = registry.get("tmdb")
    detail = tmdb_client.get_tv_season(tmdb_id, season)  # type: ignore[attr-defined]
    return {ep.episode_number: dict(ep.external_ids) for ep in detail.episodes}


def xref_fetch_tvdb_season(registry: "ProviderRegistry", tvdb_id: int, season: int) -> dict[int, dict[str, str]]:
    """Return ``{episode_number: external_ids}`` from a TVDB season fetch.

    Legitimately direct dispatch — see :func:`xref_fetch_tmdb_season`.
    """
    tvdb_client = registry.get("tvdb")
    detail = tvdb_client.get_series_episodes(tvdb_id, season)  # type: ignore[attr-defined]
    return {ep.episode_number: dict(ep.external_ids) for ep in detail.episodes}


__all__ = [
    "_episode_payload",
    "fetch_season_with_fallback",
    "match_tvshow_candidates",
    "ordered_episode_providers",
    "xref_fetch_tmdb_season",
    "xref_fetch_tvdb_season",
]
