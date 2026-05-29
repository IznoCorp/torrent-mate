"""Tests for the ``--format`` flag on ``library-show``."""

from __future__ import annotations

import json
from unittest.mock import patch

from personalscraper.cli import app
from tests.conftest import make_cli_runner

# ``make_cli_runner`` separates stdout from stderr so JSON parsing on
# ``result.stdout`` is not polluted by structlog log lines emitted to stderr
# (e.g. ``registry_boot_loaded`` since Phase 15 removed the autouse stub).
runner = make_cli_runner()

MOCK_PAYLOAD: dict[str, object] = {
    "item": {"id": 42, "title": "Test Movie", "year": 2023, "kind": "movie", "nfo_status": "valid"},
    "item_id": 42,
    "seasons": [],
    "files": [
        {
            "id": 1,
            "filename": "test.mkv",
            "rel_path": "Movies/Test",
            "disk_id": "disk1",
            "size_bytes": 12345,
            "mtime_ns": 123456789000,
            "streams": [
                {"idx": 0, "kind": "video", "codec": "h264", "lang": "eng"},
                {"idx": 1, "kind": "audio", "codec": "aac", "lang": "eng"},
            ],
        }
    ],
    "attributes": [{"key": "tmdb_id", "value": "12345"}],
    "deleted_history": [],
}


class TestFormatFlagLibraryShow:
    """--format flag on library-show produces valid output for each mode."""

    def test_format_json_produces_parseable_json(self) -> None:
        """--format json emits valid JSON with expected keys."""
        with patch(
            "personalscraper.indexer.cli.library_show_command",
            return_value=(0, MOCK_PAYLOAD),
        ):
            result = runner.invoke(app, ["--format", "json", "library-show", "42"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "item" in parsed
        assert "files" in parsed
        assert parsed["item"]["title"] == "Test Movie"

    def test_format_plain_produces_key_value(self) -> None:
        """--format plain emits key:value lines."""
        with patch(
            "personalscraper.indexer.cli.library_show_command",
            return_value=(0, MOCK_PAYLOAD),
        ):
            result = runner.invoke(app, ["--format", "plain", "library-show", "42"])
        assert result.exit_code == 0
        assert "item:" in result.output

    def test_format_rich_is_default(self) -> None:
        """Default (rich) invokes the section renderer and exits 0."""
        with patch(
            "personalscraper.indexer.cli.library_show_command",
            return_value=(0, MOCK_PAYLOAD),
        ):
            result = runner.invoke(app, ["library-show", "42"])
        assert result.exit_code == 0
        assert "media_item id=42" in result.output

    def test_non_zero_rc_propagates(self) -> None:
        """Non-zero rc from the command function propagates."""
        with patch(
            "personalscraper.indexer.cli.library_show_command",
            return_value=(2, {"error": "no item with id 999"}),
        ):
            result = runner.invoke(app, ["library-show", "999"])
        assert result.exit_code == 2
