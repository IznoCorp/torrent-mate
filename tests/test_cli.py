"""Tests for personalscraper.cli — CLI commands and global options."""

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()


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


def test_ingest_stub():
    """Ingest stub command runs without error."""
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_sort_stub():
    """Sort stub command runs without error."""
    result = runner.invoke(app, ["sort"])
    assert result.exit_code == 0


def test_scrape_stub():
    """Scrape stub command runs without error."""
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 0


def test_quiet_mode():
    """--quiet flag suppresses console output."""
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0
