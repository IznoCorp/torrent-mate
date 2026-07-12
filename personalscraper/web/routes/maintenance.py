"""Maintenance dashboard panel routes (maint-dash feature).

Three read-only GET endpoints under ``/api/maintenance/*`` serving the
monitoring-panel data contract defined in
``docs/features/maint-dash/plan/phase-02-panels-backend.md`` §2.2:

- ``GET /disks`` → :class:`DisksResponse`
- ``GET /locks`` → :class:`LocksResponse`
- ``GET /index-health`` → :class:`IndexHealthResponse`

All routes are guarded by ``require_session`` inherited from the parent
``guarded_api`` router (registration in app.py).  Auth dependencies are NOT
added per-route — the auth perimeter is a single dependency at registration
time, per ``docs/reference/web-ui.md`` §6 (the single authority for this
convention; R14/R24).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import staging_path as _compute_staging_path
from personalscraper.core.sqlite._pragmas import apply_pragmas as _apply_pragmas
from personalscraper.dispatch.disk_scanner import get_disk_status
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.deps import (
    require_not_staging,
    require_x_requested_with,
)
from personalscraper.web.maintenance.models import (
    ActionRunRequest,
    ActionRunResponse,
    ActionsResponse,
    DiskInfo,
    DisksResponse,
    IndexHealthResponse,
    LocksResponse,
    LockState,
    NfoStats,
    SchedulerItem,
    SchedulersResponse,
    Sentinels,
    TmpOrphan,
)
from personalscraper.web.maintenance.registry import (
    REGISTRY,
    MaintenanceAction,
    canonical_options_json,
)
from personalscraper.web.schedulers.registry import CRON_JOBS, CronJob

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])
logger = get_logger(__name__)

# ── Sentinel prefixes matched during the bounded tmp-orphan sweep ─────────
_TMP_ORPHAN_PREFIXES = ("_tmp_dispatch_", "_tmp_ingest_")
_MAX_ORPHANS = 100
_MAX_SCAN_DEPTH = 2
_STUCK_SCAN_THRESHOLD_S = 3600  # 1 hour

#: 428 detail returned when a destructive apply lacks a fresh dry-run.
_DRY_RUN_FIRST_DETAIL = (
    "A fresh successful dry-run (within 30 minutes, same options) is required before applying this destructive action"
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


# ── GET /disks ────────────────────────────────────────────────────────────


@router.get("/disks", response_model=DisksResponse)
def get_disks(
    request: Request,
) -> DisksResponse:
    """Return mount status and capacity for every configured storage disk.

    Iterates ``config.disks``, calling :func:`get_disk_status` for each.
    Total capacity is derived from ``shutil.disk_usage`` at query time
    (DiskConfig does not carry a ``size_gb`` field).

    Returns:
        A :class:`DisksResponse` with one entry per configured disk.
    """
    config = request.app.state.config
    disks: list[DiskInfo] = []

    for disk_cfg in config.disks:
        status = get_disk_status(config=disk_cfg)

        total_gb = 0.0
        if status.is_mounted:
            try:
                total_gb = shutil.disk_usage(disk_cfg.path).total / (1024**3)
            except OSError:
                total_gb = 0.0

        used_pct = round((1 - status.free_space_gb / total_gb) * 100, 1) if total_gb > 0 else 0.0

        disks.append(
            DiskInfo(
                id=disk_cfg.id,
                label=disk_cfg.id,
                mounted=status.is_mounted,
                free_gb=round(status.free_space_gb, 1),
                total_gb=round(total_gb, 1),
                used_pct=used_pct,
            )
        )

    return DisksResponse(disks=disks)


# ── GET /locks helpers ────────────────────────────────────────────────────


def _build_lock_state(lock_path: Path) -> LockState:
    """Build a :class:`LockState` from the ``pipeline.lock`` file.

    Reuses :func:`personalscraper.lock.is_lock_held` for the alive
    determination (same stale-PID logic), then adds age and PID extraction
    for the full response model.  Fail-soft: a file that disappears
    between the ``exists()`` check and the ``stat()`` call is treated as
    not held.

    Args:
        lock_path: Absolute path to ``pipeline.lock``.

    Returns:
        A fully populated :class:`LockState`.
    """
    if not lock_path.exists():
        return LockState(held=False)

    held = is_lock_held(lock_path)

    try:
        age_s = time.time() - lock_path.stat().st_mtime
    except OSError:
        return LockState(held=False)

    pid: int | None = None
    pid_alive = False
    try:
        pid = int(lock_path.read_text().strip())
    except (ValueError, OSError):
        pid = None

    if pid is not None:
        try:
            os.kill(pid, 0)
            pid_alive = True
        except ProcessLookupError:
            pid_alive = False
        except PermissionError:
            # Process exists but owned by another user — treat as alive.
            pid_alive = True

    stale = lock_path.exists() and not pid_alive

    return LockState(
        held=held,
        pid=pid,
        pid_alive=pid_alive,
        stale=stale,
        age_s=round(age_s, 1),
    )


def _sentinel_state(sentinel_path: Path) -> tuple[bool, float | None]:
    """Check whether a sentinel file exists and return its age.

    Args:
        sentinel_path: Absolute path to the sentinel file.

    Returns:
        A ``(exists, age_s)`` tuple.  *age_s* is ``None`` when the file
        does not exist.
    """
    if not sentinel_path.exists():
        return False, None
    try:
        age_s = round(time.time() - sentinel_path.stat().st_mtime, 1)
    except OSError:
        return False, None
    return True, age_s


def _sweep_dir(root: Path, now: float, orphans: list[TmpOrphan], depth: int) -> None:
    """Recurse into *root* at limited depth, collecting tmp-orphan entries.

    Args:
        root: Directory to scan.
        now: Current ``time.time()`` value for age computation.
        orphans: Accumulator list — mutated in place.
        depth: Current recursion depth (0-based).
    """
    if depth > _MAX_SCAN_DEPTH or len(orphans) >= _MAX_ORPHANS:
        return

    try:
        with os.scandir(root) as it:
            for entry in it:
                if len(orphans) >= _MAX_ORPHANS:
                    return
                name = entry.name
                for prefix in _TMP_ORPHAN_PREFIXES:
                    if name.startswith(prefix):
                        try:
                            age_s = round(now - entry.stat().st_mtime, 1)
                        except OSError:
                            age_s = 0.0
                        orphans.append(
                            TmpOrphan(
                                path=str(entry.path),
                                prefix=prefix,
                                age_s=age_s,
                            )
                        )
                        break
                # Recurse one level deeper into subdirectories.
                if entry.is_dir():
                    _sweep_dir(Path(entry.path), now, orphans, depth + 1)
    except OSError:
        logger.debug("tmp_orphan_sweep_root_unreadable", path=str(root))


def _sweep_tmp_orphans(config: Config) -> list[TmpOrphan]:
    """Perform a bounded sweep for temporary orphan files and directories.

    Scans the staging root, each staging subdirectory, and each mounted
    disk root at depth ≤ :data:`_MAX_SCAN_DEPTH`.  Only entries whose
    **name** starts with ``_tmp_dispatch_`` or ``_tmp_ingest_`` are
    collected.  Unreadable roots are silently skipped (fail-soft).

    Args:
        config: The application :class:`Config`.

    Returns:
        A list of :class:`TmpOrphan` entries, capped at
        :data:`_MAX_ORPHANS`.
    """
    now = time.time()
    orphans: list[TmpOrphan] = []

    # Gather roots: staging dir, each staging subdir, each mounted disk.
    roots: list[Path] = [config.paths.staging_dir]
    for entry in config.staging_dirs:
        roots.append(_compute_staging_path(config, entry))
    for disk_cfg in config.disks:
        if disk_cfg.path.exists():
            roots.append(disk_cfg.path)

    for root in roots:
        if len(orphans) >= _MAX_ORPHANS:
            break
        _sweep_dir(root, now, orphans, depth=0)

    return orphans


#: TTL for the tmp-orphan sweep cache. The sweep walks the storage disk roots
#: (slow macFUSE/NTFS mounts — up to ~27 s), so caching it keeps GET /locks
#: responsive: lock state + sentinels stay real-time, orphan data is at most
#: this stale (a maintenance signal, not a live metric).
_ORPHAN_CACHE_TTL_S = 60.0
_orphan_lock = threading.Lock()
_orphan_cache: dict[str, object] = {"ts": 0.0, "data": []}


def _sweep_tmp_orphans_cached(config: Config) -> list[TmpOrphan]:
    """Return the tmp-orphan sweep, cached for :data:`_ORPHAN_CACHE_TTL_S`.

    The lock is held across the scan so a burst of concurrent ``/locks`` calls
    triggers exactly one disk walk (the rest wait, then read the fresh cache)
    instead of a thundering herd of 27 s sweeps. A sync route runs in the
    threadpool, so blocking here never stalls the event loop.

    Args:
        config: The application :class:`Config`.

    Returns:
        The (possibly cached) list of :class:`TmpOrphan` entries.
    """
    now = time.time()
    with _orphan_lock:
        ts = cast(float, _orphan_cache["ts"])
        if ts > 0 and now - ts < _ORPHAN_CACHE_TTL_S:
            return cast("list[TmpOrphan]", _orphan_cache["data"])
        data = _sweep_tmp_orphans(config)
        _orphan_cache["ts"] = time.time()
        _orphan_cache["data"] = data
        return data


# ── GET /locks ────────────────────────────────────────────────────────────


@router.get("/locks", response_model=LocksResponse)
def get_locks(
    request: Request,
) -> LocksResponse:
    """Return pipeline lock state, sentinels, and bounded tmp-orphan sweep.

    Reads ``pipeline.lock``, ``pipeline.pause``, and ``watcher.paused``
    from the configured ``data_dir``, then performs a bounded filesystem
    sweep for stale ``_tmp_dispatch_*`` / ``_tmp_ingest_*`` entries
    across staging and disk roots (capped at 100 entries, depth ≤ 2).

    Returns:
        A :class:`LocksResponse` with lock, sentinel, and orphan data.
    """
    data_dir = _data_dir(request)
    config = request.app.state.config

    lock_state = _build_lock_state(data_dir / "pipeline.lock")

    pause_exists, pause_age = _sentinel_state(data_dir / "pipeline.pause")
    watcher_exists, watcher_age = _sentinel_state(data_dir / "watcher.paused")

    sentinels = Sentinels(
        pause=pause_exists,
        pause_age_s=pause_age,
        watcher_paused=watcher_exists,
        watcher_paused_age_s=watcher_age,
    )

    tmp_orphans = _sweep_tmp_orphans_cached(config)

    return LocksResponse(
        pipeline_lock=lock_state,
        sentinels=sentinels,
        tmp_orphans=tmp_orphans,
    )


# ── GET /index-health helpers ─────────────────────────────────────────────


def _empty_health(*, degraded: bool = False, error: str | None = None) -> IndexHealthResponse:
    """Return a zeroed :class:`IndexHealthResponse` for fail-soft paths.

    Used when the database file is missing (``degraded=False`` — a legitimately
    empty library) or present-but-broken (``degraded=True`` — a query failed on
    a missing / mis-migrated table, Finding D).

    Args:
        degraded: ``True`` when the DB file exists but a query failed, so the
            zeroed counts must not be read as a pristine empty library.
        error: Optional error message describing the query failure.

    Returns:
        A default :class:`IndexHealthResponse` with all counts set to
        zero / ``None`` and the ``degraded`` / ``error`` fields set.
    """
    return IndexHealthResponse(
        items=0,
        movies=0,
        shows=0,
        files=0,
        size_gb=0.0,
        nfo=NfoStats(valid=0, invalid=0, missing=0),
        repair_queue_pending=0,
        repair_queue_oldest_age_s=None,
        outbox_pending=0,
        outbox_oldest_age_s=None,
        last_scan_id=None,
        last_scan_mode=None,
        last_scan_status=None,
        last_scan_started_at=None,
        last_scan_finished_at=None,
        last_scan_stuck=False,
        soft_deleted=0,
        canonical_null=0,
        degraded=degraded,
        error=error,
    )


# ── GET /index-health ─────────────────────────────────────────────────────


@router.get("/index-health", response_model=IndexHealthResponse)
def get_index_health(
    request: Request,
) -> IndexHealthResponse:
    """Return an aggregate health snapshot of the indexer database.

    Opens a regular connection to ``library.db`` (mirroring the pipeline
    history route) and runs a single batch of lightweight aggregate
    queries.  No filesystem walk is performed.  When the database file is
    missing or unreadable, a zeroed response is returned (fail-soft, no
    500).

    Query summary:

    * ``media_item`` total + movie/show breakdown (``kind`` column).
    * ``media_file`` count + ``size_bytes`` sum (non-deleted only).
    * NFO status breakdown (``valid`` / ``invalid`` / ``missing``).
    * ``repair_queue`` pending count + oldest ``enqueued_at`` age.
    * ``index_outbox`` pending count + oldest ``created_at`` age
      (table-missing → 0 / ``None``, fail-soft).
    * ``scan_run`` latest row with stuck detection (> 1 h running).
    * Soft-deleted ``media_file`` rows (``deleted_at IS NOT NULL``).
    * ``media_item`` rows with ``canonical_provider IS NULL``.

    Returns:
        A :class:`IndexHealthResponse` with per-table counts, NFO stats,
        queue backlogs, and the most recent scan run metadata.
    """
    db_path = _db_path(request)

    if not db_path.exists():
        return _empty_health()

    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            _apply_pragmas(conn)
            conn.row_factory = sqlite3.Row

            # ── Media item counts ─────────────────────────────────────────
            items_row = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()
            items = items_row[0] if items_row else 0

            movies_row = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()
            movies = movies_row[0] if movies_row else 0

            shows_row = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'show'").fetchone()
            shows = shows_row[0] if shows_row else 0

            # ── Media file counts (non-deleted only) ──────────────────────
            files_row = conn.execute("SELECT COUNT(*) FROM media_file WHERE deleted_at IS NULL").fetchone()
            files = files_row[0] if files_row else 0

            size_row = conn.execute(
                "SELECT COALESCE(SUM(size_bytes), 0) FROM media_file WHERE deleted_at IS NULL"
            ).fetchone()
            size_bytes = size_row[0] if size_row else 0
            size_gb = round(size_bytes / (1024**3), 2)

            # ── NFO status breakdown ──────────────────────────────────────
            nfo_valid = conn.execute("SELECT COUNT(*) FROM media_item WHERE nfo_status = 'valid'").fetchone()[0]

            nfo_invalid = conn.execute("SELECT COUNT(*) FROM media_item WHERE nfo_status = 'invalid'").fetchone()[0]

            nfo_missing = conn.execute(
                "SELECT COUNT(*) FROM media_item WHERE nfo_status = 'missing' OR nfo_status IS NULL"
            ).fetchone()[0]

            nfo = NfoStats(valid=nfo_valid, invalid=nfo_invalid, missing=nfo_missing)

            # ── Repair queue ──────────────────────────────────────────────
            rep_row = conn.execute(
                "SELECT COUNT(*), MIN(enqueued_at) FROM repair_queue WHERE status = 'pending'"
            ).fetchone()
            repair_pending: int = rep_row[0] if rep_row else 0
            repair_oldest_age: float | None = None
            if rep_row and rep_row[1] is not None:
                repair_oldest_age = round(time.time() - rep_row[1], 1)

            # ── Outbox (table may not exist in pre-migration DBs) ─────────
            try:
                out_row = conn.execute(
                    "SELECT COUNT(*), MIN(created_at) FROM index_outbox WHERE status = 'pending'"
                ).fetchone()
                outbox_pending: int = out_row[0] if out_row else 0
                outbox_oldest_age: float | None = None
                if out_row and out_row[1] is not None:
                    outbox_oldest_age = round(time.time() - out_row[1], 1)
            except sqlite3.OperationalError:
                outbox_pending = 0
                outbox_oldest_age = None

            # ── Last scan ─────────────────────────────────────────────────
            scan_row = conn.execute(
                "SELECT id, mode, status, started_at, finished_at FROM scan_run ORDER BY started_at DESC LIMIT 1"
            ).fetchone()

            last_scan_id: int | None = None
            last_scan_mode: str | None = None
            last_scan_status: str | None = None
            last_scan_started_at: str | None = None
            last_scan_finished_at: str | None = None
            last_scan_stuck = False

            if scan_row is not None:
                last_scan_id = scan_row["id"]
                last_scan_mode = scan_row["mode"]
                last_scan_status = scan_row["status"]
                if scan_row["started_at"] is not None:
                    last_scan_started_at = datetime.fromtimestamp(scan_row["started_at"], tz=timezone.utc).isoformat()
                    # Stuck detection: running + started > 1 h ago (mirrors
                    # doctor.py _check_no_stuck_scan_run threshold).
                    if (
                        scan_row["status"] == "running"
                        and (time.time() - scan_row["started_at"]) > _STUCK_SCAN_THRESHOLD_S
                    ):
                        last_scan_stuck = True
                if scan_row["finished_at"] is not None:
                    last_scan_finished_at = datetime.fromtimestamp(scan_row["finished_at"], tz=timezone.utc).isoformat()

            # ── Soft-deleted files ────────────────────────────────────────
            soft_deleted = conn.execute("SELECT COUNT(*) FROM media_file WHERE deleted_at IS NOT NULL").fetchone()[0]

            # ── Canonical NULL ────────────────────────────────────────────
            canonical_null = conn.execute(
                "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL"
            ).fetchone()[0]

    except sqlite3.OperationalError as exc:
        # The file exists but a query failed (missing / mis-migrated table, or
        # a locked DB). Surface this as ``degraded`` rather than masquerading a
        # broken DB as a pristine empty library (Finding D). Logged at ERROR.
        logger.error("index_health_db_query_failed", path=str(db_path), error=str(exc), exc_info=True)
        return _empty_health(degraded=True, error=str(exc))

    return IndexHealthResponse(
        items=items,
        movies=movies,
        shows=shows,
        files=files,
        size_gb=size_gb,
        nfo=nfo,
        repair_queue_pending=repair_pending,
        repair_queue_oldest_age_s=repair_oldest_age,
        outbox_pending=outbox_pending,
        outbox_oldest_age_s=outbox_oldest_age,
        last_scan_id=last_scan_id,
        last_scan_mode=last_scan_mode,
        last_scan_status=last_scan_status,
        last_scan_started_at=last_scan_started_at,
        last_scan_finished_at=last_scan_finished_at,
        last_scan_stuck=last_scan_stuck,
        soft_deleted=soft_deleted,
        canonical_null=canonical_null,
    )


# ── GET /schedulers helpers ────────────────────────────────────────────────────


def _watcher_scheduler(data_dir: Path, acquire_db_path: Path | None) -> SchedulerItem:
    """Build the watcher :class:`SchedulerItem` from its sentinel + ``watch_state``.

    The watcher is a long-running daemon (not a cron): its enabled state is the
    absence of the ``watcher.paused`` sentinel, and its last run is the
    ``last_successful_run_at`` KV value in ``acquire.db`` ``watch_state``.  Both
    reads are fail-soft — a missing sentinel dir or DB yields ``enabled=True`` /
    ``last_run_at=None`` rather than an error.

    Args:
        data_dir: The configured pipeline ``data_dir`` (holds ``watcher.paused``).
        acquire_db_path: Absolute path to ``acquire.db``, or ``None`` when
            unresolved.

    Returns:
        The watcher's :class:`SchedulerItem`.
    """
    enabled = not (data_dir / "watcher.paused").exists()

    last_run_at: float | None = None
    if acquire_db_path is not None and acquire_db_path.exists():
        try:
            with closing(sqlite3.connect(str(acquire_db_path))) as conn:
                _apply_pragmas(conn)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT value FROM watch_state WHERE key = ?",
                    ("last_successful_run_at",),
                ).fetchone()
                if row is not None:
                    last_run_at = float(row["value"])
        except sqlite3.Error:
            logger.warning("schedulers_watch_state_read_failed", exc_info=True)

    return SchedulerItem(
        name="personalscraper-watch",
        kind="watcher",
        display_name="Surveillance des téléchargements",
        schedule=None,
        enabled=enabled,
        last_run_at=last_run_at,
        last_outcome=None,
    )


def _cron_last_run(conn: sqlite3.Connection, job: CronJob) -> tuple[float | None, str | None]:
    """Find the most recent ``pipeline_run`` row matching *job*.

    Matches ``kind='pipeline'`` rows whose ``command`` starts with the job's
    ``command_prefix``.  Returns ``(None, None)`` when no row matches — the
    current reality for every cron, since none writes a ``pipeline_run`` row yet
    (surfaced fail-soft).

    Args:
        conn: An open, read-only connection to ``library.db``.
        job: The static cron job whose last run is being looked up.

    Returns:
        A ``(last_run_at, last_outcome)`` tuple.  ``last_run_at`` is the row's
        ``started_at`` (epoch seconds); ``last_outcome`` is its ``outcome``.
    """
    row = conn.execute(
        "SELECT started_at, outcome FROM pipeline_run "
        "WHERE kind = 'pipeline' AND command LIKE ? "
        "ORDER BY started_at DESC LIMIT 1",
        (job.command_prefix + "%",),
    ).fetchone()
    if row is None:
        return None, None
    started_at = float(row["started_at"]) if row["started_at"] is not None else None
    return started_at, row["outcome"]


def _cron_schedulers(indexer_db_path: Path) -> list[SchedulerItem]:
    """Build a :class:`SchedulerItem` for every static cron job.

    Opens ONE read-only connection to ``library.db`` and looks up each cron's
    last run.  When the DB is absent or a query fails, every cron is surfaced
    with ``last_run_at=None`` (fail-soft) — the schedule + display name are
    static, so the panel still renders.

    Args:
        indexer_db_path: Absolute path to ``library.db``.

    Returns:
        One :class:`SchedulerItem` per :data:`CRON_JOBS` entry, in registry
        order.
    """
    last_runs: dict[str, tuple[float | None, str | None]] = {}
    if indexer_db_path.exists():
        try:
            with closing(sqlite3.connect(str(indexer_db_path))) as conn:
                _apply_pragmas(conn)
                conn.row_factory = sqlite3.Row
                for job in CRON_JOBS:
                    last_runs[job.name] = _cron_last_run(conn, job)
        except sqlite3.Error:
            logger.warning("schedulers_cron_last_run_read_failed", exc_info=True)

    items: list[SchedulerItem] = []
    for job in CRON_JOBS:
        last_run_at, last_outcome = last_runs.get(job.name, (None, None))
        items.append(
            SchedulerItem(
                name=job.name,
                kind="cron",
                display_name=job.display_name,
                schedule=job.schedule,
                enabled=None,
                last_run_at=last_run_at,
                last_outcome=last_outcome,
            )
        )
    return items


# ── GET /schedulers ────────────────────────────────────────────────────────────


@router.get("/schedulers", response_model=SchedulersResponse)
def get_schedulers(request: Request) -> SchedulersResponse:
    """Return the scheduler overview: the watcher plus every static cron job.

    Aggregates each scheduled agent's state from three fail-soft sources: the
    ``watcher.paused`` sentinel + ``acquire.db`` ``watch_state`` (watcher), the
    static :data:`CRON_JOBS` registry (schedule + display names), and the last
    matching ``pipeline_run`` row per cron (``library.db``).  Read-only,
    lock-free, per-request ``sqlite3`` connections (mirrors the acquisition
    status read pattern).  Never 500s — a missing source DB yields
    ``last_run_at=None`` rather than an error.

    Returns:
        A :class:`SchedulersResponse` with the watcher first, then each cron in
        registry order.
    """
    config = request.app.state.config
    data_dir = _data_dir(request)

    watcher = _watcher_scheduler(data_dir, config.acquire.db_path)
    crons = _cron_schedulers(_db_path(request))

    return SchedulersResponse(schedulers=[watcher, *crons])


# ── POST /actions/{action_id}/run helpers ──────────────────────────────────────


def _validate_options(action: MaintenanceAction, body_options: dict[str, object]) -> None:
    """Validate *body_options* against the action's registered :class:`ActionOption` entries.

    No coercion is performed — every value must already match the declared type.
    Unknown keys, missing required options, type mismatches, and enum values outside the
    declared set are all rejected with 422.

    Args:
        action: The maintenance action from :data:`REGISTRY`.
        body_options: The ``options`` dict from the :class:`ActionRunRequest` body.

    Raises:
        HTTPException: 422 with a ``detail`` message describing the first validation failure.
    """
    registered = {opt.name: opt for opt in action.options}

    # Unknown keys.
    for key in body_options:
        if key not in registered:
            raise HTTPException(status_code=422, detail=f"Unknown option: {key!r}")

    # Missing required options.
    for opt in action.options:
        if opt.required and opt.name not in body_options:
            raise HTTPException(status_code=422, detail=f"Missing required option: {opt.name!r}")

    # Type / enum validation for each provided key.
    for key, value in body_options.items():
        opt = registered[key]

        if opt.type == "bool":
            if not isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be a boolean")
        elif opt.type == "int":
            # bool is a subclass of int — reject it explicitly.
            if not isinstance(value, int) or isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be an integer")
        elif opt.type == "str":
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be a string")
        elif opt.type == "enum":
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be a string")
            if opt.enum_values and value not in opt.enum_values:
                raise HTTPException(
                    status_code=422,
                    detail=(f"Option {key!r}: {value!r} is not a valid value. Allowed: {', '.join(opt.enum_values)}"),
                )


def _guard_no_running_maintenance(conn: sqlite3.Connection, action_id: str) -> None:
    """Raise 409 when a maintenance action with a live pid is already running.

    Queries ``pipeline_run`` for rows with ``kind='maintenance'`` and
    ``outcome='running'`` and checks liveness via ``os.kill(pid, 0)``. Rows with
    a dead or NULL pid are stale (crashed runner / pre-pid migration) and are
    ignored — we never mutate them here.

    Args:
        conn: An open connection (inside the reserve transaction).
        action_id: The action being launched (for log context).

    Raises:
        HTTPException: 409 when a live maintenance runner is found.
    """
    rows = conn.execute(
        "SELECT run_uid, pid FROM pipeline_run WHERE kind='maintenance' AND outcome='running'"
    ).fetchall()
    for row in rows:
        run_uid_db = row["run_uid"]
        pid_db = row["pid"]
        if pid_db is None:
            # NULL pid → stale row (pre-pid-migration or a runner that crashed
            # before claiming its pid).
            logger.info("maintenance_stale_row_ignored", run_uid=run_uid_db, pid=None, action_id=action_id)
            continue
        try:
            os.kill(pid_db, 0)
        except ProcessLookupError:
            # Dead process → stale row (crashed runner).
            logger.info("maintenance_stale_row_ignored", run_uid=run_uid_db, pid=pid_db, action_id=action_id)
            continue
        except PermissionError:
            # Process exists but owned by another user → treat as alive.
            raise HTTPException(status_code=409, detail="A maintenance action is already running")
        else:
            raise HTTPException(status_code=409, detail="A maintenance action is already running")


def _guard_recent_dry_run(conn: sqlite3.Connection, action_id: str, options_json: str) -> None:
    """Raise 428 unless a fresh successful dry-run (same options) exists.

    Args:
        conn: An open connection (inside the reserve transaction).
        action_id: The destructive action being applied.
        options_json: Canonical options JSON compared by string equality.

    Raises:
        HTTPException: 428 when no matching dry-run row exists within 30 minutes.
    """
    cutoff = time.time() - 1800
    row = conn.execute(
        "SELECT 1 FROM pipeline_run "
        "WHERE kind='maintenance' AND command=? AND options_json=? "
        "AND dry_run=1 AND outcome='success' AND ended_at >= ? LIMIT 1",
        (action_id, options_json, cutoff),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=428, detail=_DRY_RUN_FIRST_DETAIL)


def _reserve_run_row(
    db_path: Path,
    *,
    run_uid: str,
    action: MaintenanceAction,
    command: str,
    options_json: str,
    dry_run: bool,
) -> None:
    """Atomically guard concurrency + dry-run-first and reserve the run row.

    Opens one connection under ``BEGIN IMMEDIATE`` so the "no maintenance action
    is already running" check and the ``pipeline_run`` INSERT are a single
    serialised transaction: a second concurrent destructive POST blocks on the
    write lock, then observes the freshly-inserted running row (409), closing the
    check→insert TOCTOU race (Finding C). The row is reserved with a placeholder
    pid of the web process (guaranteed alive) — the caller updates it to the
    spawned runner's pid right after spawn.

    Guard order (preserved from the original route): 409 concurrency → 428
    dry-run-first → INSERT. The pipeline-lock 409 is checked by the caller before
    this helper (filesystem, no DB) and re-probed right after it (R11) — the
    reserved row is finalized ``'error'`` if the lock appeared in between.

    On a DB read error while verifying concurrency, a ``destructive`` action is
    fail-CLOSED (409) — the only concurrency protection must never be dropped
    silently (Finding E). ``write`` / ``ro`` actions stay permissive.

    Args:
        db_path: Absolute path to ``library.db``.
        run_uid: The unique run identifier reserved by the caller.
        action: The resolved maintenance action.
        command: The action id (stored in the ``command`` column).
        options_json: Canonical options JSON (stored + compared for 428).
        dry_run: ``True`` for a dry run.

    Raises:
        HTTPException: 409 (already running / cannot verify) or 428 (no fresh
            dry run). The transaction is rolled back before raising.
    """
    destructive = action.risk == "destructive"
    check_concurrency = action.risk in ("write", "destructive")

    if not db_path.exists():
        # No DB yet (fresh install / test) — nothing to verify and no row to
        # reserve. A destructive apply still requires a prior dry-run, which
        # cannot exist without a DB → 428 (preserves the original semantics).
        if destructive and not dry_run:
            raise HTTPException(status_code=428, detail=_DRY_RUN_FIRST_DETAIL)
        return

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            if check_concurrency:
                _guard_no_running_maintenance(conn, command)
            if destructive and not dry_run:
                _guard_recent_dry_run(conn, command, options_json)
            conn.execute(
                "INSERT INTO pipeline_run "
                "(run_uid, trigger, dry_run, started_at, outcome, steps_json, pid, "
                "kind, command, options_json) "
                "VALUES (?, 'web', ?, ?, 'running', '[]', ?, 'maintenance', ?, ?)",
                (run_uid, 1 if dry_run else 0, time.time(), os.getpid(), command, options_json),
            )
            conn.execute("COMMIT")
        except HTTPException:
            _safe_rollback(conn)
            raise
        except sqlite3.OperationalError as exc:
            _safe_rollback(conn)
            logger.warning("maintenance_reserve_db_error", command=command, error=str(exc))
            if destructive:
                # Fail-CLOSED: cannot verify no destructive action is running.
                raise HTTPException(
                    status_code=409,
                    detail="Cannot verify no maintenance action is running",
                ) from exc
            # write / ro — permissive: proceed to spawn without a reserved row.
    finally:
        conn.close()


def _safe_rollback(conn: sqlite3.Connection) -> None:
    """Roll back *conn* best-effort, ignoring "no transaction active" errors.

    Args:
        conn: The connection to roll back.
    """
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


def _spawn_runner(run_uid: str, action_id: str, options_json: str, dry_run: bool) -> int:
    """Spawn the maintenance runner as a detached subprocess.

    The runner module (``personalscraper.web.maintenance.runner``) reads its
    configuration from the environment variables set here. It is responsible for
    executing the CLI command, streaming output, and finalizing the
    ``pipeline_run`` row (reserved by the caller before this spawn).

    Args:
        run_uid: The unique run identifier (``uuid4().hex``).
        action_id: The maintenance action id (e.g. ``"library-index"``).
        options_json: Canonical JSON string of validated options (produced by
            :func:`canonical_options_json`).
        dry_run: ``True`` when this is a dry run.

    Returns:
        The pid of the spawned runner process.
    """
    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_MAINT_COMMAND": action_id,
        "PERSONALSCRAPER_MAINT_OPTIONS_JSON": options_json,
        "PERSONALSCRAPER_MAINT_DRY_RUN": "1" if dry_run else "0",
    }
    logger.info(
        "maintenance_run_spawned",
        run_uid=run_uid,
        action_id=action_id,
        dry_run=dry_run,
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "personalscraper.web.maintenance.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid


# ── POST /actions/{action_id}/run ──────────────────────────────────────────────


@router.post("/actions/{action_id}/run", response_model=ActionRunResponse, status_code=202)
def action_run(
    action_id: str,
    body: ActionRunRequest,
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
    _staging: None = Depends(require_not_staging),
) -> ActionRunResponse:
    """Launch a maintenance action as a detached subprocess.

    Mirror of ``POST /api/pipeline/run`` — validates the action id, options, and
    preconditions (pipeline lock, concurrent maintenance run, dry-run-first for
    destructive actions), then spawns a runner subprocess and returns ``202``
    with the ``run_uid``.

    Args:
        action_id: The kebab-case action id (e.g. ``"library-index"``).
        body: The request payload with ``options`` and ``dry_run``.
        request: The incoming FastAPI request (for ``app.state`` access).

    Returns:
        ``202`` with :class:`ActionRunResponse` (``{"run_uid": "..."}``).

    Raises:
        404: *action_id* is not in the :data:`REGISTRY`.
        422: Invalid or missing options, or dry-run requested for an action
            that does not support it.
        409: The pipeline lock is held, or a maintenance action is already running.
        428: A destructive action was requested without a recent successful
            dry run (same options, within the last 30 minutes).
    """
    # 1. Lookup action in REGISTRY.
    registry_index: dict[str, MaintenanceAction] = {a.id: a for a in REGISTRY}
    action = registry_index.get(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Unknown action: {action_id!r}")

    # 2. Validate options.
    if action.dry_run == "unsupported" and body.dry_run:
        raise HTTPException(
            status_code=422,
            detail=f"Action {action_id!r} does not support dry-run",
        )
    _validate_options(action, body.options)

    data_dir = _data_dir(request)
    db_path = _db_path(request)
    options_json = canonical_options_json(body.options)
    run_uid = uuid.uuid4().hex

    # 3. Pipeline-lock 409 (write / destructive only). Independent of the
    #    concurrent-maintenance check because a maintenance action may run
    #    without holding the pipeline lock (e.g. a read-only action).
    if action.risk in ("write", "destructive") and is_lock_held(data_dir / "pipeline.lock"):
        raise HTTPException(status_code=409, detail="Pipeline lock held")

    # 4. Atomic concurrency-409 + 428 dry-run-first + reserve the running row
    #    under BEGIN IMMEDIATE (Finding C: closes the check→insert race so the
    #    row exists the instant 202 is returned and a second concurrent POST
    #    sees it; Finding E: destructive fails CLOSED if concurrency cannot be
    #    verified).
    _reserve_run_row(
        db_path,
        run_uid=run_uid,
        action=action,
        command=action_id,
        options_json=options_json,
        dry_run=body.dry_run,
    )

    # 4b. Re-probe the pipeline lock after the reservation (R11): a pipeline
    #     run may grab the lock between the step-3 probe and here. The runner
    #     itself re-acquires the lock atomically for its whole lifetime, so
    #     this re-probe only converts the near-miss into a fast 409 (with the
    #     reserved row finalized) instead of a 202 whose run immediately
    #     finalizes 'error'.
    if action.risk in ("write", "destructive") and is_lock_held(data_dir / "pipeline.lock"):
        PipelineRunWriter(db_path).finalize(run_uid, "error", error="Pipeline lock held")
        raise HTTPException(status_code=409, detail="Pipeline lock held")

    # 5. Spawn the runner and claim the reserved row with its pid, so a runner
    #    that dies before finalizing leaves a dead-pid (stale) row rather than a
    #    live-pid (permanently blocking) one. A spawn failure finalizes the
    #    reserved row 'error' so it never stays 'running'.
    try:
        pid = _spawn_runner(run_uid, action_id, options_json, body.dry_run)
    except (OSError, ValueError) as exc:
        PipelineRunWriter(db_path).finalize(run_uid, "error", error=str(exc))
        logger.error("maintenance_spawn_failed", run_uid=run_uid, action_id=action_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to spawn maintenance runner") from exc
    if isinstance(pid, int):
        PipelineRunWriter(db_path).update_pid(run_uid, pid)

    return ActionRunResponse(run_uid=run_uid)


# ── GET /actions ────────────────────────────────────────────────────────────


@router.get("/actions", response_model=ActionsResponse)
def get_actions() -> ActionsResponse:
    """Return the full maintenance action registry with category counts.

    The registry is defined at module level in
    :mod:`personalscraper.web.maintenance.registry` and is read-only at
    runtime — no database or filesystem access is needed.

    Returns:
        An :class:`ActionsResponse` with all 25 registered actions and
        per-category counts for UI grouping chips.
    """
    category_counts: dict[str, int] = {}
    for action in REGISTRY:
        category_counts[action.category] = category_counts.get(action.category, 0) + 1

    return ActionsResponse(actions=REGISTRY, category_counts=category_counts)
