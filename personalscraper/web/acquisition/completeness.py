"""§5 completeness read-model — aired vs library vs queue, per season/episode.

``compute_completeness`` answers the constitution's series requirement: "montrer
ce qui est déjà sorti vs ce qui est en médiathèque, saison par saison, épisode
par épisode, pour voir ce qui reste à acquérir".

**One derivation, two surfaces** (acq-states phase 5). The card and this panel
read the SAME facts through the SAME
:func:`~personalscraper.web.acquisition.states.derive_episode_state`. There is
no local re-derivation here and no second catalog source — the two surfaces can
no longer answer differently about the same episode at the same instant, which
is exactly what happened on 2026-07-27 (the card said « À jour » from raw wanted
counters while this panel would have listed three episodes as missing from a
LIVE provider poll).

Sources (each fail-soft, never a 500):

* Aired catalog — the detect-written ``aired_episode`` cache, and ONLY that
  cache. No provider is ever polled from this read path (NE-DOIT-PAS-8: pas de
  rafale providers). An absent cache is honest ignorance: empty seasons and
  ``source="unknown"``, matching the card's ``unverified`` — both say « we
  don't know yet ». Phase 6 makes that state short-lived by priming the catalog
  at follow creation.
* Library ownership — :meth:`ownership.owns` per aired episode (indexer
  ``library.db`` by provider id; live files only).
* Wanted queue — ONE bulk read of the follow's rows, from which
  :func:`~personalscraper.web.acquisition.states.select_wanted_facts` picks the
  governing row exactly as the card does (open rows only, latest wins). Its
  status AND its last search verdict (``last_search_outcome`` /
  ``last_search_found``) are read, because « panne ≠ absence ».

Read-only: no table is written, no provider call, no network — safe on the
read-only staging web instance.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.web.acquisition.states import (
    NO_WANTED_FACTS,
    WantedFacts,
    derive_episode_state,
    governing_facts_by_episode,
)
from personalscraper.web.models.acquisition import (
    CompletenessResponse,
    EpisodeCompleteness,
    SeasonCompleteness,
)

if TYPE_CHECKING:
    from personalscraper.acquire.domain import AiredEpisodeRow, FollowedSeries

logger = get_logger(__name__)

#: One ``wanted`` row reduced to what the selector needs:
#: ``(id, status, last_search_outcome, last_search_found)``.
_WantedRow = tuple[int, str | None, str | None, int | None]


def _governing_facts(store: object, followed_id: int) -> dict[tuple[int, int], WantedFacts]:
    """Read this follow's queue once and hand it to the single governing-facts seam.

    TWO queries for the whole follow (episodes + seasons) rather than a lookup per
    episode, and the closed rows come back too: deciding WHICH row speaks is
    :func:`~personalscraper.web.acquisition.states.governing_facts_by_episode`'s
    job, never a WHERE clause this module would own alone. The season rows are
    loaded because an absorbed episode's acquisition is carried by its season row —
    this module reads, it does not re-derive.

    Args:
        store: The acquire store.
        followed_id: The ``followed_series`` row id.

    Returns:
        ``(season, episode)`` → its governing facts. Empty on a read error — an
        unreadable queue reads as « never searched », never as « rien à prendre ».
    """
    try:
        rows = store.wanted.list_for_followed(followed_id, kind="episode")  # type: ignore[attr-defined]
        season_rows = store.wanted.list_for_followed(followed_id, kind="season")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — fail-soft: no queue knowledge, not a 500
        logger.debug("completeness_wanted_error", followed_id=followed_id, error=str(exc))
        return {}
    return governing_facts_by_episode(
        [
            (r.id or 0, r.season, r.episode, r.status, r.last_search_outcome, r.last_search_found, r.absorbed_by)
            for r in rows
            if r.season is not None and r.episode is not None
        ],
        [(r.id or 0, r.status, r.last_search_outcome, r.last_search_found) for r in season_rows],
    )


def _parse_iso(value: str | None) -> date | None:
    """Parse an ISO ``YYYY-MM-DD`` air-date string, tolerating garbage/None.

    Args:
        value: The cached ``air_date`` string, or ``None``.

    Returns:
        The parsed :class:`datetime.date`, or ``None`` when absent or malformed —
        a missing date simply disables the ``annonce`` distinction for that row
        (it derives through the five aired states, unchanged).
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def compute_completeness(
    followed: FollowedSeries,
    *,
    ownership: object,
    store: object,
    today: date | None = None,
) -> CompletenessResponse:
    """Compute the per-season / per-episode completeness for one follow.

    Every episode's state comes from
    :func:`~personalscraper.web.acquisition.states.derive_episode_state` — the
    single derivation the followed cards read too — fed with persisted facts
    only: library ownership × the episode's ``wanted`` row × that row's last
    search verdict.

    Args:
        followed: The followed series (or movie — movies return no seasons;
            their lifecycle lives on the card status).
        ownership: The indexer ownership checker (``owns`` by provider id).
        store: The acquire store (aired-catalog cache + wanted-queue lookups).
        today: Reference date for the aired-vs-future split (episode-states D2).
            Defaults to ``date.today()``; injected in tests for determinism. A
            cached episode whose ``air_date`` is after ``today`` reads
            ``annonce`` and is counted in ``announced``, never in the aired
            tallies.

    Returns:
        The :class:`CompletenessResponse` — never raises for a data problem
        (each source is fail-soft). A follow with no cached catalog returns
        empty seasons with ``source="unknown"``: honest ignorance rather than a
        fabricated all-missing matrix.
    """
    ref_today = today if today is not None else date.today()
    if followed.kind == "movie" or followed.id is None:
        return CompletenessResponse(
            followed_id=followed.id or 0,
            title=followed.title,
            kind=followed.kind,
            provider_catalog_empty=False,
            seasons=[],
            source="unknown",
        )

    # The detect-written cache is the ONLY catalog source. The old live
    # provider-poll fallback is gone (acq-states phase 5): it polled an airing
    # provider from a web READ and, worse, produced a matrix that contradicted
    # the card reading the very same empty cache.
    cached: list[AiredEpisodeRow]
    try:
        cached = list(store.aired.list_for_followed(followed.id))  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — fail-soft: a broken cache read is ignorance, not a 500
        logger.warning("completeness_cache_error", followed_id=followed.id, error=str(exc))
        cached = []

    if not cached:
        # No catalog ⇒ no knowledge. NOT ``provider_catalog_empty``: that flag
        # claims « the provider knows the series and lists no episode » (the Top
        # Chef case), a DETECT-confirmed fact this read path cannot establish.
        return CompletenessResponse(
            followed_id=followed.id,
            title=followed.title,
            kind=followed.kind,
            provider_catalog_empty=False,
            seasons=[],
            source="unknown",
        )

    # One row per (season, episode) — a duplicated cache row must never double
    # an episode in the matrix (B.1).
    unique: dict[tuple[int, int], AiredEpisodeRow] = {}
    for row in cached:
        unique.setdefault((row.season, row.episode), row)
    refreshed_at = float(max(r.updated_at for r in cached))

    facts_by_episode = _governing_facts(store, followed.id)

    by_season: dict[int, list[EpisodeCompleteness]] = {}
    for (season, episode), row in sorted(unique.items()):
        # Ownership check (fail-soft: error → treated as not owned).
        try:
            owned = ownership.owns(  # type: ignore[attr-defined]
                followed.media_ref, kind="episode", season=season, episode=episode
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft per episode
            logger.debug("completeness_ownership_error", error=str(exc))
            owned = False

        # Which row governs is decided by the SHARED selector, so this panel and
        # the card read the same row for the same episode (open rows only,
        # latest wins). An episode with only a closed row therefore reads
        # « never searched », not that row's stale verdict.
        wanted_status, last_search_outcome, last_search_found = facts_by_episode.get((season, episode), NO_WANTED_FACTS)

        by_season.setdefault(season, []).append(
            EpisodeCompleteness(
                episode=episode,
                title=row.title,
                air_date=row.air_date,
                state=derive_episode_state(
                    owned=owned,
                    wanted_status=wanted_status,
                    last_search_outcome=last_search_outcome,
                    last_search_found=last_search_found,
                    # episode-states D2: a future cached episode reads ``annonce``.
                    air_date=_parse_iso(row.air_date),
                    today=ref_today,
                ),
                # The SAME verdict the state was derived from — exposed (never
                # re-read from another row) so the UI can explain the wait in
                # French. The two can therefore never contradict each other.
                last_search_outcome=last_search_outcome,
            )
        )

    seasons = [
        SeasonCompleteness(
            season=season,
            owned=sum(1 for e in eps if e.state == "in_library"),
            # « queued » counts what is IN MOTION. ``absorbed`` belongs here
            # (season-grab R5): the episode's acquisition is carried by the
            # season wanted that absorbed it, so the header stays honest about
            # a season being grabbed.
            queued=sum(1 for e in eps if e.state in ("to_grab", "acquiring", "absorbed")),
            # ``total`` counts AIRED episodes only — the announced futures are
            # tallied separately (episode-states D2) so they never inflate the
            # season's completeness denominator.
            total=sum(1 for e in eps if e.state != "announced"),
            announced=sum(1 for e in eps if e.state == "announced"),
            episodes=eps,
        )
        # Newest season first — the operator's eye goes to the current season.
        for season, eps in sorted(by_season.items(), reverse=True)
    ]
    return CompletenessResponse(
        followed_id=followed.id,
        title=followed.title,
        kind=followed.kind,
        provider_catalog_empty=False,
        seasons=seasons,
        source="cache",
        catalog_refreshed_at=refreshed_at,
    )
