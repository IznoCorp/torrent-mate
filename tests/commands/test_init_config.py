"""Tests for personalscraper.commands.init_config."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.commands.init_config import _backup_dir, init_config

_EXAMPLE_DIR = Path(__file__).parent.parent.parent / "config.example"


class TestBackupDir:
    """Tests for the _backup_dir helper."""

    def test_creates_bak(self, tmp_path: Path) -> None:
        """_backup_dir must create <name>.bak."""
        output = tmp_path / "config"
        output.mkdir()
        _backup_dir(output)
        assert (tmp_path / "config.bak").exists()
        assert not output.exists()

    def test_overwrites_existing_backup(self, tmp_path: Path) -> None:
        """Second call must overwrite the existing .bak (idempotent)."""
        output = tmp_path / "config"
        output.mkdir()
        (output / "first.json5").write_text("{}")
        _backup_dir(output)

        output.mkdir()
        (output / "second.json5").write_text("{}")
        _backup_dir(output)

        bak = tmp_path / "config.bak"
        assert bak.exists()
        assert (bak / "second.json5").exists()


class TestInitConfigCreate:
    """Tests for init_config creating a config directory from template."""

    def test_creates_config_from_example_non_interactive(self, tmp_path: Path) -> None:
        """Non-interactive run must copy config.example/ to output."""
        output = tmp_path / "config"
        init_config(_EXAMPLE_DIR, output, interactive=False, force=False)
        assert output.is_dir()
        assert (output / "config.json5").is_file()

    def test_output_has_expected_files(self, tmp_path: Path) -> None:
        """Output must contain the overlay files from the template."""
        output = tmp_path / "config"
        init_config(_EXAMPLE_DIR, output, interactive=False, force=False)
        assert (output / "paths.json5").is_file()
        assert (output / "disks.json5").is_file()
        assert (output / "categories.json5").is_file()

    def test_exits_2_if_output_exists_without_force(self, tmp_path: Path) -> None:
        """Exit code 2 if output exists and --force not set."""
        output = tmp_path / "config"
        output.mkdir()
        with pytest.raises(SystemExit) as exc_info:
            init_config(_EXAMPLE_DIR, output, interactive=False, force=False)
        assert exc_info.value.code == 2

    def test_force_backs_up_existing(self, tmp_path: Path) -> None:
        """--force must create .bak of the existing directory."""
        output = tmp_path / "config"
        output.mkdir()
        (output / "old.json5").write_text("{}")
        init_config(_EXAMPLE_DIR, output, interactive=False, force=True)
        bak = tmp_path / "config.bak"
        assert bak.exists()
        assert output.is_dir()
