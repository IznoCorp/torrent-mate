"""Air-date set-poll service for the acquire lobe (RP9).

Exposes :func:`poll_aired` — a stateless function that, given a set of
followed TV series and a metadata ``ProviderRegistry``, returns the list of
episodes that have already aired (air-date <= today).

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

from personalscraper.acquire.domain import AiredEpisode, FollowedSeries
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


def poll_aired(
    series: Sequence[FollowedSeries],
    registry: "ProviderRegistry",
    *,
    today: date,
) -> list[AiredEpisode]:
    """Return the list of episodes that have already aired across a set of followed series.

    For each series whose ``media_ref.tvdb_id`` is set, fetches the season catalog
    via ``registry.chain(TvDetailsProvider)`` then fetches episode details per
    non-special season (``season_number >= 1``) via ``registry.chain(EpisodeFetcher)``.
    Episodes are filtered to those whose ``air_date`` is a known past-or-today date
    (DESIGN §5 predicate).

    Provider chain fall-through: if the primary provider returns an empty list for a
    season, the next provider in the chain is tried (mirrors
    ``scraper.tv_service_episodes.fetch_season_with_fallback``).

    Fail-soft: any ``ApiError``, ``CircuitOpenError``, or unexpected ``Exception``
    per series or per season is logged at warning level and skipped — the remaining
    series/seasons are still polled.

    Args:
        series: The set of followed series to poll.  Typically the result of
            ``store.follow.list_active()`` — RP9 does not read the store itself.
        registry: The live ``ProviderRegistry`` from the composition root.
        today: Reference date (injected for determinism/testability — no hidden
            ``date.today()`` call).

    Returns:
        Flat list of :class:`~personalscraper.acquire.domain.AiredEpisode` objects,
        one per aired episode found across all series.  Empty when no episodes have
        aired or all providers are unavailable.
    """
    result: list[AiredEpisode] = []

    for fs in series:
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
            seasons = [s for s in (details.seasons or []) if s.season_number >= 1]

        except (ApiError, CircuitOpenError) as exc:
            log.warning("acquire.airing.poll_failed", tvdb_id=tvdb_id, title=fs.title, error=str(exc))
            continue
        except Exception as exc:  # noqa: BLE001 — fail-soft: one bad series must not block others
            log.warning("acquire.airing.poll_failed", tvdb_id=tvdb_id, title=fs.title, error=str(exc), exc_info=True)
            continue

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
                if parsed is not None and parsed <= today:
                    result.append(
                        AiredEpisode(
                            media_ref=media_ref,
                            season=season_num,
                            episode=ep.episode_number,
                            air_date=parsed,
                            title=ep.title,
                        )
                    )

    return result


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


__all__ = ["AiredEpisode", "_is_aired", "_parse_date", "poll_aired"]
