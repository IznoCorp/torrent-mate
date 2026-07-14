"""Acquisition REST routes (acq-watch feature).

Four GET endpoints + three mutating endpoints (POST/PATCH/DELETE) under
/api/acquisition/ exposing the followed-series list, wanted queue, seed
obligations, watcher status, and follow CRUD.  Fed by direct reads/writes of
the shared WAL acquire.db — NOT an event projection (unlike S6).

All routes are guarded by require_session inherited from the parent
guarded_api router (registration in app.py).  Auth dependencies are NOT
added per-route — the auth perimeter is a single dependency at registration
time, per docs/reference/web-ui.md §6 (the single authority for this
convention; R14/R24).

Reads open a FRESH read-only sqlite3 connection PER REQUEST — the store's
shared self._conn is not safe across FastAPI request threads (TestClient
threadpool + uvicorn workers → thread-affinity ProgrammingError).  This
mirrors pipeline.py's _build_status pattern.

Writes use ``build_acquire_store`` to create a fresh ConcreteAcquireStore per
request — its own connection, safe across threads.  Each mutating route also
carries ``require_not_staging`` (staging → 403) and
``require_x_requested_with`` (CSRF → 400) as per-route dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from personalscraper.acquire.cadence import Cadence
from personalscraper.acquire.desired import cadence_from_config, cadence_from_json, effective_cadence
from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.store import build_acquire_store
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.acquisition._helpers import (
    _backfill_from_indexer,
    _cadence_readout,
    _parse_json_dict,
    _parse_media_ref,
    _row_col,
)
from personalscraper.web.deps import require_not_staging, require_x_requested_with
from personalscraper.web.models.acquisition import (
    AcquisitionStatusResponse,
    CompletenessResponse,
    CreateFollowRequest,
    FollowedResponse,
    FollowedSeriesItem,
    GrabTriggerResponse,
    MediaRefResponse,
    MediaSearchResponse,
    MediaSearchResult,
    ObligationItem,
    ObligationsResponse,
    RecentRun,
    UpdateFollowRequest,
    WantedItemResponse,
    WantedResponse,
)

if TYPE_CHECKING:
    from personalscraper.scraper.decision_candidate import DecisionCandidate

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])
logger = get_logger(__name__)

_MAX_PAGE_SIZE = 200
_WATCHER_RECENT_RUNS = 10

# ── watcher trigger values ─────────────────────────────────────────────
# The watcher daemon spawns ``personalscraper run --trigger-reason <reason>``
# where reason ∈ {completion, safety_net, manual} (acquire/watcher.py:45-46).
# Each is persisted as pipeline_run.trigger.  We filter on this set to
# surface only watcher-triggered runs (not "web"-triggered ones).
_WATCHER_TRIGGERS = ("completion", "safety_net", "manual")


# ── helpers ────────────────────────────────────────────────────────────


def _write_follow_metadata(
    acquire_db_path: Path | None,
    followed_id: int,
    body: CreateFollowRequest,
) -> None:
    """Persist the card metadata captured from the add-by-search candidate (OBJ3).

    A no-op when nothing was supplied. Fail-soft: a DB error is logged and
    swallowed — the follow itself already succeeded, the metadata is a nicety.

    Args:
        acquire_db_path: Absolute path to ``acquire.db``, or ``None``.
        followed_id: The row to update.
        body: The create request carrying optional ``poster_url``/``overview``/``year``.
    """
    if acquire_db_path is None:
        return
    if body.poster_url is None and body.overview is None and body.year is None:
        return
    try:
        with closing(sqlite3.connect(str(acquire_db_path))) as conn:
            apply_pragmas(conn)
            conn.execute(
                "UPDATE followed_series SET poster_url = ?, overview = ?, year = ? WHERE id = ?",
                (body.poster_url, body.overview, body.year, followed_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.warning("acquisition_follow_metadata_write_failed", followed_id=followed_id, exc_info=True)


# ── /api/acquisition/followed ──────────────────────────────────────────


@router.get("/followed", response_model=FollowedResponse)
def get_followed(
    request: Request,
    active: Literal["all", "active", "inactive"] = Query("active"),
) -> FollowedResponse:
    """List followed series, filtered by active status.

    Args:
        request: The incoming FastAPI request.
        active: Filter: ``"active"`` (default), ``"all"``, or ``"inactive"``.

    Returns:
        A ``FollowedResponse`` with the matching items.
    """
    db_path = request.app.state.config.acquire.db_path
    if db_path is None or not Path(db_path).exists():
        return FollowedResponse(items=[])

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            if active == "inactive":
                rows = conn.execute("SELECT * FROM followed_series WHERE active = 0 ORDER BY id").fetchall()
            elif active == "all":
                rows = conn.execute("SELECT * FROM followed_series ORDER BY id").fetchall()
            else:
                rows = conn.execute("SELECT * FROM followed_series WHERE active = 1 ORDER BY id").fetchall()

            indexer_db_path = request.app.state.config.indexer.db_path

            # Cadence readout (OBJ3): resolve the global default once and batch the
            # pending wanted timings per series, so the next-search estimate + the
            # governing tier cost a single extra query for the whole list.
            now = int(time.time())
            try:
                global_cadence: Cadence | None = cadence_from_config(request.app.state.config.acquire.cadence)
            except (ValueError, AttributeError):  # a malformed cadence config must not 500 the list
                global_cadence = None
            timings_by_series: dict[int, list[tuple[int, int | None]]] = {}
            if global_cadence is not None:
                for w in conn.execute(
                    "SELECT followed_id, enqueued_at, last_search_at FROM wanted "
                    "WHERE followed_id IS NOT NULL AND status IN ('pending', 'searching')"
                ).fetchall():
                    last = None if w["last_search_at"] is None else int(w["last_search_at"])
                    timings_by_series.setdefault(int(w["followed_id"]), []).append((int(w["enqueued_at"]), last))

            items: list[FollowedSeriesItem] = []
            for row in rows:
                # COUNT wanted pending for this series.
                pending = conn.execute(
                    "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status IN ('pending', 'searching')",
                    (row["id"],),
                ).fetchone()[0]
                # COUNT grabbed — the §5 "en cours d'acquisition" window (torrent
                # spotted → pipeline finished) that drives the film card status.
                grabbed = conn.execute(
                    "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status = 'grabbed'",
                    (row["id"],),
                ).fetchone()[0]

                # Card metadata (OBJ3): cached columns first; year + season_count
                # backfilled from the indexer when the cache is empty.
                media_ref = _parse_media_ref(row["media_ref_json"])
                poster_url = cast("str | None", _row_col(row, "poster_url"))
                overview = cast("str | None", _row_col(row, "overview"))
                year = cast("int | None", _row_col(row, "year"))
                season_count = cast("int | None", _row_col(row, "season_count"))
                if year is None or season_count is None:
                    bf_year, bf_seasons = _backfill_from_indexer(indexer_db_path, media_ref.tvdb_id, media_ref.tmdb_id)
                    if year is None:
                        year = bf_year
                    if season_count is None:
                        season_count = bf_seasons

                # Next-search estimate + governing tier from the series' pending items.
                next_due: float | None = None
                cadence_tier: str | None = None
                if global_cadence is not None:
                    effective = effective_cadence(cadence_from_json(row["cadence_json"]), global_cadence)
                    next_due, cadence_tier = _cadence_readout(timings_by_series.get(row["id"], []), effective, now)

                items.append(
                    FollowedSeriesItem(
                        id=row["id"],
                        title=row["title"],
                        media_ref=media_ref,
                        active=bool(row["active"]),
                        kind=cast("str", _row_col(row, "kind")) or "show",
                        cadence=_parse_json_dict(row["cadence_json"]),
                        added_at=float(row["added_at"]),
                        wanted_pending=pending,
                        wanted_grabbed=grabbed,
                        quality_profile=_parse_json_dict(row["quality_profile_json"]),
                        poster_url=poster_url,
                        overview=overview,
                        year=year,
                        season_count=season_count,
                        next_search_at=next_due,
                        cadence_tier=cadence_tier,
                    )
                )
            return FollowedResponse(items=items)
    except sqlite3.Error:
        logger.warning("acquisition_followed_read_failed", exc_info=True)
        return FollowedResponse(items=[])


# ── /api/acquisition/followed/{id}/completeness ────────────────────────


@router.get("/followed/{followed_id}/completeness", response_model=CompletenessResponse)
def get_followed_completeness(request: Request, followed_id: int) -> CompletenessResponse:
    """Per-season / per-episode completeness for one followed series (§5).

    Read-only: crosses the provider catalog (aired episodes), the library
    (ownership by provider id) and the wanted queue into one honest matrix —
    "ce qui est déjà sorti vs ce qui est en médiathèque". An empty provider
    catalog is an explicit state (``provider_catalog_empty``), never a
    misleading all-missing grid.

    Args:
        request: The incoming FastAPI request.
        followed_id: The ``followed_series`` rowid.

    Returns:
        The :class:`CompletenessResponse`.

    Raises:
        HTTPException: 404 unknown follow; 502 when the provider registry
            cannot be built.
    """
    from personalscraper.core.ownership import NullOwnershipChecker
    from personalscraper.indexer.ownership import IndexerOwnershipChecker
    from personalscraper.web.acquisition.completeness import compute_completeness

    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        followed = store.follow.get(followed_id)
        if followed is None:
            raise HTTPException(status_code=404, detail="Followed series not found")

        from personalscraper.cli_helpers import _build_app_context

        try:
            app_context = _build_app_context(config, request.app.state.settings)
            registry = app_context.provider_registry
        except Exception as exc:
            logger.error("acquisition_completeness_registry_failed", error=str(exc))
            raise HTTPException(status_code=502, detail="Provider registry unavailable") from exc

        indexer_db = config.indexer.db_path
        checker = IndexerOwnershipChecker(Path(indexer_db)) if indexer_db is not None else NullOwnershipChecker()
        try:
            return compute_completeness(followed, registry=registry, ownership=checker, store=store)
        finally:
            if isinstance(checker, IndexerOwnershipChecker):
                checker.close()
    finally:
        store.close()


# ── /api/acquisition/wanted ────────────────────────────────────────────


_WANTED_STATUSES = Literal["all", "pending", "searching", "grabbed", "done", "abandoned"]


@router.get("/wanted", response_model=WantedResponse)
def get_wanted(
    request: Request,
    status: _WANTED_STATUSES = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
) -> WantedResponse:
    """List wanted items, paginated, with optional status filter.

    Args:
        request: The incoming FastAPI request.
        status: Filter by wanted status (default ``"all"``).
        page: Page number (1-based, default 1).
        page_size: Items per page (1–200, default 50).

    Returns:
        A ``WantedResponse`` with the matching items + pagination metadata.
    """
    db_path = request.app.state.config.acquire.db_path
    if db_path is None or not Path(db_path).exists():
        return WantedResponse(items=[], total=0, page=page, page_size=page_size)

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            # Build WHERE clause.
            where = ""
            params: list[str | int] = []
            if status != "all":
                where = "WHERE w.status = ?"
                params.append(status)

            # Count total.
            total = conn.execute(f"SELECT COUNT(*) FROM wanted w {where}", params).fetchone()[0]

            # Fetch page.
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"""
                SELECT w.*, fs.title AS fs_title
                FROM wanted w
                LEFT JOIN followed_series fs ON w.followed_id = fs.id
                {where}
                ORDER BY w.enqueued_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

            items: list[WantedItemResponse] = []
            for row in rows:
                items.append(
                    WantedItemResponse(
                        id=row["id"],
                        title=row["fs_title"] or "",
                        kind=row["kind"],
                        season=row["season"],
                        episode=row["episode"],
                        status=row["status"],
                        attempts=row["attempts"],
                        enqueued_at=float(row["enqueued_at"]),
                        last_search_at=(float(row["last_search_at"]) if row["last_search_at"] is not None else None),
                    )
                )
            return WantedResponse(items=items, total=total, page=page, page_size=page_size)
    except sqlite3.Error:
        logger.warning("acquisition_wanted_read_failed", exc_info=True)
        return WantedResponse(items=[], total=0, page=page, page_size=page_size)


