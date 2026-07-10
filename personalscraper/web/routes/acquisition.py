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
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.store import build_acquire_store
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.web.deps import require_not_staging, require_x_requested_with
from personalscraper.web.models.acquisition import (
    AcquisitionStatusResponse,
    CreateFollowRequest,
    FollowedResponse,
    FollowedSeriesItem,
    MediaRefResponse,
    ObligationItem,
    ObligationsResponse,
    RecentRun,
    UpdateFollowRequest,
    WantedItemResponse,
    WantedResponse,
)

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


def _parse_media_ref(media_ref_json: str | None) -> MediaRefResponse:
    """Parse a ``media_ref_json`` column into a :class:`MediaRefResponse`.

    Args:
        media_ref_json: The raw JSON string from the DB, or ``None``.

    Returns:
        A ``MediaRefResponse`` with the parsed fields, or an empty one on
        parse failure / ``None``.
    """
    if not media_ref_json:
        return MediaRefResponse()
    try:
        data = json.loads(media_ref_json)
    except (json.JSONDecodeError, TypeError):
        return MediaRefResponse()
    return MediaRefResponse(
        tvdb_id=data.get("tvdb_id"),
        tmdb_id=data.get("tmdb_id"),
        imdb_id=data.get("imdb_id"),
    )


def _parse_json_dict(raw: str | None) -> dict[str, object] | None:
    """Parse a JSON text column into a dict, or ``None`` on failure.

    Args:
        raw: The raw JSON string from the DB, or ``None``.

    Returns:
        The parsed dict, or ``None``.
    """
    if not raw:
        return None
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, TypeError):
        return None


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

            items: list[FollowedSeriesItem] = []
            for row in rows:
                # COUNT wanted pending for this series.
                pending = conn.execute(
                    "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status IN ('pending', 'searching')",
                    (row["id"],),
                ).fetchone()[0]
                items.append(
                    FollowedSeriesItem(
                        id=row["id"],
                        title=row["title"],
                        media_ref=_parse_media_ref(row["media_ref_json"]),
                        active=bool(row["active"]),
                        cadence=_parse_json_dict(row["cadence_json"]),
                        added_at=float(row["added_at"]),
                        wanted_pending=pending,
                        quality_profile=_parse_json_dict(row["quality_profile_json"]),
                    )
                )
            return FollowedResponse(items=items)
    except sqlite3.Error:
        logger.warning("acquisition_followed_read_failed", exc_info=True)
        return FollowedResponse(items=[])


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


def _query_watcher_recent_runs(db_path: Path) -> list[RecentRun]:
    """Query the last N watcher-triggered pipeline_run rows from library.db.

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
                SELECT run_uid, started_at, ended_at, outcome
                FROM pipeline_run
                WHERE trigger IN ({placeholders})
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
            # Reactivate.
            store.follow.set_active(existing.id, True)
            reactivated = store.follow.get(existing.id)
            assert reactivated is not None  # noqa: S101 — just wrote it
            return _item_from_followed(reactivated)

        # New follow.
        series = FollowedSeries(
            media_ref=media_ref,
            title=title,
            added_at=int(time.time()),
            active=True,
        )
        new_id = store.follow.add(series)
        created = store.follow.get(new_id)
        assert created is not None  # noqa: S101 — just inserted it
        return _item_from_followed(created)
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
