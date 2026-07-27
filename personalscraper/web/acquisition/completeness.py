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
  ``source="unknown"``, matching the card's ``non_verifie`` — both say « we
  don't know yet ». Phase 6 makes that state short-lived by priming the catalog
  at follow creation.
* Library ownership — :meth:`ownership.owns` per aired episode (indexer
  ``library.db`` by provider id; live files only).
* Wanted queue — the acquire store's NULL-safe ``find`` per episode, read for
  its status AND its last search verdict (``last_search_outcome`` /
  ``last_search_found``), because « panne ≠ absence ».

Read-only: no table is written, no provider call, no network — safe on the
read-only staging web instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.web.acquisition.states import derive_episode_state
from personalscraper.web.models.acquisition import (
    CompletenessResponse,
    EpisodeCompleteness,
    SeasonCompleteness,
)

if TYPE_CHECKING:
    from personalscraper.acquire.domain import AiredEpisodeRow, FollowedSeries

logger = get_logger(__name__)


def compute_completeness(
    followed: FollowedSeries,
    *,
    ownership: object,
    store: object,
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

    Returns:
        The :class:`CompletenessResponse` — never raises for a data problem
        (each source is fail-soft). A follow with no cached catalog returns
        empty seasons with ``source="unknown"``: honest ignorance rather than a
        fabricated all-missing matrix.
    """
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

        # The wanted row carries the three queue facts the derivation needs; an
        # unreadable row degrades to « never searched », never to « rien à
        # prendre ».
        wanted_status: str | None = None
        last_search_outcome: str | None = None
        last_search_found: int | None = None
        try:
            wanted_row = store.wanted.find(  # type: ignore[attr-defined]
                followed_id=followed.id, kind="episode", season=season, episode=episode
            )
            if wanted_row is not None:
                wanted_status = wanted_row.status
                last_search_outcome = wanted_row.last_search_outcome
                last_search_found = wanted_row.last_search_found
        except Exception as exc:  # noqa: BLE001 — fail-soft per episode
            logger.debug("completeness_wanted_error", error=str(exc))

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
                ),
            )
        )

    seasons = [
        SeasonCompleteness(
            season=season,
            owned=sum(1 for e in eps if e.state == "en_mediatheque"),
            queued=sum(1 for e in eps if e.state in ("a_recuperer", "en_acquisition")),
            total=len(eps),
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
