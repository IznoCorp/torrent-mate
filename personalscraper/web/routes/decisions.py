"""Decision queue REST routes (scrape-arbiter feature).

Five endpoints under ``/api/decisions/`` implementing the interactive scraping
decision queue contract defined in ``docs/features/scrape-arbiter/DESIGN.md`` §6:

- ``GET /`` → :class:`DecisionsResponse` — paginated list with orphan GC.
- ``GET /{id}`` → :class:`DecisionDetail` — single decision (404/410).
- ``POST /{id}/search`` → :class:`SearchResponse` — live provider search.
- ``POST /{id}/resolve`` → :class:`ResolveResponse` (202) — launch scraper.
- ``POST /{id}/dismiss`` → :class:`DecisionDetail` — dismiss decision.

All routes are guarded by ``require_session`` inherited from the parent
``guarded_api`` router (registration in app.py).  Auth dependencies are NOT
added per-route — the auth perimeter is a single dependency at registration
time, per ``docs/reference/web-ui.md`` §6 (the single authority for this
convention; R14/R24).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from personalscraper.core.sqlite._pragmas import apply_pragmas as _apply_pragmas
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.scraper.decision_candidate import DecisionCandidate
from personalscraper.scraper.decision_writer import DecisionWriteError, DecisionWriter
from personalscraper.web.decisions.reserve import _reserve_decision_run
from personalscraper.web.decisions.search import ProviderSearchError, search_candidates
from personalscraper.web.deps import (
    is_staging_role,
    require_not_staging,
    require_x_requested_with,
)
from personalscraper.web.models.decisions import (
    DecisionActivityItem,
    DecisionActivityResponse,
    DecisionDetail,
    DecisionListItem,
    DecisionsResponse,
    ResolveRequest,
    ResolveResponse,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/api/decisions", tags=["decisions"])
logger = get_logger(__name__)

#: Maximum page size accepted by the list endpoint.
_MAX_PAGE_SIZE = 200


def _data_dir(request: Request) -> Path:
    """Extract the configured ``data_dir`` from the application state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The absolute ``Path`` to the pipeline data directory.
    """
    return cast(Path, request.app.state.config.paths.data_dir)


def _db_path(request: Request) -> Path:
    """Extract the resolved indexer database path from the application state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The absolute ``Path`` to ``library.db``.
    """
    return cast(Path, request.app.state.config.indexer.db_path)


def _row_to_list_item(row: sqlite3.Row) -> DecisionListItem:
    """Convert a ``scrape_decision`` row to a :class:`DecisionListItem`.

    Computes ``candidates_count`` from the raw JSON string so the caller
    does not need to deserialize the full array.

    Args:
        row: A ``sqlite3.Row`` from the ``scrape_decision`` table.

    Returns:
        A :class:`DecisionListItem` populated from the row.
    """
    try:
        candidates = json.loads(row["candidates_json"])
        candidates_count = len(candidates) if isinstance(candidates, list) else 0
    except (json.JSONDecodeError, TypeError):
        candidates_count = 0

    return DecisionListItem(
        id=row["id"],
        staging_path=row["staging_path"],
        media_kind=row["media_kind"],
        extracted_title=row["extracted_title"],
        extracted_year=row["extracted_year"],
        trigger=row["trigger"],
        candidates_count=candidates_count,
        status=row["status"],
        created_at=row["created_at"],
    )


def _row_to_detail(row: sqlite3.Row) -> DecisionDetail:
    """Convert a ``scrape_decision`` row to a :class:`DecisionDetail`.

    Deserializes ``candidates_json`` into a ``list[DecisionCandidate]`` and
    ``resolution_json`` into a ``dict`` (or ``None``).

    Args:
        row: A ``sqlite3.Row`` from the ``scrape_decision`` table.

    Returns:
        A :class:`DecisionDetail` populated from the row.
    """
    try:
        raw = json.loads(row["candidates_json"])
        candidates = [DecisionCandidate(**c) for c in raw] if isinstance(raw, list) else []
    except (json.JSONDecodeError, TypeError):
        candidates = []

    resolution: dict[str, object] | None = None
    if row["resolution_json"]:
        try:
            resolution = json.loads(row["resolution_json"])
        except json.JSONDecodeError:
            resolution = None

    return DecisionDetail(
        id=row["id"],
        staging_path=row["staging_path"],
        media_kind=row["media_kind"],
        extracted_title=row["extracted_title"],
        extracted_year=row["extracted_year"],
        trigger=row["trigger"],
        candidates_count=len(candidates),
        status=row["status"],
        created_at=row["created_at"],
        candidates=candidates,
        resolution_json=resolution,
    )


def _fetch_decision_row(db_path: Path, decision_id: int) -> sqlite3.Row:
    """Fetch a single ``scrape_decision`` row by id, raising 404 when absent.

    Args:
        db_path: Absolute path to ``library.db``.
        decision_id: Primary key of the decision row.

    Returns:
        The ``sqlite3.Row`` for the requested decision.

    Raises:
        HTTPException: 404 when the row does not exist.
    """
    with closing(sqlite3.connect(str(db_path))) as conn:
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scrape_decision WHERE id = ?", (decision_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        return cast(sqlite3.Row, row)


def _guard_not_superseded(row: sqlite3.Row) -> None:
    """Raise 410 when the decision row has status ``'superseded'``.

    Args:
        row: A ``sqlite3.Row`` from the ``scrape_decision`` table.

    Raises:
        HTTPException: 410 when ``status == 'superseded'``.
    """
    if row["status"] == "superseded":
        raise HTTPException(status_code=410, detail="Decision has been superseded")


# ── GET / ────────────────────────────────────────────────────────────────────


@router.get("/", response_model=DecisionsResponse)
def list_decisions(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_MAX_PAGE_SIZE),
    status: Literal["pending", "resolved", "dismissed", "superseded"] = "pending",
) -> DecisionsResponse:
    """Return a paginated list of scrape decisions.

    Runs :meth:`DecisionWriter.mark_superseded_orphans` before querying so
    rows whose staging path no longer exists are garbage-collected to
    ``'superseded'`` before the list is built — **except on the read-only
    staging instance**, where a GET must not mutate the shared prod DB
    (ENV-SEP, coherence study F04).

    The query params are OpenAPI-constrained (``page >= 1``,
    ``1 <= page_size <= 200``, ``status`` a closed enum) so the typed frontend
    contract can reject an out-of-range value at compile time and the backend
    returns 422 on an invalid one (F42) instead of silently clamping.

    Args:
        request: The incoming FastAPI request.
        page: 1-indexed page number (default 1, >= 1).
        page_size: Items per page (default 50, 1..200).
        status: Filter by status (default ``'pending'``).

    Returns:
        A :class:`DecisionsResponse` with items, ``pending_count``,
        ``total``, ``page``, and ``page_size``.
    """
    db_path = _db_path(request)

    # 1. Garbage-collect orphans before querying — prod only.  On staging this
    #    GET must stay side-effect-free (shared library.db is prod-owned; F04).
    if db_path.exists() and not is_staging_role():
        DecisionWriter(db_path).mark_superseded_orphans()

    if not db_path.exists():
        return DecisionsResponse(items=[], pending_count=0, total=0, page=page, page_size=page_size)

    with closing(sqlite3.connect(str(db_path))) as conn:
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row

        # 2. Always compute pending_count (independent of status filter).
        pending_row = conn.execute("SELECT COUNT(*) FROM scrape_decision WHERE status = 'pending'").fetchone()
        pending_count: int = pending_row[0] if pending_row else 0

        # 3. Count + fetch filtered rows.
        total_row = conn.execute(
            "SELECT COUNT(*) FROM scrape_decision WHERE status = ?",
            (status,),
        ).fetchone()
        total: int = total_row[0] if total_row else 0

        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM scrape_decision WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, page_size, offset),
        ).fetchall()

    items = [_row_to_list_item(r) for r in rows]
    return DecisionsResponse(
        items=items,
        pending_count=pending_count,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /activity ────────────────────────────────────────────────────────────


@router.get("/activity", response_model=DecisionActivityResponse)
def decision_activity(request: Request) -> DecisionActivityResponse:
    """Live scraping activity — the scrapes running now + the pending queue size.

    Reuses data that already exists: each resolve reserves a ``pipeline_run`` row
    (``command='scrape-resolve'``); a row with no ``ended_at`` is a scrape in flight.
    The queue size is the count of ``pending`` decisions. No new state is written —
    this is the read surface the operator was missing next to true-parallel scraping
    (product-intent.md §3: the file/scrapes-in-progress must be visible).

    Args:
        request: The incoming FastAPI request.

    Returns:
        A :class:`DecisionActivityResponse` with the in-progress scrapes and the
        pending-queue count.
    """
    db_path = _db_path(request)
    if not db_path.exists():
        return DecisionActivityResponse(in_progress=[], pending_count=0)

    in_progress: list[DecisionActivityItem] = []
    with closing(sqlite3.connect(str(db_path))) as conn:
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row

        runs = conn.execute(
            "SELECT started_at, options_json FROM pipeline_run "
            "WHERE command = 'scrape-resolve' AND ended_at IS NULL "
            "ORDER BY started_at DESC"
        ).fetchall()
        for run in runs:
            try:
                options = json.loads(run["options_json"]) if run["options_json"] else {}
            except (json.JSONDecodeError, TypeError):
                options = {}
            decision_id = options.get("decision_id")
            if not isinstance(decision_id, int):
                continue
            drow = conn.execute(
                "SELECT extracted_title FROM scrape_decision WHERE id = ?",
                (decision_id,),
            ).fetchone()
            in_progress.append(
                DecisionActivityItem(
                    decision_id=decision_id,
                    title=drow["extracted_title"] if drow else "?",
                    started_at=run["started_at"],
                )
            )

        pending_row = conn.execute("SELECT COUNT(*) FROM scrape_decision WHERE status = 'pending'").fetchone()
        pending_count: int = pending_row[0] if pending_row else 0

    return DecisionActivityResponse(in_progress=in_progress, pending_count=pending_count)


# ── GET /{id} ────────────────────────────────────────────────────────────────


@router.get("/{decision_id}", response_model=DecisionDetail)
def get_decision(
    decision_id: int,
    request: Request,
) -> DecisionDetail:
    """Return full detail for a single scrape decision.

    Args:
        decision_id: Primary key of the ``scrape_decision`` row.
        request: The incoming FastAPI request.

    Returns:
        A :class:`DecisionDetail` with the full candidate list and
        optional resolution metadata.

    Raises:
        404: The decision does not exist.
        410: The decision has status ``'superseded'``.
    """
    db_path = _db_path(request)
    row = _fetch_decision_row(db_path, decision_id)
    _guard_not_superseded(row)
    return _row_to_detail(row)


# ── POST /{id}/search ────────────────────────────────────────────────────────


@router.post("/{decision_id}/search", response_model=SearchResponse)
def search_decision(
    decision_id: int,
    body: SearchRequest,
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
) -> SearchResponse:
    """Search live providers for candidate matches.

    Read-only — no state change.  Creates per-request provider clients
    and delegates to the detailed confidence matchers
    (:func:`~personalscraper.scraper.confidence.match_movie_detailed` or
    :func:`~personalscraper.scraper.confidence.match_tvshow_detailed`) to
    build a fresh candidate list.  The existing decision row is read only
    to determine ``media_kind``; the search title/year come from the
    request body so the operator can correct the extracted guess.

    Args:
        decision_id: Primary key of the ``scrape_decision`` row.
        body: Search request with ``title`` and optional ``year``.
        request: The incoming FastAPI request.

    Returns:
        A :class:`SearchResponse` with fresh provider candidates.

    Raises:
        404: The decision does not exist.
        410: The decision has status ``'superseded'``.
        502: Provider API failure or client build failure.
    """
    db_path = _db_path(request)
    row = _fetch_decision_row(db_path, decision_id)
    _guard_not_superseded(row)

    media_kind: str = row["media_kind"]

    try:
        candidates = search_candidates(request, media_kind, body.title, body.year)
    except ProviderSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SearchResponse(candidates=candidates)


# ── POST /{id}/resolve helpers ───────────────────────────────────────────────


def _spawn_decision_runner(
    run_uid: str,
    decision_id: int,
    provider: str,
    provider_id: int,
    via: str,
) -> int:
    """Spawn the decision runner as a detached subprocess.

    The runner module (``personalscraper.web.decisions.runner``) reads its
    configuration from the environment variables set here.  It is
    responsible for executing ``scrape-resolve``, streaming output, and
    finalizing the ``pipeline_run`` row (reserved by the caller).

    Args:
        run_uid: The unique run identifier (``uuid4().hex``).
        decision_id: The ``scrape_decision.id`` being resolved.
        provider: Metadata provider name (``'tmdb'`` or ``'tvdb'``).
        provider_id: Numeric identifier assigned by the provider.
        via: Resolution provenance (``'pick'`` or ``'search_override'``),
            threaded to the CLI so ``resolution_json.via`` is accurate (F09).

    Returns:
        The pid of the spawned runner process.
    """
    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_DECISION_ID": str(decision_id),
        "PERSONALSCRAPER_DECISION_PROVIDER": provider,
        "PERSONALSCRAPER_DECISION_PROVIDER_ID": str(provider_id),
        "PERSONALSCRAPER_DECISION_VIA": via,
    }
    logger.info(
        "decision_resolve_spawned",
        run_uid=run_uid,
        decision_id=decision_id,
        provider=provider,
        provider_id=provider_id,
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "personalscraper.web.decisions.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid


def _finalize_fail_soft(db_path: Path, run_uid: str, error: str) -> None:
    """Finalize a reserved ``pipeline_run`` row 'error', fail-soft on DB error.

    The finalize on the resolve error/spawn-fail paths must NEVER let a raising
    ``PipelineRunWriter.finalize`` (contended DB) leave the reserved ``running``
    row behind: that row carries the long-lived web-process pid, which is live, so
    the next resolve's ``_guard_no_running_resolve`` would see it and return a
    PERMANENT 409 for that decision (SF3).  A finalize failure is logged as a
    warning and swallowed so the intended HTTP response still fires — the worst
    case degrades to a stale ``running`` row that the next resolve reclaims,
    never a permanent block from THIS request.

    Args:
        db_path: Absolute path to ``library.db``.
        run_uid: The reserved run's unique identifier.
        error: The error string to persist on the finalized row.
    """
    try:
        PipelineRunWriter(db_path).finalize(run_uid, "error", error=error)
    except sqlite3.Error as exc:
        logger.warning(
            "decision_resolve_finalize_failed",
            run_uid=run_uid,
            error=str(exc),
        )


# ── POST /{id}/resolve ───────────────────────────────────────────────────────


@router.post("/{decision_id}/resolve", response_model=ResolveResponse, status_code=202)
def resolve_decision(
    decision_id: int,
    body: ResolveRequest,
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
) -> ResolveResponse:
    """Launch a targeted re-scrape for a decision.

    Mirrors ``POST /api/maintenance/actions/{action_id}/run``: validates
    preconditions (pipeline lock, concurrent resolve), reserves a
    ``pipeline_run`` row atomically, re-probes the lock, spawns the runner
    subprocess, and returns ``202`` with the ``run_uid``.

    Args:
        decision_id: Primary key of the ``scrape_decision`` row.
        body: The request payload with ``provider`` and ``provider_id``.
        request: The incoming FastAPI request (for ``app.state`` access).

    Returns:
        ``202`` with :class:`ResolveResponse` (``{"run_uid": "..."}``).

    Concurrency (webui-ux phase 4): two DIFFERENT decisions resolve concurrently
    (both 202) — the reservation guard is scoped to THIS ``decision_id``.  409
    fires only when THIS decision is already resolving, or when a GLOBAL pipeline
    holder (full run / maintenance) owns ``pipeline.lock`` — resolves are excluded
    from those, so they must not start while one is mid-dispatch.

    Raises:
        404: The decision does not exist.
        410: The decision has status ``'superseded'``.
        409: The decision is not ``'pending'`` (already resolved / dismissed),
            a GLOBAL pipeline lock is held (full run / maintenance), or THIS
            decision is already resolving.
        500: The runner subprocess failed to spawn.
    """
    db_path = _db_path(request)
    data_dir = _data_dir(request)

    # 1. Fetch + guard the decision row.  Reject a non-pending decision here
    #    (409) rather than accepting a 202 whose run fails asynchronously with
    #    an "expected 'pending'" error (F34/F46).
    row = _fetch_decision_row(db_path, decision_id)
    _guard_not_superseded(row)
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Decision is '{row['status']}', not 'pending'")

    # 2. Pipeline-lock 409 (mirrors maintenance action_run).  A scrape-resolve
    #    writes to staging, so it must not run while the pipeline holds the lock.
    if is_lock_held(data_dir / "pipeline.lock"):
        raise HTTPException(status_code=409, detail="Pipeline lock held")

    run_uid = uuid.uuid4().hex

    # 3. Atomic per-decision concurrency-409 + reserve the running row under
    #    BEGIN IMMEDIATE (closes the check→insert race so a second concurrent
    #    resolve POST FOR THE SAME decision sees the freshly-inserted running row
    #    and gets 409).  A resolve of a DIFFERENT decision is not blocked — the
    #    guard is scoped to decision_id (webui-ux phase 4). Same-staging-path
    #    exclusivity across two decision rows is enforced one layer down by the
    #    CLI's per-item scrape lock (acquire_scrape_resolve_lock).
    _reserve_decision_run(
        db_path,
        run_uid=run_uid,
        decision_id=decision_id,
        provider=body.provider,
        provider_id=body.provider_id,
    )

    # 4. Re-probe the pipeline lock after the reservation (R11): a pipeline run
    #    may grab the lock between the step-2 probe and here.  Finalize the
    #    reserved row 'error' + 409 rather than returning 202 whose run would
    #    immediately fail.  The finalize is fail-soft (SF3): a raising finalize
    #    (contended DB) must NOT keep the reserved row 'running' with the
    #    long-lived web-process pid — that pid is live, so _guard_no_running_resolve
    #    would see it and PERMANENTLY 409 this decision.  Log + still raise the 409.
    if is_lock_held(data_dir / "pipeline.lock"):
        _finalize_fail_soft(db_path, run_uid, "Pipeline lock held")
        raise HTTPException(status_code=409, detail="Pipeline lock held")

    # 5. Spawn the runner and claim the reserved row with its pid, so a runner
    #    that dies before finalizing leaves a dead-pid (stale) row rather than a
    #    live-pid (permanently blocking) one.  A spawn failure finalizes the
    #    reserved row 'error' so it never stays 'running' (fail-soft — SF3).
    try:
        pid = _spawn_decision_runner(run_uid, decision_id, body.provider, body.provider_id, body.via)
    except (OSError, ValueError) as exc:
        _finalize_fail_soft(db_path, run_uid, str(exc))
        logger.error(
            "decision_resolve_spawn_failed",
            run_uid=run_uid,
            decision_id=decision_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Failed to spawn decision runner") from exc
    if isinstance(pid, int):
        # Fail-soft (SF3): a raising update_pid must not abort the 202 — the row is
        # already reserved and the runner will (re)claim its own pid on start.
        try:
            PipelineRunWriter(db_path).update_pid(run_uid, pid)
        except sqlite3.Error as exc:
            logger.warning(
                "decision_resolve_update_pid_failed",
                run_uid=run_uid,
                decision_id=decision_id,
                error=str(exc),
            )

    return ResolveResponse(run_uid=run_uid)


# ── POST /{id}/dismiss ───────────────────────────────────────────────────────


@router.post("/{decision_id}/dismiss", response_model=DecisionDetail)
def dismiss_decision(
    decision_id: int,
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
) -> DecisionDetail:
    """Dismiss a decision (manual or MediaElch path).

    Marks the decision ``'dismissed'`` via :meth:`DecisionWriter.dismiss`.
    Returns the refreshed :class:`DecisionDetail` so the UI can update its
    row without an extra round-trip.

    Args:
        decision_id: Primary key of the ``scrape_decision`` row.
        request: The incoming FastAPI request.

    Returns:
        The refreshed :class:`DecisionDetail` with ``status='dismissed'``.

    Raises:
        404: The decision does not exist.
        409: The decision is not ``'pending'`` (already resolved / dismissed).
        410: The decision has status ``'superseded'``.
        500: The dismiss write failed at the DB layer.
    """
    db_path = _db_path(request)

    # 1. Fetch + guard the decision row (before mutating so 404/410 fire first).
    row = _fetch_decision_row(db_path, decision_id)
    _guard_not_superseded(row)
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Decision is '{row['status']}', not 'pending'")

    # 2. Dismiss (pending-only at the writer layer; fail-loud on DB error).
    try:
        dismissed = DecisionWriter(db_path).dismiss(decision_id)
    except DecisionWriteError as exc:
        logger.error("decision_dismiss_failed", decision_id=decision_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to dismiss decision") from exc
    if not dismissed:
        # Lost a race with a concurrent resolve/dismiss between the guard and
        # the write — surface it rather than returning a stale 200.
        raise HTTPException(status_code=409, detail="Decision is no longer pending")

    # 3. Re-fetch the refreshed row for the response.
    refreshed = _fetch_decision_row(db_path, decision_id)
    return _row_to_detail(refreshed)
