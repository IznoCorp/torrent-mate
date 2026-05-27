"""Shared fixtures for the scraper unit-test suite (post-registry-migration)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata.registry import ProviderRegistry


@pytest.fixture
def mock_registry() -> ProviderRegistry:
    """Default MagicMock(spec=ProviderRegistry).

    ``.get(name)`` returns a freshly created MagicMock for tmdb/tvdb access.
    ``.chain(capability)`` returns an empty list (orchestrator no-eligible-provider path → error).

    Tests that need specific behavior override on the returned mock::

        mock_registry.get.return_value = my_specific_client
        mock_registry.chain.return_value = [my_client]
    """
    registry = MagicMock(spec=ProviderRegistry)
    _named_mocks: dict[str, MagicMock] = {}

    def _get(name: str) -> MagicMock:
        if name not in _named_mocks:
            m = MagicMock()
            m.name = name
            _named_mocks[name] = m
        return _named_mocks[name]

    registry.get.side_effect = _get
    registry.chain.return_value = [MagicMock()]  # non-empty → "circuits closed" by default
    return registry
