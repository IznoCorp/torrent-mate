"""Pydantic response models for the maintenance dashboard panels.

These models serve the three monitoring-panel ``GET`` endpoints defined in
``docs/features/maint-dash/plan/phase-02-panels-backend.md`` §2.1:

- ``GET /api/maintenance/disks`` → ``DisksResponse``
- ``GET /api/maintenance/locks`` → ``LocksResponse``
- ``GET /api/maintenance/index-health`` → ``IndexHealthResponse``

All fields are read-only aggregates or filesystem-observed values; none
accept untrusted user input.
"""

from __future__ import annotations

from pydantic import BaseModel

from personalscraper.web.maintenance.registry import MaintenanceAction


class DiskInfo(BaseModel):
    """A single configured storage disk with its mount and capacity data.

    Attributes:
        id: The disk identifier as declared in ``config/disks.json5``
            (e.g. ``"disk_1"``, ``"disk_2"``).
        label: Human-readable disk label configured by the operator.
        mounted: ``True`` if the disk mount path currently exists and is
            accessible on the filesystem.
        free_gb: Free space in gibibytes, rounded to one decimal.
        total_gb: Total capacity in gibibytes, derived from
            ``shutil.disk_usage(path).total`` at query time.
        used_pct: Percentage of capacity currently in use, rounded to one
            decimal (``(1 - free_gb / total_gb) * 100``).
    """

    id: str
    label: str
    mounted: bool
    free_gb: float
    total_gb: float
    used_pct: float


class DisksResponse(BaseModel):
    """Top-level response for the disks monitoring panel.

    Attributes:
        disks: List of disk info entries, one per configured disk.
    """

    disks: list[DiskInfo]


class LockState(BaseModel):
    """State of a single filesystem lock file.

    Attributes:
        held: ``True`` when the lock file exists on disk.
        pid: The process ID read from the lock file, or ``None`` when the
            lock is not held or the PID couldn't be parsed.
        pid_alive: ``True`` when the PID reported in the lock file
            corresponds to a live process (checked via ``os.kill(pid, 0)``).
        stale: ``True`` when the lock file exists but the PID inside it is
            no longer alive — the lock should be cleaned up.
        age_s: Age of the lock file in seconds (``time.time() - mtime``),
            or ``None`` when the lock is not held.
    """

    held: bool
    pid: int | None = None
    pid_alive: bool = False
    stale: bool = False
    age_s: float | None = None


class Sentinels(BaseModel):
    """State of the pause and watcher-paused sentinel files.

    These are not traditional locks — they signal the pipeline engine to
    pause at the next step boundary or to disable the directory watcher.

    Attributes:
        pause: ``True`` when ``data_dir/pipeline.pause`` exists.
        pause_age_s: Age of the pause sentinel in seconds, or ``None`` when
            it does not exist.
        watcher_paused: ``True`` when ``data_dir/watcher.paused`` exists.
        watcher_paused_age_s: Age of the watcher-paused sentinel in seconds,
            or ``None`` when it does not exist.
    """

    pause: bool = False
    pause_age_s: float | None = None
    watcher_paused: bool = False
    watcher_paused_age_s: float | None = None


class TmpOrphan(BaseModel):
    """A single temporary orphan entry found during a bounded filesystem sweep.

    Matched by prefix (``_tmp_dispatch_*``, ``_tmp_ingest_*``) and reported
    up to a hard cap of 100 entries.

    Attributes:
        path: Absolute or relative path to the orphan entry.
        prefix: The matched prefix (``"_tmp_dispatch_"`` or
            ``"_tmp_ingest_"``).
        age_s: Age of the orphan entry in seconds (``time.time() - mtime``).
    """

    path: str
    prefix: str
    age_s: float


