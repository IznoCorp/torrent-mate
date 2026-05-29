"""Unit tests for ``ProviderRegistry.fan_out()`` (DESIGN §6.3, §8.2).

All tests are xfail-decorated except ``test_fan_out_wrong_semantic_raises``,
which exercises the synchronous semantic guard.
"""

from __future__ import annotations

import pytest

from personalscraper.api.metadata._contracts import RatingProvider, Searchable
from personalscraper.api.metadata.registry._errors import WrongSemanticBug
from personalscraper.api.metadata.registry._events import RegistryFanOutCompleted
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.core.circuit import CircuitState

from .conftest import FakeRating, FakeSearchable

# ---------------------------------------------------------------------------
# All-eligible iteration
# ---------------------------------------------------------------------------


def test_fan_out_all_eligible_iteration(build_registry: object) -> None:
    """Every CLOSED/HALF_OPEN RatingProvider must appear in ``fan_out().values``."""
    fakes = {
        "r1": FakeRating(provider_name="r1", circuit_state=CircuitState.CLOSED),
        "r2": FakeRating(provider_name="r2", circuit_state=CircuitState.HALF_OPEN),
    }
    config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    result = registry.fan_out(RatingProvider)
    names = [p.provider_name for p in result.values]
    assert set(names) == {"r1", "r2"}
    # No filtered providers => attempted is empty.
    # Frozen-dataclass invariant (I5): ``attempted`` is a ``tuple``.
    assert result.attempted == ()


# ---------------------------------------------------------------------------
# Circuit-OPEN exclusion
# ---------------------------------------------------------------------------


def test_fan_out_excludes_open_circuit(build_registry: object) -> None:
    """OPEN-circuit providers are filtered out of ``fan_out()``."""
    fakes = {
        "r1": FakeRating(provider_name="r1", circuit_state=CircuitState.OPEN),
        "r2": FakeRating(provider_name="r2", circuit_state=CircuitState.CLOSED),
    }
    config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    result = registry.fan_out(RatingProvider)
    names = [p.provider_name for p in result.values]
    assert names == ["r2"]
    # r1 was OPEN — recorded in attempted with circuit_open reason.
    assert [a.provider for a in result.attempted] == ["r1"]
    assert result.attempted[0].reason == "circuit_open"


# ---------------------------------------------------------------------------
# Empty results (no error — fan_out is best-effort)
# ---------------------------------------------------------------------------


def test_fan_out_empty_when_no_eligible(build_registry: object) -> None:
    """``fan_out().values`` is ``[]`` when no provider is eligible — no error."""
    fakes = {
        "r1": FakeRating(provider_name="r1", circuit_state=CircuitState.OPEN),
        "r2": FakeRating(provider_name="r2", circuit_state=CircuitState.OPEN),
    }
    config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    result = registry.fan_out(RatingProvider)
    assert result.values == ()
    # Both providers attempted but filtered.
    assert [a.provider for a in result.attempted] == ["r1", "r2"]
    assert all(a.reason == "circuit_open" for a in result.attempted)


def test_fan_out_empty_when_all_capability_filtered(build_registry: object) -> None:
    """``fan_out().values`` is ``[]`` when no provider is configured under the section."""
    fakes = {"x": FakeSearchable(provider_name="x")}
    # RatingProvider section is empty — no providers under fan_out at all.
    config = ProvidersConfig(Searchable={"x": 1}, RatingProvider={})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    result = registry.fan_out(RatingProvider)
    assert result.values == ()
    assert result.attempted == ()


# ---------------------------------------------------------------------------
# WrongSemanticBug
# ---------------------------------------------------------------------------


def test_fan_out_wrong_semantic_raises(build_registry: object) -> None:
    """``fan_out(Searchable)`` must raise ``WrongSemanticBug`` (Searchable is chain, not fan_out).

    Design: docs/reference/architecture.md#three-operations
    Design: docs/reference/scraping.md#three-semantics-provider-registry
    Contract: fan_out with wrong semantic raises WrongSemanticBug, validating the three operation modes.
    """
    fakes = {"x": FakeSearchable(provider_name="x")}
    config = ProvidersConfig(Searchable={"x": 1})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    with pytest.raises(WrongSemanticBug):
        registry.fan_out(Searchable)


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


def test_RegistryFanOutCompleted_always_emitted_even_on_success(
    build_registry: object,
    mock_event_bus: object,
) -> None:
    """``RegistryFanOutCompleted`` is emitted by ``fan_out()`` (DESIGN §6.3 last paragraph).

    Even on full success the event must fire — provenance must be observable
    without log-scraping.
    """
    fakes = {"r1": FakeRating(provider_name="r1", circuit_state=CircuitState.CLOSED)}
    config = ProvidersConfig(RatingProvider={"r1": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=mock_event_bus,
    )
    registry.fan_out(RatingProvider)
    assert any(isinstance(e, RegistryFanOutCompleted) for e in mock_event_bus.emitted)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AttemptOutcome population (sub-phase 5.4)
# ---------------------------------------------------------------------------


def test_fan_out_populates_attempted_with_circuit_open_skips(
    build_registry: object,
    mock_event_bus: object,
) -> None:
    """RegistryFanOutCompleted.attempted carries reason='circuit_open' for filtered providers."""
    fakes = {
        "r1": FakeRating(provider_name="r1", circuit_state=CircuitState.OPEN),
        "r2": FakeRating(provider_name="r2", circuit_state=CircuitState.CLOSED),
    }
    config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=mock_event_bus,
    )
    registry.fan_out(RatingProvider)
    event = next(e for e in mock_event_bus.emitted if isinstance(e, RegistryFanOutCompleted))  # type: ignore[attr-defined]
    assert len(event.attempted) == 1
    open_entry = next(a for a in event.attempted if a.reason == "circuit_open")
    assert open_entry.provider == "r1"
    assert event.eligible == 1


def test_fan_out_attempted_empty_when_no_providers_configured(
    build_registry: object,
    mock_event_bus: object,
) -> None:
    """When the index has no providers for capability, attempted list is empty (not an error)."""
    config = ProvidersConfig(RatingProvider={})
    registry = build_registry(  # type: ignore[operator]
        fakes={},
        providers_config=config,
        event_bus=mock_event_bus,
    )
    registry.fan_out(RatingProvider)
    event = next(e for e in mock_event_bus.emitted if isinstance(e, RegistryFanOutCompleted))  # type: ignore[attr-defined]
    assert event.attempted == ()
    assert event.eligible == 0
