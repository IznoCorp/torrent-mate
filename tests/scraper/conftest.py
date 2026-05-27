"""Shared fixtures for the scraper unit-test suite (post-registry-migration)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata._contracts import (
    MovieDetailsProvider,
    TvDetailsProvider,
)
from personalscraper.api.metadata.registry import ProviderRegistry


@pytest.fixture
def mock_registry() -> ProviderRegistry:
    """Default MagicMock(spec=ProviderRegistry).

    ``.get(name)`` returns a freshly created MagicMock for tmdb/tvdb access.
    Each named MagicMock carries a ``provider_name`` attribute equal to its
    name so production code that filters chain providers by
    ``match.source == provider.provider_name`` can resolve the same instance.

    ``.chain(capability)`` mirrors the production chain wiring used by
    ``movie_service`` / ``tv_service`` (sub-phase 7.1):

    - ``MovieDetailsProvider`` → ``[get("tmdb")]``
    - ``TvDetailsProvider`` → ``[get("tvdb"), get("tmdb")]``
    - any other capability → ``[MagicMock()]`` so the legacy
      "non-empty default" eligibility gate still passes.

    Tests that need specific behavior override on the returned mock::

        mock_registry.get.return_value = my_specific_client
        mock_registry.chain.side_effect = lambda cap: [my_client]
    """
    registry = MagicMock(spec=ProviderRegistry)
    _named_mocks: dict[str, MagicMock] = {}

    def _get(name: str) -> MagicMock:
        if name not in _named_mocks:
            m = MagicMock()
            m.name = name
            # provider_name is the production attribute the chain iterator
            # inspects when matching ``MatchResult.source``. Keep it in sync
            # with the ``get(name)`` key so the two access paths line up.
            m.provider_name = name
            _named_mocks[name] = m
        return _named_mocks[name]

    def _chain(capability: type) -> list[MagicMock]:
        if capability is MovieDetailsProvider:
            return [_get("tmdb")]
        if capability is TvDetailsProvider:
            return [_get("tvdb"), _get("tmdb")]
        # Default: any other capability gets a generic non-empty list so
        # the legacy circuit-closed eligibility gate keeps passing.
        return [MagicMock()]

    registry.get.side_effect = _get
    registry.chain.side_effect = _chain
    return registry
