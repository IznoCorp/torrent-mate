"""Pipeline observer protocol and associated types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


@runtime_checkable
class PipelineObserver(Protocol):
    """Observer contract for pipeline lifecycle and per-item progress.

    Observers receive typed notifications at every pipeline boundary.
    Implement this Protocol to add custom behaviour (console output,
    Telegram notifications, WebSocket streaming, metrics collection)
    without modifying the pipeline core.
    """

    name: str

    def on_pipeline_start(self, report: PipelineReport) -> None:
        """Called before the pipeline loop begins."""
        ...

    def on_pipeline_end(self, report: PipelineReport) -> None:
        """Called after all steps complete."""
        ...

    def on_step_start(self, step: str) -> None:
        """Called before a step executes."""
        ...

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:
        """Called after a step completes successfully."""
        ...

    def on_step_error(self, step: str, error: Exception) -> None:
        """Called when a step raises an exception."""
        ...

    def on_progress(self, event: StepEvent) -> None:
        """Called for per-item progress during step execution."""
        ...


class PipelineObserverBase:
    """No-op base class for observers that only implement a subset of callbacks.

    Inherit from this class and override only the methods you need.
    """

    name = "base"

    def on_pipeline_start(self, report: PipelineReport) -> None:  # noqa: ARG002
        """No-op — override to receive pipeline start notification."""
        pass

    def on_pipeline_end(self, report: PipelineReport) -> None:  # noqa: ARG002
        """No-op — override to receive pipeline end notification."""
        pass

    def on_step_start(self, step: str) -> None:  # noqa: ARG002
        """No-op — override to receive step start notification."""
        pass

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:  # noqa: ARG002
        """No-op — override to receive step completion notification."""
        pass

    def on_step_error(self, step: str, error: Exception) -> None:  # noqa: ARG002
        """No-op — override to receive step error notification."""
        pass

    def on_progress(self, event: StepEvent) -> None:  # noqa: ARG002
        """No-op — override to receive per-item progress events."""
        pass


@dataclass(frozen=True)
class StepEvent:
    """Per-item progress event emitted by pipeline steps.

    Frozen (immutable) — events are fire-and-forget snapshots.

    Attributes:
        step: Step identifier (e.g. ``"ingest"``, ``"sort"``, ``"scrape"``).
        item: Human-readable item identifier (filename, folder name).
        status: Event status (``"started"``, ``"completed"``, ``"skipped"``, ``"failed"``).
        details: Optional structured payload (provider, confidence, size_mb, …).
    """

    step: str
    item: str
    status: str
    details: dict[str, object] = field(default_factory=dict)


def notify_progress(
    observers: tuple[PipelineObserver, ...],
    event: StepEvent,
) -> None:
    """Call ``on_progress`` on every observer.

    Survives individual observer failures — one broken observer must not
    crash the pipeline.

    Args:
        observers: Tuple of observers to notify.
        event: The progress event to emit.
    """
    for obs in observers:
        try:
            obs.on_progress(event)
        except Exception:
            pass


class CollectorObserver(PipelineObserverBase):
    """Records every callback for test assertions.

    Inherits from ``PipelineObserverBase`` (all no-ops) and overrides
    each callback to append to ordered lists.
    """

    name = "collector"

    def __init__(self) -> None:
        """Initialize empty recording lists."""
        super().__init__()
        self.pipeline_starts: list[PipelineReport] = []
        self.pipeline_ends: list[PipelineReport] = []
        self.starts: list[str] = []
        self.ends: list[tuple[str, StepReport, float]] = []
        self.errors: list[tuple[str, Exception]] = []
        self.progress: list[StepEvent] = []

    def on_pipeline_start(self, report: PipelineReport) -> None:
        """Record pipeline start."""
        self.pipeline_starts.append(report)

    def on_pipeline_end(self, report: PipelineReport) -> None:
        """Record pipeline end."""
        self.pipeline_ends.append(report)

    def on_step_start(self, step: str) -> None:
        """Record step start."""
        self.starts.append(step)

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:
        """Record step completion."""
        self.ends.append((step, report, elapsed))

    def on_step_error(self, step: str, error: Exception) -> None:
        """Record step error."""
        self.errors.append((step, error))

    def on_progress(self, event: StepEvent) -> None:
        """Record progress event."""
        self.progress.append(event)


__all__ = [
    "CollectorObserver",
    "PipelineObserver",
    "PipelineObserverBase",
    "StepEvent",
    "notify_progress",
]
