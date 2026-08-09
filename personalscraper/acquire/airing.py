"""Air-date set-poll service for the acquire lobe (RP9).

Exposes two stateless views over ONE provider poll (episode-states D1):

- :func:`poll_known` — every episode with a known air date, future INCLUDED
  (the ``aired_episode`` cache stores these so the matrix can show ``annonce``);
- :func:`poll_aired` — only the episodes that have already aired
  (``air_date <= today``), the enqueue view: a future is not searchable on
  trackers and must never become a ``wanted`` row.

``poll_aired`` filters ``poll_known``'s result — the provider is polled once.

Mirrors :mod:`personalscraper.acquire.title_resolver` in structure:
no ``AcquireContext`` handle, no store/indexer import.

Import direction: ``api/metadata`` + ``api._contracts`` (downward) +
``acquire.domain`` + stdlib ``datetime``.  MediaRef reaches this module only
transitively via ``acquire.domain``; never imports ``core.identity``, store,
or indexer directly.

Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Sequence, cast

from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, SeriesCatalog
from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.metadata._base import EpisodeInfo
from personalscraper.api.metadata._contracts import EpisodeFetcher, TvDetailsProvider
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry

log = get_logger("acquire.airing")


# ---------------------------------------------------------------------------
# Predicate helpers (phase 1)
# ---------------------------------------------------------------------------


def _parse_date(air_date: str) -> date | None:
    """Parse an ISO-8601 date string from a provider response.

    Args:
        air_date: Raw ``EpisodeInfo.air_date`` string (``"YYYY-MM-DD"`` or ``""``).

    Returns:
        A :class:`datetime.date` on success, ``None`` on empty string or any
        parse failure.  Never raises.
    """
    if not air_date:
        return None
    try:
        return datetime.strptime(air_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _is_aired(air_date: str, today: date) -> bool:
    """Return True iff *air_date* is a known past-or-today date.

    Implements the DESIGN §5 predicate:
    ``aired ⇔ air_date != "" AND parse_date(air_date) is not None AND parsed <= today``

    The ``<= today`` comparison is **inclusive**: an episode whose air-date is
    exactly today counts as aired (day-boundary ambiguity is acceptable for
    the calendar-trigger; documented in DESIGN §5).

    Args:
        air_date: Raw ``EpisodeInfo.air_date`` string.
        today: The reference date injected by the caller (no hidden ``date.today()``).

    Returns:
        ``True`` when the episode has aired; ``False`` for TBA / future / malformed.
    """
    parsed = _parse_date(air_date)
    return parsed is not None and parsed <= today


# ---------------------------------------------------------------------------
# Set-poll service (phase 2)
# ---------------------------------------------------------------------------


def poll_known(
    series: Sequence[FollowedSeries],
    registry: "ProviderRegistry",
    *,
    today: date,
) -> list[AiredEpisode]:
    """Return EVERY known-date episode across a set of followed series (episode-states D1).

    Flat view over :func:`poll_catalog` — the same single poll, with the
    per-series envelope dropped. Callers that need the series' production status
    (« Ended » vs « Continuing ») take :func:`poll_catalog` instead; they do NOT
    poll twice.

    Args:
        series: The set of followed series to poll.
        registry: The live ``ProviderRegistry`` from the composition root.
        today: Reference date (injected for determinism).

    Returns:
        Flat list of :class:`~personalscraper.acquire.domain.AiredEpisode`, one
        per known-date episode (aired AND announced) across all series.
    """
    return [ep for catalog in poll_catalog(series, registry, today=today) for ep in catalog.episodes]


def poll_catalog(
    series: Sequence[FollowedSeries],
    registry: "ProviderRegistry",
    *,
    today: date,
) -> list["SeriesCatalog"]:
    """Return one :class:`SeriesCatalog` per successfully polled series.

    The widest view over the single provider poll: the episodes AND the series'
    production status, which the poll already had in hand (it fetches the series
    details to enumerate the seasons) and used to throw away. Surfacing it costs
    ZERO extra provider calls — the same NE-DOIT-PAS-8 discipline that governed
    widening the episode result.

    That status is what lets a card say « Terminé » honestly. The obvious
    alternative — « nothing announced ahead » — is not a statement about the end
    of a series: on 2026-08-09 « House of the Dragon » had no future episode in
    the catalogue while airing that very day.

    Fail-soft per series exactly like the episode poll: a series whose details
    call fails is ABSENT from the result rather than present with a ``None``
    status, so a provider outage never overwrites a known status with ignorance.

    The future episodes are kept (``air_date > today``), which the
    ``aired_episode`` cache needs so the completeness matrix can show them as
    ``annonce``. Only episodes with NO parseable air date (TBA / malformed) are
    dropped — without a date there is nothing to announce and nothing to
    schedule.

    For each series whose ``media_ref.tvdb_id`` is set, fetches the season catalog
    via ``registry.chain(TvDetailsProvider)`` then the episode details per
    non-special season (``season_number >= 1``) via ``registry.chain(EpisodeFetcher)``
    — exactly ONE catalog call + one per-season call per series.

    Provider chain fall-through, fail-soft per series / per season: identical to
    :func:`poll_aired` (they all share this body).

    Args:
        series: The set of followed series to poll (typically
            ``store.follow.list_active()`` — this module never reads the store).
        registry: The live ``ProviderRegistry`` from the composition root.
        today: Reference date (injected for determinism; used only to stamp
            aired-vs-future callers downstream — this function keeps both).

    Returns:
        One :class:`~personalscraper.acquire.domain.SeriesCatalog` per series the
        poll reached. Empty when every provider is unavailable.
    """
    catalogs: list[SeriesCatalog] = []

    for fs in series:
        result: list[AiredEpisode] = []
        media_ref = fs.media_ref
        tvdb_id = media_ref.tvdb_id
        if tvdb_id is None:
            log.debug("acquire.airing.skip_no_tvdb_id", title=fs.title)
            continue

        try:
            tv_providers = cast(
                list[TvDetailsProvider],
                list(registry.chain(TvDetailsProvider)),  # type: ignore[type-abstract]
            )
            if not tv_providers:
                log.debug("acquire.airing.no_tv_provider", tvdb_id=tvdb_id)
                continue

            details = tv_providers[0].get_tv(tvdb_id)
            # Defensive season-number dedup (belt to the parser's order-type
            # dedup): fetching the same number twice doubles every episode
            # downstream AND doubles the per-season provider calls.
            seasons = []
            seen_numbers: set[int] = set()
            for season_info in details.seasons or []:
                if season_info.season_number >= 1 and season_info.season_number not in seen_numbers:
                    seen_numbers.add(season_info.season_number)
                    seasons.append(season_info)

        except (ApiError, CircuitOpenError) as exc:
            log.warning("acquire.airing.poll_failed", tvdb_id=tvdb_id, title=fs.title, error=str(exc))
            continue
        except Exception as exc:  # noqa: BLE001 — fail-soft: one bad series must not block others
            log.warning("acquire.airing.poll_failed", tvdb_id=tvdb_id, title=fs.title, error=str(exc), exc_info=True)
            continue

        seen_pairs: set[tuple[int, int]] = set()
        for season_info in seasons:
            season_num = season_info.season_number
            try:
                episodes = _fetch_season_with_fallback(tvdb_id, season_num, registry)
            except Exception as exc:  # noqa: BLE001 — fail-soft per season
                log.warning(
                    "acquire.airing.poll_failed",
                    tvdb_id=tvdb_id,
                    season=season_num,
                    error=str(exc),
                )
                continue

            for ep in episodes:
                parsed = _parse_date(ep.air_date)
                # Widened predicate (D1): keep every episode with a KNOWN date,
                # future included. The <= today filter now lives in poll_aired,
                # applied to this result — one poll, two views.
                if parsed is not None and (season_num, ep.episode_number) not in seen_pairs:
                    seen_pairs.add((season_num, ep.episode_number))
                    result.append(
                        AiredEpisode(
                            media_ref=media_ref,
                            season=season_num,
                            episode=ep.episode_number,
                            air_date=parsed,
                            title=ep.title,
                        )
                    )

        catalogs.append(
            SeriesCatalog(
                followed_id=fs.id,
                media_ref=media_ref,
                series_status=details.series_status,
                episodes=result,
            )
        )

    return catalogs


def poll_aired(
    series: Sequence[FollowedSeries],
    registry: "ProviderRegistry",
    *,
    today: date,
) -> list[AiredEpisode]:
    """Return only the episodes that have already AIRED (air_date <= today).

    Derived from :func:`poll_known` — the SAME single provider poll — by dropping
    the futures. This is the enqueue view: an unaired episode is not searchable
    on trackers, so it must never reach the ``wanted`` queue. The ``<= today``
    comparison is inclusive (an episode airing exactly today counts as aired).

    Args:
        series: The set of followed series to poll.
        registry: The live ``ProviderRegistry`` from the composition root.
        today: Reference date (injected for determinism/testability).

    Returns:
        Flat list of aired :class:`~personalscraper.acquire.domain.AiredEpisode`,
        one per aired episode. Empty when nothing has aired or all providers are
        unavailable.
    """
    return [ep for ep in poll_known(series, registry, today=today) if ep.air_date <= today]


def _fetch_season_with_fallback(
    tvdb_id: int | str,
    season: int,
    registry: "ProviderRegistry",
) -> list[EpisodeInfo]:
    """Fetch episode list for one season, falling back through the provider chain.

    Tries each ``EpisodeFetcher`` in the chain in order.  A provider is
    considered successful only when it returns a non-empty list — an empty
    response falls through to the next provider (mirrors
    ``scraper.tv_service_episodes.fetch_season_with_fallback``).

    Args:
        tvdb_id: The TVDB series identifier.
        season: Season number to fetch (>= 1; specials excluded upstream).
        registry: The live ``ProviderRegistry``.

    Returns:
        List of :class:`~personalscraper.api.metadata._base.EpisodeInfo` objects,
        or an empty list when no provider returned data.
    """
    fetchers = cast(
        list[EpisodeFetcher],
        list(registry.chain(EpisodeFetcher)),  # type: ignore[type-abstract]
    )
    for fetcher in fetchers:
        try:
            episodes = fetcher.get_episodes(str(tvdb_id), season)
            if episodes:
                return episodes
        except (ApiError, CircuitOpenError) as exc:
            log.warning(
                "acquire.airing.season_provider_error",
                tvdb_id=tvdb_id,
                season=season,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "acquire.airing.season_provider_error",
                tvdb_id=tvdb_id,
                season=season,
                error=str(exc),
                exc_info=True,
            )
    return []


__all__ = ["AiredEpisode", "_is_aired", "_parse_date", "poll_aired", "poll_known"]
