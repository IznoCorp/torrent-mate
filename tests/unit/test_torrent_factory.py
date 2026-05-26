"""Tests for api/torrent/_factory.py.

Regression test for DEV #38: factory return type narrowed from the monolithic
``TorrentClientFull`` composite Protocol to the union of concrete implementations
(``QBitClient | TransmissionClient``). Each mock now uses the atomic capability
Protocol that the tested scenario exercises, rather than the composite.
"""

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._contracts import TorrentLister, TorrentStateInspector
from personalscraper.api.torrent._factory import build_active_torrent_client
from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig


def _make_cfg(active: str = "qbittorrent", *, enabled: bool = True) -> TorrentConfig:
    """Build a TorrentConfig with a single client entry."""
    return TorrentConfig(
        active=active,
        clients={active: TorrentClientEntry(enabled=enabled)},
    )


def _make_env() -> dict[str, str]:
    """Credential dict with qBittorrent keys set."""
    return {"QBIT_USERNAME": "admin", "QBIT_PASSWORD": "adminadmin"}


class TestBuildActiveTorrentClient:
    """build_active_torrent_client() validation and construction."""

    def test_missing_creds_raises_api_error(self) -> None:
        """Empty env + qbittorrent → ApiError for missing creds."""
        cfg = _make_cfg()
        with pytest.raises(ApiError, match="Missing required credentials"):
            build_active_torrent_client(cfg, env={})

    def test_empty_active_raises_value_error(self) -> None:
        """cfg.active="" → ValueError."""
        cfg = TorrentConfig(active="")
        with pytest.raises(ValueError, match="No active torrent client configured"):
            build_active_torrent_client(cfg, env=_make_env())

    def test_active_not_in_clients_raises_value_error(self) -> None:
        """cfg.active not in cfg.clients → ValueError."""
        cfg = TorrentConfig(active="qbittorrent", clients={})
        with pytest.raises(ValueError, match="not found in torrent.clients"):
            build_active_torrent_client(cfg, env=_make_env())

    def test_disabled_client_raises_value_error(self) -> None:
        """Disabled client entry → ValueError."""
        cfg = _make_cfg(enabled=False)
        with pytest.raises(ValueError, match="is disabled"):
            build_active_torrent_client(cfg, env=_make_env())

    def test_unknown_client_raises_value_error(self) -> None:
        """cfg.active="unknown" → ValueError."""
        cfg = TorrentConfig(
            active="unknown",
            clients={"unknown": TorrentClientEntry(enabled=True)},
        )
        with pytest.raises(ValueError, match="Unknown torrent client"):
            build_active_torrent_client(cfg, env=_make_env())

    def test_transmission_returns_client(self) -> None:
        """cfg.active="transmission" + creds → returns a TorrentLister instance.

        The mock uses TorrentLister as spec — the narrowest capability
        the factory guarantees for all implementations (DEV #38).
        """
        cfg = TorrentConfig(
            active="transmission",
            clients={"transmission": TorrentClientEntry(enabled=True)},
        )
        env = {"TRANSMISSION_USERNAME": "u", "TRANSMISSION_PASSWORD": "p"}
        # Spec narrowed to TorrentLister: shared read capability present on
        # both TransmissionClient and QBitClient (DEV #38 migration).
        mock_client = MagicMock(spec=TorrentLister)
        mock_mod = MagicMock()
        mock_mod.build_client.return_value = mock_client

        with patch("importlib.import_module", return_value=mock_mod):
            result = build_active_torrent_client(cfg, env=env)
        assert result is mock_client

    def test_qbittorrent_returns_client(self) -> None:
        """cfg.active="qbittorrent" + creds → returns a TorrentLister instance.

        The mock uses TorrentLister as spec — the narrowest shared capability
        guaranteed by the factory union return type (DEV #38 migration).
        """
        cfg = _make_cfg()
        # Spec narrowed to TorrentLister (shared read capability) instead
        # of the monolithic TorrentClientFull (DEV #38 migration).
        mock_client = MagicMock(spec=TorrentLister)
        mock_mod = MagicMock()
        mock_mod.build_client.return_value = mock_client

        with patch("importlib.import_module", return_value=mock_mod):
            result = build_active_torrent_client(cfg, env=_make_env())

        assert result is mock_client
        mock_mod.build_client.assert_called_once()

    def test_factory_return_satisfies_torrent_lister(self) -> None:
        """Factory mock result satisfies TorrentLister — narrowest shared capability.

        Regression: before DEV #38, tests asserted isinstance(result, TorrentClientFull).
        Post-migration the factory returns QBitClient | TransmissionClient; both
        implement TorrentLister so isinstance(result, TorrentLister) is the correct
        structural assertion for the shared read surface.
        """
        from personalscraper.api.torrent.qbittorrent import QBitClient

        # QBitClient is a concrete class, so isinstance works at runtime
        # via @runtime_checkable TorrentLister.
        # We verify the protocol has not regressed by checking the concrete class.
        assert issubclass(QBitClient, TorrentLister)
        assert issubclass(QBitClient, TorrentStateInspector)
