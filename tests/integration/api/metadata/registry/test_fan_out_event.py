"""Integration smoke test: fan_out(RatingProvider) always emits RegistryFanOutCompleted.

Even when no provider returns data (empty list), the event MUST fire (DESIGN §7.4 always-emit invariant).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from personalscraper.api.metadata._contracts import RatingProvider
from personalscraper.api.metadata.registry._events import RegistryFanOutCompleted
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.core.circuit import CircuitState
from tests._doubles.registry import MockEventBus
from tests.unit.api.metadata.registry.conftest import FakeRating


def _build_registry(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fakes: dict[str, Any],
    providers_config: ProvidersConfig,
    event_bus: Any = None,
) -> Any:
    """Build a ProviderRegistry from fake providers for integration testing.

    Monkeypatches ``_factory.build_providers`` and bypasses validators so
    the registry only exercises capability dispatch semantics.
    """
    from personalscraper.api.metadata.registry import ProviderRegistry, _factory, _validation

    if event_bus is None:
        event_bus = MockEventBus()

    def fake_build_providers(
        provider_names: list[str],
        settings_arg: Any,
        cb_policy_arg: Any,
        event_bus_arg: Any,
    ) -> dict[str, Any]:
        return {name: fakes[name] for name in provider_names if name in fakes}

    monkeypatch.setattr(_factory, "build_providers", fake_build_providers)
    monkeypatch.setattr(_validation, "_CRED_MAP", {})
    monkeypatch.setattr(_validation, "_check_empty_chain_sections", lambda _: [])
    monkeypatch.setattr(_validation, "_check_protocol_mismatch", lambda *a: [])

    return ProviderRegistry(
        settings=SimpleNamespace(),
        event_bus=event_bus,
        cb_policy=SimpleNamespace(),
        providers_config=providers_config,
    )


def test_fan_out_emits_completed_event_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """RegistryFanOutCompleted is emitted when fan_out returns eligible providers."""
    fakes = {"r1": FakeRating(provider_name="r1", circuit_state=CircuitState.CLOSED)}
    config = ProvidersConfig(RatingProvider={"r1": 1})
    bus = MockEventBus()
    registry = _build_registry(monkeypatch, fakes=fakes, providers_config=config, event_bus=bus)

    result = registry.fan_out(RatingProvider)
    assert len(result.values) >= 1
    assert any(isinstance(e, RegistryFanOutCompleted) for e in bus.emitted)


def test_fan_out_emits_completed_event_even_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """RegistryFanOutCompleted is emitted even when fan_out returns empty list."""
    fakes = {"r1": FakeRating(provider_name="r1", circuit_state=CircuitState.OPEN)}
    config = ProvidersConfig(RatingProvider={"r1": 1})
    bus = MockEventBus()
    registry = _build_registry(monkeypatch, fakes=fakes, providers_config=config, event_bus=bus)

    result = registry.fan_out(RatingProvider)
    assert result.values == ()
    assert any(isinstance(e, RegistryFanOutCompleted) and e.eligible == 0 for e in bus.emitted)
