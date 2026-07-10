"""Tests for structlog integration with CLI commands."""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.models import StepReport

runner = CliRunner()

_mock_report = StepReport(name="ingest")


@patch("personalscraper.cli.run_ingest", return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
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


@patch("personalscraper.cli.run_ingest", return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
def test_verbose_mode(mock_lock, mock_release, mock_run, tmp_path, monkeypatch):
    """--verbose flag sets log level to DEBUG without error."""
    import personalscraper.logger as logger_mod

    monkeypatch.setattr(logger_mod, "LOGS_DIR", tmp_path / "logs")
    result = runner.invoke(app, ["--verbose", "ingest"])
    assert result.exit_code == 0


@patch("personalscraper.cli.run_ingest", return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
def test_quiet_mode(mock_lock, mock_release, mock_run, tmp_path, monkeypatch):
    """--quiet flag suppresses console output without error."""
    import personalscraper.logger as logger_mod

    monkeypatch.setattr(logger_mod, "LOGS_DIR", tmp_path / "logs")
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0