# ── /api/acquisition/obligations ───────────────────────────────────────


_ObligationStatusFilter = Literal["all", "pending", "breached", "satisfied"]


@router.get("/obligations", response_model=ObligationsResponse)
def get_obligations(
    request: Request,
    status: _ObligationStatusFilter = Query("all"),
) -> ObligationsResponse:
    """List seed obligations with their current ratio state.

    Args:
        request: The incoming FastAPI request.
        status: Filter: ``"all"`` (default), ``"pending"``, ``"breached"``,
            or ``"satisfied"``.

    Returns:
        An ``ObligationsResponse`` with matching items.  Each item LEFT JOINs
        ``ratio_state`` on tracker name.
    """
    db_path = request.app.state.config.acquire.db_path
    if db_path is None or not Path(db_path).exists():
        return ObligationsResponse(items=[])

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            where = ""
            params: list[str | int] = []
            if status == "pending":
                where = "WHERE so.satisfied_at IS NULL AND so.breached_at IS NULL"
            elif status == "breached":
                where = "WHERE so.breached_at IS NOT NULL"
            elif status == "satisfied":
                where = "WHERE so.satisfied_at IS NOT NULL"

            rows = conn.execute(
                f"""
                SELECT so.*, rs.observed_ratio, rs.accumulated_seed_time_s,
                       rs.hnr_count
                FROM seed_obligation so
                LEFT JOIN ratio_state rs ON so.source_tracker = rs.tracker_name
                {where}
                ORDER BY so.added_at DESC
                """,
                params,
            ).fetchall()

            items: list[ObligationItem] = []
            for row in rows:
                items.append(
                    ObligationItem(
                        info_hash=row["info_hash"],
                        source_tracker=row["source_tracker"],
                        dispatched_path=row["dispatched_path"],
                        min_seed_time_s=row["min_seed_time_s"],
                        min_ratio=float(row["min_ratio"]),
                        added_at=float(row["added_at"]),
                        satisfied_at=(float(row["satisfied_at"]) if row["satisfied_at"] is not None else None),
                        breached_at=(float(row["breached_at"]) if row["breached_at"] is not None else None),
                        released_at=(float(row["released_at"]) if row["released_at"] is not None else None),
                        observed_ratio=(float(row["observed_ratio"]) if row["observed_ratio"] is not None else None),
                        accumulated_seed_time_s=(
                            row["accumulated_seed_time_s"] if row["accumulated_seed_time_s"] is not None else None
                        ),
                        hnr_count=(row["hnr_count"] if row["hnr_count"] is not None else None),
                    )
                )
            return ObligationsResponse(items=items)
    except sqlite3.Error:
        logger.warning("acquisition_obligations_read_failed", exc_info=True)
        return ObligationsResponse(items=[])


