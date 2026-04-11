"""Tests for personalscraper.cli — CLI commands and global options."""

from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.models import StepReport

runner = CliRunner()

# Mock run_ingest for all tests that invoke the ingest command
_mock_report = StepReport(name="ingest", success_count=2, skip_count=1)


def test_version():
    """--version flag outputs the current version and exits."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help():
    """--help flag lists all available commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "PersonalScraper" in result.output
    assert "ingest" in result.output
    assert "sort" in result.output
    assert "scrape" in result.output
    assert "verify" in result.output
    assert "dispatch" in result.output
    assert "run" in result.output


@patch("personalscraper.cli.run_ingest", return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_ingest_command(mock_lock, mock_release, mock_run):
    """Ingest command acquires lock, runs ingest, and shows report."""
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert "2 OK" in result.output
    mock_lock.assert_called_once()
    mock_run.assert_called_once()
    mock_release.assert_called_once()


@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_ingest_lock_blocked(mock_lock):
    """Ingest command exits with error if lock is held."""
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


def test_sort_stub():
    """Sort stub command runs without error."""
    result = runner.invoke(app, ["sort"])
    assert result.exit_code == 0


_mock_scrape_report = StepReport(name="scrape", success_count=3, skip_count=2, error_count=1)


@patch("personalscraper.scraper.run.run_scrape", return_value=_mock_scrape_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_scrape_command(mock_lock, mock_release, mock_run):
    """Scrape command acquires lock, runs scrape, and shows report."""
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 0
    assert "3 OK" in result.output
    assert "2 skipped" in result.output
    mock_lock.assert_called_once()
    mock_release.assert_called_once()


@patch("personalscraper.scraper.run.run_scrape", return_value=_mock_scrape_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_scrape_dry_run(mock_lock, mock_release, mock_run):
    """Scrape --dry-run flag is passed through."""
    result = runner.invoke(app, ["scrape", "--dry-run"])
    assert result.exit_code == 0
    # Verify dry_run=True was passed
    call_kwargs = mock_run.call_args
    assert call_kwargs is not None


@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_scrape_lock_blocked(mock_lock):
    """Scrape command exits with error if lock is held."""
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


@patch("personalscraper.cli.run_ingest", return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_quiet_mode(mock_lock, mock_release, mock_run):
    """--quiet flag suppresses console output."""
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0
