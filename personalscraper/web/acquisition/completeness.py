"""§5 completeness read-model — aired vs library vs queue, per season/episode.

``compute_completeness`` answers the constitution's series requirement: "montrer
ce qui est déjà sorti vs ce qui est en médiathèque, saison par saison, épisode
par épisode, pour voir ce qui reste à acquérir".

Sources (each fail-soft, never a 500):

* Aired catalog — the detect-written ``aired_episode`` cache first (P0-B.1 —
  zero provider calls), falling back to ONE live
  :func:`~personalscraper.acquire.airing.poll_aired` for a series never cached
  yet (aired episodes only, specials excluded). An empty result surfaces as
  ``provider_catalog_empty=True`` (the Top Chef case: TVDB knows the series but
  lists no episodes) — the UI must say so instead of rendering a misleading
  all-missing matrix. A provider outage degrades to the same honest state.
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

    # P0-B.1 — cache first: the detect-written aired catalog serves the matrix
    # with ZERO provider calls (the old synchronous per-season polling was the
    # « met très longtemps » complaint). A series never cached yet falls back
    # to one live poll.
    entries: list[tuple[int, int, str | None, str]] = []
    source: str = "live"
    refreshed_at: float | None = None
    try:
        cached = list(store.aired.list_for_followed(followed.id))  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — fail-soft: degrade to the live poll
        logger.debug("completeness_cache_error", followed_id=followed.id, error=str(exc))
        cached = []
    if cached:
        entries = [(r.season, r.episode, r.title, r.air_date) for r in cached]
        source = "cache"
        refreshed_at = float(max(r.updated_at for r in cached))
    else:
        try:
            aired = poll_aired([followed], registry, today=date.today())  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 — defensive; poll_aired is fail-soft internally
            logger.warning("completeness_poll_failed", followed_id=followed.id, error=str(exc))
            aired = []
        entries = [(e.season, e.episode, e.title or None, e.air_date.isoformat()) for e in aired]

    if not entries:
        return CompletenessResponse(
            followed_id=followed.id,
            title=followed.title,
            kind=followed.kind,
            provider_catalog_empty=True,
            seasons=[],
        )

    # One row per (season, episode) — a duplicated provider season order must
    # never double an episode in the matrix (B.1).
    unique: dict[tuple[int, int], tuple[int, int, str | None, str]] = {}
    for entry in entries:
        unique.setdefault((entry[0], entry[1]), entry)

    by_season: dict[int, list[EpisodeCompleteness]] = {}
    for season, episode, title, air_date in sorted(unique.values(), key=lambda e: (e[0], e[1])):
        # Ownership check (fail-soft: error → treated as not owned).
        try:
            owned = ownership.owns(  # type: ignore[attr-defined]
                followed.media_ref, kind="episode", season=season, episode=episode
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft per episode
            logger.debug("completeness_ownership_error", error=str(exc))
            owned = False

        wanted_status: str | None = None
        try:
            row = store.wanted.find(  # type: ignore[attr-defined]
                followed_id=followed.id, kind="episode", season=season, episode=episode
            )
            wanted_status = row.status if row is not None else None
        except Exception as exc:  # noqa: BLE001 — fail-soft per episode
            logger.debug("completeness_wanted_error", error=str(exc))

        by_season.setdefault(season, []).append(
            EpisodeCompleteness(
                episode=episode,
                title=title,
                air_date=air_date,
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
        source=source,  # type: ignore[arg-type]
        catalog_refreshed_at=refreshed_at,
    )
