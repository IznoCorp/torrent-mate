"""Tests for the ``--format`` flag on ``library-search``."""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

MOCK_ROWS: list[dict[str, object]] = [
    {"id": 1, "title": "Test Movie", "year": 2020, "kind": "movie", "nfo_status": "valid"},
    {"id": 2, "title": "Another Show", "year": 2021, "kind": "show", "nfo_status": ""},
]


class TestFormatFlagLibrarySearch:
    """--format flag on library-search produces valid output for each mode."""

    def test_format_json_produces_parseable_json(self) -> None:
        """--format json emits valid JSON with expected keys."""
        with patch(
            "personalscraper.indexer.cli.library_search_command",
            return_value=(0, MOCK_ROWS),
        ):
            result = runner.invoke(app, ["--format", "json", "library-search", "year:2020"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "rows" in parsed
        assert "count" in parsed
        assert parsed["count"] == 2
        assert parsed["query"] == "year:2020"

    def test_format_plain_produces_key_value(self) -> None:
        """--format plain emits key:value lines for the wrapper payload."""
        with patch(
            "personalscraper.indexer.cli.library_search_command",
            return_value=(0, MOCK_ROWS),
        ):
            result = runner.invoke(app, ["--format", "plain", "library-search", "year:2020"])
        assert result.exit_code == 0
        assert "count:" in result.output
        assert "query:" in result.output

    def test_format_rich_is_default(self) -> None:
        """Default (rich) invokes the table renderer and exits 0."""
        with patch(
            "personalscraper.indexer.cli.library_search_command",
            return_value=(0, MOCK_ROWS),
        ):
            result = runner.invoke(app, ["library-search", "year:2020"])
        assert result.exit_code == 0
        assert "Test Movie" in result.output

    def test_non_zero_rc_propagates(self) -> None:
        """Non-zero rc from the command function propagates."""
        with patch(
            "personalscraper.indexer.cli.library_search_command",
            return_value=(2, []),
        ):
            result = runner.invoke(app, ["library-search", "bad:field"])
        assert result.exit_code == 2

    def test_empty_results(self) -> None:
        """Empty results produce clean output in all formats."""
        with patch(
            "personalscraper.indexer.cli.library_search_command",
            return_value=(0, []),
        ):
            result = runner.invoke(app, ["library-search", "nonexistent"])
        assert result.exit_code == 0
