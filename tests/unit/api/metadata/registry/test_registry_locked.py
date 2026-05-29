"""Unit tests for ``ProviderRegistry.locked()`` (DESIGN §6.4, §8.2).

Most tests are xfail-decorated. The last test
(``test_LockedProvider_construction_outside_registry_module_raises``)
exercises the sentinel-token mechanism in the ``LockedProvider`` dataclass
which IS implemented in sub-phase 0.2 — it passes immediately.
"""

from __future__ import annotations

import pytest

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.metadata._contracts import ArtworkProvider
from personalscraper.api.metadata.registry import (
    LockedProvider,
    ProviderMatch,
    RegistryProviderName,
)
from personalscraper.api.metadata.registry._events import LockedCapabilityUnresolved
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.core.circuit import CircuitState

from .conftest import FakeArtwork, FakeIDCrossRef, FakeMultiCapability, FakeSearchable

# ---------------------------------------------------------------------------
# Match-provider path (no IDCrossRef needed)
# ---------------------------------------------------------------------------


def test_locked_match_provider_path_no_xref(build_registry: object) -> None:
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
# IDCrossRef escape
# ---------------------------------------------------------------------------


def test_locked_idcrossref_escape_xref_succeeds(build_registry: object) -> None:
    """If match's provider lacks the capability, IDCrossRef translates to one that has it."""
    # match's provider implements IDCrossRef but NOT ArtworkProvider.
    xref_provider = FakeIDCrossRef(
        provider_name="xref",
        circuit_state=CircuitState.CLOSED,
        xref_table={"123": {"art": "456"}},
    )
    art_provider = FakeArtwork(provider_name="art", circuit_state=CircuitState.CLOSED)
    fakes = {"xref": xref_provider, "art": art_provider}
    config = ProvidersConfig(
        Searchable={"xref": 1},
        ArtworkProvider={"art": 1},
        IDCrossRef={"xref": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    match = ProviderMatch(provider=RegistryProviderName("xref"), id="123", media_type=MediaType.MOVIE)
    locked = registry.locked(ArtworkProvider, match)
    assert locked is not None
    assert locked.bound_id == "456"
    assert locked.translated_via == "xref"


# ---------------------------------------------------------------------------
# Circuit-OPEN along xref chain
# ---------------------------------------------------------------------------


def test_locked_circuit_open_along_xref_chain(build_registry: object) -> None:
    """OPEN-circuit providers along the xref chain are skipped; first eligible wins."""
    xref_provider = FakeIDCrossRef(
        provider_name="xref",
        circuit_state=CircuitState.CLOSED,
        xref_table={"123": {"art_open": "x", "art_closed": "y"}},
    )
    art_open = FakeArtwork(provider_name="art_open", circuit_state=CircuitState.OPEN)
    art_closed = FakeArtwork(provider_name="art_closed", circuit_state=CircuitState.CLOSED)
    fakes = {"xref": xref_provider, "art_open": art_open, "art_closed": art_closed}
    config = ProvidersConfig(
        Searchable={"xref": 1},
        ArtworkProvider={"art_open": 1, "art_closed": 2},
        IDCrossRef={"xref": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    match = ProviderMatch(provider=RegistryProviderName("xref"), id="123", media_type=MediaType.MOVIE)
    locked = registry.locked(ArtworkProvider, match)
    assert locked is not None
    # art_open is OPEN → must skip; art_closed wins with its xref id.
    assert locked.bound_id == "y"


# ---------------------------------------------------------------------------
# All paths blocked → returns None
# ---------------------------------------------------------------------------


def test_locked_returns_none_when_all_paths_blocked(build_registry: object) -> None:
    """``locked()`` returns ``None`` when no eligible provider can be bound."""
    xref_provider = FakeIDCrossRef(
        provider_name="xref",
        circuit_state=CircuitState.CLOSED,
        xref_table={},  # no translation paths
    )
    art_open = FakeArtwork(provider_name="art_open", circuit_state=CircuitState.OPEN)
    fakes = {"xref": xref_provider, "art_open": art_open}
    config = ProvidersConfig(
        Searchable={"xref": 1},
        ArtworkProvider={"art_open": 1},
        IDCrossRef={"xref": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    match = ProviderMatch(provider=RegistryProviderName("xref"), id="123", media_type=MediaType.MOVIE)
    assert registry.locked(ArtworkProvider, match) is None


def test_locked_returns_none_emits_LockedCapabilityUnresolved_event(
    build_registry: object,
    mock_event_bus: object,
) -> None:
    """When ``locked()`` returns ``None``, ``LockedCapabilityUnresolved`` is emitted."""
    xref_provider = FakeIDCrossRef(provider_name="xref", circuit_state=CircuitState.CLOSED, xref_table={})
    art_open = FakeArtwork(provider_name="art_open", circuit_state=CircuitState.OPEN)
    fakes = {"xref": xref_provider, "art_open": art_open}
    config = ProvidersConfig(
        Searchable={"xref": 1},
        ArtworkProvider={"art_open": 1},
        IDCrossRef={"xref": 1},
    )
    registry = build_registry(  # type: ignore[operator]
        fakes=fakes,
        providers_config=config,
        event_bus=mock_event_bus,
    )
    match = ProviderMatch(provider=RegistryProviderName("xref"), id="123", media_type=MediaType.MOVIE)
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


# ---------------------------------------------------------------------------
# cross_ref exception narrowing (sub-phase 5.5)
# ---------------------------------------------------------------------------


class _BrokenIDCrossRef:
    """IDCrossRef-like provider that raises KeyError from ``get_cross_refs()``."""

    provider_name: str = "broken"

    def get_cross_refs(self, _id: str) -> dict[str, str]:
        raise KeyError("oops")

    def close(self) -> None:
        pass


class _FailingTransportIDCrossRef:
    """IDCrossRef-like provider that raises ApiError from ``get_cross_refs()``."""

    provider_name: str = "failing"

    def get_cross_refs(self, _id: str) -> dict[str, str]:
        raise ApiError(provider="failing", http_status=502, message="upstream unreachable")

    def close(self) -> None:
        pass


def test_cross_ref_propagates_non_transport_exception(build_registry: object) -> None:
    """A KeyError in get_cross_refs() propagates — it is NOT silently None'd."""
    broken = _BrokenIDCrossRef()
    fakes = {"broken": broken}
    config = ProvidersConfig(
        Searchable={"broken": 1},
        IDCrossRef={"broken": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    match = ProviderMatch(provider=RegistryProviderName("broken"), id="x", media_type=MediaType.MOVIE)
    with pytest.raises(KeyError, match="oops"):
        registry.cross_ref(match, target="tmdb")


def test_cross_ref_returns_none_on_api_error_and_logs(build_registry: object, caplog: pytest.LogCaptureFixture) -> None:
    """ApiError in get_cross_refs() → returns None + logs at WARNING."""
    import logging

    caplog.set_level(logging.WARNING)
    failing = _FailingTransportIDCrossRef()
    fakes = {"failing": failing}
    config = ProvidersConfig(
        Searchable={"failing": 1},
        IDCrossRef={"failing": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    match = ProviderMatch(provider=RegistryProviderName("failing"), id="x", media_type=MediaType.MOVIE)
    result = registry.cross_ref(match, target="tmdb")
    assert result is None
    assert any("registry_cross_ref_failed" in rec.message for rec in caplog.records), (
        f"Expected registry_cross_ref_failed in log, got: {[r.message for r in caplog.records]}"
    )
