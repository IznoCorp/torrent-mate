"""Tests for GlobalRateLimiter protocol + qBittorrent implementation."""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.torrent._contracts import GlobalRateLimiter
from personalscraper.api.torrent.qbittorrent import QBitClient


class TestQBitGlobalRateLimiter:
    """Tests for QBitClient.apply_global_limits (sub-phase 2.1)."""

    def test_qbit_is_global_rate_limiter(self) -> None:
        """QBitClient satisfies isinstance(client, GlobalRateLimiter)."""
        client = QBitClient.__new__(QBitClient)
        assert isinstance(client, GlobalRateLimiter)

    def test_both_set(self) -> None:
        """When both limits are passed, both transfer_set_* are called."""
        client = QBitClient.__new__(QBitClient)
        mock_api = MagicMock()
        client._client = mock_api

        client.apply_global_limits(up_bytes_per_s=102400, down_bytes_per_s=204800)

        mock_api.transfer_set_upload_limit.assert_called_once_with(102400)
        mock_api.transfer_set_download_limit.assert_called_once_with(204800)

    def test_down_only(self) -> None:
        """When up is None, transfer_set_upload_limit is NOT called."""
        client = QBitClient.__new__(QBitClient)
        mock_api = MagicMock()
        client._client = mock_api

        client.apply_global_limits(down_bytes_per_s=102400)

        mock_api.transfer_set_download_limit.assert_called_once_with(102400)
        mock_api.transfer_set_upload_limit.assert_not_called()

    def test_up_only(self) -> None:
        """When down is None, transfer_set_download_limit is NOT called."""
        client = QBitClient.__new__(QBitClient)
        mock_api = MagicMock()
        client._client = mock_api

        client.apply_global_limits(up_bytes_per_s=102400)

        mock_api.transfer_set_upload_limit.assert_called_once_with(102400)
        mock_api.transfer_set_download_limit.assert_not_called()

    def test_both_none_noops(self) -> None:
        """When both limits are None, neither method is called."""
        client = QBitClient.__new__(QBitClient)
        mock_api = MagicMock()
        client._client = mock_api

        client.apply_global_limits()

        mock_api.transfer_set_upload_limit.assert_not_called()
        mock_api.transfer_set_download_limit.assert_not_called()
