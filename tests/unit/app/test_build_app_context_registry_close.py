"""``build_app_context``: a step after the provider registry that raises closes the registry.

A request-scoped caller (the v1 provider search) builds a context per call. The registry holds
sessions and connection pools; before this, an acquisition context that refused to build (a tracker
misconfigured) left them open, one registry leaked per failed search.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.app.composition import build_app_context


def _config() -> MagicMock:
    """A minimal config (no torrent client).

    Returns:
        The mock.
    """
    cfg = MagicMock()
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300.0
    cfg.torrent.active = ""
    return cfg


def test_a_failing_acquisition_context_closes_the_registry_already_built() -> None:
    """The registry is closed once, and the failure still reaches the caller."""
    registry = MagicMock()
    with (
        patch("personalscraper.api.metadata.registry.ProviderRegistry", return_value=registry),
        patch("personalscraper.acquire.build_acquire_context", side_effect=RuntimeError("tracker misconfigured")),
        pytest.raises(RuntimeError, match="tracker misconfigured"),
    ):
        build_app_context(_config(), MagicMock())

    registry.close.assert_called_once_with()


def test_a_context_that_builds_leaves_its_registry_open() -> None:
    """The registry belongs to the context that holds it: the success path closes nothing."""
    registry = MagicMock()
    with (
        patch("personalscraper.api.metadata.registry.ProviderRegistry", return_value=registry),
        patch("personalscraper.acquire._factory.build_tracker_registry", return_value=MagicMock()),
    ):
        context = build_app_context(_config(), MagicMock())

    assert context.provider_registry is registry
    registry.close.assert_not_called()
