"""Architecture test: registry events conform to the Event contract (arch-cleanup-2 Phase 1).

Invariants:
- All 5 classes in api/metadata/registry/_events.py subclass Event.
- All 5 are in _EVENT_CLASS_REGISTRY after importing personalscraper.events.
- All 5 round-trip through event_to_envelope / event_from_envelope.
- Public import path from registry package is preserved.
"""

from __future__ import annotations

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
    Contract: the five provider-registry events are full Event subclasses, auto-registered in _EVENT_CLASS_REGISTRY so base-Event subscribers receive them.
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
