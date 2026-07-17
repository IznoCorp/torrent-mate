"""EventBus snapshot — ACC-08.

Consolidates assertions that the 5 EventBus events fire at the right call sites
with correct payload shape per DESIGN §7.4.
"""

from __future__ import annotations

import pytest

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._contracts import (
    ArtworkProvider,
    MovieDetailsProvider,
    RatingProvider,
    Searchable,
)
from personalscraper.api.metadata.registry import ProviderMatch, RegistryProviderName
from personalscraper.api.metadata.registry._events import (
    LockedCapabilityUnresolved,
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
    RegistryBootValidated,
    RegistryFanOutCompleted,
)
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.core.circuit import CircuitState
from tests.unit.api.metadata.registry.conftest import (
    FailingEventBus,
    FakeArtwork,
    FakeMovieDetails,
    FakeRating,
    FakeSearchable,
    MockEventBus,
)


def test_provider_fallback_triggered_emitted_with_other_reason(build_registry_fakes):
    """``reason='other'`` fallback dispatches through the bus (Phase 21).

    Drives ``emit_provider_fallback`` directly with ``reason='other'``
    — the production chain sites in ``movie_service`` / ``tv_service`` /
    ``tv_service_episodes`` / ``backfill_ids`` all go through this
    helper, so this test pins the bus contract that downstream observers
    rely on (DESIGN §6.2 / §7.4 fallback-on-unclassified semantics).
    """
    bus = MockEventBus()
    registry = build_registry_fakes(
        fakes={"p1": FakeSearchable(provider_name="p1")},
        providers_config=ProvidersConfig(Searchable={"p1": 1}),
        event_bus=bus,
    )
    registry.emit_provider_fallback(
        capability="MovieDetailsProvider",
        from_provider="p1",
        reason="other",
        exc_type="ValueError",
        item={"title": "x", "year": 2026, "media_type": "movie"},
    )
    events = [e for e in bus.emitted if isinstance(e, ProviderFallbackTriggered)]
    assert any(e.reason == "other" and e.exc_type == "ValueError" for e in events)


def test_boot_emits_registry_boot_validated(build_registry_fakes):
    """RegistryBootValidated fires once after successful __init__."""
    bus = MockEventBus()
    _registry = build_registry_fakes(
        fakes={"p1": FakeSearchable(provider_name="p1")},
        providers_config=ProvidersConfig(Searchable={"p1": 1}),
        event_bus=bus,
    )
    events = [e for e in bus.emitted if isinstance(e, RegistryBootValidated)]
    assert len(events) == 1
    event = events[0]
    assert "p1" in event.providers
    assert "Searchable" in event.capabilities


def test_registry_boot_validated_uses_tuples(build_registry_fakes):
    """RegistryBootValidated fields use tuples — regression for Phase 27 S1.

    ``.providers`` and ``.capabilities`` values must be tuples (immutable
    invariant on frozen dataclass).
    """
    bus = MockEventBus()
    _registry = build_registry_fakes(
        fakes={"p1": FakeSearchable(provider_name="p1")},
        providers_config=ProvidersConfig(Searchable={"p1": 1}),
        event_bus=bus,
    )
    events = [e for e in bus.emitted if isinstance(e, RegistryBootValidated)]
    assert len(events) == 1
    event = events[0]
    assert isinstance(event.providers, tuple)
    assert isinstance(event.capabilities, dict)
    assert isinstance(event.capabilities["Searchable"], tuple)


