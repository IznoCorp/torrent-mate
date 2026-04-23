"""E2E test: auto-create staging tree on first run via CLI.

Validates the full path: config.json5 with empty staging_dir -> CLI invocation
-> staging subdirectories created on disk -> no crash.

Note: The ``run --dry-run`` command attempts to connect to qBittorrent as part
of the ingest step. In CI / test environments without a live qBittorrent, the
ingest step returns an error report (exit code 1). The staging tree is still
auto-created by ``ensure_staging_tree`` inside ``Pipeline.run()`` *before*
ingest runs, so the directory assertions are valid regardless of exit code.
"""

from __future__ import annotations

from pathlib import Path

import json5
import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.conf.models import Config
from personalscraper.conf.staging import folder_name

_STAGING_DIRS = [
    {"id": 1, "name": "movies", "file_type": "movie"},
    {"id": 2, "name": "tvshows", "file_type": "tvshow"},
    {"id": 3, "name": "ebooks", "file_type": "ebook"},
    {"id": 4, "name": "audio", "file_type": "audio"},
    {"id": 5, "name": "apps", "file_type": "app"},
    {"id": 6, "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres", "file_type": "other"},
]


@pytest.fixture
def e2e_env(tmp_path: Path):
    """Create a minimal config.json5 in tmp_path with an empty staging_dir.

    Args:
        tmp_path: pytest-provided temporary directory.

    Returns:
        Dict with keys: tmp_path, staging, config_file.
    """
    staging = tmp_path / "staging"
    # Do NOT create staging -- let the CLI auto-create it

    config_data = {
        "config_version": 1,
        "paths": {
            "torrent_complete_dir": str(tmp_path / "torrents"),
            "staging_dir": str(staging),
            "data_dir": str(tmp_path / ".data"),
        },
        "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
        "staging_dirs": _STAGING_DIRS,
    }
    config_file = tmp_path / "config.json5"
    config_file.write_text(json5.dumps(config_data))

    # Create the disk dir so dispatch can resolve it
    (tmp_path / "disk_a").mkdir()

    return {"tmp_path": tmp_path, "staging": staging, "config_file": config_file}


class TestStagingBootstrapE2E:
    """Full E2E: staging tree auto-created on first run via `run --dry-run`."""

    def test_dry_run_creates_staging_tree(self, e2e_env):
        """Personalscraper run --dry-run creates all 8 staging subdirs from scratch.

        The staging tree is bootstrapped by ``ensure_staging_tree`` inside
        ``Pipeline.run()`` before any pipeline step executes, so it is created
        even when downstream steps (e.g. ingest qBittorrent) error out.

        Args:
            e2e_env: Fixture providing tmp_path, staging, and config_file.
        """
        runner = CliRunner()
        config_path = str(e2e_env["config_file"])
        staging = e2e_env["staging"]

        # Staging does not exist before the run
        assert not staging.exists(), "Pre-condition: staging dir must not exist"

        result = runner.invoke(app, ["--config", config_path, "run", "--dry-run"])

        # Exit code 0 (empty staging, no errors) or 1 (ingest failed -- qBittorrent
        # not available in test env). Both are acceptable: staging creation happens
        # before ingest and is independent of qBittorrent connectivity.
        assert result.exit_code in (0, 1), f"Unexpected exit code {result.exit_code}.\nOutput:\n{result.output}"

        # All 8 subdirectories must have been created regardless of exit code
        assert staging.is_dir(), "staging_dir root must have been created"

        config = Config.model_validate(
            {
                "paths": {
                    "torrent_complete_dir": str(e2e_env["tmp_path"] / "torrents"),
                    "staging_dir": str(staging),
                    "data_dir": str(e2e_env["tmp_path"] / ".data"),
                },
                "disks": [
                    {
                        "id": "disk_a",
                        "path": str(e2e_env["tmp_path"] / "disk_a"),
                        "categories": ["movies"],
                    }
                ],
                "staging_dirs": _STAGING_DIRS,
            }
        )
        for entry in config.staging_dirs:
            expected = staging / folder_name(entry)
            assert expected.is_dir(), f"Expected staging subdir {expected} to be created"

    def test_dry_run_idempotent_no_error(self, e2e_env):
        """Second dry-run on complete tree exits with same code and does not error.

        The staging tree already exists after the first run. A second run must
        not raise or crash -- ``ensure_staging_tree`` is idempotent (existing
        directories are silently skipped).

        Args:
            e2e_env: Fixture providing tmp_path, staging, and config_file.
        """
        runner = CliRunner()
        config_path = str(e2e_env["config_file"])

        # First run creates the tree
        result_first = runner.invoke(app, ["--config", config_path, "run", "--dry-run"])
        first_code = result_first.exit_code

        # Second run should return the same exit code without crashing
        result = runner.invoke(app, ["--config", config_path, "run", "--dry-run"])
        assert result.exit_code in (0, 1), (
            f"Second run failed with unexpected exit code {result.exit_code}.\nOutput:\n{result.output}"
        )
        # Must not regress: second run is never worse than the first
        assert result.exit_code == first_code, (
            f"Second run exit code {result.exit_code} differs from first {first_code}"
        )

    def test_missing_staging_dirs_config_exits_nonzero(self, tmp_path):
        """Config without staging_dirs section fails with a friendly error message.

        The ``_check_staging_dirs_present`` model validator raises a clear
        ValueError pointing the user to MANUAL.md SS Staging layout.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        config_data = {
            "config_version": 1,
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            # staging_dirs intentionally omitted
        }
        config_file = tmp_path / "config.json5"
        config_file.write_text(json5.dumps(config_data))

        runner = CliRunner()
        result = runner.invoke(app, ["--config", str(config_file), "run", "--dry-run"])

        assert result.exit_code != 0
        assert "MANUAL.md" in result.output or "staging_dirs" in result.output