class LocksResponse(BaseModel):
    """Top-level response for the locks and orphans monitoring panel.

    Attributes:
        pipeline_lock: State of the main ``pipeline.lock`` file.
        sentinels: State of the pause and watcher-paused sentinels.
        tmp_orphans: List of temporary orphan files or directories found
            during a bounded sweep (capped at 100 entries).
    """

    pipeline_lock: LockState
    sentinels: Sentinels
    tmp_orphans: list[TmpOrphan]


class NfoStats(BaseModel):
    """Aggregate NFO file status counts across the indexed library.

    Attributes:
        valid: Number of media items with a valid NFO file.
        invalid: Number of media items with a structurally invalid NFO file.
        missing: Number of media items without any NFO file.
    """

    valid: int
    invalid: int
    missing: int


class IndexHealthResponse(BaseModel):
    """Aggregate health snapshot of the indexer database (``library.db``).

    All fields are derived from a single read-only WAL query over the
    database; no filesystem walk is performed.

    Attributes:
        items: Total number of rows in ``media_item``.
        movies: Number of media items with a movie category.
        shows: Number of media items with a TV-show category.
        files: Total number of rows in ``media_file``.
        size_gb: Sum of ``media_file.size_bytes`` converted to gibibytes,
            rounded to two decimals.
        nfo: Aggregate NFO status counts (valid / invalid / missing).
        repair_queue_pending: Number of ``repair_queue`` rows with
            ``status = 'pending'``.
        repair_queue_oldest_age_s: Age in seconds of the oldest pending
            repair-queue entry (based on ``enqueued_at``), or ``None`` when
            the queue is empty.
        outbox_pending: Number of ``outbox`` rows awaiting processing, or 0
            when the outbox table does not exist.
        outbox_oldest_age_s: Age in seconds of the oldest outbox entry
            (based on ``created_at``), or ``None`` when the outbox is empty.
        last_scan_id: Primary-key ``id`` of the most recent ``scan_run`` row,
            or ``None`` when no scan has ever been recorded.
        last_scan_mode: Scan mode of the most recent scan (``"quick"``,
            ``"full"``, ``"incremental"``, or ``"full-disk"``), or ``None``.
        last_scan_status: Final status of the most recent scan
            (``"done"``, ``"error"``, etc.), or ``None``.
        last_scan_started_at: ISO 8601 UTC timestamp of when the most recent
            scan started, or ``None``.
        last_scan_finished_at: ISO 8601 UTC timestamp of when the most
            recent scan finished, or ``None``.
        last_scan_stuck: ``True`` when the most recent scan started more than
            a configurable threshold ago and hasn't finished — typically
            indicating a hung or killed scan process.
        soft_deleted: Count of soft-deleted ``media_file`` rows (where
            ``deleted_at IS NOT NULL``).
        canonical_null: Count of ``media_item`` rows where
            ``canonical_provider IS NULL``.
    """

    items: int
    movies: int
    shows: int
    files: int
    size_gb: float

    nfo: NfoStats

    repair_queue_pending: int
    repair_queue_oldest_age_s: float | None = None

    outbox_pending: int
    outbox_oldest_age_s: float | None = None

    last_scan_id: int | None = None
    last_scan_mode: str | None = None
    last_scan_status: str | None = None
    last_scan_started_at: str | None = None
    last_scan_finished_at: str | None = None
    last_scan_stuck: bool = False

    soft_deleted: int = 0
    canonical_null: int = 0


class ActionsResponse(BaseModel):
    """Top-level response for the maintenance actions catalog.

    Serves the ``GET /api/maintenance/actions`` endpoint. Returns the full
    read-only :data:`REGISTRY` (25 entries across 6 categories) together
    with per-category counts for the web UI grouping chips.

    Attributes:
        actions: The full maintenance action registry (25 entries across
            the query, scan, repair, clean, analyze, and fix categories).
        category_counts: Count of actions per category for UI grouping chips
            (e.g. ``{"query": 5, "scan": 4, "repair": 2, "clean": 2,
            "analyze": 4, "fix": 8}``).
    """

    actions: list[MaintenanceAction]
    category_counts: dict[str, int]
