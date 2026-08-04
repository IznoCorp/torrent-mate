"""Season-scoped acquisition routes — the manual whole-season grab (R4 / R5).

Split out of :mod:`personalscraper.web.routes.acquisition` when that module reached the
1000-non-blank-LOC ceiling. This is a PURE extraction: the path, status codes, response
model and per-route dependencies are unchanged, and the auth perimeter stays the single
``guarded_api`` dependency mounted in :mod:`personalscraper.web.app` (web-ui.md §6) — no
per-route ``require_session`` is added here.

Writes use ``build_acquire_store`` to create a fresh ConcreteAcquireStore per request; the
mutating route carries ``require_not_staging`` (staging → 403) and
``require_x_requested_with`` (CSRF → 400) as per-route dependencies.
"""

from __future__ import annotations

import sqlite3
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES
from personalscraper.acquire.store import build_acquire_store
from personalscraper.logger import get_logger
from personalscraper.web.deps import require_not_staging, require_x_requested_with
from personalscraper.web.models.acquisition import SeasonGrabResponse
from personalscraper.web.routes.acquisition_triggers import enqueue_prime_run

if TYPE_CHECKING:
    from personalscraper.acquire.store import ConcreteAcquireStore

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])
logger = get_logger(__name__)


def _count_absorbed_for_season(
    store: "ConcreteAcquireStore",
    followed_id: int,
    season: int,
) -> int:
    """Count episode rows already absorbed for a season by a season wanted.

    Args:
        store: An open acquire store.
        followed_id: FK to ``followed_series``.
        season: Season number (1-based).

    Returns:
        Number of episode rows with ``status='absorbed'`` for the follow+season.
    """
    store.wanted._conn.row_factory = sqlite3.Row
    row = store.wanted._conn.execute(
        "SELECT COUNT(*) AS cnt FROM wanted "
        "WHERE followed_id IS ? AND kind = 'episode' "
        "AND season = ? AND status = 'absorbed'",
        (followed_id, season),
    ).fetchone()
    return int(row["cnt"]) if row else 0


def _absorb_live_episodes_for_season(
    store: "ConcreteAcquireStore",
    followed_id: int,
    season: int,
    season_wanted_id: int,
) -> list[int]:
    """Absorb all live episode wanted rows for a season (R5).

    Args:
        store: An open acquire store.
        followed_id: FK to ``followed_series``.
        season: Season number (1-based).
        season_wanted_id: Rowid of the season wanted to absorb into.

    Returns:
        The list of episode rowids that were absorbed.
    """
    store.wanted._conn.row_factory = sqlite3.Row
    rows = store.wanted._conn.execute(
        "SELECT id FROM wanted "
        "WHERE followed_id IS ? AND kind = 'episode' "
        "AND season = ? AND status IN ('pending', 'searching', 'available')",
        (followed_id, season),
    ).fetchall()
    episode_ids = tuple(int(r["id"]) for r in rows)
    if episode_ids:
        store.wanted.absorb_episodes(season_wanted_id, episode_ids)
    return list(episode_ids)


@router.post(
    "/follows/{followed_id}/seasons/{season}/grab",
    status_code=201,
    response_model=SeasonGrabResponse,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def grab_season(
    request: Request,
    response: Response,
    followed_id: int,
    season: int,
) -> SeasonGrabResponse:
    """Manually enqueue a season wanted for a followed series (R4).

    Creates a ``WantedItem(kind='season', season=N, episode=None)`` and
    absorbs every live episode wanted for that season (R5). Idempotent on the
    LIVE row only: an existing OPEN season row is reused (HTTP 200,
    ``reused=True``); a terminal row (``fallback_episodes`` / ``done`` /
    ``abandoned``) is history and never blocks a fresh grab — this endpoint is
    the manual escape hatch after an R6 fallback, so it must be able to
    re-enqueue the season (201, new row).

    A FRESH grab also starts the acquisition pass for that follow (D3), exactly as
    ``create_follow`` does — the operator's action must produce an observable run
    rather than waiting up to 12 h for the next cron. ``run_started`` reports what
    actually happened (§5: no success toast over a dead run).

    Web mutations deliberately emit NO domain event: the web layer has no
    event bus, and provenance comes from the store rows themselves.

    Args:
        request: The incoming FastAPI request.
        response: The outgoing response (status downgraded to 200 on reuse).
        followed_id: Rowid of the ``followed_series`` row.
        season: Season number (1-based).

    Returns:
        The created (201) or reused live (200) season wanted with absorption
        count, the ``reused`` flag, and ``run_started`` telling whether this call
        actually queued an acquisition run.

    Raises:
        HTTPException: 404 if the followed_id does not exist.
        HTTPException: 400 if season < 1 or the follow is not a show.
    """
    if season < 1:
        raise HTTPException(status_code=400, detail="Season must be >= 1")

    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        followed = store.follow.get(followed_id)
        if followed is None:
            raise HTTPException(status_code=404, detail="Followed series not found")
        if followed.kind != "show":
            raise HTTPException(
                status_code=400,
                detail="Season grab only applies to TV shows (kind='show')",
            )

        # Dedup: one LIVE season wanted per follow+season. Status-scoped to the
        # open statuses — a terminal row (fallback_episodes/done/abandoned)
        # must not be « reused »: that answered 201 with nothing enqueued,
        # closing the only manual escape hatch after a fallback (review F5).
        existing = store.wanted.find(
            followed_id=followed_id,
            kind="season",
            season=season,
            episode=None,
            statuses=tuple(sorted(OPEN_WANTED_STATUSES)),
        )
        if existing is not None:
            # Count already-absorbed episodes for a truthful response.
            absorbed = _count_absorbed_for_season(store, followed_id, season)
            response.status_code = 200
            return SeasonGrabResponse(
                season_wanted_id=existing.id or 0,
                season=season,
                absorbed_count=absorbed,
                reused=True,
            )

        assert followed.id is not None  # noqa: S101 — get() sets id
        now = int(time.time())

        from personalscraper.acquire.domain import WantedItem

        # Enqueue the season wanted
        season_wid = store.wanted.add(
            WantedItem(
                media_ref=followed.media_ref,
                kind="season",
                status="pending",
                enqueued_at=now,
                followed_id=followed.id,
                season=season,
                episode=None,
            )
        )

        # Absorb live episode wanteds for this season
        absorbed_ids = _absorb_live_episodes_for_season(
            store,
            followed.id,
            season,
            season_wid,
        )

        # D3 — the operator's action must START, not wait up to 12 h for the next
        # cron (search 10 3,15 / grab 20 3,15). Same amorce ``create_follow``
        # already uses: detect → search → grab, scoped to this follow.
        #
        # Fire-and-forget by contract: ``enqueue_prime_run`` logs and swallows every
        # failure and never raises, so a dead spawn degrades to ``run_started=False``
        # rather than failing an enqueue that DID happen. Its own idempotence guard
        # is the only refusal §6 permits — a duplicate of the same action on the
        # same target — so this route never answers 409.
        prime_outcome = enqueue_prime_run(config.indexer.db_path, followed.id)

        return SeasonGrabResponse(
            season_wanted_id=season_wid,
            season=season,
            absorbed_count=len(absorbed_ids),
            reused=False,
            # Mirror create_follow's mapping so both operator entry points report
            # a started run identically.
            run_started=prime_outcome in ("spawned", "already_running"),
        )
    finally:
        store.close()
