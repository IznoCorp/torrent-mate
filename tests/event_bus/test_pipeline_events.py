"""Tests for the pipeline event catalog — Sub-phase 3.1.

Six events flow through the bus around every pipeline run. This test module
locks:

- Each event inherits from :class:`Event` and stays a frozen dataclass.
- Each event is auto-registered in ``_EVENT_CLASS_REGISTRY``.
- Each event has a registered factory in :data:`EVENT_SAMPLE_FACTORIES`.
- Each event survives ``event_to_envelope`` → ``json.dumps`` →
  ``json.loads`` → ``event_from_envelope`` with equality preserved (the
  gate test that exercises the Report round-trip path validated in the
  pre-3.1 investigation commits).
- The generic ``test_every_event_has_factory`` assertion (vacuous in
  Phase 1) is now non-vacuous — it covers all 6 pipeline events.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from personalscraper.core.event_bus import (
    _EVENT_CLASS_REGISTRY,
    Event,
    event_from_envelope,
    event_to_envelope,
)
from personalscraper.pipeline_events import (
    ItemProgressed,
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

PIPELINE_EVENT_CLASSES: tuple[type[Event], ...] = (
    PipelineStarted,
    PipelineEnded,
    StepStarted,
    StepCompleted,
    StepErrored,
    ItemProgressed,
)


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_inherit_event_base(cls: type[Event]) -> None:
    """Every pipeline event inherits from :class:`Event`."""
    assert issubclass(cls, Event)


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_are_frozen(cls: type[Event]) -> None:
    """Every pipeline event is a frozen dataclass."""
    assert dataclasses.is_dataclass(cls)
    instance = EVENT_SAMPLE_FACTORIES[cls]()
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.source = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_auto_registered(cls: type[Event]) -> None:
    """Each event class name appears in ``_EVENT_CLASS_REGISTRY``."""
    assert _EVENT_CLASS_REGISTRY.get(cls.__name__) is cls


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_have_factories(cls: type[Event]) -> None:
    """Each event has a registered factory in ``EVENT_SAMPLE_FACTORIES``."""
    assert cls in EVENT_SAMPLE_FACTORIES


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_envelope_roundtrip(cls: type[Event]) -> None:
    """Envelope round-trip preserves equality for every pipeline event.

    The gate test — exercises Report serialization across the
    JSON-coerced fields fixed in the pre-3.1 investigation commits
    (``failed_items`` → ``list[FailedItem]``; ``details_payload`` →
    ``dict[str, Any]``).
    """
    e1 = EVENT_SAMPLE_FACTORIES[cls]()
    envelope = event_to_envelope(e1)
    e2 = event_from_envelope(json.loads(json.dumps(envelope)))
    assert e2 == e1


def test_every_event_has_factory() -> None:
    """Every production-registered event has a factory (Sub-phase 1.8 gate).

    Vacuous in Phase 1 (no production events). Phase 3.1 makes it
    non-vacuous — the 6 pipeline events live in the registry and every
    one MUST have a factory. Phase 4 will add more events; each must
    register its factory before the phase gate.
    """
    registered = set(_EVENT_CLASS_REGISTRY.values())
    factored = set(EVENT_SAMPLE_FACTORIES.keys())
    assert registered, "Phase 3.1: registry is non-empty (6 pipeline events)"
    missing = registered - factored
    assert not missing, (
        f"Production events missing factories in EVENT_SAMPLE_FACTORIES: {sorted(c.__name__ for c in missing)}"
    )


def test_event_registry_has_eighteen_v1_events() -> None:
    """The v1 catalog is pinned at 18 events.

    Phase 5 acceptance landed at 13 ; the ``provider-ids`` feature
    (sub-phase 8.4) added 4 ``Backfill*`` events for the IDs/ratings
    backfill lifecycle (→ 17). The ``tech-debt`` 0.16.0 sub-phase 3.1
    (DEV #6/#40) added ``VerifyItemDone`` for per-item verify
    telemetry (→ 18). The literal count guards against silent
    additions that bypass the documented event catalog in
    ``docs/reference/event-bus.md`` (Phase 8.13 ships the v1.2 catalog
    sync that bumps the doc table from 17 to 18).
    """
    import personalscraper.events  # noqa: F401 — eager-import side effect
    import personalscraper.verify.events  # noqa: F401 — eager-import side effect

    assert len(_EVENT_CLASS_REGISTRY) == 18, (
        f"Expected 18 v1 events, found {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}"
    )


def test_item_progressed_details_defaults_to_empty_dict() -> None:
    """``ItemProgressed.details`` defaults to ``{}`` for steps that emit no extras."""
    event = ItemProgressed(step="ingest", item="file.mkv", status="moved")
    assert event.details == {}


def test_step_completed_elapsed_s_is_float() -> None:
    """``StepCompleted.elapsed_s`` is the wall-clock duration in seconds."""
    event = EVENT_SAMPLE_FACTORIES[StepCompleted]()
    assert isinstance(event, StepCompleted)
    assert isinstance(event.elapsed_s, float)
    assert event.elapsed_s > 0
