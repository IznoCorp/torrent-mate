"""EventBus snapshot — ACC-08.

Consolidates assertions that the 5 EventBus events fire at the right call sites
with correct payload shape per DESIGN §7.4.
"""

from __future__ import annotations

import pytest

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._contracts import ArtworkProvider, RatingProvider, Searchable
from personalscraper.api.metadata.registry import ProviderMatch, ProviderName
from personalscraper.api.metadata.registry._events import (
    LockedCapabilityUnresolved,
    RegistryBootValidated,
    RegistryFanOutCompleted,
)
from personalscraper.conf.models.providers import ProvidersConfig
from tests.unit.api.metadata.registry.conftest import (
    FailingEventBus,
    FakeArtwork,
    FakeRating,
    FakeSearchable,
    MockEventBus,
)


def test_boot_emits_registry_boot_validated(build_registry_fakes):
    """RegistryBootValidated fires once after successful __init__."""
    bus = MockEventBus()
    _registry = build_registry_fakes(
        fakes={"p1": FakeSearchable(name="p1")},
        providers_config=ProvidersConfig(Searchable={"p1": 1}),
        event_bus=bus,
    )
    events = [e for e in bus.emitted if isinstance(e, RegistryBootValidated)]
    assert len(events) == 1
    event = events[0]
    assert "p1" in event.providers
    assert "Searchable" in event.capabilities


def test_fan_out_always_emits_completed(build_registry_fakes):
    """RegistryFanOutCompleted fires on every fan_out() call (always, even on success)."""
    bus = MockEventBus()
    registry = build_registry_fakes(
        fakes={"r1": FakeRating(name="r1", circuit_state="CLOSED")},
        providers_config=ProvidersConfig(RatingProvider={"r1": 1}),
        event_bus=bus,
    )
    registry.fan_out(RatingProvider)
    events = [e for e in bus.emitted if isinstance(e, RegistryFanOutCompleted)]
    assert len(events) == 1
    assert events[0].capability == "RatingProvider"


def test_locked_unresolved_emits_event(build_registry_fakes):
    """LockedCapabilityUnresolved fires when locked() returns None."""
    bus = MockEventBus()
    # "tmdb" is a FakeSearchable (no ArtworkProvider), listed in IDCrossRef so
    # locked-orphan validation passes, but cross_ref fails at runtime because
    # FakeSearchable doesn't implement IDCrossRef → locked() returns None.
    registry = build_registry_fakes(
        fakes={"tmdb": FakeSearchable(name="tmdb"), "tvdb": FakeArtwork(name="tvdb")},
        providers_config=ProvidersConfig(
            Searchable={"tmdb": 1, "tvdb": 2},
            ArtworkProvider={"tvdb": 1},
            IDCrossRef={"tmdb": 1},
        ),
        event_bus=bus,
    )
    match = ProviderMatch(
        provider=ProviderName("tmdb"),
        id="tmdb-123",
        media_type=MediaType.MOVIE,
    )
    result = registry.locked(ArtworkProvider, match)
    assert result is None
    assert any(isinstance(e, LockedCapabilityUnresolved) for e in bus.emitted)


def test_event_bus_failure_does_not_crash_registry(build_registry_fakes):
    """If bus.emit() raises, registry catches it via _event_bus_safe_emit (no propagation)."""
    registry = build_registry_fakes(
        fakes={"p1": FakeSearchable(name="p1")},
        providers_config=ProvidersConfig(Searchable={"p1": 1}),
        event_bus=FailingEventBus(),
    )
    result = registry.chain(Searchable)  # type: ignore[arg-type]
    assert isinstance(result, list)


def test_registry_event_emit_failed_logged_on_bus_failure(
    build_registry_fakes,
    caplog: pytest.LogCaptureFixture,
):
    """When bus.emit() raises, registry_event_emit_failed is logged at WARNING."""
    with caplog.at_level("WARNING"):
        build_registry_fakes(
            fakes={"p1": FakeSearchable(name="p1")},
            providers_config=ProvidersConfig(Searchable={"p1": 1}),
            event_bus=FailingEventBus(),
        )
    assert any("registry_event_emit_failed" in r.message for r in caplog.records)
