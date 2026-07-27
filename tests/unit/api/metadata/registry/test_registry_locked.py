"""Unit tests for ``ProviderRegistry.locked()`` (DESIGN §6.4, §8.2).

``locked()`` binds the match's own provider when it implements the locked
capability and is circuit-eligible, otherwise it returns ``None`` and emits
``LockedCapabilityUnresolved``. Cross-provider ID translation was removed
with the cross-ref machinery (API-TRANSPORT-03) — a locked capability can
only be served by the provider that owns the match's id.
"""

from __future__ import annotations

import pytest

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._contracts import ArtworkProvider
from personalscraper.api.metadata.registry import (
    LockedProvider,
    ProviderMatch,
    RegistryProviderName,
)
from personalscraper.api.metadata.registry._events import LockedCapabilityUnresolved
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.core.circuit import CircuitState

from .conftest import FakeMultiCapability, FakeSearchable

# ---------------------------------------------------------------------------
# Match-provider path — the match's own provider serves the capability
# ---------------------------------------------------------------------------


def test_locked_match_provider_path(build_registry: object) -> None:
    """If match's provider already implements the capability, ``locked()`` returns it directly.

    Design: docs/reference/architecture.md#three-operations
    Design: docs/reference/scraping.md#three-semantics-provider-registry
    Contract: locked operation respects capability boundaries, validating the three operation modes.
    """
    multi = FakeMultiCapability(provider_name="multi", circuit_state=CircuitState.CLOSED)
    fakes = {"multi": multi}
    config = ProvidersConfig(
        Searchable={"multi": 1},
        ArtworkProvider={"multi": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    match = ProviderMatch(provider=RegistryProviderName("multi"), id="123", media_type=MediaType.MOVIE)
    locked = registry.locked(ArtworkProvider, match)
    assert locked is not None
    assert isinstance(locked, LockedProvider)
    assert locked.bound_id == "123"
    assert locked.translated_via is None


# ---------------------------------------------------------------------------
# No binding possible → returns None + emits LockedCapabilityUnresolved
# ---------------------------------------------------------------------------


def test_locked_returns_none_emits_LockedCapabilityUnresolved_event(
    build_registry: object,
    mock_event_bus: object,
) -> None:
    """When the match's provider is circuit-ineligible, ``locked()`` returns ``None`` + emits.

    The match's provider implements the capability but its circuit is OPEN,
    and no cross-provider translation exists — so nothing can be bound.
    """
    multi_open = FakeMultiCapability(provider_name="multi_open", circuit_state=CircuitState.OPEN)
    fakes = {"multi_open": multi_open}
    config = ProvidersConfig(
        Searchable={"multi_open": 1},
        ArtworkProvider={"multi_open": 1},
    )
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=mock_event_bus,
    )
    match = ProviderMatch(provider=RegistryProviderName("multi_open"), id="123", media_type=MediaType.MOVIE)
    result = registry.locked(ArtworkProvider, match)
    assert result is None
    assert any(isinstance(e, LockedCapabilityUnresolved) for e in mock_event_bus.emitted)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Sentinel-token enforcement (NO xfail — implemented in sub-phase 0.2)
# ---------------------------------------------------------------------------


def test_LockedProvider_construction_outside_registry_module_raises() -> None:
    """``LockedProvider(...)`` raises ``TypeError`` when constructed without the sentinel token.

    The sentinel mechanism (DESIGN §6.4 / I3) guarantees that only the
    registry's internal ``_make_locked()`` helper can build instances.
    """
    match = ProviderMatch(provider=RegistryProviderName("p"), id="x", media_type=MediaType.MOVIE)
    fake = FakeSearchable(provider_name="p")
    with pytest.raises(TypeError):
        LockedProvider(
            provider=fake,
            bound_id="x",
            source_match=match,
            translated_via=None,
            _token=object(),  # wrong token — must reject
        )
    # And the default (no token) must also reject.
    with pytest.raises(TypeError):
        LockedProvider(
            provider=fake,
            bound_id="x",
            source_match=match,
            translated_via=None,
        )
