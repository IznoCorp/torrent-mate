"""Tests for E2E torrent setup — mock qBittorrent interactions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.e2e.registry import TestRegistry
from tests.e2e.setup_torrents import TorrentSetup


@patch("tests.e2e.setup_torrents.time.sleep")
class TestAddTorrentFiles:
    """Tests for TorrentSetup.add_torrent_files()."""

    def test_adds_torrent_files_with_category(self, _mock_sleep, tmp_path):
        """Adds each .torrent file to qBit with the e2e-test category."""
        mock_client = MagicMock()
        registry = TestRegistry(session_id="test-add", base_dir=tmp_path)
        setup = TorrentSetup(client=mock_client, registry=registry)

        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_torrent.name = "Movie (2024)"
        mock_client.torrents_info.return_value = [mock_torrent]

        files = [Path("/tmp/movie.torrent")]
        hashes = setup.add_torrent_files(files, category="e2e-test")

        mock_client.torrents_add.assert_called_once_with(
            torrent_files=files[0], category="e2e-test",
        )
        assert "abc123" in hashes
        assert "abc123" in setup.registry.torrent_hashes

    def test_registers_multiple_torrents(self, _mock_sleep, tmp_path):
        """Registers all returned hashes from qBit."""
        mock_client = MagicMock()
        registry = TestRegistry(session_id="test-multi", base_dir=tmp_path)
        setup = TorrentSetup(client=mock_client, registry=registry)

        t1, t2 = MagicMock(), MagicMock()
        t1.hash, t1.name = "hash1", "Movie 1"
        t2.hash, t2.name = "hash2", "Show S01"
        mock_client.torrents_info.return_value = [t1, t2]

        files = [Path("/tmp/movie.torrent"), Path("/tmp/show.torrent")]
        hashes = setup.add_torrent_files(files)

        assert len(hashes) == 2
        assert set(hashes) == {"hash1", "hash2"}


class TestWaitForCompletion:
    """Tests for TorrentSetup.wait_for_completion()."""

    @patch("tests.e2e.setup_torrents.time.sleep")
    def test_returns_when_all_complete(self, _mock_sleep, tmp_path):
        """Returns once all torrents are complete (no timeout)."""
        mock_client = MagicMock()
        registry = TestRegistry(session_id="test-wait", base_dir=tmp_path)
        setup = TorrentSetup(client=mock_client, registry=registry)

        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_torrent.name = "Test Movie"
        mock_torrent.state_enum.is_complete = True
        mock_torrent.progress = 1.0
        mock_torrent.dlspeed = 0
        mock_client.torrents_info.return_value = [mock_torrent]

        # Should return without error (no timeout — waits until done)
        setup.wait_for_completion(["abc123"])


class TestGetDownloadedPaths:
    """Tests for TorrentSetup.get_downloaded_paths()."""

    def test_returns_content_paths(self, tmp_path):
        """Returns paths for matching hashes."""
        mock_client = MagicMock()
        registry = TestRegistry(session_id="test-paths", base_dir=tmp_path)
        setup = TorrentSetup(client=mock_client, registry=registry)

        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_torrent.content_path = "/tmp/downloads/Movie"
        mock_client.torrents_info.return_value = [mock_torrent]

        paths = setup.get_downloaded_paths(["abc123"])
        assert len(paths) == 1
        assert paths[0] == Path("/tmp/downloads/Movie")


class TestGetTorrentNames:
    """Tests for TorrentSetup.get_torrent_names()."""

    def test_returns_name_mapping(self, tmp_path):
        """Returns dict mapping hash to name."""
        mock_client = MagicMock()
        registry = TestRegistry(session_id="test-names", base_dir=tmp_path)
        setup = TorrentSetup(client=mock_client, registry=registry)

        t1 = MagicMock()
        t1.hash, t1.name = "abc", "Movie (2024)"
        mock_client.torrents_info.return_value = [t1]

        names = setup.get_torrent_names(["abc"])
        assert names == {"abc": "Movie (2024)"}
