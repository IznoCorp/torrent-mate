"""Pydantic models for the pipeline control API (pipe-control feature).

See docs/features/pipe-control/DESIGN.md §4 for the route contract these
models serve.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class PipelineState(str, Enum):
    """Current run-state of the pipeline process.

    Attributes:
        idle: No pipeline run is in progress.
        running: A pipeline run is actively executing.
        paused: A pipeline run is in progress but paused at a step boundary.
    """

    idle = "idle"
    running = "running"
    paused = "paused"


class PipelineOutcome(str, Enum):
    """Final outcome of a completed (or killed) pipeline run.

    Used in the ``pipeline_run.outcome`` column and the ``StatusResponse``
    for active runs.

    Attributes:
        success: The run completed without errors.
        error: The run terminated with an unhandled error.
        killed: The run was killed via the ``/api/pipeline/kill`` endpoint.
        running: The run is still in progress.
        paused: The run is paused at a step boundary.
    """

    success = "success"
    error = "error"
    killed = "killed"
    running = "running"
    paused = "paused"


class RunRequest(BaseModel):
    """Request body for ``POST /api/pipeline/run``.

    Attributes:
        dry_run: If ``True``, the pipeline performs a dry run without
            mutating the filesystem.
    """

    dry_run: bool = False


class WatcherRequest(BaseModel):
    """Request body for ``POST /api/pipeline/watcher``.

    Attributes:
        enabled: If ``True``, enable the directory watcher; if ``False``,
            pause it.
    """

    enabled: bool


class RunResponse(BaseModel):
    """Response body returned after a successful ``POST /api/pipeline/run``.

    Attributes:
        run_uid: The unique identifier of the newly launched pipeline run.
    """

    run_uid: str


class StatusResponse(BaseModel):
    """Response body for ``GET /api/pipeline/status``.

    Reflects the live state of the pipeline engine, the pause sentinel,
    the watcher sentinel, and the latest run metadata.

    Attributes:
        state: The current pipeline run-state.
        run_uid: The unique identifier of the latest or active run, or
            ``None`` when idle.
        step: The human-readable name of the current step, or ``None``
            when idle.
        paused: Whether the pipeline is currently paused at a step boundary.
        watcher_enabled: Whether the directory watcher is currently active.
        pid: The OS process ID of the running pipeline subprocess, or
            ``None`` when idle.
    """

    state: PipelineState
    run_uid: str | None = None
    step: str | None = None
    paused: bool
    watcher_enabled: bool
    pid: int | None = None


class WatcherResponse(BaseModel):
    """Response body for ``POST /api/pipeline/watcher``.

    Attributes:
        watcher_enabled: Whether the directory watcher is now enabled.
    """

    watcher_enabled: bool


class RunSummary(BaseModel):
    """Summary row for the pipeline run-history list endpoint.

    Attributes:
        run_uid: Unique run identifier (uuid4 hex).
        trigger: What triggered the run (``"cli"``, ``"web"``, ``"watcher"``, etc.).
        dry_run: Whether this was a dry run.
        started_at: ISO 8601 UTC timestamp of run start.
        ended_at: ISO 8601 UTC timestamp of run end, or ``None`` if still
            running.
        outcome: Final outcome, or ``None`` if still in progress.
        duration_s: Wall-clock duration in seconds (``ended_at - started_at``),
            or ``None`` if either timestamp is missing.
        kind: Run kind discriminator. ``"pipeline"`` for media pipeline runs
            (ingest→sort→scrape→dispatch), ``"maintenance"`` for maintenance
            action runs (e.g. ``library-clean``).  Defaults to ``"pipeline"``.
        command: CLI command name for maintenance runs (e.g.
            ``"library-clean"``, ``"library-rescrape"``), or ``None`` for
            pipeline runs.
    """

    run_uid: str
    trigger: str
    dry_run: bool
    started_at: str
    ended_at: str | None = None
    outcome: PipelineOutcome | None = None
    duration_s: float | None = None
    kind: str = "pipeline"
    command: str | None = None


class StepTiming(BaseModel):
    """Timing record for a single pipeline step within a run.

    Attributes:
        name: Human-readable step name (e.g. ``"ingest"``, ``"sort"``).
        status: Step status (``"done"``, ``"running"``, ``"error"``, etc.).
        started_at: ISO 8601 UTC timestamp of step start, or ``None``.
        ended_at: ISO 8601 UTC timestamp of step end, or ``None``.
        elapsed_s: Step duration in seconds, or ``None`` if either timestamp
            is missing.
    """

    name: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    elapsed_s: float | None = None


class RunDetail(BaseModel):
    """Full detail for a single pipeline run, including step timings.

    Attributes:
        run_uid: Unique run identifier.
        trigger: What triggered the run.
        dry_run: Whether this was a dry run.
        started_at: ISO 8601 UTC timestamp of run start.
        ended_at: ISO 8601 UTC timestamp of run end, or ``None``.
        outcome: Final outcome, or ``None``.
        duration_s: Wall-clock duration in seconds, or ``None``.
        steps: Per-step timing records parsed from ``steps_json``.
        error: Error message if the run failed, or ``None``.
        kind: Run kind discriminator. ``"pipeline"`` for media pipeline runs,
            ``"maintenance"`` for maintenance action runs.  Defaults to
            ``"pipeline"``.
        command: CLI command name for maintenance runs (e.g.
            ``"library-clean"``), or ``None`` for pipeline runs.
        options_json: JSON-serialized CLI options for maintenance runs, or
            ``None`` for pipeline runs.
        output_tail: Tail of the subprocess/CLI output (last 64 KiB ring
            buffer) — populated for maintenance runs and, since the universal
            run journal (#235), for pipeline runs too; ``None`` for legacy
            rows recorded before output capture existed.
    """

    run_uid: str
    trigger: str
    dry_run: bool
    started_at: str
    ended_at: str | None = None
    outcome: PipelineOutcome | None = None
    duration_s: float | None = None
    steps: list[StepTiming] = []
    error: str | None = None
    kind: str = "pipeline"
    command: str | None = None
    options_json: str | None = None
    output_tail: str | None = None


class HistoryResponse(BaseModel):
    """Paginated response for the run-history list endpoint.

    Attributes:
        runs: List of run summaries for the current page.
        total: Total number of runs in the database (for pagination).
    """

    runs: list[RunSummary]
    total: int
