"""Tests for the ``--format`` flag on ``torrents-list``."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()


def _mock_torrent(
    name: str,
    state: str = "completed",
    progress: float = 1.0,
    size_bytes: int = 1073741824,
) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.state = state
    t.progress = progress
    t.size_bytes = size_bytes
    return t


class TestFormatFlagTorrentsList:
    """--format flag on torrents-list produces valid output for each mode."""

    def test_format_json_produces_parseable_json(self) -> None:
        """--format json emits valid JSON with expected keys."""
        mock_client = MagicMock()
        mock_client.get_completed.return_value = [
            _mock_torrent("Test Movie 2023.mkv"),
            _mock_torrent("Another Show S01.mkv", state="paused", progress=0.5, size_bytes=536870912),
        ]
        mock_client.get_all_hashes.return_value = {"a": "hash1", "b": "hash2", "c": "hash3"}
        mock_client.is_seeding.side_effect = [True, False]

        with patch(
            "personalscraper.api.torrent.qbittorrent.QBitClient",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["--format", "json", "torrents-list"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "torrents" in parsed
        assert "completed" in parsed
        assert parsed["completed"] == 2
        assert parsed["tracked"] == 3
        assert len(parsed["torrents"]) == 2
        assert parsed["torrents"][0]["name"] == "Test Movie 2023.mkv"

    def test_format_plain_produces_key_value(self) -> None:
        """--format plain emits key:value lines."""
        mock_client = MagicMock()
        mock_client.get_completed.return_value = [_mock_torrent("Movie.mkv")]
        mock_client.get_all_hashes.return_value = {"a": "h1"}
        mock_client.is_seeding.return_value = True

        with patch(
            "personalscraper.api.torrent.qbittorrent.QBitClient",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["--format", "plain", "torrents-list"])
        assert result.exit_code == 0
        assert "completed:" in result.output

    def test_format_rich_is_default(self) -> None:
        """Default (rich) emits the formatted table."""
        mock_client = MagicMock()
        mock_client.get_completed.return_value = [_mock_torrent("Movie.mkv")]
        mock_client.get_all_hashes.return_value = {"a": "h1"}
        mock_client.is_seeding.return_value = True

        with patch(
            "personalscraper.api.torrent.qbittorrent.QBitClient",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["torrents-list"])
        assert result.exit_code == 0
        assert "Movie.mkv" in result.output
        assert "Total:" in result.output
