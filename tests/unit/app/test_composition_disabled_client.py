"""A disabled active torrent client means no client, decided once in ``build_app_context``.

The supervisor boot and the pipeline worker both go through it, so one decision serves both. The
torrent factory's own refusal for a direct caller is a separate contract, pinned here as unchanged.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.torrent import build_active_torrent_client
from personalscraper.app.composition import build_app_context
from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig


def _config(*, enabled: bool) -> MagicMock:
    """A configuration whose active client is ``qbittorrent``, enabled or not.

    Args:
        enabled: Whether the active client is enabled.

    Returns:
        A config double carrying a real ``TorrentConfig``.
    """
    cfg = MagicMock()
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300.0
    cfg.torrent = TorrentConfig(active="qbittorrent", clients={"qbittorrent": TorrentClientEntry(enabled=enabled)})
    return cfg


def _build(cfg: MagicMock) -> object:
    """Build the context with the provider registry stubbed and the torrent factory spied.

    Args:
        cfg: The configuration.

    Returns:
        The factory's spy and the context, as a tuple.
    """
    with (
        patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        patch("personalscraper.api.torrent.build_active_torrent_client") as factory,
    ):
        factory.side_effect = lambda torrent: build_active_torrent_client(torrent)
        return factory, build_app_context(cfg, MagicMock(), build_torrent_client=True)


def test_a_disabled_active_client_builds_no_client() -> None:
    """No client, no error and no contact when the active client is disabled."""
    _factory, ctx = _build(_config(enabled=False))

    assert ctx.torrent_client is None


def test_an_enabled_active_client_is_still_built() -> None:
    """An enabled client keeps today's path: the factory is asked for it."""
    sentinel = MagicMock()
    cfg = _config(enabled=True)
    with (
        patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        patch("personalscraper.api.torrent.build_active_torrent_client", return_value=sentinel) as factory,
        patch("personalscraper.api.torrent.TorrentAdder", MagicMock),
    ):
        ctx = build_app_context(cfg, MagicMock(), build_torrent_client=True)

    factory.assert_called_once_with(cfg.torrent)
    assert ctx.torrent_client is sentinel


def test_the_factory_still_refuses_a_disabled_client_for_a_direct_caller() -> None:
    """Only the composition treats disabled as no client; the factory keeps its refusal."""
    with pytest.raises(ValueError, match="is disabled"):
        build_active_torrent_client(_config(enabled=False).torrent)
