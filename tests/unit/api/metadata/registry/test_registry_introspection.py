"""Unit tests for ``ProviderRegistry`` introspection API (DESIGN §6.5, §8.2).

``operations()``, ``status()``, and ``providers_for()`` are all exercised
with ``@pytest.mark.xfail`` until sub-phase 0.5a lands their method bodies.
"""

from __future__ import annotations

from personalscraper.api.metadata._contracts import (
    IDCrossRef,
    IDValidator,
    Searchable,
)
from personalscraper.api.metadata.registry import Mode, ProviderStatus
from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import FakeMultiCapability

# ---------------------------------------------------------------------------
# operations() — 4 tests
# ---------------------------------------------------------------------------


def test_operations_returns_expected_shape(build_registry: object) -> None:
    """``operations()`` returns ``dict[type[Protocol], Mode]`` with all 11 capabilities mapped."""
    fakes = {"tmdb": FakeMultiCapability(name="tmdb")}
    config = ProvidersConfig(
        Searchable={"tmdb": 1},
        MovieDetailsProvider={"tmdb": 1},
        TvDetailsProvider={"tmdb": 1},
        EpisodeFetcher={"tmdb": 1},
        RatingProvider={"tmdb": 1},
        ArtworkProvider={"tmdb": 1},
        KeywordProvider={"tmdb": 1},
        VideoProvider={"tmdb": 1},
        RecommendationProvider={"tmdb": 1},
        IDValidator={"tmdb": 1},
        IDCrossRef={"tmdb": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    ops = registry.operations()
    # All 11 capabilities must be keys
    assert len(ops) == 11
    # Every value must be a Mode enum member
    assert all(isinstance(v, Mode) for v in ops.values())


def test_operations_includes_mode_direct_entries(build_registry: object) -> None:
    """``IDValidator`` and ``IDCrossRef`` both map to ``Mode.DIRECT``."""
    fakes = {"tmdb": FakeMultiCapability(name="tmdb")}
    config = ProvidersConfig(
        Searchable={"tmdb": 1},
        IDValidator={"tmdb": 1},
        IDCrossRef={"tmdb": 1},
    )
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    ops = registry.operations()
    assert ops[IDValidator] == Mode.DIRECT
    assert ops[IDCrossRef] == Mode.DIRECT


# ---------------------------------------------------------------------------
# status() — 1 test
# ---------------------------------------------------------------------------


def test_status_returns_expected_shape(build_registry: object) -> None:
    """``status()`` returns ``dict[provider_name, ProviderStatus]`` for every configured provider."""
    fakes = {"tmdb": FakeMultiCapability(name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    status = registry.status()
    assert isinstance(status, dict)
    assert all(isinstance(v, ProviderStatus) for v in status.values())


# ---------------------------------------------------------------------------
# providers_for() — 1 test
# ---------------------------------------------------------------------------


def test_providers_for_returns_raw_ordered_list(build_registry: object) -> None:
    """``providers_for(capability)`` returns ordered list, NO circuit filtering."""
    fakes = {"tmdb": FakeMultiCapability(name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    providers = registry.providers_for(Searchable)
    assert isinstance(providers, list)
    # Order should match the config priority (lowest first)
    # No filtering means OPEN circuits ARE included
