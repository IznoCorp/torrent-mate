"""Tests for torrent fail-fast in _build_app_context() (D3/D9).

D3: enabled-but-incapable active torrent client → RegistryConfigError at boot.
D9: no client configured → torrent_client=None, no error.

Md6a: disabled client → ValueError propagates from the real factory.
Md6b: factory ApiError propagates through _build_app_context (boot fail-loud).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api._contracts import ApiError


def _cfg(active: str = "", enabled: bool = True) -> MagicMock:
    """Build a minimal config mock compatible with _build_app_context."""
    cfg = MagicMock()
    cfg.torrent.active = active
    cfg.torrent.clients = {active: MagicMock(enabled=enabled)} if active else {}
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300
    cfg.providers = {}
    return cfg


# Lazy `from X import Y` imports inside _build_app_context resolve against the
# SOURCE module, not cli_helpers — patch the source modules.
_SRC_PROVIDER_REGISTRY = "personalscraper.api.metadata.registry.ProviderRegistry"
_SRC_CIRCUIT_POLICY = "personalscraper.api.transport._policy.CircuitPolicy"
_SRC_FACTORY = "personalscraper.api.torrent._factory.build_active_torrent_client"


class TestBuildAppContextTorrent:
    """Torrent fail-fast behavior in _build_app_context (D3/D9)."""

    def test_no_active_torrent_client_gives_none(self) -> None:
        """D9: no client configured → torrent_client is None."""
        from personalscraper.cli_helpers import _build_app_context

        with patch(_SRC_PROVIDER_REGISTRY) as mock_reg, patch(_SRC_CIRCUIT_POLICY):
            mock_reg.return_value = MagicMock()
            ctx = _build_app_context(_cfg(active=""), MagicMock())
        assert ctx.torrent_client is None

    def test_capable_client_wired(self) -> None:
        """D3: capable active client → wired into AppContext.

        Design: docs/reference/architecture.md#torrent-client-boot-wiring-torrent-write-v0200
        Contract: The torrent-write boot-wiring promotes the active torrent
        client into AppContext — a capable client resolved by
        build_active_torrent_client() is stored in ctx.torrent_client.
        """
        from personalscraper.api.torrent._contracts import TorrentAdder
        from personalscraper.cli_helpers import _build_app_context

        mock_client = MagicMock(spec=TorrentAdder)

        with (
            patch(_SRC_PROVIDER_REGISTRY) as mock_reg,
            patch(_SRC_CIRCUIT_POLICY),
            patch(_SRC_FACTORY, return_value=mock_client),
        ):
            mock_reg.return_value = MagicMock()
            ctx = _build_app_context(_cfg(active="qbittorrent"), MagicMock())
        assert ctx.torrent_client is mock_client

    def test_incapable_client_raises(self) -> None:
        """D3: enabled-but-incapable client → RegistryConfigError at boot.

        Design: docs/reference/architecture.md#boot-sequence
        Contract: In the boot sequence, _build_app_context() asserts the active
        torrent client composes TorrentAdder and raises RegistryConfigError
        (protocol_mismatch, section torrent) when it does not (D3 fail-fast).
        """
        from personalscraper.api.metadata.registry import RegistryConfigError
        from personalscraper.cli_helpers import _build_app_context

        mock_client = MagicMock(spec=[])  # satisfies nothing

        with (
            patch(_SRC_PROVIDER_REGISTRY) as mock_reg,
            patch(_SRC_CIRCUIT_POLICY),
            patch(_SRC_FACTORY, return_value=mock_client),
        ):
            mock_reg.return_value = MagicMock()
            with pytest.raises(RegistryConfigError, match="TorrentAdder"):
                _build_app_context(_cfg(active="qbittorrent"), MagicMock())

    def test_disabled_client_raises(self) -> None:
        """Md6a: disabled client → ValueError propagates from real factory.

        Uses the real ``build_active_torrent_client`` (not patched) so the
        factory's own enabled=False check is exercised — the ValueError
        propagates through ``_build_app_context`` to the CLI boundary (boot
        fail-loud).

        Approach: the MagicMock config from ``_cfg(active="qbittorrent",
        enabled=False)`` provides enough structure (``.active``, ``.clients``,
        ``.clients[active].enabled``) to reach the factory's disabled check
        before any real credentials or imports are needed.
        """
        from personalscraper.cli_helpers import _build_app_context

        with (
            patch(_SRC_PROVIDER_REGISTRY) as mock_reg,
            patch(_SRC_CIRCUIT_POLICY),
        ):
            mock_reg.return_value = MagicMock()
            with pytest.raises(ValueError, match="disabled"):
                _build_app_context(_cfg(active="qbittorrent", enabled=False), MagicMock())

    def test_factory_raise_propagates(self) -> None:
        """Md6b: factory ApiError propagates through _build_app_context.

        When ``build_active_torrent_client`` raises ``ApiError`` (e.g. missing
        credentials), ``_build_app_context`` does NOT swallow it into a None
        client — the error propagates unchanged (boot fail-loud, D3/D9 contract).
        """
        from personalscraper.cli_helpers import _build_app_context

        with (
            patch(_SRC_PROVIDER_REGISTRY) as mock_reg,
            patch(_SRC_CIRCUIT_POLICY),
            patch(
                _SRC_FACTORY,
                side_effect=ApiError(
                    provider="qbittorrent",
                    http_status=0,
                    message="missing creds",
                ),
            ),
        ):
            mock_reg.return_value = MagicMock()
            with pytest.raises(ApiError, match="missing creds"):
                _build_app_context(_cfg(active="qbittorrent"), MagicMock())
