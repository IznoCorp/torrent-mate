"""Shared pytest fixtures for PersonalScraper tests."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.config import Settings

# Expose shared fixtures from the fixtures package
pytest_plugins = ["tests.fixtures.config"]

# Disable Rich/Typer color output so help-text assertions (e.g. "--disk" in output)
# match the rendered text without ANSI escape codes splitting option names.
os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("TERM", "dumb")

# Patch targets for the eager config load in the CLI callback.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


@pytest.fixture(autouse=True)
def _mock_cli_config_load(request, test_config):
    """Patch the eager config load in the CLI callback for CLI test files only.

    Intercepts load_config / resolve_config_path so tests do not need a
    real config.json5 on disk. Only active for test files that invoke the
    Typer CLI via CliRunner (test_cli.py, test_logger_cli.py). Other test
    files (e.g. tests/conf/) call the loader directly and are unaffected.

    Args:
        request: Pytest request object for introspection.
        test_config: Synthetic Config fixture from tests/fixtures/config.py.
    """
    # Only intercept in files that drive the CLI via CliRunner.
    cli_test_files = {"test_cli.py", "test_logger_cli.py"}
    if request.fspath.basename not in cli_test_files:
        yield
        return

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=test_config),
    ):
        yield


@pytest.fixture
def mock_settings(tmp_path, monkeypatch):
    """Provide a Settings instance with temp paths and no real .env.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture for env vars.

    Returns:
        A Settings instance pointing to temporary directories.
    """
    monkeypatch.setenv("TORRENT_COMPLETE_DIR", str(tmp_path / "complete"))
    monkeypatch.setenv("STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setenv("DISK1_DIR", str(tmp_path / "disk1"))
    monkeypatch.setenv("DISK2_DIR", str(tmp_path / "disk2"))
    monkeypatch.setenv("DISK3_DIR", str(tmp_path / "disk3"))
    monkeypatch.setenv("DISK4_DIR", str(tmp_path / "disk4"))
    (tmp_path / "complete").mkdir()
    (tmp_path / "staging").mkdir()
    return Settings(_env_file=None)
