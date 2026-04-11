"""Tests for personalscraper.ingest.qbit_client — QBitClient wrapper.

Unit tests use mocked qbittorrent-api objects.
The live test (test_live_api) connects to the real qBittorrent instance
and is skipped if qBittorrent is not accessible.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import qbittorrentapi

from personalscraper.ingest.qbit_client import QBitClient


@pytest.fixture
def mock_client():
    """Provide a QBitClient with a mocked underlying qbittorrent-api Client."""
    with patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client") as mock_cls:
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

    except (qbittorrentapi.LoginFailed, qbittorrentapi.APIConnectionError) as e:
        pytest.skip(f"qBittorrent not accessible: {e}")
