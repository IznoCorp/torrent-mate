"""Smoke tests for the acquire event catalog (Phase 1 gate)."""

from __future__ import annotations

import dataclasses
import json

import pytest

import personalscraper.events  # noqa: F401 — eager-import side effect
from personalscraper.acquire.events import (
    GrabFailed,
    GrabSucceeded,
    RatioMeasured,
    SeedObligationBreached,
    SeedObligationRecorded,
    SeedObligationSatisfied,
    SeriesFollowed,
    SeriesUnfollowed,
    WantedAbandoned,
    WantedEnqueued,
)
from personalscraper.core.event_bus import (
    _EVENT_CLASS_REGISTRY,
    Event,
    event_from_envelope,
    event_to_envelope,
)
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

ACQUIRE_EVENT_CLASSES: tuple[type[Event], ...] = (
    SeriesFollowed,
    SeriesUnfollowed,
    WantedEnqueued,
    WantedAbandoned,
    GrabSucceeded,
    GrabFailed,
    SeedObligationRecorded,
    SeedObligationBreached,
    SeedObligationSatisfied,
    RatioMeasured,
)


@pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_acquire_events_inherit_event_base(cls: type[Event]) -> None:
    """Every acquire event inherits from Event."""
    assert issubclass(cls, Event)


@pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_acquire_events_are_frozen(cls: type[Event]) -> None:
    """Every acquire event is a frozen dataclass."""
    assert dataclasses.is_dataclass(cls)
    instance = EVENT_SAMPLE_FACTORIES[cls]()
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.source = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_acquire_events_auto_registered(cls: type[Event]) -> None:
    """Each acquire event class name appears in _EVENT_CLASS_REGISTRY."""
    assert _EVENT_CLASS_REGISTRY.get(cls.__name__) is cls


@pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_acquire_events_envelope_roundtrip(cls: type[Event]) -> None:
    """Envelope round-trip preserves equality for every acquire event (incl. MediaRef)."""
    e1 = EVENT_SAMPLE_FACTORIES[cls]()
    envelope = event_to_envelope(e1)
    e2 = event_from_envelope(json.loads(json.dumps(envelope)))
    assert e2 == e1, f"Round-trip failed for {cls.__name__}: {e2!r} != {e1!r}"
