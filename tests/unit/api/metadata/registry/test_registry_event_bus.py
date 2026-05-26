"""Unit tests for ``ProviderRegistry`` event-bus safety (DESIGN §7.4, §8.2).

``_event_bus_safe_emit`` wraps every ``bus.emit()`` call — it must never
propagate and must log failures at WARNING. All three tests exercise the
wrapper through ``locked()``, which triggers emissions. All are xfail-
decorated until sub-phase 0.5c lands the registry constructor and the
wrapper.
"""

from __future__ import annotations

import pytest

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._contracts import ArtworkProvider
from personalscraper.api.metadata.registry import ProviderMatch, ProviderName
from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import FailingEventBus, FakeMultiCapability

# ---------------------------------------------------------------------------
# event_bus=None — no-op
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="TDD — impl pending sub-phase 0.5c", raises=NotImplementedError, strict=True)
def test_event_bus_none_accepted_no_op(build_registry: object) -> None:
    """``ProviderRegistry`` accepts ``event_bus=None`` — emissions become no-op."""
    fakes = {"art": FakeMultiCapability(name="art")}
    config = ProvidersConfig(
        Searchable={"art": 1},
        ArtworkProvider={"art": 1},
    )
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=None,
    )
    match = ProviderMatch(provider=ProviderName("art"), id="x", media_type=MediaType.MOVIE)
    # locked() triggers _event_bus_safe_emit — when event_bus is None, no exception
    registry.locked(ArtworkProvider, match)


# ---------------------------------------------------------------------------
# emit() failure does not propagate
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="TDD — impl pending sub-phase 0.5c", raises=NotImplementedError, strict=True)
def test_event_bus_emit_failure_does_not_propagate(build_registry: object) -> None:
    """If ``event_bus.emit()`` raises, the registry catches it — caller never sees the exception."""
    fakes = {"art": FakeMultiCapability(name="art")}
    config = ProvidersConfig(
        Searchable={"art": 1},
        ArtworkProvider={"art": 1},
    )
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=FailingEventBus(),
    )
    match = ProviderMatch(provider=ProviderName("art"), id="x", media_type=MediaType.MOVIE)
    # A call that triggers emit — should NOT raise RuntimeError
    registry.locked(ArtworkProvider, match)


# ---------------------------------------------------------------------------
# emit() failure logs WARNING
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="TDD — impl pending sub-phase 0.5c", raises=NotImplementedError, strict=True)
def test_event_bus_emit_failure_logs_warning(
    build_registry: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When ``bus.emit()`` raises, ``registry_event_emit_failed`` is logged at WARNING."""
    fakes = {"art": FakeMultiCapability(name="art")}
    config = ProvidersConfig(
        Searchable={"art": 1},
        ArtworkProvider={"art": 1},
    )
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=FailingEventBus(),
    )
    match = ProviderMatch(provider=ProviderName("art"), id="x", media_type=MediaType.MOVIE)
    with caplog.at_level("WARNING"):
        registry.locked(ArtworkProvider, match)
    assert any("registry_event_emit_failed" in r.message for r in caplog.records)
