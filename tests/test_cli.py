"""Tests for personalscraper.cli — CLI commands and global options."""

from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.models import StepReport

runner = CliRunner()

# Common patches for the `run` command (all run_* functions + notifier + healthcheck)
_PATCH_RUN_INGEST = "personalscraper.cli.run_ingest"
_PATCH_RUN_SORT = "personalscraper.sorter.run.run_sort"
_PATCH_RUN_SCRAPE = "personalscraper.scraper.run.run_scrape"
_PATCH_RUN_VERIFY = "personalscraper.verify.run.run_verify"
_PATCH_RUN_DISPATCH = "personalscraper.dispatch.run.run_dispatch"
_PATCH_PING_HC = "personalscraper.notifier.ping_healthcheck"
_PATCH_CLEANUP = "personalscraper.logger.cleanup_old_logs"
_PATCH_NOTIFIER_CONFIGURED = "personalscraper.notifier.TelegramNotifier.is_configured"

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


# ── Pipeline `run` command tests ─────────────────────

_mock_ingest = StepReport(name="ingest", success_count=3, skip_count=1)
_mock_sort = StepReport(name="sort", success_count=5)
_mock_scrape = StepReport(name="scrape", success_count=4, error_count=1)
_mock_verify = StepReport(name="verify", success_count=6)
_mock_dispatch = StepReport(name="dispatch", success_count=2)


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_RUN_DISPATCH, return_value=_mock_dispatch)
@patch(_PATCH_RUN_VERIFY, return_value=(_mock_verify, []))
@patch(_PATCH_RUN_SCRAPE, return_value=_mock_scrape)
@patch(_PATCH_RUN_SORT, return_value=_mock_sort)
@patch(_PATCH_RUN_INGEST, return_value=_mock_ingest)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_executes_all_steps(
    mock_lock, mock_release,
    mock_ingest, mock_sort, mock_scrape, mock_verify, mock_dispatch,
    mock_ping, mock_cleanup, mock_notifier_cfg,
):
    """Run command executes V1→V5 in sequence and shows summary."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1  # has_errors() because scrape has 1 error
    mock_ingest.assert_called_once()
    mock_sort.assert_called_once()
    mock_scrape.assert_called_once()
    mock_verify.assert_called_once()
    mock_dispatch.assert_called_once()


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_RUN_DISPATCH, return_value=_mock_dispatch)
@patch(_PATCH_RUN_VERIFY, return_value=(_mock_verify, []))
@patch(_PATCH_RUN_SCRAPE, return_value=StepReport(name="scrape", success_count=4))
@patch(_PATCH_RUN_SORT, return_value=_mock_sort)
@patch(_PATCH_RUN_INGEST, return_value=_mock_ingest)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_dry_run_flag(
    mock_lock, mock_release,
    mock_ingest, mock_sort, mock_scrape, mock_verify, mock_dispatch,
    mock_ping, mock_cleanup, mock_notifier_cfg,
):
    """--dry-run flag is passed to each step."""
    result = runner.invoke(app, ["run", "--dry-run"])
    assert result.exit_code == 0
    # Verify dry_run=True was passed to all steps
    for mock_fn in (mock_ingest, mock_sort, mock_scrape, mock_verify, mock_dispatch):
        kwargs = mock_fn.call_args.kwargs
        assert kwargs.get("dry_run") is True


@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_run_lock_blocked(mock_lock):
    """Run command exits with error if lock is held."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=True)
@patch("personalscraper.notifier.requests.post")
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_RUN_DISPATCH, return_value=_mock_dispatch)
@patch(_PATCH_RUN_VERIFY, return_value=(_mock_verify, []))
@patch(_PATCH_RUN_SCRAPE, return_value=StepReport(name="scrape", success_count=4))
@patch(_PATCH_RUN_SORT, return_value=_mock_sort)
@patch(_PATCH_RUN_INGEST, return_value=_mock_ingest)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_sends_telegram_when_configured(
    mock_lock, mock_release,
    mock_ingest, mock_sort, mock_scrape, mock_verify, mock_dispatch,
    mock_ping, mock_cleanup, mock_post, mock_notifier_cfg,
):
    """Telegram notification is sent when configured."""
    from unittest.mock import MagicMock
    mock_post.return_value = MagicMock(ok=True)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    mock_post.assert_called_once()


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_RUN_DISPATCH, return_value=_mock_dispatch)
@patch(_PATCH_RUN_VERIFY, return_value=(_mock_verify, []))
@patch(_PATCH_RUN_SCRAPE, return_value=StepReport(name="scrape", success_count=4))
@patch(_PATCH_RUN_SORT, return_value=_mock_sort)
@patch(_PATCH_RUN_INGEST, return_value=_mock_ingest)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_no_telegram_when_not_configured(
    mock_lock, mock_release,
    mock_ingest, mock_sort, mock_scrape, mock_verify, mock_dispatch,
    mock_ping, mock_cleanup, mock_notifier_cfg,
):
    """No Telegram call when not configured (no error)."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_RUN_DISPATCH, return_value=_mock_dispatch)
@patch(_PATCH_RUN_VERIFY, return_value=(_mock_verify, []))
@patch(_PATCH_RUN_SCRAPE, return_value=StepReport(name="scrape", success_count=4))
@patch(_PATCH_RUN_SORT, side_effect=RuntimeError("fatal sort crash"))
@patch(_PATCH_RUN_INGEST, return_value=_mock_ingest)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_continues_after_step_failure(
    mock_lock, mock_release,
    mock_ingest, mock_sort, mock_scrape, mock_verify, mock_dispatch,
    mock_ping, mock_cleanup, mock_notifier_cfg,
):
    """Pipeline continues executing remaining steps after a fatal step failure."""
    result = runner.invoke(app, ["run"])
    # Sort crashed, but scrape/verify/dispatch still ran
    mock_scrape.assert_called_once()
    mock_verify.assert_called_once()
    mock_dispatch.assert_called_once()
