"""Tests for personalscraper.commands.init_config."""

from __future__ import annotations

from pathlib import Path

import json5
import pytest

from personalscraper.commands.init_config import _backup_output, init_config

EXAMPLE_JSON5 = Path(__file__).parent.parent.parent / "config.example.json5"


class TestBackupOutput:
    """Tests for the _backup_output helper."""

    def test_creates_bak(self, tmp_path: Path) -> None:
        """_backup_output must create <name>.bak."""
        output = tmp_path / "config.json5"
        output.write_text("{}", encoding="utf-8")
        _backup_output(output)
        assert (tmp_path / "config.json5.bak").exists()
        assert not output.exists()

    def test_overwrites_existing_backup(self, tmp_path: Path) -> None:
        """Second call must overwrite the existing .bak (idempotent)."""
        output = tmp_path / "config.json5"
        output.write_text('{"first": true}', encoding="utf-8")
        _backup_output(output)
        output.write_text('{"second": true}', encoding="utf-8")
        _backup_output(output)
        bak = tmp_path / "config.json5.bak"
        assert bak.exists()
        assert json5.loads(bak.read_text(encoding="utf-8")) == {"second": True}


class TestInitConfigCreate:
    """Tests for init_config creating a new config file."""

    def test_creates_config_from_example_non_interactive(self, tmp_path: Path) -> None:
        """Non-interactive run with example must create config.json5."""
        output = tmp_path / "config.json5"
        init_config(EXAMPLE_JSON5, output, interactive=False, force=False)
        assert output.exists()

    def test_output_is_valid_json5(self, tmp_path: Path) -> None:
        """Written config.json5 must parse as JSON5."""
        output = tmp_path / "config.json5"
        init_config(EXAMPLE_JSON5, output, interactive=False, force=False)
        content = output.read_text(encoding="utf-8")
        parsed = json5.loads(content)
        assert isinstance(parsed, dict)

    def test_exits_2_if_output_exists_without_force(self, tmp_path: Path) -> None:
        """Exit code 2 if output exists and --force not set."""
        output = tmp_path / "config.json5"
        output.write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            init_config(EXAMPLE_JSON5, output, interactive=False, force=False)
        assert exc_info.value.code == 2

    def test_force_backs_up_existing(self, tmp_path: Path) -> None:
        """--force must create .bak of the existing file."""
        output = tmp_path / "config.json5"
        output.write_text('{"original": true}', encoding="utf-8")
        init_config(EXAMPLE_JSON5, output, interactive=False, force=True)
        bak = tmp_path / "config.json5.bak"
        assert bak.exists()
        assert output.exists()

    def test_force_idempotent_second_run_overwrites_bak(self, tmp_path: Path) -> None:
        """Running --force twice must overwrite the previous .bak."""
        output = tmp_path / "config.json5"
        output.write_text('{"run": 1}', encoding="utf-8")
        init_config(EXAMPLE_JSON5, output, interactive=False, force=True)
        init_config(EXAMPLE_JSON5, output, interactive=False, force=True)
        bak = tmp_path / "config.json5.bak"
        assert bak.exists()
        assert output.exists()
