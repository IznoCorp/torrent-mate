from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help():
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
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_sort_stub():
    result = runner.invoke(app, ["sort"])
    assert result.exit_code == 0


def test_scrape_stub():
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 0


def test_quiet_mode():
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0
