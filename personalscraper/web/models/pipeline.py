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
