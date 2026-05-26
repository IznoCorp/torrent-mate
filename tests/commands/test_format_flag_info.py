"""Tests for ``--format`` global flag on ``personalscraper info``.

Verifies the global ``--format`` flag drives output mode for the info
command: ``rich`` (default, formatted text), ``json`` (parseable JSON),
and ``plain`` (key: value lines).
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()


class TestFormatFlagInfo:
    """Global ``--format`` flag drives info command output."""

    def test_format_json_emits_valid_json(self, test_config) -> None:
        """``--format json info`` outputs parseable JSON with version + disks."""
        result = runner.invoke(app, ["--format", "json", "info"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert "version" in data
        assert "staging_path" in data
        assert "disks" in data
        assert isinstance(data["disks"], list)

    def test_default_format_is_rich(self, test_config) -> None:
        """No ``--format`` flag → default rich output with version string."""
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0, result.output
        assert "personalscraper" in result.output.lower()
