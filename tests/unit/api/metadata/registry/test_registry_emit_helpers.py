"""Unit tests for the chain-iteration emit helpers (DESIGN §6.2 / §7.4).

``ProviderRegistry._emit_provider_fallback`` and
``ProviderRegistry._emit_provider_exhausted`` are the centralised emission
sites used by every chain iteration call site (movie_service, tv_service,
existing_validator). Production code never re-implements the dataclass
construction — these helpers are the only authorised path.

Test plan:

- ``_emit_provider_fallback`` builds a :class:`ProviderFallbackTriggered`
  with the right capability, from/to provider, reason, exc_type, and item
  payload, then routes it through ``_event_bus_safe_emit``.
- ``_emit_provider_exhausted`` builds a :class:`ProviderExhaustedEvent`
  with the right capability, attempted list, and item payload, then routes
  it through ``_event_bus_safe_emit``.
- Both helpers are safe in the face of a failing bus (delegated to
  ``_event_bus_safe_emit``), so a ``FailingEventBus`` does not propagate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.api.metadata.registry import (
    AttemptOutcome,
    RegistryProviderName,
)
from personalscraper.api.metadata.registry._events import (
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
)
from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import FailingEventBus, FakeMultiCapability, MockEventBus

if TYPE_CHECKING:
    pass


def test_emit_provider_fallback_constructs_expected_event(build_registry: object) -> None:
    """``_emit_provider_fallback`` emits a fully populated ProviderFallbackTriggered."""
    bus = MockEventBus()
    fakes = {"tmdb": FakeMultiCapability(provider_name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=bus,
    )
    bus.emitted.clear()  # Drop the boot-validated event for clarity.

    registry._emit_provider_fallback(
        capability="MovieDetailsProvider",
        from_provider="tmdb",
        reason="empty_result",
        item={"title": "The Matrix", "year": 1999},
    )

    assert len(bus.emitted) == 1
    event = bus.emitted[0]
    assert isinstance(event, ProviderFallbackTriggered)
    assert event.capability == "MovieDetailsProvider"
    assert event.from_provider == "tmdb"
    assert event.to_provider == ""  # Unknown at emit time.
    assert event.reason == "empty_result"
    assert event.exc_type is None
    assert event.item == {"title": "The Matrix", "year": 1999}


def test_emit_provider_fallback_network_reason_carries_exc_type(build_registry: object) -> None:
    """Network reason carries an ``exc_type`` populated by the caller."""
    bus = MockEventBus()
    fakes = {"tmdb": FakeMultiCapability(provider_name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=bus,
    )
    bus.emitted.clear()

    registry._emit_provider_fallback(
        capability="MovieDetailsProvider",
        from_provider="tmdb",
        to_provider="tvdb",
        reason="network",
        exc_type="ConnectionError",
        item={"title": "Heat", "year": 1995},
    )

    assert len(bus.emitted) == 1
    event = bus.emitted[0]
    assert isinstance(event, ProviderFallbackTriggered)
    assert event.reason == "network"
    assert event.exc_type == "ConnectionError"
    assert event.from_provider == "tmdb"
    assert event.to_provider == "tvdb"


def test_emit_provider_exhausted_constructs_expected_event(build_registry: object) -> None:
    """``_emit_provider_exhausted`` emits a ProviderExhaustedEvent with the attempted list."""
    bus = MockEventBus()
    fakes = {"tmdb": FakeMultiCapability(provider_name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=bus,
    )
    bus.emitted.clear()

    attempted = [
        AttemptOutcome(provider=RegistryProviderName("tmdb"), reason="empty_result"),
        AttemptOutcome(provider=RegistryProviderName("tvdb"), reason="circuit_open"),
    ]
    registry._emit_provider_exhausted(
        capability="MovieDetailsProvider",
        attempted=attempted,
        item={"title": "Unknown Film", "year": None},
    )

    assert len(bus.emitted) == 1
    event = bus.emitted[0]
    assert isinstance(event, ProviderExhaustedEvent)
    assert event.capability == "MovieDetailsProvider"
    assert list(event.attempted) == attempted
    assert event.item == {"title": "Unknown Film", "year": None}


def test_emit_helpers_swallow_failing_bus(build_registry: object) -> None:
    """A FailingEventBus does not propagate through the emit helpers."""
    fakes = {"tmdb": FakeMultiCapability(provider_name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=FailingEventBus(),
    )

    # Neither call should raise — _event_bus_safe_emit swallows.
    registry._emit_provider_fallback(
        capability="MovieDetailsProvider",
        from_provider="tmdb",
        reason="empty_result",
        item={"title": "X", "year": None},
    )
    registry._emit_provider_exhausted(
        capability="MovieDetailsProvider",
        attempted=[
            AttemptOutcome(provider=RegistryProviderName("tmdb"), reason="empty_result"),
        ],
        item={"title": "X", "year": None},
    )
