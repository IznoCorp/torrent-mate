"""Unit tests for ``ProviderRegistry`` event-bus safety (DESIGN §7.4, §8.2).

``_event_bus_safe_emit`` wraps every ``bus.emit()`` call — it must never
propagate and must log failures at WARNING. The constructor emits
``RegistryBootValidated`` through the wrapper, so these tests exercise it
via construction rather than via ``locked()`` (which lands in sub-phase 0.5b).

The project architectural contract (event-bus 0.14.0) requires ``event_bus:
EventBus`` on every public site — no ``| None`` permitted. Tests pass a
MockEventBus or FailingEventBus, never None.
"""

from __future__ import annotations

import inspect

import pytest

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import FailingEventBus, FakeMultiCapability

# ---------------------------------------------------------------------------
# event_bus is required, never None
# ---------------------------------------------------------------------------


def test_event_bus_required_param_no_none_default() -> None:
    """``ProviderRegistry.__init__`` requires ``event_bus: EventBus`` — no ``| None``."""
    sig = inspect.signature(ProviderRegistry.__init__)
    param = sig.parameters["event_bus"]

    # The annotation must not include None.
    annot = param.annotation
    # When ``from __future__ import annotations`` is active, annotations are
    # strings. Check for the union operator in the string form.
    annot_str = str(annot)
    assert "| None" not in annot_str, f"event_bus annotation must not accept None: got {annot_str!r}"
    assert "None" not in annot_str, f"event_bus annotation must not mention None at all: got {annot_str!r}"

    # The default is inspect.Parameter.empty (required parameter).
    assert param.default is inspect.Parameter.empty, "event_bus must be a required parameter (no default)"


# ---------------------------------------------------------------------------
# emit() failure does not propagate
# ---------------------------------------------------------------------------


def test_event_bus_emit_failure_does_not_propagate(build_registry: object) -> None:
    """If ``event_bus.emit()`` raises, the registry catches it — caller never sees the exception."""
    fakes = {"tmdb": FakeMultiCapability(name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=FailingEventBus(),
    )
    # Construction succeeded — _event_bus_safe_emit caught the FailingEventBus error.
    assert registry is not None


# ---------------------------------------------------------------------------
# emit() failure logs WARNING
# ---------------------------------------------------------------------------


def test_event_bus_emit_failure_logs_warning(
    build_registry: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When ``bus.emit()`` raises, ``registry_event_emit_failed`` is logged at WARNING."""
    fakes = {"tmdb": FakeMultiCapability(name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    with caplog.at_level("WARNING"):
        build_registry(  # type: ignore[operator]
            fakes=fakes,
            providers_config=config,
            event_bus=FailingEventBus(),
        )
    assert any("registry_event_emit_failed" in r.message for r in caplog.records)
