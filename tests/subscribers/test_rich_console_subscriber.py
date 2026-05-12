"""Tests for :class:`RichConsoleSubscriber` — Sub-phase 3.5.

Locks the visual-regression contract against
``tests/snapshots/rich_console_canonical.txt`` (baseline frozen by INDEX
Pre-flight #7), plus subscription / teardown semantics.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from rich.console import Console

from personalscraper.core.event_bus import EventBus
from personalscraper.observers.rich_console import RichConsoleObserver
from personalscraper.pipeline_events import (
    ItemProgressed,
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)
from personalscraper.subscribers.rich_console import RichConsoleSubscriber
from tests.fixtures.event_bus import CollectingSubscriber
from tests.snapshots._canonical_sequence import (
    CANONICAL_OBSERVER_CONFIGS,
    CANONICAL_SEQUENCE,
)

BASELINE_PATH = Path(__file__).resolve().parents[1] / "snapshots" / "rich_console_canonical.txt"


def _make_recording_console() -> Console:
    """Build a deterministic Console with output recording enabled."""
    return Console(
        width=120,
        color_system=None,
        force_terminal=False,
        file=StringIO(),
        record=True,
    )


def _translate_and_emit(bus: EventBus, callback: str, args: tuple[Any, ...]) -> None:
    """Translate a legacy Observer callback into a bus emit.

    The mapping table mirrors the one documented in
    ``phase-03-pipeline-events-migration.md`` §Sub-phase 3.5.
    """
    if callback == "on_pipeline_start":
        bus.emit(PipelineStarted(report=args[0]))
    elif callback == "on_pipeline_end":
        bus.emit(PipelineEnded(report=args[0]))
    elif callback == "on_step_start":
        bus.emit(StepStarted(step=args[0]))
    elif callback == "on_step_end":
        bus.emit(StepCompleted(step=args[0], report=args[1], elapsed_s=args[2]))
    elif callback == "on_step_error":
        exc = args[1]
        bus.emit(StepErrored(step=args[0], error_class=type(exc).__name__, error_message=str(exc)))
    elif callback == "on_progress":
        step_event = args[0]
        bus.emit(
            ItemProgressed(
                step=step_event.step,
                item=step_event.item,
                status=step_event.status,
                details=step_event.details,
            )
        )
    else:
        raise AssertionError(f"unknown legacy callback in canonical sequence: {callback!r}")


def _replay_sequence_through_subscriber(config: dict[str, Any], console: Console) -> RichConsoleSubscriber:
    """Replay the canonical sequence into one subscriber bound to ``console``."""
    bus = EventBus()
    subscriber = RichConsoleSubscriber(bus, console=console, **config)
    for callback, args in CANONICAL_SEQUENCE:
        _translate_and_emit(bus, callback, args)
    return subscriber


def _replay_sequence_through_observer(config: dict[str, Any], console: Console) -> RichConsoleObserver:
    """Replay the canonical sequence directly into the legacy observer."""
    observer = RichConsoleObserver(console=console, **config)
    for callback, args in CANONICAL_SEQUENCE:
        getattr(observer, callback)(*args)
    return observer


def test_rich_console_subscriber_subscribes_on_init() -> None:
    """``__init__`` registers exactly six subscription tokens."""
    bus = EventBus()
    sub = RichConsoleSubscriber(bus)
    assert len(sub._tokens) == 6  # noqa: SLF001


def test_rich_console_subscriber_close_unsubscribes_all() -> None:
    """``close()`` removes every subscription so further emits are no-ops."""
    bus = EventBus()
    sub = RichConsoleSubscriber(bus)
    sub.close()
    # After close, a fresh CollectingSubscriber is the only listener on the bus.
    sentinel = CollectingSubscriber(bus, ItemProgressed)
    bus.emit(ItemProgressed(step="ingest", item="x", status="started"))
    assert len(sentinel.received) == 1  # noqa: PLR2004 — exactly one collector got the emit
    # And the closed subscriber never re-renders anything (tokens cleared).
    assert sub._tokens == []  # noqa: SLF001


def test_rich_console_subscriber_snapshot_matches_baseline() -> None:
    """Replay both canonical configs through the subscriber; expect baseline equality."""
    console = _make_recording_console()
    for config in CANONICAL_OBSERVER_CONFIGS:
        _replay_sequence_through_subscriber(config, console)
    rendered = console.export_text()
    expected = BASELINE_PATH.read_text(encoding="utf-8")
    assert rendered == expected, (
        "RichConsoleSubscriber output diverged from the canonical baseline.\n"
        "Fix the subscriber rendering — DO NOT re-record the baseline inside Phase 3."
    )


# TODO(3.7a): delete this test when RichConsoleObserver is removed.
def test_rich_console_subscriber_outputs_match_legacy_observer_directly() -> None:
    """In-process side-by-side check of subscriber vs legacy observer outputs."""
    for config in CANONICAL_OBSERVER_CONFIGS:
        observer_console = _make_recording_console()
        subscriber_console = _make_recording_console()
        _replay_sequence_through_observer(config, observer_console)
        _replay_sequence_through_subscriber(config, subscriber_console)
        assert subscriber_console.export_text() == observer_console.export_text()
