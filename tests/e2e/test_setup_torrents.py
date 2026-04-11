"""Tests for E2E torrent setup — mock qBittorrent interactions."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.e2e.registry import TestRegistry
from tests.e2e.setup_torrents import TorrentSetup


@pytest.fixture()
def mock_client():
    """Return a mock qBittorrent client."""
    return MagicMock()


@pytest.fixture()
def registry(tmp_path):
    """Return a TestRegistry using tmp_path."""
    return TestRegistry(session_id="setup-test", base_dir=tmp_path)


@pytest.fixture()
def setup(mock_client, registry):
    """Return a TorrentSetup instance."""
    return TorrentSetup(client=mock_client, registry=registry, timeout=5)


class TestLoadMagnets:
    """Tests for TorrentSetup.load_magnets()."""

    def test_loads_valid_json(self, setup, tmp_path):
        """Loads and returns magnet entries from valid JSON."""
        magnets = [
            {"name": "Test", "magnet": "magnet:?xt=...", "type": "movie", "expected_category": "films"}
        ]
        config = tmp_path / "magnets.json"
        config.write_text(json.dumps(magnets))

        result = setup.load_magnets(config)
        assert len(result) == 1
        assert result[0]["name"] == "Test"

    def test_raises_on_missing_fields(self, setup, tmp_path):
        """Raises ValueError when required fields are missing."""
        bad_magnets = [{"name": "Incomplete"}]
        config = tmp_path / "magnets.json"
        config.write_text(json.dumps(bad_magnets))

        with pytest.raises(ValueError, match="missing fields"):
            setup.load_magnets(config)


class TestAddMagnets:
    """Tests for TorrentSetup.add_magnets()."""

    @patch("tests.e2e.setup_torrents.time.sleep")
    def test_adds_magnets_with_category(self, mock_sleep, setup, mock_client):
        """Adds each magnet to qBit with the e2e-test category."""
        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_client.torrents_info.return_value = [mock_torrent]

        magnets = [{"name": "Movie", "magnet": "magnet:?xt=abc"}]
        hashes = setup.add_magnets(magnets, category="e2e-test")

        mock_client.torrents_add.assert_called_once_with(urls="magnet:?xt=abc", category="e2e-test")
        assert "abc123" in hashes
        assert "abc123" in setup.registry.torrent_hashes


class TestWaitForCompletion:
    """Tests for TorrentSetup.wait_for_completion()."""

    @patch("tests.e2e.setup_torrents.time.sleep")
    @patch("tests.e2e.setup_torrents.time.time")
    def test_returns_completed_status(self, mock_time, mock_sleep, setup, mock_client):
        """Returns True for completed torrents."""
        # Simulate: first call returns time 0, second returns time 1, third returns timeout
        mock_time.side_effect = [0, 1, 100]

        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_torrent.name = "Test Movie"
        mock_torrent.state_enum.is_complete = True
        mock_client.torrents_info.return_value = [mock_torrent]

        result = setup.wait_for_completion(["abc123"])
        assert result["abc123"] is True

    @patch("tests.e2e.setup_torrents.time.sleep")
    @patch("tests.e2e.setup_torrents.time.time")
    def test_timeout_returns_incomplete(self, mock_time, mock_sleep, setup, mock_client):
        """Returns False for torrents that didn't complete before timeout."""
        # Simulate: immediate timeout
        mock_time.side_effect = [0, 100]

        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_torrent.state_enum.is_complete = False
        mock_client.torrents_info.return_value = [mock_torrent]

        result = setup.wait_for_completion(["abc123"])
        assert result["abc123"] is False


class TestGetDownloadedPaths:
    """Tests for TorrentSetup.get_downloaded_paths()."""

    def test_returns_content_paths(self, setup, mock_client):
        """Returns paths for matching hashes."""
        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_torrent.content_path = "/tmp/downloads/Movie"
        mock_client.torrents_info.return_value = [mock_torrent]

        paths = setup.get_downloaded_paths(["abc123"])
        assert len(paths) == 1
        assert paths[0] == Path("/tmp/downloads/Movie")
