"""Pipeline step protocol and context bundle."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.app_context import AppContext
    from personalscraper.models import StepReport
    from personalscraper.pipeline_observer import PipelineObserver


@dataclass(frozen=True)
class StepContext:
    """Immutable context bundle passed to every pipeline step adapter.

    Sub-phase 2.2a transitional shape: ``app`` + ``run_id`` are NEW required
    fields. ``config`` and ``settings`` are now derived from ``app`` via
    ``__post_init__`` and declared ``field(init=False)`` — callers cannot
    pass them and so cannot create a mismatched context. Both names point
    to the same object (``self.app.config``) so callsite migration in
    Sub-phase 2.2b is purely cosmetic, and 2.2c drops the legacy mirrors.

    Attributes:
        app: Process-scoped service bundle (config, settings, event_bus).
        run_id: Per-run UUID, identifies a single pipeline invocation.
        dry_run: If True, preview operations without side effects.
        interactive: If True, prompt before destructive actions.
        verbose: If True, emit detailed progress output.
        observers: Tuple of pipeline observers (REMOVED in Phase 3.7b).
        upstream: Reports from previously executed steps, keyed by step name.
        extras: Mutable mapping for ad-hoc cross-step data.
        config: Mirror of ``app.config`` — derived, NOT a constructor arg.
        settings: Mirror of ``app.settings`` — derived, NOT a constructor arg.
    """

    app: "AppContext"
    run_id: UUID
    dry_run: bool
    interactive: bool
    verbose: bool
    observers: tuple["PipelineObserver", ...]
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]
    # Legacy mirrors — populated by __post_init__, removed in 2.2c once all
    # callsites read via ctx.app.config / ctx.app.settings. ``init=False``
    # keeps callers from passing a mismatched value (no runtime assert needed).
    config: "Config" = field(init=False)
    settings: "Settings" = field(init=False)

    def __post_init__(self) -> None:
        """Populate the derived legacy mirrors from ``app``.

        Frozen dataclass — uses ``object.__setattr__`` to bypass the freeze
        guard. Same pattern as ``Event.__post_init__`` (1.1).
        """
        object.__setattr__(self, "config", self.app.config)
        object.__setattr__(self, "settings", self.app.settings)


@runtime_checkable
class PipelineStep(Protocol):
    """Callable pipeline step contract.

    Every pipeline step must expose a ``name`` attribute and be callable
    with a single ``StepContext`` argument.  Steps may return a plain
    ``StepReport`` or a ``(StepReport, extras)`` tuple.
    """

    name: str

    def __call__(self, ctx: StepContext) -> "StepReport | tuple[StepReport, Any]": ...  # noqa: D102


def is_pipeline_step(obj: Any) -> bool:
    """Return True when *obj* satisfies the runtime step convention.

    Checks that *obj* is an instance of ``PipelineStep`` (structural
    subtyping via ``@runtime_checkable``) and that its ``name`` attribute
    is a non-empty string.

    Args:
        obj: Object to test against the PipelineStep protocol.

    Returns:
        True if *obj* is a valid pipeline step.
    """
    if not isinstance(obj, PipelineStep):
        return False
    name = getattr(obj, "name", None)
    return isinstance(name, str) and bool(name)


__all__ = ["PipelineStep", "StepContext", "is_pipeline_step"]
