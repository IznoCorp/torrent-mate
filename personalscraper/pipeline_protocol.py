"""Pipeline step protocol, context bundle, and shared per-item reporter."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline_events import ItemProgressed, StepItemStatus

if TYPE_CHECKING:
    from personalscraper.core.app_context import AppContext


@dataclass(frozen=True)
class StepContext:
    """Immutable context bundle passed to every pipeline step adapter.

    The :class:`EventBus` carried by ``ctx.app.event_bus`` is the sole emit
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


# ---------------------------------------------------------------------------
# Status-to-counter mapping for :func:`record`.
#
# Derived from the counter conventions in every run_* module across all 9
# pipeline steps.  Each status from :class:`StepItemStatus` maps to exactly
# one counter on :class:`StepReport`.
#
# Source evidence (one representative per group):
#
# SUCCESS group → ``report.success_count += 1``:
#   - ``copied``:   personalscraper/ingest/ingest.py:536
#   - ``matched``:  personalscraper/scraper/run.py:395,405,411
#   - ``moved``:    personalscraper/sorter/run.py:108,119
#                   personalscraper/dispatch/run.py:167,340
#   - ``fixed``:    personalscraper/enforce/run.py:74,111,137
#   - ``ok``:       personalscraper/verify/run.py:135,190
#   - ``cleaned``:  personalscraper/process/run.py:198
#   - ``replaced``: personalscraper/dispatch/run.py:167,340
#   - ``merged``:   personalscraper/dispatch/run.py:167,340
#   - ``removed``:  personalscraper/process/run.py:250
#
# SKIP group → ``report.skip_count += 1``:
#   - ``skipped``:  personalscraper/sorter/run.py:130
#                   personalscraper/dispatch/run.py:342
#   - ``skipped_low_confidence``: personalscraper/scraper/run.py:416-417
#   - ``blocked``:  personalscraper/verify/run.py:198
#   - ``queued_for_decision``: (no counter increment today; mapped to
#       skip for forward compat with scrape loop integration in P1.3)
#
# ERROR group → ``report.error_count += 1``:
#   - ``failed``:   personalscraper/ingest/ingest.py:570
#   - ``error``:    personalscraper/sorter/run.py:142
#                   personalscraper/dispatch/run.py:347
#                   personalscraper/scraper/run.py:427
#
# NEUTRAL (no counter increment):
#   - ``started``:  emitted by every step before work begins
# ---------------------------------------------------------------------------

_SUCCESS_STATUSES: frozenset[str] = frozenset(
    {
        StepItemStatus.COPIED,
        StepItemStatus.MATCHED,
        StepItemStatus.MOVED,
        StepItemStatus.FIXED,
        StepItemStatus.OK,
        StepItemStatus.CLEANED,
        StepItemStatus.REPLACED,
        StepItemStatus.MERGED,
        StepItemStatus.REMOVED,
    }
)

_SKIP_STATUSES: frozenset[str] = frozenset(
    {
        StepItemStatus.SKIPPED,
        StepItemStatus.SKIPPED_LOW_CONFIDENCE,
        StepItemStatus.BLOCKED,
        StepItemStatus.QUEUED_FOR_DECISION,
    }
)

_ERROR_STATUSES: frozenset[str] = frozenset(
    {
        StepItemStatus.FAILED,
        StepItemStatus.ERROR,
    }
)


def record(
    report: StepReport,
    bus: EventBus,
    *,
    step: str,
    item: str,
    status: StepItemStatus | str,
    detail: str | None = None,
    warning: str | None = None,
    event_details: Mapping[str, Any] | None = None,
) -> None:
    """Record a per-item progress event and update the step report.

    Emits exactly one :class:`ItemProgressed` event on *bus* and increments
    the matching counter on *report*.  ``status`` controls the counter
    destination:

    * **success_count**: ``copied``, ``matched``, ``moved``, ``fixed``,
      ``ok``, ``cleaned``, ``replaced``, ``merged``, ``removed``.
    * **skip_count**: ``skipped``, ``skipped_low_confidence``, ``blocked``,
      ``queued_for_decision``.
    * **error_count**: ``failed``, ``error``.
    * **no counter**: ``started`` and any other unrecognised status
      (non-terminal lifecycle events).

    The counter mapping is declared in the module-level ``_SUCCESS_STATUSES``,
    ``_SKIP_STATUSES``, and ``_ERROR_STATUSES`` frozensets, derived from the
    conventions in every ``run_*`` module.  See those frozensets for the
    source file:line evidence.

    Args:
        report: Step report whose counters, details, and warnings are mutated
            in-place.
        bus: Required in-process EventBus.  The event is emitted immediately.
        step: Step identifier (``"sort"``, ``"dispatch"``, …).
        item: Per-item identifier (filename, IMDb id, torrent hash, …).
        status: Terminal status from :class:`StepItemStatus` (or a raw
            string normalised via ``str(status)``).
        detail: Optional detail string appended to ``report.details``.
        warning: Optional warning string appended to ``report.warnings``.
        event_details: Optional JSON-safe payload attached to the emitted
            :class:`ItemProgressed` event's ``details`` field (provider name,
            confidence, destination disk, error reason, …).  ``None`` leaves
            the event's ``details`` at its empty-dict default.  This is the
            structured-payload channel; it never affects ``report`` counters or
            ``report.details``/``report.warnings``.
    """
    status_str = str(status)
    if event_details is not None:
        bus.emit(ItemProgressed(step=step, item=item, status=status_str, details=dict(event_details)))
    else:
        bus.emit(ItemProgressed(step=step, item=item, status=status_str))

    if status_str in _SUCCESS_STATUSES:
        report.success_count += 1
    elif status_str in _SKIP_STATUSES:
        report.skip_count += 1
    elif status_str in _ERROR_STATUSES:
        report.error_count += 1
    # else: "started" and unrecognised statuses are neutral — no counter change

    if detail is not None:
        report.details.append(detail)
    if warning is not None:
        report.warnings.append(warning)


__all__ = [
    "PipelineStep",
    "StepContext",
    "is_pipeline_step",
    "record",
]
