"""Shared pytest fixtures for PersonalScraper tests.

Installs structlog via :func:`personalscraper.logger.configure_logging` before any test runs,
so that stdlib-bridged `caplog` assertions see the expected records irrespective of which
subset of tests is collected (e.g. ``pytest tests/sorter/`` in isolation).
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import personalscraper.logger as _logger_mod
from personalscraper.config import Settings
from personalscraper.logger import configure_logging

# Expose shared fixtures from the fixtures package
pytest_plugins = ["tests.fixtures.config"]

# Disable Rich/Typer color output so help-text assertions (e.g. "--disk" in output)
# match the rendered text without ANSI escape codes splitting option names.
os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("TERM", "dumb")

# Patch targets for the eager config load in the CLI callback.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


@pytest.fixture(scope="session", autouse=True)
def _configure_logging_for_tests(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Configure structlog once per session for caplog interop.

    Points LOGS_DIR to a temporary directory so tests never write to the
    real ``logs/`` directory at the repository root.  Wraps the call in
    try/except so a misconfiguration surfaces as an explicit pytest failure
    rather than a silent no-op that lets later assertions fail for obscure
    reasons.

    Args:
        tmp_path_factory: Session-scoped factory for temporary directories.
    """
    # Redirect log output to a per-session temp dir so the real logs/ dir is
    # never touched during the test run.
    session_logs_dir: Path = tmp_path_factory.mktemp("logs", numbered=True)

    # Use pytest.MonkeyPatch.context() for session-scoped attribute patching
    # (the function-scoped monkeypatch fixture is not available here).
    mp = pytest.MonkeyPatch()
    mp.setattr(_logger_mod, "LOGS_DIR", session_logs_dir)

    try:
        configure_logging(verbose=False, quiet=False)
    except Exception as exc:  # noqa: BLE001 — surface any misconfiguration
        pytest.fail(f"configure_logging() failed: {exc}")


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

    V15: disk paths and staging/torrent dirs removed from Settings — they now
    live in Config (conf/models.py). This fixture only sets env vars for
    fields that still exist in Settings.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture for env vars.

    Returns:
        A Settings instance with neutral test values.
    """
    return Settings(_env_file=None)
