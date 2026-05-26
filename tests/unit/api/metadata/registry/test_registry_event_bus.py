"""Unit tests for ``ProviderRegistry`` event-bus safety (DESIGN §7.4, §8.2).

``_event_bus_safe_emit`` wraps every ``bus.emit()`` call — it must never
propagate and must log failures at WARNING. The constructor emits
``RegistryBootValidated`` through the wrapper, so these tests exercise it
via construction rather than via ``locked()`` (which lands in sub-phase 0.5b).
"""

from __future__ import annotations

import pytest

from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import FailingEventBus, FakeMultiCapability

# ---------------------------------------------------------------------------
# event_bus=None — no-op
# ---------------------------------------------------------------------------


def test_event_bus_none_accepted_no_op(build_registry: object) -> None:
    """``ProviderRegistry`` accepts ``event_bus=None`` — emissions become no-op."""
    fakes = {"tmdb": FakeMultiCapability(name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=None,
    )
    # Construction succeeded without error — _event_bus_safe_emit was a no-op.
    assert registry is not None


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
