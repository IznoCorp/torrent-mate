"""Pipeline step protocol and context bundle."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from personalscraper.core.app_context import AppContext
    from personalscraper.models import StepReport


@dataclass(frozen=True)
class StepContext:
    """Immutable context bundle passed to every pipeline step adapter.

    Sub-phase 3.7b shape: the ``observers`` field is removed — the
    :class:`EventBus` carried by ``ctx.app.event_bus`` is the sole emit
    substrate. Every step reads its config/settings via ``ctx.app.config``
    / ``ctx.app.settings``.

    Attributes:
        app: Process-scoped service bundle (config, settings, event_bus).
        run_id: Per-run UUID, identifies a single pipeline invocation.
        dry_run: If True, preview operations without side effects.
        interactive: If True, prompt before destructive actions.
        verbose: If True, emit detailed progress output.
        upstream: Reports from previously executed steps, keyed by step name.
        extras: Mutable mapping for ad-hoc cross-step data.
    """

    app: "AppContext"
    run_id: UUID
    dry_run: bool
    interactive: bool
    verbose: bool
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]


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
