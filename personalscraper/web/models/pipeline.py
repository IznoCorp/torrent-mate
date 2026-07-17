"""Pydantic models for the pipeline control API (pipe-control feature).

See docs/features/pipe-control/DESIGN.md §4 for the route contract these
models serve.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel


def parse_steps_json(steps_json: str | None) -> list[dict[str, object]]:
    """Deserialize a ``pipeline_run.steps_json`` column into step-entry dicts.

    This is the single owner of ``steps_json`` deserialization (WEB-BACKEND-06):
    every route/read site that needs the per-step summaries goes through here,
    then applies its own domain logic on the returned list. Consolidating the
    ×3 previously-divergent copies removes the drift between them:

    - divergent exception tuples — ``(JSONDecodeError, TypeError)`` in
      ``acquisition._parse_run_counts`` / ``pipeline._parse_steps`` /
      ``decisions`` activity vs ``(JSONDecodeError, TypeError, ValueError)`` in
      ``pipeline_history_detail`` vs ``(JSONDecodeError, TypeError, KeyError)``
      in ``pipeline._build_status``;
    - divergent shape guards — most sites checked ``isinstance(steps, list)``,
      but the ``decisions`` activity read did ``reversed(steps)`` with no guard
      (a non-list JSON value would raise ``TypeError`` outside its ``try``), and
      ``pipeline_history_detail`` iterated raw entries calling ``s.get(...)``
      without filtering non-dict members (an ``AttributeError`` waiting to 500).

    The consolidated semantics are the strictest correct union: the widest
    fail-soft exception set, a mandatory ``list`` guard, and non-dict entries
    dropped so every consumer receives a homogeneous ``list[dict]``.

    Args:
        steps_json: The raw ``pipeline_run.steps_json`` column value (may be
            ``None`` or an empty string for a run that recorded no steps).

    Returns:
        The list of step-entry dicts in recorded order (last entry = the
        live/most-recent step). An empty list for a ``None``/empty column, a
        malformed payload, or a non-list JSON value — parsing a run's history
        must never raise.
    """
    if not steps_json:
        return []
    try:
        raw = json.loads(steps_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    return [step for step in raw if isinstance(step, dict)]


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
        run_uid: The unique identifier of the newly launched pipeline run, or
            of the ``pipeline-queue`` row when the launch was queued.
        queued: ``True`` when the lock was held by a maintenance/resolve run —
            the launch waits in the visible queue (§6) and executes when the
            lock frees; the UI shows « En file » instead of « lancé ».
    """

    run_uid: str
    queued: bool = False


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

    The five count fields (webui-ux Phase 2.2) mirror the
    :class:`~personalscraper.models.StepReport` summary persisted into
    ``steps_json`` so the interpreted last-run report survives past the live
    WS event stream. They are all optional and default to ``None`` for legacy
    ``steps_json`` entries written before Phase 2.2 (fail-soft parsing).

    Attributes:
        name: Human-readable step name (e.g. ``"ingest"``, ``"sort"``).
        status: Step status (``"done"``, ``"running"``, ``"error"``, etc.).
        started_at: ISO 8601 UTC timestamp of step start, or ``None``.
        ended_at: ISO 8601 UTC timestamp of step end, or ``None``.
        elapsed_s: Step duration in seconds, or ``None`` if either timestamp
            is missing.
        success_count: StepReport ``success_count``, or ``None`` for a legacy
            entry that predates the persisted summary.
        skip_count: StepReport ``skip_count``, or ``None`` for a legacy entry.
        error_count: StepReport ``error_count``, or ``None`` for a legacy entry.
        unmatched_count: Number of folders the scraper could not confidently
            match (length of StepReport ``unmatched_paths``), or ``None`` for a
            legacy entry.
        counts: StepReport ``counts`` sub-category dict, or ``None`` when the
            step tracks no sub-categories / for a legacy entry.
        reasons: Bounded list of human-readable reason strings explaining WHY
            the step skipped / deferred / errored (StepReport warnings +
            details), or ``None`` for a step with nothing to report / a legacy
            entry. Lets the run detail show the "why" after the live stream is
            gone (§8).
    """

    name: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    elapsed_s: float | None = None
    success_count: int | None = None
    skip_count: int | None = None
    error_count: int | None = None
    unmatched_count: int | None = None
    counts: dict[str, int] | None = None
    reasons: list[str] | None = None


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


#: The five ring-states a Flow Board station can be in (mirrors the frontend
#: ``StageState`` union in ``StageStation.tsx``).
StageStateT = Literal["idle", "ok", "active", "attention", "blocked"]

#: The five sub-count tones (mirrors the frontend ``StatusTone`` union).
StageToneT = Literal["success", "warning", "danger", "info", "neutral"]


class StageSplit(BaseModel):
    """One sub-count shown inside a Flow Board station.

    Example: the Matching station splits its pending decisions into
    ``ambigu`` / ``sans correspondance`` / ``incertain`` buckets, each a
    :class:`StageSplit` with its own tone.

    Attributes:
        label: Human-readable French sub-count label.
        count: Number of items in this sub-bucket.
        tone: Semantic tone driving the dot colour on the station.
    """

    label: str
    count: int
    tone: StageToneT


class PipelineStage(BaseModel):
    """Aggregated state of one Flow Board stage (OBJ1 living pipeline).

    A stage rolls up one or more real pipeline steps (or, for ``matching``,
    the pending ``scrape_decision`` queue) into a single station: a headline
    ``count``, a derived ring ``state``, the ``attention`` / ``blocked`` item
    counts feeding that state, and an optional ``split`` of sub-counts.

    Attributes:
        key: Stable machine identifier (e.g. ``"scraping"``).
        label: French display label (e.g. ``"Scraping"``).
        count: Headline item count at this stage (successfully processed, or
            — for ``matching`` — the number of pending decisions).
        state: Derived ring state (``idle`` / ``ok`` / ``active`` /
            ``attention`` / ``blocked``).
        attention: Number of items needing an operator look (soft signal —
            unmatched folders, pending decisions).
        blocked: Number of items that errored at this stage (hard signal).
        split: Optional sub-counts (e.g. réussi / ignoré / erreur), or
            ``None`` when the stage has nothing meaningful to break down.
    """

    key: str
    label: str
    count: int
    state: StageStateT
    attention: int = 0
    blocked: int = 0
    split: list[StageSplit] | None = None


class StagesResponse(BaseModel):
    """Response body for ``GET /api/pipeline/stages`` (Flow Board).

    Each station carries the CURRENT STOCK of media at that position
    (single-position axiom, P0-A.1/A.3); the last run's throughput lives in
    the header fields, never on the stations.

    Attributes:
        stages: The eight stations in board (left-to-right flow) order.
        run_uid: The latest pipeline run, or ``None`` when none was recorded.
        run_state: Live pipeline run-state (``idle`` / ``running`` /
            ``paused``) — drives whether the active stage pulses.
        updated_at: Epoch seconds of the latest run's start, or ``None``.
        run_trigger: The latest run's trigger (e.g. ``watch`` / ``manual`` /
            ``cron``), or ``None`` — lets the board caption its provenance.
        run_processed: How many media the latest run processed (max across
            its steps of success+error+unmatched), or ``None`` — feeds the
            board header « Dernier run · il y a X · N médias traités ».
    """

    stages: list[PipelineStage]
    run_uid: str | None = None
    run_state: PipelineState
    updated_at: float | None = None
    run_trigger: str | None = None
    run_processed: int | None = None
