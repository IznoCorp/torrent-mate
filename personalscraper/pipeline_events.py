"""Pipeline-level event catalog.

Eight events flow through the bus around every pipeline run:

- :class:`PipelineStarted` / :class:`PipelineEnded` — outer lifecycle.
- :class:`StepStarted` / :class:`StepCompleted` / :class:`StepErrored` —
  per-step lifecycle around each of the 9 pipeline steps.
- :class:`ItemProgressed` — per-item progress notification.
- :class:`PipelinePaused` / :class:`PipelineResumed` — pause checkpoint
  lifecycle (between steps, sentinel-driven).

All eight are frozen dataclasses inheriting from
:class:`personalscraper.core.event_bus.Event`. ``kw_only=True`` is declared
explicitly on every subclass — dataclass machinery does NOT inherit it
transitively, and without it the base's defaulted fields (``timestamp``,
``source``, ``event_id``, ``correlation_id``) would force every concrete
field to carry a default (DESIGN §Event base).

Auto-registration into ``_EVENT_CLASS_REGISTRY`` happens through
``Event.__init_subclass__``; the module is eagerly imported by
``personalscraper.events`` so the registry is populated before the first
envelope round-trip.

This module is the **flat companion** to ``personalscraper/pipeline.py`` —
converting ``pipeline.py`` to a package and moving these classes inside
``pipeline/events.py`` is explicitly out of scope for the event-bus feature
(deferred to a future refactor; see DESIGN §Naming).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from personalscraper.core.event_bus import Event
from personalscraper.models import PipelineReport, StepReport


@dataclass(frozen=True, kw_only=True)
class PipelineStarted(Event):
    """Emitted once at the start of :meth:`Pipeline.run`.

    Attributes:
        report: The freshly-constructed :class:`PipelineReport` (empty
            ``steps`` mapping, ``started_at`` set, ``finished_at`` None).
    """

    report: PipelineReport


@dataclass(frozen=True, kw_only=True)
class PipelineEnded(Event):
    """Emitted exactly once at the end of :meth:`Pipeline.run` (success or failure).

    Attributes:
        report: The fully-populated :class:`PipelineReport` (every step
            either added a :class:`StepReport` or raised; ``finished_at`` set).
    """

    report: PipelineReport


@dataclass(frozen=True, kw_only=True)
class StepStarted(Event):
    """Emitted just before each pipeline step begins executing.

    Attributes:
        step: Step identifier (``"ingest"``, ``"sort"``, ``"clean"``,
            ``"scrape"``, ``"cleanup"``, ``"enforce"``, ``"verify"``,
            ``"trailers"``, ``"dispatch"``).
    """

    step: str


@dataclass(frozen=True, kw_only=True)
class StepCompleted(Event):
    """Emitted after a pipeline step returns successfully.

    Attributes:
        step: Step identifier (see :class:`StepStarted.step`).
        report: The :class:`StepReport` produced by the step.
        elapsed_s: Wall-clock duration of the step in seconds (``time.monotonic`` delta).
    """

    step: str
    report: StepReport
    elapsed_s: float


@dataclass(frozen=True, kw_only=True)
class StepErrored(Event):
    """Emitted when a pipeline step raises an exception during execution.

    Attributes:
        step: Step identifier (see :class:`StepStarted.step`).
        error_class: Exception class name (``type(exc).__name__``).
        error_message: Stringified exception (``str(exc)``).
    """

    step: str
    error_class: str
    error_message: str


@dataclass(frozen=True, kw_only=True)
class ItemProgressed(Event):
    """Emitted by a pipeline step for each item it processes.

    ``details`` MUST contain only JSON-safe primitives (str, int, float,
    bool, None, list, dict) — the bus encoder raises ``TypeError`` on
    anything else.

    Attributes:
        step: Step identifier emitting the progress (see :class:`StepStarted.step`).
        item: Per-item identifier (filename, IMDb id, torrent hash, …).
        status: Short status tag (``"scraped"``, ``"skipped"``, ``"failed"``,
            ``"moved"``, …) — the vocabulary is per-step.
        details: Optional JSON-safe payload of step-specific extras
            (confidence score, provider name, error reason, …).
    """

    step: str
    item: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class PipelinePaused(Event):
    """Emitted when the pipeline pauses at a step boundary.

    The pause is cooperative: the engine blocks at the next
    :meth:`PauseController.checkpoint` call (between steps) until the
    ``pipeline.pause`` sentinel file is cleared.

    No extra fields — the event itself is the signal. Consumers (web UI,
    log subscribers) react to its presence.
    """


@dataclass(frozen=True, kw_only=True)
class PipelineResumed(Event):
    """Emitted when the pipeline resumes after a pause.

    Fired once the ``pipeline.pause`` sentinel is cleared and the
    engine proceeds to the next step. Pairs with
    :class:`PipelinePaused` — every pause that entered the wait loop
    emits exactly one ``PipelineResumed`` when it exits.

    No extra fields — the event itself is the signal.
    """


__all__ = [
    "ItemProgressed",
    "PipelineEnded",
    "PipelinePaused",
    "PipelineResumed",
    "PipelineStarted",
    "StepCompleted",
    "StepErrored",
    "StepStarted",
]
