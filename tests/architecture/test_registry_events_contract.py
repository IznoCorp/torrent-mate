"""Architecture test: registry events conform to the Event contract (arch-cleanup-2 Phase 1).

Invariants:
- All 5 classes in api/metadata/registry/_events.py subclass Event.
- All 5 are in _EVENT_CLASS_REGISTRY after importing personalscraper.events.
- All 5 round-trip through event_to_envelope / event_from_envelope.
- EVERY registered event (drive off _EVENT_CLASS_REGISTRY + EVENT_SAMPLE_FACTORIES)
  round-trips through a full JSON envelope cycle and compares equal — this guards
  the Phase-5 NameError regression where get_type_hints could not resolve
  AttemptOutcome / ProviderMatch on three registry events (arch-cleanup-2 Phase 5).
- Public import path from registry package is preserved.
"""

from __future__ import annotations

import json

import pytest

# Trigger auto-registration of all production events including registry events.
import personalscraper.events  # noqa: F401
from personalscraper.api.metadata.registry import _events as reg_events
from personalscraper.core.event_bus import (
    _EVENT_CLASS_REGISTRY,
    Event,
    event_from_envelope,
    event_to_envelope,
)
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

_REGISTRY_EVENT_NAMES = [
    "ProviderFallbackTriggered",
    "ProviderExhaustedEvent",
    "LockedCapabilityUnresolved",
    "RegistryFanOutCompleted",
    "RegistryBootValidated",
]


@pytest.mark.parametrize("name", _REGISTRY_EVENT_NAMES)
def test_registry_event_subclasses_event(name: str) -> None:
    """Each registry event class is an Event subclass."""
    cls = getattr(reg_events, name)
    assert issubclass(cls, Event), f"{name} does not subclass Event"


@pytest.mark.parametrize("name", _REGISTRY_EVENT_NAMES)
def test_registry_event_in_catalog(name: str) -> None:
    """Each registry event is registered in _EVENT_CLASS_REGISTRY.

    Design: docs/reference/architecture.md#registry-events-on-the-event-contract
    Contract: the 5 registry events subclass Event and are auto-registered in _EVENT_CLASS_REGISTRY.
    """
    assert name in _EVENT_CLASS_REGISTRY, (
        f"{name} missing from _EVENT_CLASS_REGISTRY. Registered: {sorted(_EVENT_CLASS_REGISTRY)}"
    )


def test_provider_fallback_triggered_round_trips() -> None:
    """ProviderFallbackTriggered survives envelope round-trip."""
    ev = reg_events.ProviderFallbackTriggered(
        capability="MetadataClient",
        from_provider="tmdb",
        to_provider="tvdb",
        reason="network",
        exc_type="requests.Timeout",
        item={"title": "Test", "year": 2024},
    )
    reconstructed = event_from_envelope(event_to_envelope(ev))
    assert reconstructed == ev


def test_registry_boot_validated_round_trips() -> None:
    """RegistryBootValidated survives envelope round-trip."""
    ev = reg_events.RegistryBootValidated(
        providers=("tmdb", "tvdb"),
        capabilities={"MetadataClient": ("tmdb", "tvdb")},
    )
    reconstructed = event_from_envelope(event_to_envelope(ev))
    assert reconstructed == ev


def test_public_import_path_preserved() -> None:
    """Registry events are importable from the registry package public surface."""
    from personalscraper.api.metadata.registry import (  # noqa: F401
        ProviderFallbackTriggered,
        RegistryBootValidated,
    )


@pytest.mark.parametrize("event_name", sorted(_EVENT_CLASS_REGISTRY))
def test_every_registered_event_round_trips_through_json(event_name: str) -> None:
    """Every registered event survives a full JSON envelope round-trip equal.

    Drives off ``_EVENT_CLASS_REGISTRY`` (the production catalog) crossed with
    ``EVENT_SAMPLE_FACTORIES`` (one real-data factory per event). Each sample
    event is serialized to an envelope, JSON-encoded, JSON-decoded, then
    reconstructed via ``event_from_envelope`` and asserted equal to the original.

    Regression: before arch-cleanup-2 Phase 5, ``ProviderExhaustedEvent``,
    ``RegistryFanOutCompleted`` (``tuple[AttemptOutcome, ...]``) and
    ``LockedCapabilityUnresolved`` (``match: ProviderMatch``) raised
    ``NameError`` here because ``_events.py`` imported those names only under
    ``TYPE_CHECKING`` while ``get_type_hints`` evaluated the string annotations
    at runtime. This test fails on the pre-fix code and passes after the leaf
    ``_types`` module makes them runtime-importable.
    """
    cls = _EVENT_CLASS_REGISTRY[event_name]
    factory = EVENT_SAMPLE_FACTORIES.get(cls)
    assert factory is not None, (
        f"No EVENT_SAMPLE_FACTORIES entry for registered event {event_name!r}; "
        f"add a factory in tests/fixtures/event_samples.py so the round-trip is exercised."
    )
    original = factory()
    round_tripped = event_from_envelope(json.loads(json.dumps(event_to_envelope(original))))
    assert round_tripped == original
