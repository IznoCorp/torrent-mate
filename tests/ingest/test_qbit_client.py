"""Tests for personalscraper.ingest.qbit_client — QBitClient wrapper.

Unit tests use mocked qbittorrent-api objects.
The live test (test_live_api) connects to the real qBittorrent instance
and is skipped if qBittorrent is not accessible.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import qbittorrentapi

from personalscraper.ingest.qbit_client import (
    QBitAuthLockoutError,  # noqa: F401
    QBitClient,
)


@pytest.fixture
def mock_client(tmp_path):
    """Provide a QBitClient with a mocked underlying qbittorrent-api Client.

    Also mocks requests.get (pre-check) with a 200 response so tests focused
    on post-login behaviour are not affected by the IP-ban pre-check.
    """
    fake_lockout = tmp_path / "qbit_auth_lockout"
    mock_200 = MagicMock()
    mock_200.status_code = 200
    with patch("personalscraper.ingest.qbit_client._LOCKOUT_FILE", fake_lockout), \
         patch("personalscraper.ingest.qbit_client.requests.get", return_value=mock_200), \
         patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client") as mock_cls:
        client = QBitClient(host="localhost", port=8081, username="test", password="test")
        client._client = mock_cls.return_value
        yield client


def test_context_manager_calls_login_logout(mock_client):
    """Context manager calls auth_log_in on enter and auth_log_out on exit."""
    with mock_client:
        mock_client._client.auth_log_in.assert_called_once()
    mock_client._client.auth_log_out.assert_called_once()


def test_get_completed_torrents(mock_client):
    """get_completed_torrents calls torrents_info with completed filter."""
    fake_torrent = MagicMock()
    mock_client._client.torrents_info.return_value = [fake_torrent]

    result = mock_client.get_completed_torrents()
    mock_client._client.torrents_info.assert_called_once_with(status_filter="completed")
    assert result == [fake_torrent]


def test_is_seeding_uploading(mock_client):
    """is_seeding returns True when torrent state_enum.is_uploading is True."""
    torrent = MagicMock()
    torrent.state_enum.is_uploading = True
    assert mock_client.is_seeding(torrent) is True


def test_is_seeding_stopped(mock_client):
    """is_seeding returns False when torrent is stopped (not uploading)."""
    torrent = MagicMock()
    torrent.state_enum.is_uploading = False
    assert mock_client.is_seeding(torrent) is False


def test_get_content_path(mock_client):
    """get_content_path returns a Path from torrent.content_path."""
    torrent = MagicMock()
    torrent.content_path = "/Volumes/IznoServer SSD/torrents/complete/The.Boys.S05E01"
    result = mock_client.get_content_path(torrent)
    assert isinstance(result, Path)
    assert result.name == "The.Boys.S05E01"


def test_get_all_torrent_hashes(mock_client):
    """get_all_torrent_hashes returns a set of hash strings."""
    t1 = MagicMock()
    t1.hash = "abc123"
    t2 = MagicMock()
    t2.hash = "def456"
    mock_client._client.torrents_info.return_value = [t1, t2]

    result = mock_client.get_all_torrent_hashes()
    assert result == {"abc123", "def456"}


class TestPreCheck:
    """Tests for qBit reachability pre-check before auth_log_in."""

    @patch("personalscraper.ingest.qbit_client.requests.get")
    @patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client")
    @patch("personalscraper.ingest.qbit_client._LOCKOUT_FILE")
    def test_pre_check_uses_root_page_not_api(self, mock_lockout, mock_client_cls, mock_get) -> None:
        """Pre-check should GET / (root page), not /api/v2/app/version.

        The root page always returns 200 regardless of auth state.
        API endpoints return 403 without auth and those 403s count
        toward the ban threshold — so we must NOT use them.
        """
        mock_lockout.exists.return_value = False

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = QBitClient(host="localhost", port=8081, username="u", password="p")
        client.__enter__()

        # Verify the pre-check hit the root page, NOT an API endpoint
        call_url = mock_get.call_args[0][0]
        assert call_url.endswith("/"), f"Pre-check should use root page (/), not {call_url}"
        assert "/api/" not in call_url, f"Pre-check must NOT use API endpoints: {call_url}"

    @patch("personalscraper.ingest.qbit_client.requests.get")
    @patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client")
    @patch("personalscraper.ingest.qbit_client._LOCKOUT_FILE")
    def test_connection_refused_raises_api_error(self, mock_lockout, mock_client_cls, mock_get) -> None:
        """Connection refused on pre-check should raise APIConnectionError."""
        import requests as req

        # Lockout file does not exist — isolate from any real lock on disk
        mock_lockout.exists.return_value = False
        mock_get.side_effect = req.ConnectionError("Connection refused")

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = QBitClient(host="localhost", port=8081, username="u", password="p")

        with pytest.raises(qbittorrentapi.APIConnectionError):
            client.__enter__()

        mock_client.auth_log_in.assert_not_called()

    @patch("personalscraper.ingest.qbit_client.requests.get")
    @patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client")
    @patch("personalscraper.ingest.qbit_client._LOCKOUT_FILE")
    def test_200_pre_check_proceeds_to_login(self, mock_lockout, mock_client_cls, mock_get) -> None:
        """When pre-check returns 200, auth_log_in should be called normally."""
        # Lockout file does not exist — isolate from any real lock on disk
        mock_lockout.exists.return_value = False

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = QBitClient(host="localhost", port=8081, username="u", password="p")

        client.__enter__()

        mock_client.auth_log_in.assert_called_once()


def test_live_api():
    """Connect to the real qBittorrent API and list torrents.

    Skipped if qBittorrent is not accessible. Validates that:
    - Login succeeds
    - Torrents can be listed
    - State detection (seeding vs stopped) works
    - Content paths resolve to real filesystem paths
    """
    try:
        client = QBitClient(host="localhost", port=8081, username="izno", password="")
        with client:
            torrents = client.get_completed_torrents()
            all_hashes = client.get_all_torrent_hashes()

            assert isinstance(all_hashes, set)

            for t in torrents[:3]:  # Check first 3 only
                seeding = client.is_seeding(t)
                path = client.get_content_path(t)
                assert isinstance(seeding, bool)
                assert isinstance(path, Path)
                # Content path should exist on disk
                assert path.exists(), f"Content path does not exist: {path}"

    except QBitAuthLockoutError as e:
        pytest.skip(f"qBittorrent auth lockout active: {e}")
    except (qbittorrentapi.LoginFailed, qbittorrentapi.APIConnectionError) as e:
        pytest.skip(f"qBittorrent not accessible: {e}")