# ── /api/acquisition/status ────────────────────────────────────────────


def _parse_run_counts(steps_json: str | None) -> dict[str, int] | None:
    """Extract the §5 numeric result from a run's ``steps_json``, or ``None``.

    The acquisition CLIs persist their counts as the ``counts`` mapping of a
    ``steps_json`` entry (see ``commands/_cli_run_row``). The LAST entry
    carrying counts wins.

    Args:
        steps_json: The raw ``steps_json`` column value.

    Returns:
        The counts mapping, or ``None`` when absent/unparseable.
    """
    if not steps_json:
        return None
    try:
        steps = json.loads(steps_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(steps, list):
        return None
    for step in reversed(steps):
        counts = step.get("counts") if isinstance(step, dict) else None
        if isinstance(counts, dict):
            return {str(k): int(v) for k, v in counts.items() if isinstance(v, (int, float))}
    return None


def _query_watcher_recent_runs(db_path: Path) -> list[RecentRun]:
    """Query the last N acquisition-relevant pipeline_run rows from library.db.

    Covers BOTH populations (§5 visibility): the watcher-triggered pipeline
    runs (legacy triggers) AND the acquisition CLI runs — ``follow-detect`` /
    ``grab`` rows written by the crons, a human CLI, or the web runner — each
    carrying its structured numeric result when recorded.

    Args:
        db_path: Absolute path to the indexer SQLite database (library.db).

    Returns:
        A list of :class:`RecentRun` items, most recent first.
    """
    if not db_path.exists():
        return []

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            placeholders = ", ".join("?" * len(_WATCHER_TRIGGERS))
            rows = conn.execute(
                f"""
                SELECT run_uid, started_at, ended_at, outcome, command, "trigger", steps_json
                FROM pipeline_run
                WHERE trigger IN ({placeholders})
                   OR command IN ('follow-detect', 'grab')
                ORDER BY started_at DESC
                LIMIT ?
                """,
                list(_WATCHER_TRIGGERS) + [_WATCHER_RECENT_RUNS],
            ).fetchall()

            return [
                RecentRun(
                    run_uid=row["run_uid"],
                    started_at=float(row["started_at"]),
                    ended_at=(float(row["ended_at"]) if row["ended_at"] is not None else None),
                    outcome=row["outcome"],
                    command=row["command"],
                    trigger=row["trigger"],
                    result=_parse_run_counts(row["steps_json"]),
                )
                for row in rows
            ]
    except sqlite3.Error:
        logger.warning("acquisition_recent_runs_read_failed", exc_info=True)
        return []


@router.get("/status", response_model=AcquisitionStatusResponse)
def get_acquisition_status(request: Request) -> AcquisitionStatusResponse:
    """Return the watcher status and recent watcher-triggered runs.

    Args:
        request: The incoming FastAPI request.

    Returns:
        An ``AcquisitionStatusResponse`` with watcher enabled state, last
        successful run timestamp, and recent runs.
    """
    config = request.app.state.config
    acquire_path = config.acquire.db_path
    data_dir = config.paths.data_dir

    # watcher_enabled: NOT the watcher.paused sentinel.
    watcher_enabled = not (data_dir / "watcher.paused").exists()

    # last_successful_run_at: from watch_state KV in acquire.db.
    last_successful_run_at: float | None = None
    if acquire_path is not None and acquire_path.exists():
        try:
            with closing(sqlite3.connect(str(acquire_path))) as conn:
                apply_pragmas(conn)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT value FROM watch_state WHERE key = ?",
                    ("last_successful_run_at",),
                ).fetchone()
                if row is not None:
                    last_successful_run_at = float(row["value"])
        except sqlite3.Error:
            logger.warning("acquisition_status_watch_state_failed", exc_info=True)

    # recent_runs: from library.db.
    indexer_path = config.indexer.db_path
    recent_runs = _query_watcher_recent_runs(indexer_path)

    return AcquisitionStatusResponse(
        last_successful_run_at=last_successful_run_at,
        watcher_enabled=watcher_enabled,
        recent_runs=recent_runs,
    )


