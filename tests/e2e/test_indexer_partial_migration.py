"""E2E test for partial config migration failure and recovery.

Scenario (DESIGN §15.5):
1. Invoke ``config migrate-to-v2`` with a mock that raises mid-write,
   leaving ``.in-progress/`` on disk.
2. Assert ``.in-progress/`` exists and ``target_dir`` does not.
3. Assert that the next ``load_config_dir(target_dir)`` call refuses with a
   ``ConfigNotFoundError`` that contains an actionable message.
4. Resolve: remove ``.in-progress/`` and re-run the migration for real.
5. Assert the final ``load_config_dir`` returns a valid ``Config``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.conf.loader import ConfigNotFoundError, load_config_dir
from personalscraper.conf.migration import MigrationError, migrate_v1_to_v2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_V1 = """\
{{
    config_version: 1,
    paths: {{
        torrent_complete_dir: "{complete}",
        staging_dir: "{staging}",
        data_dir: "{data}",
    }},
    disks: [
        {{
            id: "disk_a",
            path: "{disk_a}",
            categories: ["movies", "tv_shows"],
        }},
    ],
    staging_dirs: [
        {{ id: 1, name: "movies", file_type: "movie" }},
        {{ id: 2, name: "tvshows", file_type: "tvshow" }},
        {{ id: 3, name: "ebooks", file_type: "ebook" }},
        {{ id: 4, name: "audio", file_type: "audio" }},
        {{ id: 5, name: "apps", file_type: "app" }},
        {{ id: 6, name: "android", file_type: "app" }},
        {{ id: 97, name: "temp", file_type: null, role: "ingest" }},
        {{ id: 98, name: "autres", file_type: "other" }},
    ],
}}
"""


def _write_v1(tmp_path: Path) -> Path:
    """Write a minimal valid v1 config to tmp_path/config.json5.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Path to the written config.json5.
    """
    legacy = tmp_path / "config.json5"
    legacy.write_text(
        _MINIMAL_V1.format(
            complete=tmp_path / "complete",
            staging=tmp_path / "staging",
            data=tmp_path / ".data",
            disk_a=tmp_path / "disk_a",
        ),
        encoding="utf-8",
    )
    return legacy


# ---------------------------------------------------------------------------
# E2E: partial failure → loader refuses → recovery
# ---------------------------------------------------------------------------


class TestPartialMigrationE2E:
    """End-to-end scenario: simulated mid-write kill, loader refusal, and recovery."""

    def test_partial_failure_leaves_in_progress(self, tmp_path: Path) -> None:
        """Simulated mid-write crash must leave .in-progress/ and NOT create target_dir."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        in_progress = Path(str(target) + ".in-progress")

        # Simulate a crash after the first write (master config.json5).
        write_call_count = 0
        original_write = __import__("personalscraper.conf.migration", fromlist=["_write_file"])._write_file

        def _crashing_write(path: Path, content: str) -> None:
            nonlocal write_call_count
            write_call_count += 1
            if write_call_count >= 3:
                # Crash on the third write — simulates SIGKILL mid-execution
                # without requiring a real subprocess.
                raise OSError("simulated mid-write crash (SIGKILL equivalent)")
            original_write(path, content)

        with patch("personalscraper.conf.migration._write_file", side_effect=_crashing_write):
            with pytest.raises(MigrationError):
                migrate_v1_to_v2(legacy, target)

        assert in_progress.is_dir(), ".in-progress/ must exist after simulated crash"
        assert not target.is_dir(), "target_dir must NOT be created after crash"

    def test_loader_refuses_when_only_in_progress_exists(self, tmp_path: Path) -> None:
        """load_config_dir on a missing target_dir raises ConfigNotFoundError."""
        # This simulates what the user would see after a crash: target_dir absent,
        # .in-progress/ present.  The loader is pointed at target_dir (which does
        # not exist) and must raise with an actionable message.
        target = tmp_path / "config"
        in_progress = Path(str(target) + ".in-progress")
        in_progress.mkdir()

        with pytest.raises(ConfigNotFoundError) as exc_info:
            load_config_dir(target)

        # The error message must be actionable: reference init-config or migration.
        msg = str(exc_info.value)
        assert "config.json5" in msg or "init-config" in msg or "migration" in msg.lower(), (
            f"Error message should be actionable, got: {msg!r}"
        )

    def test_recovery_by_rm_and_rerun(self, tmp_path: Path) -> None:
        """After removing .in-progress/ and re-running, migration completes successfully."""
        import shutil

        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        in_progress = Path(str(target) + ".in-progress")

        # Step 1: Simulate partial failure.
        write_call_count = 0
        original_write = __import__("personalscraper.conf.migration", fromlist=["_write_file"])._write_file

        def _crashing_write(path: Path, content: str) -> None:
            nonlocal write_call_count
            write_call_count += 1
            if write_call_count >= 3:
                raise OSError("simulated crash")
            original_write(path, content)

        with patch("personalscraper.conf.migration._write_file", side_effect=_crashing_write):
            with pytest.raises(MigrationError):
                migrate_v1_to_v2(legacy, target)

        assert in_progress.is_dir()

        # Step 2: Resolve — rm -rf .in-progress/ (as the actionable message says).
        shutil.rmtree(in_progress)
        assert not in_progress.exists()

        # Step 3: Re-run migration for real (no mock).
        migrate_v1_to_v2(legacy, target)

        # Step 4: load_config_dir must succeed.
        from personalscraper.conf.loader import load_config_dir
        from personalscraper.conf.models import Config

        config = load_config_dir(target)
        assert isinstance(config, Config)

    def test_full_scenario_via_cli(self, tmp_path: Path) -> None:
        """Full E2E via the CLI runner: crash → loader refuses → rm → rerun → success."""
        import shutil

        from typer.testing import CliRunner

        from personalscraper.cli import app
        from personalscraper.conf.loader import load_config_dir
        from personalscraper.conf.models import Config

        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        in_progress = Path(str(target) + ".in-progress")

        # Step 1: Simulate partial failure via CLI (mocked _write_file).
        write_call_count = 0
        original_write = __import__("personalscraper.conf.migration", fromlist=["_write_file"])._write_file

        def _crashing_write(path: Path, content: str) -> None:
            nonlocal write_call_count
            write_call_count += 1
            if write_call_count >= 3:
                raise OSError("simulated crash in CLI path")
            original_write(path, content)

        runner = CliRunner(mix_stderr=False)

        with patch("personalscraper.conf.migration._write_file", side_effect=_crashing_write):
            result = runner.invoke(app, ["config", "migrate-to-v2", str(legacy), str(target)])

        # CLI must exit non-zero on migration failure.
        assert result.exit_code != 0, f"Expected non-zero exit after crash, got {result.exit_code}"
        assert in_progress.is_dir()
        assert not target.is_dir()

        # Step 2: Loader refuses.
        with pytest.raises(ConfigNotFoundError):
            load_config_dir(target)

        # Step 3: Resolve by removing .in-progress/.
        shutil.rmtree(in_progress)

        # Step 4: Re-run migration for real via CLI.
        result2 = runner.invoke(app, ["config", "migrate-to-v2", str(legacy), str(target)])
        assert result2.exit_code == 0, result2.output

        # Step 5: Loader succeeds.
        config = load_config_dir(target)
        assert isinstance(config, Config)
