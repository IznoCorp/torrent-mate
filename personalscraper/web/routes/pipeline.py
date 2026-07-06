"""Pipeline control REST routes (pipe-control feature).

Six routes under ``/api/pipeline/*`` guarded by ``require_session`` and
(for mutating POSTs) ``X-Requested-With: TorrentMate``.  See
docs/features/pipe-control/DESIGN.md §4 for the full route contract.
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.web.deps import (
    Session,
    require_session,
    require_x_requested_with,
)
from personalscraper.web.models.pipeline import (
    PipelineState,
    RunRequest,
    RunResponse,
    StatusResponse,
    WatcherRequest,
    WatcherResponse,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])
logger = get_logger(__name__)


def _build_status(data_dir: Path, db_path: Path) -> StatusResponse:
    """Build a :class:`StatusResponse` from the filesystem sentinels and DB.

    Reads the lock file, pause sentinel, and watcher sentinel from
    *data_dir*, then queries the latest ``pipeline_run`` row from the
    indexer database at *db_path* for the active run's metadata.

    Args:
        data_dir: The configured ``paths.data_dir`` (contains sentinels).
        db_path: Absolute path to the indexer SQLite database.

    Returns:
        A fully populated ``StatusResponse``.
    """
    lock_path = data_dir / "pipeline.lock"
    pause_path = data_dir / "pipeline.pause"
    watcher_paused_path = data_dir / "watcher.paused"

    lock_held = is_lock_held(lock_path)
    paused = pause_path.exists()
    watcher_enabled = not watcher_paused_path.exists()

    if lock_held:
        state = PipelineState.paused if paused else PipelineState.running
    else:
        state = PipelineState.idle

    pid: int | None = None
    run_uid: str | None = None
    step: str | None = None

    if lock_held:
        # Read the PID from the lock file (guarded — is_lock_held already
        # confirmed the file exists and contains a valid PID).
        try:
            pid = int(lock_path.read_text().strip())
        except (ValueError, OSError):
            pid = None

        # Query the latest pipeline_run row for run_uid + current step.
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT run_uid, steps_json FROM pipeline_run ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if row is not None:
                run_uid = row["run_uid"]
                steps_raw = row["steps_json"]
                if steps_raw:
                    try:
                        steps = json.loads(steps_raw)
                        # The current step is the last one in the array.
                        if isinstance(steps, list) and steps:
                            step = steps[-1].get("name")
                    except (json.JSONDecodeError, TypeError, KeyError):
                        pass
        except sqlite3.Error:
            logger.warning("pipeline_status_db_read_failed", exc_info=True)

    return StatusResponse(
        state=state,
        run_uid=run_uid,
        step=step,
        paused=paused,
        watcher_enabled=watcher_enabled,
        pid=pid,
    )


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


@router.post("/run")
def pipeline_run(
    request: Request,
    body: RunRequest,
    _session: Session = Depends(require_session),
    _xrw: None = Depends(require_x_requested_with),
) -> JSONResponse:
    """Launch a new pipeline run as a detached subprocess.

    Returns ``202 {run_uid}`` on success, or ``409`` if the pipeline lock
    is already held by another process.
    """
    data_dir = _data_dir(request)
    if is_lock_held(data_dir / "pipeline.lock"):
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    run_uid = uuid.uuid4().hex
    cmd = [
        sys.executable,
        "-m",
        "personalscraper",
        "run",
        "--no-console",
        "--trigger-reason=web",
    ]
    if body.dry_run:
        cmd.append("--dry-run")

    logger.info("pipeline_run_spawned", run_uid=run_uid, dry_run=body.dry_run)
    subprocess.Popen(
        cmd,
        start_new_session=True,
        env={**os.environ, "PERSONALSCRAPER_RUN_UID": run_uid},
    )
    return JSONResponse(status_code=202, content=RunResponse(run_uid=run_uid).model_dump())


@router.post("/pause")
def pipeline_pause(
    request: Request,
    _session: Session = Depends(require_session),
    _xrw: None = Depends(require_x_requested_with),
) -> StatusResponse:
    """Create the ``pipeline.pause`` sentinel to pause the running pipeline.

    No-op if no pipeline is currently running (the sentinel is still
    created — it will be honoured on the next run, which is harmless since
    a fresh run clears it).

    Returns the current pipeline status.
    """
    data_dir = _data_dir(request)
    (data_dir / "pipeline.pause").touch()
    logger.info("pipeline_pause_requested")
    return _build_status(data_dir, _db_path(request))


@router.post("/resume")
def pipeline_resume(
    request: Request,
    _session: Session = Depends(require_session),
    _xrw: None = Depends(require_x_requested_with),
) -> StatusResponse:
    """Remove the ``pipeline.pause`` sentinel to resume a paused pipeline.

    Returns the current pipeline status.
    """
    data_dir = _data_dir(request)
    (data_dir / "pipeline.pause").unlink(missing_ok=True)
    logger.info("pipeline_resume_requested")
    return _build_status(data_dir, _db_path(request))


@router.post("/kill")
def pipeline_kill(
    request: Request,
    _session: Session = Depends(require_session),
    _xrw: None = Depends(require_x_requested_with),
) -> StatusResponse:
    """Kill the running pipeline subprocess with SIGTERM.

    Reads the PID from ``pipeline.lock``, sends ``SIGTERM``, and clears
    the pause sentinel.  The run process releases the lock and finalizes
    its history row as ``killed`` on its way out.

    Returns the current pipeline status (fail-soft: if the lock is absent
    or unreadable, returns the idle status without error).
    """
    data_dir = _data_dir(request)
    lock_path = data_dir / "pipeline.lock"

    try:
        pid = int(lock_path.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        # No lock or unreadable — nothing to kill.
        return _build_status(data_dir, _db_path(request))

    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("pipeline_kill_signalled", pid=pid)
    except ProcessLookupError:
        logger.info("pipeline_kill_process_gone", pid=pid)
    except PermissionError:
        logger.warning("pipeline_kill_permission_denied", pid=pid)

    # Clear the pause sentinel so a subsequent run is not blocked.
    (data_dir / "pipeline.pause").unlink(missing_ok=True)

    return _build_status(data_dir, _db_path(request))


@router.post("/watcher")
def pipeline_watcher(
    request: Request,
    body: WatcherRequest,
    _session: Session = Depends(require_session),
    _xrw: None = Depends(require_x_requested_with),
) -> WatcherResponse:
    """Enable or pause the directory watcher daemon.

    When *enabled* is ``True`` the ``watcher.paused`` sentinel is removed
    (watcher runs).  When ``False`` the sentinel is created (watcher pauses).
    This is independent of the pipeline run itself — pausing the watcher
    only prevents the daemon from auto-starting new runs.

    Args:
        request: The incoming FastAPI request.
        body: The watcher toggle payload with ``enabled: bool``.

    Returns:
        The watcher state reflecting the requested change.
    """
    data_dir = _data_dir(request)
    sentinel = data_dir / "watcher.paused"
    if body.enabled:
        sentinel.unlink(missing_ok=True)
    else:
        sentinel.touch()
    logger.info("pipeline_watcher_toggled", enabled=body.enabled)
    return WatcherResponse(watcher_enabled=body.enabled)


@router.get("/status")
def pipeline_status(
    request: Request,
    _session: Session = Depends(require_session),
) -> StatusResponse:
    """Return the live pipeline status.

    Reads the lock, pause sentinel, watcher sentinel, and the latest
    ``pipeline_run`` database row to compose a full status snapshot.
    This is the only route in the group that does **not** require the
    ``X-Requested-With`` header (it is a read-only GET).

    Returns:
        A ``StatusResponse`` with the current pipeline state and metadata.
    """
    return _build_status(_data_dir(request), _db_path(request))
