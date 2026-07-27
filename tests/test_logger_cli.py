"""Tests for structlog integration with CLI commands."""

import importlib
import json
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.models import StepReport

runner = CliRunner()

# The migrated ``ingest`` command takes the lock through the ``cli_helpers.boundary``
# decorator; patch that module's namespace for the lock helpers. ``run_ingest`` is
# still read via the ``cli`` facade, so that patch target is unchanged.
_BOUNDARY_MOD = importlib.import_module("personalscraper.cli_helpers.boundary")

_mock_report = StepReport(name="ingest")


@patch("personalscraper.cli_helpers.run_ingest", return_value=_mock_report)
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
def test_cli_creates_log_file(mock_lock, mock_release, mock_run, tmp_path, monkeypatch):
    """Running a CLI command creates a JSON log file in logs/."""
    import personalscraper.logger as logger_mod

    monkeypatch.setattr(logger_mod, "LOGS_DIR", tmp_path / "logs")
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0

    log_file = tmp_path / "logs" / "personalscraper.json"
    assert log_file.exists(), f"Expected log file was not created: {log_file}"
    for line in log_file.read_text().strip().split("\n"):
        if line:
            data = json.loads(line)
            assert "timestamp" in data
            assert "level" in data


@patch("personalscraper.cli_helpers.run_ingest", return_value=_mock_report)
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
def test_verbose_mode(mock_lock, mock_release, mock_run, tmp_path, monkeypatch):
    """--verbose flag sets log level to DEBUG without error."""
    import personalscraper.logger as logger_mod

    monkeypatch.setattr(logger_mod, "LOGS_DIR", tmp_path / "logs")
    result = runner.invoke(app, ["--verbose", "ingest"])
    assert result.exit_code == 0


@patch("personalscraper.cli_helpers.run_ingest", return_value=_mock_report)
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
def test_quiet_mode(mock_lock, mock_release, mock_run, tmp_path, monkeypatch):
    """--quiet flag suppresses console output without error."""
    import personalscraper.logger as logger_mod

    monkeypatch.setattr(logger_mod, "LOGS_DIR", tmp_path / "logs")
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0
