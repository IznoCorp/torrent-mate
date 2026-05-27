"""Unit tests for ``ProviderRegistry.get()`` (DESIGN §6.5, §8.2).

Both tests are xfail-decorated until sub-phase 0.5a lands the ``get()``
method body. ``get()`` returns a provider by name or raises
``UnknownProviderError``.
"""

from __future__ import annotations

import pytest

from personalscraper.api.metadata.registry._errors import UnknownProviderError
from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import FakeSearchable

# ---------------------------------------------------------------------------
# Known name
# ---------------------------------------------------------------------------


def test_get_known_name_returns_provider(build_registry: object) -> None:
    """``get('tmdb')`` returns the TMDB provider instance.

    Design: docs/reference/architecture.md#provider-registry
    Contract: provider registry get() resolves known names to provider instances.
    """
    fakes = {"tmdb": FakeSearchable(provider_name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    provider = registry.get("tmdb")
    assert provider is not None
    assert getattr(provider, "provider_name", None) == "tmdb"


# ---------------------------------------------------------------------------
# Unknown name
# ---------------------------------------------------------------------------


def test_get_unknown_name_raises_UnknownProviderError(build_registry: object) -> None:
    """``get('nonexistent')`` raises ``UnknownProviderError`` (NOT bare ``KeyError``)."""
    fakes = {"tmdb": FakeSearchable(provider_name="tmdb")}
    config = ProvidersConfig(Searchable={"tmdb": 1})
    registry = build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    with pytest.raises(UnknownProviderError):
        registry.get("nonexistent_provider")