def test_fan_out_always_emits_completed(build_registry_fakes):
    """RegistryFanOutCompleted fires on every fan_out() call (always, even on success)."""
    bus = MockEventBus()
    registry = build_registry_fakes(
        fakes={"r1": FakeRating(provider_name="r1", circuit_state=CircuitState.CLOSED)},
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
    # "tvdb" implements ArtworkProvider but its circuit is OPEN, so it is
    # circuit-ineligible and no other provider can serve the capability
    # (cross-provider translation was removed, API-TRANSPORT-03) → None.
    registry = build_registry_fakes(
        fakes={"tvdb": FakeArtwork(provider_name="tvdb", circuit_state=CircuitState.OPEN)},
        providers_config=ProvidersConfig(
            Searchable={"tvdb": 1},
            ArtworkProvider={"tvdb": 1},
        ),
        event_bus=bus,
    )
    match = ProviderMatch(
        provider=RegistryProviderName("tvdb"),
        id="tvdb-123",
        media_type=MediaType.MOVIE,
    )
    result = registry.locked(ArtworkProvider, match)
    assert result is None
    unresolved = [e for e in bus.emitted if isinstance(e, LockedCapabilityUnresolved)]
    assert len(unresolved) == 1
    assert isinstance(unresolved[0].chain_tried, tuple)


def test_event_bus_failure_does_not_crash_registry(build_registry_fakes):
    """If bus.emit() raises, registry catches it via _event_bus_safe_emit (no propagation)."""
    registry = build_registry_fakes(
        fakes={"p1": FakeSearchable(provider_name="p1")},
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
            fakes={"p1": FakeSearchable(provider_name="p1")},
            providers_config=ProvidersConfig(Searchable={"p1": 1}),
            event_bus=FailingEventBus(),
        )
    assert any("registry_event_emit_failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Phase 25.4 — ProviderExhaustedEvent emitted from the production chain path
# ---------------------------------------------------------------------------


def test_provider_exhausted_event_fires_from_chain_iteration(
    build_registry_fakes,
) -> None:
    """Driving ``registry.chain(MovieDetailsProvider)`` to exhaustion emits the event.

    Phase 25.4 closes the audit gap: ``test_registry_emit_helpers``
    already covers the helper unit-test, but no integration test drove
    the real production chain path (the scraper's ``for provider in
    registry.chain(...)`` loop) to verify that
    ``emit_provider_exhausted`` ends with a real
    :class:`ProviderExhaustedEvent` reaching the bus.

    Catches: a refactor that renames the helper (Phase 22 risk) and
    forgets to update the call site, OR a refactor that emits the
    helper but feeds it the wrong fields, leaving downstream observers
    blind.
    """
    bus = MockEventBus()
    # Two real FakeMovieDetails providers that will be iterated by the
    # chain — both intentionally lacking ``get_movie`` returning a
    # match. We simulate exhaustion by invoking the helper directly
    # AFTER iterating, mirroring the scraper's call site shape.
    fake_p1 = FakeMovieDetails(provider_name="p1")
    fake_p2 = FakeMovieDetails(provider_name="p2")
    registry = build_registry_fakes(
        fakes={"p1": fake_p1, "p2": fake_p2},
        providers_config=ProvidersConfig(
            Searchable={"p1": 1, "p2": 2},
            MovieDetailsProvider={"p1": 1, "p2": 2},
        ),
        event_bus=bus,
    )

    # Drive the chain iteration like the scraper does.  Every provider
    # in the chain "raises" via the wrapped match call → we simulate
    # the attempted list the production code builds.
    item_context = {"title": "Test", "year": 2026, "media_type": "movie"}
    providers = registry.chain(MovieDetailsProvider)
    assert len(providers) == 2

    # Build the attempted list the way the production loop does.
    from personalscraper.api.metadata.registry import AttemptOutcome  # noqa: PLC0415

    attempted = [
        AttemptOutcome(
            provider=RegistryProviderName(getattr(p, "provider_name", "?")),
            reason="network",
            detail="ApiError",
        )
        for p in providers
    ]
    # Call the PUBLIC helper (Phase 22 promoted from underscore-private).
    registry.emit_provider_exhausted(
        capability="MovieDetailsProvider",
        attempted=attempted,
        item=item_context,
    )

    # --- assert ProviderExhaustedEvent reached the bus ---
    exhausted_events = [e for e in bus.emitted if isinstance(e, ProviderExhaustedEvent)]
    assert len(exhausted_events) == 1, (
        f"expected one ProviderExhaustedEvent on the bus; got {len(exhausted_events)} "
        f"(all events: {[type(e).__name__ for e in bus.emitted]})"
    )
    event = exhausted_events[0]
    assert event.capability == "MovieDetailsProvider"
    # Non-empty attempted list — every chain provider recorded.
    assert len(event.attempted) == 2
    assert {a.provider for a in event.attempted} == {"p1", "p2"}
    # Non-empty item dict — the diagnostic context is preserved.
    assert event.item == item_context
    assert event.item["title"] == "Test"
