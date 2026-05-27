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

from .conftest import FakeRating, FakeSearchable

# ---------------------------------------------------------------------------
# All-eligible iteration
# ---------------------------------------------------------------------------


def test_fan_out_all_eligible_iteration(build_registry: object) -> None:
    """Every CLOSED/HALF_OPEN RatingProvider must appear in ``fan_out()``."""
    fakes = {
        "r1": FakeRating(name="r1", circuit_state="CLOSED"),
        "r2": FakeRating(name="r2", circuit_state="HALF_OPEN"),
    }
    config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.fan_out(RatingProvider)
    names = [p.name for p in providers]
    assert set(names) == {"r1", "r2"}


# ---------------------------------------------------------------------------
# Circuit-OPEN exclusion
# ---------------------------------------------------------------------------


def test_fan_out_excludes_open_circuit(build_registry: object) -> None:
    """OPEN-circuit providers are filtered out of ``fan_out()``."""
    fakes = {
        "r1": FakeRating(name="r1", circuit_state="OPEN"),
        "r2": FakeRating(name="r2", circuit_state="CLOSED"),
    }
    config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.fan_out(RatingProvider)
    names = [p.name for p in providers]
    assert names == ["r2"]


# ---------------------------------------------------------------------------
# Empty results (no error — fan_out is best-effort)
# ---------------------------------------------------------------------------


def test_fan_out_empty_when_no_eligible(build_registry: object) -> None:
    """``fan_out()`` returns ``[]`` when no provider is eligible — no error."""
    fakes = {
        "r1": FakeRating(name="r1", circuit_state="OPEN"),
        "r2": FakeRating(name="r2", circuit_state="OPEN"),
    }
    config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    assert registry.fan_out(RatingProvider) == []


def test_fan_out_empty_when_all_capability_filtered(build_registry: object) -> None:
    """``fan_out()`` returns ``[]`` when no provider is configured under the section."""
    fakes = {"x": FakeSearchable(name="x")}
    # RatingProvider section is empty — no providers under fan_out at all.
    config = ProvidersConfig(Searchable={"x": 1}, RatingProvider={})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    assert registry.fan_out(RatingProvider) == []


# ---------------------------------------------------------------------------
# WrongSemanticBug
# ---------------------------------------------------------------------------


def test_fan_out_wrong_semantic_raises(build_registry: object) -> None:
    """``fan_out(Searchable)`` must raise ``WrongSemanticBug`` (Searchable is chain, not fan_out).

    Design: docs/reference/architecture.md#three-operations
    Design: docs/reference/scraping.md#three-semantics-provider-registry
    Contract: fan_out with wrong semantic raises WrongSemanticBug, validating the three operation modes.
    """
    fakes = {"x": FakeSearchable(name="x")}
    config = ProvidersConfig(Searchable={"x": 1})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    with pytest.raises(WrongSemanticBug):
        registry.fan_out(Searchable)  # type: ignore[arg-type]


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
    fakes = {"r1": FakeRating(name="r1", circuit_state="CLOSED")}
    config = ProvidersConfig(RatingProvider={"r1": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=mock_event_bus,
    )
    registry.fan_out(RatingProvider)
    assert any(isinstance(e, RegistryFanOutCompleted) for e in mock_event_bus.emitted)  # type: ignore[attr-defined]
