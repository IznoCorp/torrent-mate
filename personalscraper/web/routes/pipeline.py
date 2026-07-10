"""Pipeline control REST routes (pipe-control feature).

Six routes under ``/api/pipeline/*`` guarded by ``require_session`` and
(for mutating POSTs) ``X-Requested-With: TorrentMate``.  See
docs/features/pipe-control/DESIGN.md §4 for the full route contract.

The ``require_session`` guard is inherited from the parent ``guarded_api``
router (registration in app.py) — auth dependencies are NOT added per-route,
per ``docs/reference/web-ui.md`` §6 (the single authority for this
convention; R14/R24).
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from personalscraper.core.sqlite._pragmas import apply_pragmas as _apply_pragmas
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.web.deps import (
    require_not_staging,
    require_x_requested_with,
)
from personalscraper.web.models.pipeline import (
    HistoryResponse,
    PipelineOutcome,
    PipelineState,
    RunDetail,
    RunRequest,
    RunResponse,
    RunSummary,
    StatusResponse,
    StepTiming,
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

        # Query the most recent RUNNING pipeline_run row for run_uid + current
        # step (R29): the lock holder is the run still marked 'running'. The
        # bare latest row may be an unrelated finished run — or, now that
        # write/destructive maintenance actions hold the lock (R11), a
        # maintenance row — started after the actual lock holder.
        # ``with closing(...)`` releases the SQLite handle deterministically
        # instead of relying on refcount finalization (R19).
        try:
            with closing(sqlite3.connect(str(db_path))) as conn:
                _apply_pragmas(conn)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT run_uid, steps_json FROM pipeline_run "
                    "WHERE outcome = 'running' ORDER BY started_at DESC LIMIT 1"
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


def _newest_running_kind(db_path: Path) -> str | None:
    """Return the ``kind`` of the newest still-running ``pipeline_run`` row.

    The lock holder is the run whose ``outcome`` is still ``'running'``.  Its
    ``kind`` distinguishes a real pipeline run (``'pipeline'`` / ``NULL``) from
    a maintenance run (``'maintenance'`` — e.g. a ``scrape-resolve`` resolution
    that self-acquired the lock, R11).  Used by :func:`pipeline_kill` to refuse
    to SIGTERM a maintenance child (which would record ``'error'`` on its way
    out, not ``'killed'`` — F32).

    Args:
        db_path: Absolute path to the indexer SQLite database.

    Returns:
        The ``kind`` string of the newest running row (``'pipeline'`` when the
        column is ``NULL``), or ``None`` when there is no running row or the
        database read fails (fail-soft — the caller proceeds with the kill).
    """
    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            _apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT kind FROM pipeline_run WHERE outcome = 'running' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        logger.warning("pipeline_kill_kind_read_failed", exc_info=True)
        return None
    if row is None:
        return None
    return row["kind"] if row["kind"] is not None else "pipeline"


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


@router.post("/run", response_model=RunResponse, status_code=202)
def pipeline_run(
    request: Request,
    body: RunRequest,
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
) -> RunResponse:
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
    return RunResponse(run_uid=run_uid)


@router.post("/pause")
def pipeline_pause(
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
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
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
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
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
) -> StatusResponse:
    """Kill the running pipeline subprocess with SIGTERM.

    Reads the PID from ``pipeline.lock``, sends ``SIGTERM``, and clears
    the pause sentinel.  The run process releases the lock and finalizes
    its history row as ``killed`` on its way out.

    Refuses (409) when the lock is held by a *maintenance* run (e.g. a
    ``scrape-resolve`` resolution that self-acquired the lock, R11): this
    endpoint targets pipeline runs, and SIGTERMing a maintenance child would
    record its history row as ``error`` rather than ``killed`` (F32).  Such a
    run must be stopped from its own surface.

    Returns the current pipeline status (fail-soft: if the lock is absent
    or unreadable, returns the idle status without error).
    """
    data_dir = _data_dir(request)
    lock_path = data_dir / "pipeline.lock"
    db_path = _db_path(request)

    # A maintenance run (kind='maintenance') holding the lock is not a pipeline
    # run — refuse rather than SIGTERM it under the wrong outcome (F32).
    if _newest_running_kind(db_path) == "maintenance":
        raise HTTPException(
            status_code=409,
            detail=(
                "A maintenance run (e.g. scrape-resolve) holds the pipeline "
                "lock; it cannot be killed from the pipeline endpoint."
            ),
        )

    try:
        pid = int(lock_path.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        # No lock or unreadable — nothing to kill.
        return _build_status(data_dir, db_path)

    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("pipeline_kill_signalled", pid=pid)
    except ProcessLookupError:
        logger.info("pipeline_kill_process_gone", pid=pid)
    except PermissionError:
        logger.warning("pipeline_kill_permission_denied", pid=pid)

    # Clear the pause sentinel so a subsequent run is not blocked.
    (data_dir / "pipeline.pause").unlink(missing_ok=True)

    return _build_status(data_dir, db_path)


@router.post("/watcher")
def pipeline_watcher(
    request: Request,
    body: WatcherRequest,
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
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


# ── History route helpers ────────────────────────────────────────────────────

_ALLOWED_SORTS = frozenset({"started_at", "-started_at", "duration", "-duration"})
_ALLOWED_KINDS = frozenset({"pipeline", "maintenance", "all"})

_SORT_COLUMN_MAP: dict[str, str] = {
    "started_at": "started_at ASC",
    "-started_at": "started_at DESC",
    "duration": ("CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END, (ended_at - started_at) ASC"),
    "-duration": ("CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END, (ended_at - started_at) DESC"),
}


def _opt_int(value: object) -> int | None:
    """Coerce a ``steps_json`` summary field to ``int`` or ``None`` (fail-soft).

    Legacy entries (pre-webui-ux Phase 2.2) lack the count fields, so ``None``
    passes through untouched. A malformed non-numeric value is treated as
    absent rather than raising — a corrupt summary must never 500 the detail
    read.

    Args:
        value: The raw value pulled from a ``steps_json`` entry (may be ``None``).

    Returns:
        The value as an ``int``, or ``None`` when absent/uncoercible.
    """
    if isinstance(value, bool):
        # bool is an int subclass; a JSON true/false is not a valid count.
        return None
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _opt_counts(value: object) -> dict[str, int] | None:
    """Coerce a ``steps_json`` ``counts`` field to ``dict[str, int]`` or ``None``.

    Only a JSON object with integer-coercible values survives; anything else
    (absent, wrong type, uncoercible members) yields ``None`` so a legacy or
    malformed entry never breaks the typed response.

    Args:
        value: The raw ``counts`` value from a ``steps_json`` entry.

    Returns:
        A ``dict[str, int]`` of the sub-category counters, or ``None``.
    """
    if not isinstance(value, dict):
        return None
    coerced: dict[str, int] = {}
    for key, raw in value.items():
        as_int = _opt_int(raw)
        if as_int is not None:
            coerced[str(key)] = as_int
    return coerced or None


def _row_to_run_summary(row: sqlite3.Row) -> RunSummary:
    """Map a ``pipeline_run`` row to a :class:`RunSummary`.

    Converts ``started_at`` / ``ended_at`` (REAL unix timestamps) to ISO 8601
    UTC strings and computes ``duration_s`` as their difference when both are
    set.  The ``outcome`` column is parsed into :class:`PipelineOutcome`; an
    unrecognized value is silently mapped to ``None``.

    Args:
        row: A ``sqlite3.Row`` from the ``pipeline_run`` table.

    Returns:
        A populated ``RunSummary``.
    """
    started_at = datetime.fromtimestamp(row["started_at"], tz=timezone.utc).isoformat()
    ended_at: str | None = None
    duration_s: float | None = None

    if row["ended_at"] is not None:
        ended_at = datetime.fromtimestamp(row["ended_at"], tz=timezone.utc).isoformat()
        duration_s = row["ended_at"] - row["started_at"]

    outcome: PipelineOutcome | None = None
    if row["outcome"] is not None:
        try:
            outcome = PipelineOutcome(row["outcome"])
        except ValueError:
            pass

    return RunSummary(
        run_uid=row["run_uid"],
        trigger=row["trigger"],
        dry_run=bool(row["dry_run"]),
        started_at=started_at,
        ended_at=ended_at,
        outcome=outcome,
        duration_s=duration_s,
        kind=row["kind"] if row["kind"] is not None else "pipeline",
        command=row["command"],
    )


# ── GET /history ─────────────────────────────────────────────────────────────


@router.get("/history")
def pipeline_history(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    sort: str = "-started_at",
    kind: str = "all",
) -> HistoryResponse:
    """Return paginated pipeline run history.

    Opens a fresh read-only connection to the indexer database on every
    request.  The database uses WAL mode so concurrent reads are safe.

    Args:
        request: The incoming FastAPI request.
        limit: Maximum number of runs to return (default 50).
        offset: Number of runs to skip (default 0).
        sort: Sort order — one of ``started_at``, ``-started_at``,
            ``duration``, ``-duration`` (default ``-started_at``).
        kind: Run kind filter — one of ``"pipeline"``, ``"maintenance"``,
            or ``"all"`` (default ``"all"``).

    Returns:
        A ``HistoryResponse`` with the requested page of run summaries.
        ``total`` reflects the filtered count, not the full table.

    Raises:
        HTTPException: 400 if *sort* or *kind* is not one of the
            allowed values.
    """
    if sort not in _ALLOWED_SORTS:
        raise HTTPException(
            status_code=400,
            detail=(f"Invalid sort '{sort}'. Allowed: {', '.join(sorted(_ALLOWED_SORTS))}"),
        )
    if kind not in _ALLOWED_KINDS:
        raise HTTPException(
            status_code=400,
            detail=(f"Invalid kind '{kind}'. Allowed: {', '.join(sorted(_ALLOWED_KINDS))}"),
        )

    db_path = _db_path(request)
    order_clause = _SORT_COLUMN_MAP[sort]

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            _apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            total_row = conn.execute(
                "SELECT COUNT(*) FROM pipeline_run WHERE (? = 'all' OR kind = ?)",
                (kind, kind),
            ).fetchone()
            total = total_row[0] if total_row else 0

            rows = conn.execute(
                f"SELECT run_uid, trigger, dry_run, started_at, ended_at, "
                f"outcome, kind, command FROM pipeline_run "
                f"WHERE (? = 'all' OR kind = ?) "
                f"ORDER BY {order_clause} LIMIT ? OFFSET ?",
                (kind, kind, limit, offset),
            ).fetchall()

            runs = [_row_to_run_summary(row) for row in rows]
    except sqlite3.OperationalError:
        # DB file missing or corrupt — return empty history.
        return HistoryResponse(runs=[], total=0)

    return HistoryResponse(runs=runs, total=total)


# ── GET /history/{run_uid} ───────────────────────────────────────────────────


@router.get("/history/{run_uid}")
def pipeline_history_detail(
    run_uid: str,
    request: Request,
) -> RunDetail:
    """Return the full detail for a single pipeline run.

    Parses the ``steps_json`` column into per-step timing records.

    Args:
        run_uid: The unique run identifier.
        request: The incoming FastAPI request.

    Returns:
        A ``RunDetail`` with step timings parsed from ``steps_json``.

    Raises:
        HTTPException: 404 if no run with the given *run_uid* exists; 500 if the
            database read fails (un-migrated / locked DB) — a genuine operational
            error must not masquerade as "run not found".
    """
    db_path = _db_path(request)

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            _apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT run_uid, trigger, dry_run, started_at, ended_at, "
                "outcome, steps_json, error, kind, command, options_json, output_tail "
                "FROM pipeline_run WHERE run_uid = ?",
                (run_uid,),
            ).fetchone()
    except sqlite3.OperationalError as exc:
        # A DB error (missing / un-migrated table, locked DB) is NOT "not
        # found" — surface it as a 500 so a broken DB is never reported as a
        # bogus 404 for every run (Finding F). Logged at ERROR.
        logger.error("pipeline_history_detail_db_error", run_uid=run_uid, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error reading run '{run_uid}'") from exc

    if row is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_uid}' not found")

    summary = _row_to_run_summary(row)

    steps: list[StepTiming] = []
    if row["steps_json"]:
        try:
            raw_steps = json.loads(row["steps_json"])
            if isinstance(raw_steps, list):
                for s in raw_steps:
                    s_start = s.get("started_at")
                    s_end = s.get("ended_at")

                    step_started_at: str | None = None
                    step_ended_at: str | None = None
                    step_elapsed: float | None = None

                    if s_start is not None:
                        step_started_at = datetime.fromtimestamp(float(s_start), tz=timezone.utc).isoformat()
                    if s_end is not None:
                        step_ended_at = datetime.fromtimestamp(float(s_end), tz=timezone.utc).isoformat()
                    if s_start is not None and s_end is not None:
                        step_elapsed = float(s_end) - float(s_start)

                    # webui-ux Phase 2.2: the StepReport summary counts are
                    # optional in steps_json — a legacy entry (pre-Phase-2.2)
                    # simply lacks them, so ``_opt_int`` / ``_opt_counts``
                    # yield ``None`` and the model defaults hold (fail-soft).
                    steps.append(
                        StepTiming(
                            name=str(s.get("name", "")),
                            status=str(s.get("status", "")),
                            started_at=step_started_at,
                            ended_at=step_ended_at,
                            elapsed_s=step_elapsed,
                            success_count=_opt_int(s.get("success_count")),
                            skip_count=_opt_int(s.get("skip_count")),
                            error_count=_opt_int(s.get("error_count")),
                            unmatched_count=_opt_int(s.get("unmatched_count")),
                            counts=_opt_counts(s.get("counts")),
                        )
                    )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return RunDetail(
        run_uid=summary.run_uid,
        trigger=summary.trigger,
        dry_run=summary.dry_run,
        started_at=summary.started_at,
        ended_at=summary.ended_at,
        outcome=summary.outcome,
        duration_s=summary.duration_s,
        steps=steps,
        error=row["error"],
        kind=row["kind"] if row["kind"] is not None else "pipeline",
        command=row["command"],
        options_json=row["options_json"],
        output_tail=row["output_tail"],
    )
