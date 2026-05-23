"""Tests for the ``--format`` flag on ``library-reconcile``."""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

MOCK_SUMMARY = {
    "merkle_drift": 0,
    "dispatch_path_missing_count": 2,
    "dispatch_path_missing_sample": ["/mnt/a/Movie", "/mnt/b/Show"],
    "enrich_stale": 1,
    "release_orphans_count": 0,
    "release_orphans_sample": [],
    "files_without_release": 3,
    "season_count_drift_count": 1,
    "season_count_drift_sample": ["Show S01: DB=10 fs=12"],
    "items_without_files_count": 0,
    "items_without_files_sample": [],
    "path_missing_count": 5,
    "path_missing_sample": ["/mnt/c/path1", "/mnt/d/path2"],
    "total_findings": 12,
    "enqueued_repairs": 0,
}


class TestFormatFlagLibraryReconcile:
    """--format flag on library-reconcile produces valid output for each mode."""

    def test_format_json_produces_parseable_json(self) -> None:
        """--format json emits valid JSON with expected keys."""
        with patch(
            "personalscraper.indexer.cli.library_reconcile_command",
            return_value=(0, MOCK_SUMMARY),
        ):
            result = runner.invoke(app, ["--format", "json", "library-reconcile"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "total_findings" in parsed
        assert parsed["total_findings"] == 12

    def test_format_plain_produces_key_value(self) -> None:
        """--format plain emits key:value lines."""
        with patch(
            "personalscraper.indexer.cli.library_reconcile_command",
            return_value=(0, MOCK_SUMMARY),
        ):
            result = runner.invoke(app, ["--format", "plain", "library-reconcile"])
        assert result.exit_code == 0
        assert "total_findings:" in result.output

    def test_format_rich_is_default(self) -> None:
        """Default (rich) invokes the rich renderer and exits 0."""
        with patch(
            "personalscraper.indexer.cli.library_reconcile_command",
            return_value=(0, MOCK_SUMMARY),
        ):
            result = runner.invoke(app, ["library-reconcile"])
        assert result.exit_code == 0
        assert "total_findings" in result.output
