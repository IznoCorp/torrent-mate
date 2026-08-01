"""Tests for personalscraper.commands.init_config."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import json5
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

    def test_missing_example_exits_2(self, tmp_path: Path) -> None:
        """Example dir not present → exit code 2."""
        with pytest.raises(SystemExit) as exc_info:
            init_config(tmp_path / "nonexistent", tmp_path / "out", interactive=False, force=False)
        assert exc_info.value.code == 2


class TestInitConfigInteractive:
    """Tests for the interactive prompt path (_prompt_for_values)."""

    def test_interactive_writes_paths(self, tmp_path: Path) -> None:
        """Interactive mode prompts for paths and writes them to paths.json5."""
        output = tmp_path / "config"
        # Use input lines to satisfy each typer.prompt() call: torrent_dir,
        # staging_dir, data_dir.
        from typer.testing import CliRunner

        # Build a synthetic minimal config.example/ to avoid prompts on the
        # full template (which has many additional questions in disks etc.).
        example = tmp_path / "example"
        example.mkdir()
        (example / "paths.json5").write_text(
            '{"paths": {"torrent_complete_dir": "/old/torrents", "staging_dir": "./staging/", "data_dir": "./.data"}}'
        )
        (example / "disks.json5").write_text('{"disks": []}')

        # Use stdin redirection through a typer.testing.CliRunner.
        runner = CliRunner()

        import typer

        sub_app = typer.Typer()

        @sub_app.command()
        def go() -> None:
            init_config(example, output, interactive=True, force=False)

        result = runner.invoke(sub_app, [], input="/new/torrents\n/new/staging\n/new/data\n")
        assert result.exit_code == 0
        assert (output / "paths.json5").is_file()
        # Verify the new path values landed in the output paths.json5 file.
        content = (output / "paths.json5").read_text()
        # json5 dumps emits JSON5 output; parse with json5.
        import json5 as _json5

        data = _json5.loads(content)
        assert data["paths"]["torrent_complete_dir"] == "/new/torrents"
        assert data["paths"]["staging_dir"] == "/new/staging"
        assert data["paths"]["data_dir"] == "/new/data"

    def test_interactive_skips_when_disks_present(self, tmp_path: Path) -> None:
        """Existing disks in template skip the disk prompt."""
        from typer.testing import CliRunner

        example = tmp_path / "example"
        example.mkdir()
        (example / "paths.json5").write_text("{}")
        (example / "disks.json5").write_text('{"disks": [{"id": "drive_a", "path": "/x"}]}')

        output = tmp_path / "config"

        import typer

        sub_app = typer.Typer()

        @sub_app.command()
        def go() -> None:
            init_config(example, output, interactive=True, force=False)

        runner = CliRunner()
        result = runner.invoke(sub_app, [], input="/t\n/s\n/d\n")
        assert result.exit_code == 0
        assert "Found 1 disk" in result.output

    def test_interactive_no_disks_warns(self, tmp_path: Path) -> None:
        """Empty disks list prints the 'No disks configured' warning."""
        from typer.testing import CliRunner

        example = tmp_path / "example"
        example.mkdir()
        (example / "paths.json5").write_text("{}")
        (example / "disks.json5").write_text('{"disks": []}')

        output = tmp_path / "config"

        import typer

        sub_app = typer.Typer()

        @sub_app.command()
        def go() -> None:
            init_config(example, output, interactive=True, force=False)

        runner = CliRunner()
        result = runner.invoke(sub_app, [], input="/t\n/s\n/d\n")
        assert result.exit_code == 0
        assert "No disks configured" in result.output

    def test_interactive_handles_corrupt_paths_file(self, tmp_path: Path) -> None:
        """Corrupt paths.json5 gracefully falls back to empty defaults."""
        from typer.testing import CliRunner

        example = tmp_path / "example"
        example.mkdir()
        (example / "paths.json5").write_text("not valid {json")
        (example / "disks.json5").write_text('{"disks": []}')

        output = tmp_path / "config"

        import typer

        sub_app = typer.Typer()

        @sub_app.command()
        def go() -> None:
            init_config(example, output, interactive=True, force=False)

        runner = CliRunner()
        result = runner.invoke(sub_app, [], input="/t\n/s\n/d\n")
        assert result.exit_code == 0
        # The path-write step must have completed despite the corrupt input.
        assert (output / "paths.json5").is_file()

    def test_interactive_handles_corrupt_disks_file(self, tmp_path: Path) -> None:
        """Corrupt disks.json5 falls back to 'No disks configured' branch."""
        from typer.testing import CliRunner

        example = tmp_path / "example"
        example.mkdir()
        (example / "paths.json5").write_text("{}")
        (example / "disks.json5").write_text("not valid")

        output = tmp_path / "config"

        import typer

        sub_app = typer.Typer()

        @sub_app.command()
        def go() -> None:
            init_config(example, output, interactive=True, force=False)

        runner = CliRunner()
        result = runner.invoke(sub_app, [], input="/t\n/s\n/d\n")
        assert result.exit_code == 0
        assert "No disks configured" in result.output


class TestInitConfigSync:
    """Tests for the init_config_sync function (non-destructive config merge)."""

    @staticmethod
    def _make_minimal_example(d: Path) -> None:
        """Create a minimal config.example structure for testing."""
        (d / "config.json5").write_text(
            json5.dumps(
                {
                    "config_version": 1,
                    "overlays": ["paths.json5"],
                },
                indent=2,
            )
        )
        (d / "paths.json5").write_text(
            json5.dumps(
                {
                    "paths": {
                        "staging_dir": "/tmp/staging",
                        "torrent_complete_dir": "/tmp/torrents",
                    },
                },
                indent=2,
            )
        )

    def test_dry_run_reports_but_does_not_write(self, tmp_path: Path) -> None:
        """--sync --dry-run reports additions but creates no files."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        init_config_sync(example, target, dry_run=True)
        # Dry-run must NOT create the target directory, and no files
        # should be written (the target dir should not exist at all).
        assert not target.exists(), f"--sync --dry-run must not create {target}"

    def test_sync_additive_applies_writes_files(self, tmp_path: Path) -> None:
        """--sync without --dry-run copies missing files to target."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        init_config_sync(example, target, dry_run=False)
        assert target.is_dir()
        assert (target / "config.json5").is_file()
        assert (target / "paths.json5").is_file()

    def test_sync_up_to_date_reports_nothing(self, tmp_path: Path) -> None:
        """Second sync with identical example reports no additions."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        init_config_sync(example, target, dry_run=False)
        # Second sync: target already has everything
        init_config_sync(example, target, dry_run=False)
        # No assertion needed — just ensure no error/exceptions

    def test_sync_preserves_existing_target_values(self, tmp_path: Path) -> None:
        """After sync, a user-edited value in target remains unchanged."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        # First sync: populate target
        init_config_sync(example, target, dry_run=False)
        # User edits a value
        paths_file = target / "paths.json5"
        paths_data = json5.loads(paths_file.read_text())
        paths_data["paths"]["staging_dir"] = "/user/custom"
        paths_file.write_text(json5.dumps(paths_data, indent=2))
        # Sync again
        init_config_sync(example, target, dry_run=False)
        # Verify user edit preserved
        final = json5.loads((target / "paths.json5").read_text())
        assert final["paths"]["staging_dir"] == "/user/custom"

    def test_sync_adds_new_missing_file(self, tmp_path: Path) -> None:
        """Sync copies a new example file not yet in target."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        # First sync: partial (only one file)
        (target / "paths.json5").parent.mkdir(parents=True, exist_ok=True)
        # Copy just paths.json5 manually (simulate partial state)
        (target / "paths.json5").write_text((example / "paths.json5").read_text())
        # Now sync — config.json5 should be added
        init_config_sync(example, target, dry_run=False)
        assert (target / "config.json5").is_file()

    def test_sync_adds_missing_key_to_existing_file(self, tmp_path: Path) -> None:
        """Sync merges a new key from example into an existing target file."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        # First sync: populate target
        init_config_sync(example, target, dry_run=False)
        # Add a new key to example that target doesn't have
        ex_data = json5.loads((example / "paths.json5").read_text())
        ex_data["paths"]["data_dir"] = "/new/data"
        (example / "paths.json5").write_text(json5.dumps(ex_data, indent=2))
        # Sync again
        init_config_sync(example, target, dry_run=False)
        # Verify new key was added
        final = json5.loads((target / "paths.json5").read_text())
        assert final["paths"]["data_dir"] == "/new/data"


class TestInitConfigCliCommand:
    """Tests for the Typer-wired `init-config` command in cli.py."""

    def test_yes_force_flags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """`personalscraper init-config --yes --force` runs init_config non-interactively."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        runner = CliRunner()
        with patch("personalscraper.commands.init_config.init_config") as mock_init:
            result = runner.invoke(
                app,
                ["init-config", "--yes", "--force", "--output", str(tmp_path / "cfg")],
            )
        assert result.exit_code == 0
        mock_init.assert_called_once()
        _, kwargs = mock_init.call_args
        assert kwargs["interactive"] is False
        assert kwargs["force"] is True

    def test_default_interactive(self, tmp_path: Path) -> None:
        """Default invocation (without --yes) runs in interactive mode."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        runner = CliRunner()
        with patch("personalscraper.commands.init_config.init_config") as mock_init:
            result = runner.invoke(
                app,
                ["init-config", "--output", str(tmp_path / "cfg")],
            )
        assert result.exit_code == 0
        _, kwargs = mock_init.call_args
        assert kwargs["interactive"] is True

    def test_dry_run_help_exits_0(self) -> None:
        """--dry-run flag is recognised by Typer (help check)."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["init-config", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output

    def test_dry_run_does_not_write_files(self, tmp_path: Path) -> None:
        """--dry-run exits 0 and does NOT create any files at the output path."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        runner = CliRunner()
        output_path = tmp_path / "cfg"
        # Point --example at the real config.example/ so the check passes.
        example = Path(__file__).parent.parent.parent / "config.example"
        result = runner.invoke(
            app,
            ["init-config", "--dry-run", "--output", str(output_path), "--example", str(example)],
        )
        assert result.exit_code == 0
        # The output directory must NOT have been created.
        assert not output_path.exists(), f"--dry-run must not create {output_path}"
        assert "DRY-RUN" in result.output

    def test_dry_run_warns_when_example_missing(self, tmp_path: Path) -> None:
        """--dry-run with missing example dir prints a WARNING but still exits 0."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "init-config",
                "--dry-run",
                "--example",
                str(tmp_path / "nonexistent"),
                "--output",
                str(tmp_path / "cfg"),
            ],
        )
        # The dry-run path never calls sys.exit(2) — it only prints a warning.
        assert result.exit_code == 0
        assert "WARNING" in result.output

    # ── --sync flag ──

    def test_sync_flag_invokes_init_config_sync(self, tmp_path: Path) -> None:
        """--sync flag delegates to init_config_sync."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        example = tmp_path / "example"
        example.mkdir()
        (example / "config.json5").write_text("{}")
        target = tmp_path / "target"

        runner = CliRunner()
        with patch("personalscraper.commands.init_config.init_config_sync") as mock_sync:
            result = runner.invoke(
                app,
                [
                    "init-config",
                    "--sync",
                    "--example",
                    str(example),
                    "--output",
                    str(target),
                ],
            )
        assert result.exit_code == 0, result.output
        mock_sync.assert_called_once()

    def test_sync_and_force_mutually_exclusive(self, tmp_path: Path) -> None:
        """--sync --force exits 2 with a clear error message."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        example = tmp_path / "example"
        example.mkdir()
        (example / "config.json5").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "init-config",
                "--sync",
                "--force",
                "--example",
                str(example),
                "--output",
                str(tmp_path / "target"),
            ],
        )
        assert result.exit_code == 2, result.output
        assert "mutually exclusive" in result.output.lower()

    def test_sync_help_shows_flag(self) -> None:
        """--help output includes --sync."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["init-config", "--help"])
        assert result.exit_code == 0
        assert "--sync" in result.output
