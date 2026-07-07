"""Maintenance dashboard panel routes (maint-dash feature).

Three read-only GET endpoints under ``/api/maintenance/*`` serving the
monitoring-panel data contract defined in
``docs/features/maint-dash/plan/phase-02-panels-backend.md`` §2.2:

- ``GET /disks`` → :class:`DisksResponse`
- ``GET /locks`` → :class:`LocksResponse`
- ``GET /index-health`` → :class:`IndexHealthResponse`

All routes are guarded by ``require_session`` inherited from the parent
``guarded_api`` router (double-added per pipeline.py convention).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, Request

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import staging_path as _compute_staging_path
from personalscraper.core.sqlite._pragmas import apply_pragmas as _apply_pragmas
from personalscraper.dispatch.disk_scanner import get_disk_status
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.web.deps import (
    Session,
    require_session,
)
from personalscraper.web.maintenance.models import (
    DiskInfo,
    DisksResponse,
    IndexHealthResponse,
    LocksResponse,
    LockState,
    NfoStats,
    Sentinels,
    TmpOrphan,
)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])
logger = get_logger(__name__)

# ── Sentinel prefixes matched during the bounded tmp-orphan sweep ─────────
_TMP_ORPHAN_PREFIXES = ("_tmp_dispatch_", "_tmp_ingest_")
_MAX_ORPHANS = 100
_MAX_SCAN_DEPTH = 2
_STUCK_SCAN_THRESHOLD_S = 3600  # 1 hour


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
    _session: Session = Depends(require_session),
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


# ── GET /locks ────────────────────────────────────────────────────────────


@router.get("/locks", response_model=LocksResponse)
def get_locks(
    request: Request,
    _session: Session = Depends(require_session),
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

    tmp_orphans = _sweep_tmp_orphans(config)

    return LocksResponse(
        pipeline_lock=lock_state,
        sentinels=sentinels,
        tmp_orphans=tmp_orphans,
    )


# ── GET /index-health helpers ─────────────────────────────────────────────


def _empty_health() -> IndexHealthResponse:
    """Return a zeroed :class:`IndexHealthResponse` for fail-soft paths.

    Used when the database file is missing, unreadable, or corrupted.

    Returns:
        A default :class:`IndexHealthResponse` with all counts set to
        zero / ``None``.
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
    )


# ── GET /index-health ─────────────────────────────────────────────────────


@router.get("/index-health", response_model=IndexHealthResponse)
def get_index_health(
    request: Request,
    _session: Session = Depends(require_session),
) -> IndexHealthResponse:
    """Return an aggregate health snapshot of the indexer database.

    Opens a read-only WAL connection to ``library.db`` and runs a single
    batch of lightweight aggregate queries.  No filesystem walk is
    performed.  When the database file is missing or unreadable, a zeroed
    response is returned (fail-soft, no 500).

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
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.isolation_level = None
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError:
        logger.warning("index_health_db_open_failed", path=str(db_path))
        return _empty_health()

    try:
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
                if scan_row["status"] == "running" and (time.time() - scan_row["started_at"]) > _STUCK_SCAN_THRESHOLD_S:
                    last_scan_stuck = True
            if scan_row["finished_at"] is not None:
                last_scan_finished_at = datetime.fromtimestamp(scan_row["finished_at"], tz=timezone.utc).isoformat()

        # ── Soft-deleted files ────────────────────────────────────────
        soft_deleted = conn.execute("SELECT COUNT(*) FROM media_file WHERE deleted_at IS NOT NULL").fetchone()[0]

        # ── Canonical NULL ────────────────────────────────────────────
        canonical_null = conn.execute("SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL").fetchone()[0]

    finally:
        conn.close()

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
