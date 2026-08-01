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

    def test_sync_up_to_date_reports_nothing(self, tmp_path: Path, capsys) -> None:
        """Second sync with identical example reports no additions."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        init_config_sync(example, target, dry_run=False)
        # Second sync: target already has everything
        init_config_sync(example, target, dry_run=False)
        captured = capsys.readouterr()
        assert "No new keys or files to add" in captured.out

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

    def test_sync_conflicts_displayed_separately(self, tmp_path: Path, capsys) -> None:
        """Type conflicts are displayed under 'Conflicts' section, excluded from 'Added' count."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        target.mkdir()

        # Example has dict, but target will have a scalar → conflict.
        (example / "paths.json5").write_text(json5.dumps({"paths": {"staging_dir": "/example/staging"}}, indent=2))
        (example / "config.json5").write_text(json5.dumps({"config_version": 1, "overlays": ["paths.json5"]}, indent=2))

        # Pre-populate target with a scalar for "paths" — incompatible with example's dict.
        (target / "paths.json5").write_text(json5.dumps({"paths": "scalar_value"}, indent=2))
        (target / "config.json5").write_text(json5.dumps({"config_version": 1, "overlays": ["paths.json5"]}, indent=2))

        init_config_sync(example, target, dry_run=False)
        captured = capsys.readouterr()

        assert "Conflicts (kept your values):" in captured.out
        assert "Added 0 item(s)" in captured.out
        assert "paths" in captured.out

    def test_sync_additions_count_excludes_conflicts(self, tmp_path: Path, capsys) -> None:
        """Conflicts do not inflate the 'Added N item(s)' count."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        target.mkdir()

        (example / "config.json5").write_text(json5.dumps({"config_version": 1, "overlays": ["paths.json5"]}, indent=2))
        (example / "paths.json5").write_text(
            json5.dumps(
                {"paths": {"staging_dir": "/s", "new_key": "added_val"}, "settings": {"theme": "dark"}},
                indent=2,
            )
        )

        # Target has "paths" as scalar (conflict) + "settings" as a dict with extra key.
        (target / "config.json5").write_text(json5.dumps({"config_version": 1, "overlays": ["paths.json5"]}, indent=2))
        (target / "paths.json5").write_text(json5.dumps({"paths": "scalar", "settings": {"existing": "ok"}}, indent=2))

        init_config_sync(example, target, dry_run=False)
        captured = capsys.readouterr()

        # "paths" → conflict (example dict vs target scalar). "settings" → merged (both dicts),
        # "theme" added. So: 1 addition ("settings.theme"), 1 conflict ("paths").
        assert "Conflicts (kept your values):" in captured.out
        assert "Added 1 item(s)" in captured.out
        assert "paths" in captured.out

    def test_sync_malformed_json5_exits_1(self, tmp_path: Path, capsys) -> None:
        """Malformed JSON5 in example → clean error, Exit(1), no traceback."""
        import typer as _typer

        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        target.mkdir()

        (example / "config.json5").write_text("{valid: true}")
        (example / "broken.json5").write_text("not valid { json ~~~\n")

        with pytest.raises(_typer.Exit) as exc_info:
            init_config_sync(example, target, dry_run=False)
        assert exc_info.value.exit_code == 1

        captured = capsys.readouterr()
        assert "Error:" in captured.err or "Error:" in captured.out

    def test_sync_commits_git_repo_on_additions(self, tmp_path: Path, capsys) -> None:
        """After non-dry-run sync with additions, the canonical target is committed (F-J)."""
        import subprocess

        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        target.mkdir()
        self._make_minimal_example(example)

        # init git repo + configure user so a commit can be created.
        subprocess.run(
            ["git", "-C", str(target), "init"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "config", "user.email", "test@test"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "config", "user.name", "Test"],
            capture_output=True,
        )

        # Sync → target gets files committed.
        init_config_sync(example, target, dry_run=False)

        # Verify a commit was created.
        log = subprocess.run(
            ["git", "-C", str(target), "log", "--oneline"],
            capture_output=True,
            text=True,
        )
        assert "config_sync:" in log.stdout, (
            f"Expected config_sync commit, got log: {log.stdout}"
        )

        # Verify the committed files are real (ls-tree content assertion).
        ls = subprocess.run(
            ["git", "-C", str(target), "ls-tree", "-r", "HEAD", "--name-only"],
            capture_output=True,
            text=True,
        )
        files = ls.stdout.strip().splitlines()
        assert "config.json5" in files
        assert "paths.json5" in files

    def test_sync_no_additions_no_commit(self, tmp_path: Path) -> None:
        """Sync with 0 additions does NOT create a commit (F-J)."""
        import subprocess

        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        target.mkdir()
        self._make_minimal_example(example)

        # Pre-populate target identically.
        for f in example.iterdir():
            (target / f.name).write_text(f.read_text())

        # init git repo + configure user.
        subprocess.run(
            ["git", "-C", str(target), "init"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "config", "user.email", "test@test"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "config", "user.name", "Test"],
            capture_output=True,
        )

        init_config_sync(example, target, dry_run=False)

        # No commits should exist (nothing was added).
        log = subprocess.run(
            ["git", "-C", str(target), "log", "--oneline"],
            capture_output=True,
            text=True,
        )
        assert "config_sync:" not in log.stdout, (
            f"Unexpected commit when nothing was added: {log.stdout}"
        )

    def test_sync_git_failure_does_not_block_sync(self, tmp_path: Path) -> None:
        """Sync with a broken git still completes — fail-soft (F-J)."""
        from personalscraper.commands.init_config import init_config_sync

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        self._make_minimal_example(example)

        # Create a broken .git that's a file, not a directory — git init will
        # fail, but sync must still succeed.
        target.mkdir(parents=True, exist_ok=True)
        (target / ".git").write_text("broken")

        # Sync must not raise.
        init_config_sync(example, target, dry_run=False)

        # Files should still be synced despite the git failure.
        assert (target / "config.json5").is_file()
        assert (target / "paths.json5").is_file()


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

    # ── F-G: --sync target resolution ──

    def test_sync_no_output_no_env_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--sync without --output and without env → exit 2 with clear message.

        Patches ``resolve_config_path`` to return a non-existent path so the
        guard fires (the pkg_root/config fallback in the real resolver would
        prevent the guard from firing inside the repo).
        """
        from typer.testing import CliRunner

        from personalscraper.cli import app

        # Ensure no env var is set.
        monkeypatch.delenv("PERSONALSCRAPER_CONFIG", raising=False)
        example = tmp_path / "example"
        example.mkdir()
        (example / "config.json5").write_text("{}")
        nonexistent = tmp_path / "nonexistent-config"

        runner = CliRunner()
        with patch(
            "personalscraper.conf.loader.resolve_config_path",
            return_value=nonexistent,
        ):
            result = runner.invoke(
                app,
                [
                    "init-config",
                    "--sync",
                    "--example",
                    str(example),
                ],
            )
        assert result.exit_code == 2, result.output
        assert "not found" in result.output.lower()
        assert "PERSONALSCRAPER_CONFIG" in result.output

    def test_sync_with_env_resolves_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--sync without --output but with PERSONALSCRAPER_CONFIG → resolves to env."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        example = tmp_path / "example"
        target = tmp_path / "canonical"
        example.mkdir()
        target.mkdir()
        (example / "config.json5").write_text('{"key": "val"}')
        (target / "config.json5").write_text("{}")

        monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(target))

        runner = CliRunner()
        with patch("personalscraper.commands.init_config.init_config_sync") as mock_sync:
            result = runner.invoke(
                app,
                [
                    "init-config",
                    "--sync",
                    "--example",
                    str(example),
                ],
            )
        assert result.exit_code == 0, result.output
        mock_sync.assert_called_once()
        _args, kwargs = mock_sync.call_args
        assert kwargs["target"] == target.resolve()

    def test_sync_output_explicit_wins_over_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--sync --output explicit wins even when PERSONALSCRAPER_CONFIG is set."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        example = tmp_path / "example"
        env_target = tmp_path / "env-target"
        explicit_target = tmp_path / "explicit-target"
        example.mkdir()
        env_target.mkdir()
        explicit_target.mkdir()
        (example / "config.json5").write_text("{}")

        monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(env_target))

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
                    str(explicit_target),
                ],
            )
        assert result.exit_code == 0, result.output
        mock_sync.assert_called_once()
        _args, kwargs = mock_sync.call_args
        # Explicit --output must win over the env var.
        assert kwargs["target"] == explicit_target.resolve()

    def test_sync_target_exists_with_output_explicit(self, tmp_path: Path) -> None:
        """--sync --output to a nonexistent dir works (guard only applies when
        --output is NOT explicit).
        """
        from typer.testing import CliRunner

        from personalscraper.cli import app

        example = tmp_path / "example"
        target = tmp_path / "target"
        example.mkdir()
        (example / "config.json5").write_text("{}")

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
        # Explicit --output → guard is NOT triggered, sync proceeds.
        assert result.exit_code == 0, result.output
        mock_sync.assert_called_once()
