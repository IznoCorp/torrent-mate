"""Unit tests for ``ProviderRegistry.chain()`` (DESIGN §6.2, §8.2).

All tests that exercise unimplemented registry method bodies are wrapped
with ``@pytest.mark.xfail(raises=NotImplementedError, strict=True)`` —
the corresponding registry methods raise ``NotImplementedError`` at this
sub-phase (TDD discipline). Sub-phase 0.5a will remove the decorators as
each method body lands.
"""

from __future__ import annotations

import pytest

from personalscraper.api.metadata._contracts import RatingProvider, Searchable
from personalscraper.api.metadata.registry._errors import WrongSemanticBug
from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import FakeSearchable

# ---------------------------------------------------------------------------
# Stable-order
# ---------------------------------------------------------------------------


def test_chain_ordering_is_stable_across_calls(build_registry: object) -> None:
    """``chain()`` must return the same order across repeated calls (DESIGN §5.2).

    Design: docs/reference/architecture.md#provider-registry
    Design: docs/reference/architecture.md#module-layout
    Contract: provider registry chain ordering is stable across calls and reflects module layout.
    """
    fakes = {
        "a": FakeSearchable(provider_name="a"),
        "b": FakeSearchable(provider_name="b"),
    }
    config = ProvidersConfig(Searchable={"a": 1, "b": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    first = [p.provider_name for p in registry.chain(Searchable)]
    second = [p.provider_name for p in registry.chain(Searchable)]
    assert first == second
    assert first == ["a", "b"]


# ---------------------------------------------------------------------------
# Circuit-state filtering
# ---------------------------------------------------------------------------


def test_chain_skips_open_circuit(build_registry: object) -> None:
    """A provider whose circuit is OPEN must be filtered out of ``chain()``."""
    fakes = {
        "open_one": FakeSearchable(provider_name="open_one", circuit_state="OPEN"),
        "closed_one": FakeSearchable(provider_name="closed_one", circuit_state="CLOSED"),
    }
    config = ProvidersConfig(Searchable={"open_one": 1, "closed_one": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.chain(Searchable)
    names = [p.provider_name for p in providers]
    assert "open_one" not in names
    assert "closed_one" in names


def test_chain_includes_half_open_providers(build_registry: object) -> None:
    """HALF_OPEN providers are eligible (probe semantics — DESIGN §7.6)."""
    fakes = {
        "ho": FakeSearchable(provider_name="ho", circuit_state="HALF_OPEN"),
        "cl": FakeSearchable(provider_name="cl", circuit_state="CLOSED"),
    }
    config = ProvidersConfig(Searchable={"ho": 1, "cl": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.chain(Searchable)
    names = [p.provider_name for p in providers]
    assert "ho" in names
    assert "cl" in names


# ---------------------------------------------------------------------------
# WrongSemanticBug (no xfail — guard can be checked synchronously)
# ---------------------------------------------------------------------------


def test_chain_wrong_semantic_raises(build_registry: object) -> None:
    """``chain(RatingProvider)`` must raise ``WrongSemanticBug`` (RatingProvider is fan_out).

    Design: docs/reference/architecture.md#three-operations
    Design: docs/reference/scraping.md#three-semantics-provider-registry
    Contract: chain with wrong semantic raises WrongSemanticBug, validating the three operation modes.
    """
    fakes = {"x": FakeSearchable(provider_name="x")}
    config = ProvidersConfig(Searchable={"x": 1})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    with pytest.raises(WrongSemanticBug):
        registry.chain(RatingProvider)


# ---------------------------------------------------------------------------
# Mid-iteration state changes + exhaustion
# ---------------------------------------------------------------------------


def test_chain_provider_flips_to_open_mid_iteration(build_registry: object) -> None:
    """A provider that flips CLOSED→OPEN between two ``chain()`` calls is excluded thereafter."""
    fake_a = FakeSearchable(provider_name="a", circuit_state="CLOSED")
    fake_b = FakeSearchable(provider_name="b", circuit_state="CLOSED")
    fakes = {"a": fake_a, "b": fake_b}
    config = ProvidersConfig(Searchable={"a": 1, "b": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]

    first = [p.provider_name for p in registry.chain(Searchable)]
    assert first == ["a", "b"]
    # Flip "a" to OPEN — the next chain() must exclude it.
    fake_a.circuit.state = "OPEN"
    second = [p.provider_name for p in registry.chain(Searchable)]
    assert second == ["b"]


def test_chain_empty_when_all_open(build_registry: object) -> None:
    """If every provider has circuit OPEN, ``chain()`` returns an empty list."""
    fakes = {
        "x": FakeSearchable(provider_name="x", circuit_state="OPEN"),
        "y": FakeSearchable(provider_name="y", circuit_state="OPEN"),
    }
    config = ProvidersConfig(Searchable={"x": 1, "y": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    assert registry.chain(Searchable) == []


# ---------------------------------------------------------------------------
# Caller-side skip helpers — chain() returns the raw eligible list; the
# caller iterates and decides on skip. These tests pin the registry-side
# expectation: a HALF_OPEN/CLOSED provider with circuit eligible IS
# returned. Network/empty-result skipping is exercised at the caller level
# (orchestrator), but the registry's chain() ordering must still let those
# skips happen — checked here by verifying the candidate is present.
# ---------------------------------------------------------------------------


def test_chain_half_open_raises_network_error_falls_to_next(build_registry: object) -> None:
    """When a HALF_OPEN provider raises NetworkError mid-iteration, fallback to next.

    From the registry's perspective: ``chain()`` returns ``[ho, cl]``. The
    caller iterates and catches the NetworkError raised by ``ho.search()``,
    then proceeds to ``cl``. This test pins the registry contract that
    HALF_OPEN providers are included so the fallback path can fire.
    """
    fakes = {
        "ho": FakeSearchable(provider_name="ho", circuit_state="HALF_OPEN"),
        "cl": FakeSearchable(provider_name="cl", circuit_state="CLOSED"),
    }
    config = ProvidersConfig(Searchable={"ho": 1, "cl": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.chain(Searchable)
    # Both must be eligible; the caller-side network-error fallback is exercised in integration tests.
    assert [p.provider_name for p in providers] == ["ho", "cl"]


def test_chain_network_exception_skip(build_registry: object) -> None:
    """The registry must keep the ordered list intact so callers can skip on NetworkError.

    Mirrors DESIGN §6.2 — the registry returns eligible providers; the
    caller is responsible for catching the network exception and moving on.
    """
    fakes = {
        "a": FakeSearchable(provider_name="a", circuit_state="CLOSED"),
        "b": FakeSearchable(provider_name="b", circuit_state="CLOSED"),
    }
    config = ProvidersConfig(Searchable={"a": 1, "b": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.chain(Searchable)
    assert [p.provider_name for p in providers] == ["a", "b"]


def test_chain_empty_result_skip(build_registry: object) -> None:
    """Empty-result is a caller-side skip — chain() still returns the provider.

    The registry does not pre-call ``search()`` to filter empties; the
    caller iterates and records ``empty_result`` in its ``AttemptOutcome``
    list (DESIGN §6.2 / §7.3).
    """
    fakes = {
        "empty": FakeSearchable(provider_name="empty", results=[], circuit_state="CLOSED"),
        "next": FakeSearchable(provider_name="next", results=[], circuit_state="CLOSED"),
    }
    config = ProvidersConfig(Searchable={"empty": 1, "next": 2})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.chain(Searchable)
    assert [p.provider_name for p in providers] == ["empty", "next"]