# ── media search (add-by-search, OBJ3) ───────────────────────────────────


def _build_provider_clients(request: Request) -> tuple[object, object]:
    """Build request-scoped TMDB + TVDB clients for a live media search.

    Mirrors the decisions-search pattern: a fresh AppContext + ProviderRegistry
    for this single request (never stored on ``app.state`` — the composition-
    boundary rule). Live search is an infrequent operator action, not a hot
    polling endpoint.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A ``(tmdb_client, tvdb_client)`` tuple of provider client objects.

    Raises:
        HTTPException: 502 when the provider registry cannot be built.
    """
    from personalscraper.cli_helpers import _build_app_context

    config = request.app.state.config
    settings = request.app.state.settings
    try:
        app_context = _build_app_context(config, settings)
        tmdb_client = app_context.provider_registry.get("tmdb")
        tvdb_client = app_context.provider_registry.get("tvdb")
    except Exception as exc:
        logger.error("acquisition_search_registry_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="Provider registry unavailable") from exc
    return tmdb_client, tvdb_client


def _to_search_result(candidate: "DecisionCandidate", kind: str) -> MediaSearchResult:
    """Map a scored :class:`DecisionCandidate` to a :class:`MediaSearchResult`.

    Args:
        candidate: The scored provider candidate.
        kind: ``"movie"`` or ``"tv"`` (which search chain produced it).

    Returns:
        The tagged search result.
    """
    return MediaSearchResult(
        provider=candidate.provider,
        provider_id=candidate.provider_id,
        title=candidate.title,
        year=candidate.year,
        kind=kind,
        poster_url=candidate.poster_url,
        overview=candidate.overview,
        score=candidate.score,
    )


@router.get("/search", response_model=MediaSearchResponse)
def search_media(
    request: Request,
    q: str = Query(..., min_length=1, description="Title to search for."),
    kind: Literal["movie", "tv"] | None = Query(
        default=None,
        description="Restrict to movies or TV; omit to search both.",
    ),
) -> MediaSearchResponse:
    """Search live providers for media to follow (add-by-search, OBJ3).

    Read-only: builds per-request provider clients and delegates to the same
    detailed confidence matchers the decisions search uses, tagging each result
    with its ``kind``. Results are merged across the requested kind(s) and
    sorted best-score-first.

    Args:
        request: The incoming FastAPI request.
        q: The title to search for.
        kind: Optional ``"movie"``/``"tv"`` restriction (both when omitted).

    Returns:
        A :class:`MediaSearchResponse` with the scored matches.

    Raises:
        HTTPException: 502 on provider registry build or provider API failure.
    """
    tmdb_client, tvdb_client = _build_provider_clients(request)
    results: list[MediaSearchResult] = []

    if kind in (None, "movie"):
        from personalscraper.scraper.confidence import match_movie_detailed

        try:
            _, movie_candidates = match_movie_detailed(tmdb_client, q, None)
        except Exception as exc:
            logger.error("acquisition_search_movie_failed", error=str(exc))
            raise HTTPException(status_code=502, detail=f"Movie search failed: {exc}") from exc
        results.extend(_to_search_result(c, "movie") for c in movie_candidates)

    if kind in (None, "tv"):
        from personalscraper.scraper.confidence import match_tvshow_detailed

        try:
            _, tv_candidates = match_tvshow_detailed(tvdb_client, tmdb_client, q, None)
        except Exception as exc:
            logger.error("acquisition_search_tvshow_failed", error=str(exc))
            raise HTTPException(status_code=502, detail=f"TV search failed: {exc}") from exc
        results.extend(_to_search_result(c, "tv") for c in tv_candidates)

    results.sort(key=lambda r: r.score, reverse=True)

    # §5 replacement confirmation: flag movie results already owned in the
    # library (by provider id, live files only) so the UI can ask before
    # following — the pipeline will REPLACE the existing version. Fail-soft:
    # an unreadable indexer leaves already_owned=False everywhere.
    indexer_db = request.app.state.config.indexer.db_path
    if indexer_db is not None and any(r.kind == "movie" for r in results):
        from personalscraper.core.identity import MediaRef
        from personalscraper.indexer.ownership import IndexerOwnershipChecker

        checker = IndexerOwnershipChecker(Path(indexer_db))
        try:
            for r in results:
                if r.kind != "movie":
                    continue
                ref = MediaRef(tmdb_id=r.provider_id) if r.provider == "tmdb" else MediaRef(tvdb_id=r.provider_id)
                r.already_owned = checker.owns(ref, kind="movie")
        finally:
            checker.close()

    return MediaSearchResponse(results=results)


# ── helpers (write routes) ───────────────────────────────────────────────


def _build_followed_item(fs: FollowedSeries, wanted_pending: int) -> FollowedSeriesItem:
    """Convert a :class:`FollowedSeries` domain object to a response item.

    Args:
        fs: The domain object from the store (must have ``id`` set).
        wanted_pending: The COUNT of pending/searching wanted rows.

    Returns:
        A :class:`FollowedSeriesItem` ready for JSON serialization.
    """
    return FollowedSeriesItem(
        id=fs.id,  # type: ignore[arg-type]  # store.get guarantees id is set
        title=fs.title,
        media_ref=MediaRefResponse(
            tvdb_id=fs.media_ref.tvdb_id,
            tmdb_id=fs.media_ref.tmdb_id,
            imdb_id=fs.media_ref.imdb_id,
        ),
        active=fs.active,
        kind=fs.kind,
        cadence=_parse_json_dict(fs.cadence_json),
        added_at=float(fs.added_at),
        wanted_pending=wanted_pending,
        quality_profile=_parse_json_dict(fs.quality_profile_json),
    )


def _item_from_followed(fs: FollowedSeries) -> FollowedSeriesItem:
    """Build a response item from a :class:`FollowedSeries` domain object.

    Populates ``media_ref`` from the domain object's ``media_ref`` field
    (NOT the raw JSON column — the domain object already has a parsed
    :class:`MediaRef`).  ``wanted_pending`` is set to 0 for newly created
    or reactivated items.

    Args:
        fs: The domain object from the store (must have ``id`` set).

    Returns:
        A :class:`FollowedSeriesItem` ready for JSON serialization.
    """
    return FollowedSeriesItem(
        id=fs.id,  # type: ignore[arg-type]  # store.get guarantees id is set
        title=fs.title,
        media_ref=MediaRefResponse(
            tvdb_id=fs.media_ref.tvdb_id,
            tmdb_id=fs.media_ref.tmdb_id,
            imdb_id=fs.media_ref.imdb_id,
        ),
        active=fs.active,
        kind=fs.kind,
        cadence=_parse_json_dict(fs.cadence_json),
        added_at=float(fs.added_at),
        wanted_pending=0,  # newly created/reactivated → no wanted items yet
        quality_profile=_parse_json_dict(fs.quality_profile_json),
    )


# ── /api/acquisition/followed (write) ─────────────────────────────────────


@router.post(
    "/followed",
    status_code=201,
    response_model=FollowedSeriesItem,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def create_follow(request: Request, body: CreateFollowRequest) -> FollowedSeriesItem:
    """Follow a new series (or reactivate an inactive one).

    Args:
        request: The incoming FastAPI request.
        body: The parsed :class:`CreateFollowRequest`.

    Returns:
        The created or reactivated :class:`FollowedSeriesItem`.

    Raises:
        HTTPException: 409 if the series is already actively followed.
    """
    config = request.app.state.config
    media_ref = MediaRef(
        tvdb_id=body.tvdb_id,
        tmdb_id=body.tmdb_id,
        imdb_id=body.imdb_id,
    )
    title = body.title or ""

    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.find_by_ref(media_ref)
        if existing is not None:
            assert existing.id is not None  # noqa: S101 — find_by_ref always sets id
            if existing.active:
                raise HTTPException(
                    status_code=409,
                    detail="Series is already followed (active=True)",
                )
            # Reactivate — matched by PRIMARY provider id (find_by_ref is more
            # lenient than the exact-media_ref_json upsert), and REFRESH the kind
            # so a re-follow of a film once followed as a series lands
            # kind='movie', not the stale 'show' (§5 — else its lifecycle stays
            # series-shaped and no movie wanted row is ever produced).
            store.follow.set_active(existing.id, True)
            store.follow.set_kind(existing.id, body.kind)
            _write_follow_metadata(config.acquire.db_path, existing.id, body)
            reactivated = store.follow.get(existing.id)
            assert reactivated is not None  # noqa: S101 — just wrote it
            item = _item_from_followed(reactivated)
            item.poster_url = body.poster_url
            item.overview = body.overview
            item.year = body.year
            return item

        # New follow. The kind ('movie'|'show') starts the §5 film lifecycle:
        # detect will produce one movie wanted row and auto-unfollow once acquired.
        series = FollowedSeries(
            media_ref=media_ref,
            title=title,
            added_at=int(time.time()),
            active=True,
            kind=body.kind,
        )
        new_id = store.follow.add(series)
        created = store.follow.get(new_id)
        assert created is not None  # noqa: S101 — just inserted it
        # Persist + echo the card metadata captured from the search candidate.
        _write_follow_metadata(config.acquire.db_path, new_id, body)
        item = _item_from_followed(created)
        item.poster_url = body.poster_url
        item.overview = body.overview
        item.year = body.year
        return item
    finally:
        store.close()


@router.patch(
    "/followed/{followed_id}",
    response_model=FollowedSeriesItem,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def update_follow(
    request: Request,
    followed_id: int,
    body: UpdateFollowRequest,
) -> FollowedSeriesItem:
    """Update the active flag or cadence for a followed series.

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.
        body: The parsed :class:`UpdateFollowRequest`.

    Returns:
        The updated :class:`FollowedSeriesItem`.

    Raises:
        HTTPException: 404 if the followed_id does not exist.
    """
    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.get(followed_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Followed series not found")

        if body.active is not None:
            store.follow.set_active(followed_id, body.active)

        if body.cadence is not None:
            cadence_json = json.dumps(body.cadence.model_dump())
            store.follow.set_cadence(followed_id, cadence_json)

        updated = store.follow.get(followed_id)
        assert updated is not None  # noqa: S101 — just wrote it

        # Count wanted pending for accurate response.
        wanted_pending = _count_wanted_pending(store, followed_id)
        return _build_followed_item(updated, wanted_pending)
    finally:
        store.close()


def _count_wanted_pending(store: Any, followed_id: int) -> int:
    """Count pending/searching wanted rows for a followed series.

    Uses the store's connection directly for a cheap COUNT query.

    Args:
        store: An open :class:`ConcreteAcquireStore`.
        followed_id: Rowid of the ``followed_series`` row.

    Returns:
        The number of wanted rows in ``pending`` or ``searching`` status.
    """
    # Access the store's internal connection — safe because the store
    # is freshly built per-request (no thread-affinity risk).
    conn = store._conn
    if conn is None:
        return 0
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status IN ('pending', 'searching')",
        (followed_id,),
    ).fetchone()
    return row[0] if row else 0


@router.delete(
    "/followed/{followed_id}",
    status_code=204,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def delete_follow(request: Request, followed_id: int) -> None:
    """Soft-unfollow a series (sets active=False).

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.

    Raises:
        HTTPException: 404 if the followed_id does not exist.
    """
    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.get(followed_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Followed series not found")
        store.follow.set_active(followed_id, False)
    finally:
        store.close()


# ── POST /api/acquisition/followed/{id}/search — per-series manual grab (OBJ3) ──


def _grab_options_json(followed_id: int) -> str:
    """Canonical ``options_json`` for a per-series grab run (stable string).

    Args:
        followed_id: The followed series id.

    Returns:
        ``'{"followed_id":N}'`` — the exact form the runner writes, so the
        concurrency guard can match it precisely.
    """
    return json.dumps({"followed_id": followed_id}, sort_keys=True, separators=(",", ":"))


def _guard_no_running_grab(db_path: Path, options_json: str, command: str = "grab") -> None:
    """Raise 409 when a live acquisition run with the same scope is in flight.

    Scans ``pipeline_run`` for an un-ended row of the given *command* whose
    ``options_json`` matches (same followed series / same detect scope) and
    whose pid is still alive. A dead/NULL pid is a stale row (crashed runner)
    and is ignored.

    Args:
        db_path: Absolute path to ``library.db``.
        options_json: The canonical options string for the run scope.
        command: The run command to match (``'grab'`` / ``'follow-detect'``).

    Raises:
        HTTPException: 409 when a live matching run is already running.
    """
    if not db_path.exists():
        return
    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT pid FROM pipeline_run WHERE command = ? AND ended_at IS NULL AND options_json = ?",
                (command, options_json),
            ).fetchall()
    except sqlite3.Error:
        logger.warning("grab_guard_query_failed", exc_info=True)
        return
    for row in rows:
        pid = row["pid"]
        if pid is None:
            continue
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            continue  # dead pid → stale row
        except PermissionError:
            pass  # alive, owned by another user
        raise HTTPException(status_code=409, detail="A matching acquisition run is already in flight")


def _spawn_grab_runner(run_uid: str, followed_id: int) -> int:
    """Spawn the grab runner as a detached subprocess.

    Args:
        run_uid: The reserved run's unique identifier.
        followed_id: The followed series to scope the grab to.

    Returns:
        The pid of the spawned runner process.
    """
    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_GRAB_FOLLOWED_ID": str(followed_id),
    }
    logger.info("grab_trigger_spawned", run_uid=run_uid, followed_id=followed_id)
    proc = subprocess.Popen(
        [sys.executable, "-m", "personalscraper.web.acquisition.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid


@router.post(
    "/detect",
    status_code=202,
    response_model=GrabTriggerResponse,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def trigger_detect(request: Request) -> GrabTriggerResponse:
    """Launch the aired-episode / film discovery on demand (§5 manual watcher).

    The detect pass (the 03:00 cron's job) polls the provider catalog for every
    active follow, enqueues the missing episodes / films as wanted rows, and —
    for movie follows already in the library — performs the §5 acquired-film
    closure. This endpoint runs it NOW: it reserves a ``pipeline_run`` row
    (``command='follow-detect'``, ``trigger='web'``), spawns the acquisition
    runner in detect mode, and returns ``202`` with the ``run_uid`` so the UI
    tracks the run to its numeric result — never a blind success toast.

    Args:
        request: The incoming FastAPI request.

    Returns:
        ``202`` with :class:`GrabTriggerResponse` (``{"run_uid": "..."}``).

    Raises:
        409: A detect run is already in flight.
        500: The runner subprocess failed to spawn.
    """
    config = request.app.state.config
    db_path = cast(Path, config.indexer.db_path)

    # Reject a duplicate concurrent detect (pid-alive guard on the same options).
    _guard_no_running_grab(db_path, "{}", command="follow-detect")

    run_uid = uuid.uuid4().hex
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command="follow-detect",
        options_json="{}",
        if_absent=True,
    )
    try:
        env = {
            **os.environ,
            "PERSONALSCRAPER_RUN_UID": run_uid,
            "PERSONALSCRAPER_ACQ_COMMAND": "detect",
        }
        logger.info("detect_trigger_spawned", run_uid=run_uid)
        subprocess.Popen(
            [sys.executable, "-m", "personalscraper.web.acquisition.runner"],
            start_new_session=True,
            env=env,
        )
    except (OSError, ValueError) as exc:
        writer.finalize(run_uid, "error", error=f"Runner spawn failed: {exc}")
        logger.error("detect_trigger_spawn_failed", run_uid=run_uid, error=str(exc))
        raise HTTPException(status_code=500, detail="Could not launch the detect runner") from exc
    return GrabTriggerResponse(run_uid=run_uid)


@router.post(
    "/followed/{followed_id}/search",
    status_code=202,
    response_model=GrabTriggerResponse,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def trigger_followed_search(request: Request, followed_id: int) -> GrabTriggerResponse:
    """Launch a targeted grab for one followed series (OBJ3 manual trigger).

    Reserves a ``pipeline_run`` row, spawns the grab runner (which runs
    ``grab --followed-id <id>`` over that series' pending wanted items), and
    returns ``202`` with the ``run_uid`` so the UI can track the outcome.

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.

    Returns:
        ``202`` with :class:`GrabTriggerResponse` (``{"run_uid": "..."}``).

    Raises:
        404: The followed series does not exist.
        409: A grab for this series is already running.
        500: The runner subprocess failed to spawn.
    """
    config = request.app.state.config
    db_path = cast(Path, config.indexer.db_path)

    # 1. Verify the series exists (404 before any run reservation).
    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.get(followed_id)
    finally:
        store.close()
    if existing is None:
        raise HTTPException(status_code=404, detail="Followed series not found")

    options_json = _grab_options_json(followed_id)

    # 2. Reject a duplicate concurrent grab for the same series (409).
    _guard_no_running_grab(db_path, options_json)

    # 3. Reserve the pipeline_run row with the web process pid (guaranteed alive
    #    until the runner claims its own pid), then spawn the runner.
    run_uid = uuid.uuid4().hex
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command="grab",
        options_json=options_json,
        if_absent=True,
    )

    try:
        pid = _spawn_grab_runner(run_uid, followed_id)
    except (OSError, ValueError) as exc:
        # Never leave the reserved row 'running' on a spawn failure (fail-soft).
        try:
            writer.finalize(run_uid, "error", error=str(exc))
        except sqlite3.Error:
            logger.warning("grab_trigger_finalize_failed", run_uid=run_uid)
        logger.error("grab_trigger_spawn_failed", run_uid=run_uid, followed_id=followed_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to spawn grab runner") from exc

    if isinstance(pid, int):
        try:
            writer.update_pid(run_uid, pid)
        except sqlite3.Error:
            logger.warning("grab_trigger_update_pid_failed", run_uid=run_uid)

    return GrabTriggerResponse(run_uid=run_uid)
