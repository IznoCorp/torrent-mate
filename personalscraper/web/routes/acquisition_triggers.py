"""Acquisition trigger routes — manual detect + per-series grab (OBJ3 / §5).

Extracted from ``web/routes/acquisition.py`` to keep that module under the
1000-LOC ceiling (same precedent as ``web/acquisition/_helpers.py``). Both
routers share the ``/api/acquisition`` prefix and are registered side by side
under the single ``guarded_api`` perimeter in ``app.py``.
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
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from personalscraper.acquire.store import build_acquire_store
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.deps import require_not_staging, require_x_requested_with
from personalscraper.web.models.acquisition import GrabTriggerResponse

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])
logger = get_logger(__name__)


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
