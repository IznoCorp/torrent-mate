"""Tests for ``--format`` global flag on ``personalscraper library-doctor``.

Verifies the global ``--format`` flag drives output mode for the doctor
command: ``rich`` (default, Rich table), ``json`` (parseable JSON), and
``plain`` (key: value lines).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()


def _build_clean_db(tmp_path: Path) -> Path:
    """Create a fully-migrated clean indexer DB."""
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

    db_file = tmp_path / "test_indexer.db"
    migrations_dir = Path(_migrations_pkg.__file__).parent
    conn = open_db(db_file, event_bus=EventBus())
    apply_migrations(conn, migrations_dir)
    conn.commit()
    conn.close()
    return db_file


class TestFormatFlagDoctor:
    """Global ``--format`` flag drives doctor command output."""

    def test_format_json_emits_valid_json(self, tmp_path, test_config) -> None:
        """``--format json`` outputs parseable JSON with overall_status."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["--format", "json", "library-doctor"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output.strip())
        assert "overall_status" in data
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_format_plain_output_no_markup(self, tmp_path, test_config) -> None:
        """``--format plain`` outputs plain key: value lines (no Rich markup)."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["--format", "plain", "library-doctor"])
        assert result.exit_code == 0, result.output
        # Plain output uses "key: value" lines — should contain check names as keys
        assert "overall_status:" in result.output or "overall_status" in result.output
        # No Rich markup tags
        assert "[green]" not in result.output
        assert "[red]" not in result.output

    def test_default_format_is_rich(self, tmp_path, test_config) -> None:
        """No ``--format`` flag → default Rich output with check names."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["library-doctor"])
        assert result.exit_code == 0, result.output
        # Rich output should contain check names in the table
        assert "integrity_check" in result.output
