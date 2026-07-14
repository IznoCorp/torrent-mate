"""§5 completeness read-model — aired vs library vs queue, per season/episode.

``compute_completeness`` answers the constitution's series requirement: "montrer
ce qui est déjà sorti vs ce qui est en médiathèque, saison par saison, épisode
par épisode, pour voir ce qui reste à acquérir".

Sources (each fail-soft, never a 500):

* Provider catalog — :func:`~personalscraper.acquire.airing.poll_aired` over the
  ONE followed series (aired episodes only, specials excluded). An empty result
  surfaces as ``provider_catalog_empty=True`` (the Top Chef case: TVDB knows the
  series but lists no episodes) — the UI must say so instead of rendering a
  misleading all-missing matrix. A provider outage degrades to the same honest
  state (poll_aired is internally fail-soft).
* Library ownership — :meth:`ownership.owns` per aired episode (indexer
  ``library.db`` by provider id; live files only).
* Wanted queue — the acquire store's NULL-safe ``find`` per episode; a pending
  row reads ``en_file``, a searching/grabbed row ``en_cours``.

Read-only: no table is written, no provider mutation — safe on the read-only
staging web instance apart from the provider HTTP calls.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from personalscraper.acquire.airing import poll_aired
from personalscraper.logger import get_logger
from personalscraper.web.models.acquisition import (
    CompletenessResponse,
    EpisodeCompleteness,
    SeasonCompleteness,
)

if TYPE_CHECKING:
    from personalscraper.acquire.domain import FollowedSeries

logger = get_logger(__name__)


def _episode_state(*, owned: bool, wanted_status: str | None) -> str:
    """Derive one episode's §5 state from its ownership + queue facts.

    Args:
        owned: Whether the library holds a live file for the episode.
        wanted_status: The episode's wanted-row status, or ``None`` when the
            episode is not in the queue.

    Returns:
        ``"en_mediatheque"`` / ``"en_cours"`` / ``"en_file"`` / ``"manquant"``.
    """
    if owned:
        return "en_mediatheque"
    if wanted_status in ("searching", "grabbed"):
        return "en_cours"
    if wanted_status == "pending":
        return "en_file"
    return "manquant"


def compute_completeness(
    followed: FollowedSeries,
    *,
    registry: object,
    ownership: object,
    store: object,
) -> CompletenessResponse:
    """Compute the per-season / per-episode completeness for one follow.

    Args:
        followed: The followed series (or movie — movies return no seasons;
            their lifecycle lives on the card status).
        registry: The provider registry (drives ``poll_aired``).
        ownership: The indexer ownership checker (``owns`` by provider id).
        store: The acquire store (wanted-queue lookups).

    Returns:
        The :class:`CompletenessResponse` — never raises for a data problem
        (each source is fail-soft); an empty/unavailable provider catalog is an
        explicit honest state.
    """
    if followed.kind == "movie" or followed.id is None:
        return CompletenessResponse(
            followed_id=followed.id or 0,
            title=followed.title,
            kind=followed.kind,
            provider_catalog_empty=False,
            seasons=[],
        )

    try:
        aired = poll_aired([followed], registry, today=date.today())  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 — defensive; poll_aired is fail-soft internally
        logger.warning("completeness_poll_failed", followed_id=followed.id, error=str(exc))
        aired = []

    if not aired:
        return CompletenessResponse(
            followed_id=followed.id,
            title=followed.title,
            kind=followed.kind,
            provider_catalog_empty=True,
            seasons=[],
        )

    by_season: dict[int, list[EpisodeCompleteness]] = {}
    for ep in sorted(aired, key=lambda e: (e.season, e.episode)):
        # Ownership check (fail-soft: error → treated as not owned).
        try:
            owned = ownership.owns(  # type: ignore[attr-defined]
                followed.media_ref, kind="episode", season=ep.season, episode=ep.episode
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft per episode
            logger.debug("completeness_ownership_error", error=str(exc))
            owned = False

        wanted_status: str | None = None
        try:
            row = store.wanted.find(  # type: ignore[attr-defined]
                followed_id=followed.id, kind="episode", season=ep.season, episode=ep.episode
            )
            wanted_status = row.status if row is not None else None
        except Exception as exc:  # noqa: BLE001 — fail-soft per episode
            logger.debug("completeness_wanted_error", error=str(exc))

        by_season.setdefault(ep.season, []).append(
            EpisodeCompleteness(
                episode=ep.episode,
                title=ep.title or None,
                air_date=ep.air_date.isoformat(),
                state=_episode_state(owned=owned, wanted_status=wanted_status),  # type: ignore[arg-type]
            )
        )

    seasons = [
        SeasonCompleteness(
            season=season,
            owned=sum(1 for e in eps if e.state == "en_mediatheque"),
            queued=sum(1 for e in eps if e.state in ("en_file", "en_cours")),
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
    )
