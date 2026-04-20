"""Tests for personalscraper.cli — CLI commands and global options."""

from datetime import datetime, timedelta
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.models import PipelineReport, StepReport

runner = CliRunner()

# Patches for standalone commands
_PATCH_CLI_RUN_INGEST = "personalscraper.cli.run_ingest"

# Patches for the `run` command (delegates to Pipeline)
_PATCH_PIPELINE_RUN = "personalscraper.pipeline.Pipeline.run"
_PATCH_PING_HC = "personalscraper.notifier.ping_healthcheck"
_PATCH_CLEANUP = "personalscraper.logger.cleanup_old_logs"
_PATCH_NOTIFIER_CONFIGURED = "personalscraper.notifier.TelegramNotifier.is_configured"


def _make_pipeline_report(has_errors: bool = False) -> PipelineReport:
    """Build a 7-step PipelineReport for testing.

    Args:
        has_errors: If True, add an error to the scrape step.

    Returns:
        PipelineReport with 7 steps populated.
    """
    report = PipelineReport(started_at=datetime(2026, 1, 1))
    report.add_step("ingest", StepReport(name="ingest", success_count=3))
    report.add_step("sort", StepReport(name="sort", success_count=5))
    report.add_step("clean", StepReport(name="clean"))
    report.add_step(
        "scrape",
        StepReport(name="scrape", success_count=4, error_count=1 if has_errors else 0),
    )
    report.add_step("cleanup", StepReport(name="cleanup"))
    report.add_step("verify", StepReport(name="verify", success_count=6))
    report.add_step("dispatch", StepReport(name="dispatch", success_count=2))
    report.finished_at = datetime(2026, 1, 1) + timedelta(seconds=30)
    return report


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
    assert "process" in result.output
    assert "run" in result.output


@patch(_PATCH_CLI_RUN_INGEST, return_value=_mock_report)
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


_mock_sort_report = StepReport(name="sort", success_count=4, skip_count=1)


@patch("personalscraper.sorter.run.run_sort", return_value=_mock_sort_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_sort_command(mock_lock, mock_release, mock_run):
    """Sort command acquires lock, runs sort, and shows report."""
    result = runner.invoke(app, ["sort"])
    assert result.exit_code == 0
    assert "4 OK" in result.output
    assert "1 skipped" in result.output
    mock_lock.assert_called_once()
    mock_run.assert_called_once()
    mock_release.assert_called_once()


@patch("personalscraper.sorter.run.run_sort", return_value=_mock_sort_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_sort_dry_run(mock_lock, mock_release, mock_run):
    """Sort --dry-run flag is passed through."""
    result = runner.invoke(app, ["sort", "--dry-run"])
    assert result.exit_code == 0
    call_kwargs = mock_run.call_args
    assert call_kwargs is not None


@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_sort_lock_blocked(mock_lock):
    """Sort command exits with error if lock is held."""
    result = runner.invoke(app, ["sort"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


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


@patch("personalscraper.process.run.run_process")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_process_command(mock_lock, mock_release, mock_run_process):
    """Process command runs and shows 3 step reports."""
    mock_run_process.return_value = (
        StepReport(name="clean", success_count=2),
        StepReport(name="scrape", success_count=5),
        StepReport(name="cleanup", success_count=1),
    )
    result = runner.invoke(app, ["process"])
    assert result.exit_code == 0
    assert "Clean" in result.output
    assert "Scrape" in result.output
    assert "Cleanup" in result.output


@patch(_PATCH_CLI_RUN_INGEST, return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_quiet_mode(mock_lock, mock_release, mock_run):
    """--quiet flag suppresses console output."""
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0


# ── Pipeline `run` command tests ─────────────────────
# CLI run() delegates to Pipeline.run() — step-level orchestration
# is tested in tests/test_pipeline.py. These tests verify CLI wiring.


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_PIPELINE_RUN)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_delegates_to_pipeline(
    mock_lock,
    mock_release,
    mock_pipeline_run,
    mock_ping,
    mock_cleanup,
    mock_notifier_cfg,
):
    """Run command delegates to Pipeline and shows 7-step summary panel."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    mock_pipeline_run.assert_called_once()
    # Verify all 7 step names appear in the panel
    for step_name in ("Ingest", "Sort", "Clean", "Scrape", "Cleanup", "Verify", "Dispatch"):
        assert step_name in result.output


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_PIPELINE_RUN, autospec=True)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_dry_run_and_interactive_flags(
    mock_lock,
    mock_release,
    mock_pipeline_run,
    mock_ping,
    mock_cleanup,
    mock_notifier_cfg,
):
    """--dry-run and --interactive flags are passed to Pipeline."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run", "--dry-run", "--interactive"])
    assert result.exit_code == 0
    # autospec=True makes the mock receive self — check Pipeline instance attributes
    pipeline_instance = mock_pipeline_run.call_args.args[0]
    assert pipeline_instance.dry_run is True
    assert pipeline_instance.interactive is True


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
@patch(_PATCH_PIPELINE_RUN)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_sends_telegram_when_configured(
    mock_lock,
    mock_release,
    mock_pipeline_run,
    mock_ping,
    mock_cleanup,
    mock_post,
    mock_notifier_cfg,
):
    """Telegram notification is sent when configured."""
    from unittest.mock import MagicMock

    mock_pipeline_run.return_value = _make_pipeline_report()
    mock_post.return_value = MagicMock(ok=True)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    mock_post.assert_called_once()


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_PIPELINE_RUN)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_no_telegram_when_not_configured(
    mock_lock,
    mock_release,
    mock_pipeline_run,
    mock_ping,
    mock_cleanup,
    mock_notifier_cfg,
):
    """No Telegram call when not configured (no error)."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_PIPELINE_RUN)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_exit_code_1_on_errors(
    mock_lock,
    mock_release,
    mock_pipeline_run,
    mock_ping,
    mock_cleanup,
    mock_notifier_cfg,
):
    """Run exits with code 1 when pipeline has errors."""
    mock_pipeline_run.return_value = _make_pipeline_report(has_errors=True)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1


@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=False)
@patch(_PATCH_CLEANUP, return_value=0)
@patch(_PATCH_PING_HC)
@patch(_PATCH_PIPELINE_RUN, side_effect=RuntimeError("pipeline crash"))
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_run_releases_lock_on_pipeline_crash(
    mock_lock,
    mock_release,
    mock_pipeline_run,
    mock_ping,
    mock_cleanup,
    mock_notifier_cfg,
):
    """Lock is released even when Pipeline.run() crashes."""
    runner.invoke(app, ["run"])
    mock_release.assert_called_once()


# ── Config error decorator tests ──────────────────────


@patch(_PATCH_CLI_RUN_INGEST, return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.get_settings")
def test_invalid_config_shows_friendly_error(mock_get_settings, mock_lock, mock_release, mock_run):
    """ValidationError from get_settings() is shown as friendly 'Configuration error'."""
    from pydantic import ValidationError

    from personalscraper.config import Settings

    # Build a real ValidationError by triggering it from Settings itself.
    try:
        Settings(qbit_port="abc")  # type: ignore[arg-type]
    except ValidationError as real_exc:
        mock_get_settings.side_effect = real_exc

    result = runner.invoke(app, ["ingest"])

    assert result.exit_code == 1
    assert "Configuration error" in result.output
    assert "qbit_port" in result.output
    assert "ValidationError" not in result.output


# --- Library maintenance CLI tests ---


class TestLibraryScan:
    """Tests for library-scan CLI command."""

    def test_help(self) -> None:
        """library-scan --help should display usage."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert result.exit_code == 0
        assert "library-scan" in result.output
        assert "--disk" in result.output
        assert "--category" in result.output

    def test_scan_produces_json(self, tmp_path, monkeypatch) -> None:
        """library-scan should produce library_scan.json."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryScanResult

        mock_result = LibraryScanResult(
            scanned_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            item_count=0,
            items=[],
        )

        with (
            patch("personalscraper.library.scanner.scan_library", return_value=mock_result),
            patch("personalscraper.library.models.write_json") as mock_write,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0
        mock_write.assert_called_once()


class TestLibraryClean:
    """Tests for library-clean CLI command."""

    def test_help(self) -> None:
        """library-clean --help should display usage."""
        result = runner.invoke(app, ["library-clean", "--help"])
        assert result.exit_code == 0
        assert "--apply" in result.output
        assert "--only" in result.output
        assert "--disk" in result.output

    def test_dry_run_by_default(self, tmp_path) -> None:
        """library-clean without --apply should be dry-run."""
        from unittest.mock import MagicMock

        from personalscraper.library.disk_cleaner import CleanResult

        mock_result = CleanResult(dry_run=True, deleted_count=5, freed_bytes=1024)

        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.library.disk_cleaner.clean_library", return_value=mock_result),
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-clean"])

        assert result.exit_code == 0
        assert "DRY-RUN" in result.output

    def test_apply_acquires_lock(self, tmp_path) -> None:
        """library-clean --apply should acquire pipeline lock."""
        from unittest.mock import MagicMock

        from personalscraper.library.disk_cleaner import CleanResult

        mock_result = CleanResult(dry_run=False, deleted_count=0)

        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.library.disk_cleaner.clean_library", return_value=mock_result),
            patch("personalscraper.cli.acquire_lock", return_value=True) as mock_lock,
            patch("personalscraper.cli.release_lock"),
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-clean", "--apply"])

        assert result.exit_code == 0
        mock_lock.assert_called_once()


class TestLibraryValidate:
    """Tests for library-validate CLI command."""

    def test_help(self) -> None:
        """library-validate --help should display usage."""
        result = runner.invoke(app, ["library-validate", "--help"])
        assert result.exit_code == 0
        assert "--disk" in result.output
        assert "--fix" in result.output

    def test_validate_produces_json(self, tmp_path) -> None:
        """library-validate should produce library_validation.json."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryValidationResult

        mock_result = LibraryValidationResult(
            validated_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            total_items=0,
            valid_count=0,
            fixed_count=0,
            issues_count=0,
        )

        with (
            patch("personalscraper.library.validator.validate_library", return_value=mock_result),
            patch("personalscraper.library.models.write_json") as mock_write,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-validate"])

        assert result.exit_code == 0
        mock_write.assert_called_once()

    def test_apply_without_fix_errors(self) -> None:
        """--apply without --fix should error."""
        from unittest.mock import MagicMock

        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
        ):
            mock_settings.return_value = MagicMock()
            result = runner.invoke(app, ["library-validate", "--apply"])
        assert result.exit_code == 1

    def test_fix_apply_acquires_lock(self, tmp_path) -> None:
        """--fix --apply should acquire pipeline lock."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryValidationResult

        mock_result = LibraryValidationResult(
            validated_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            total_items=0,
            valid_count=0,
            fixed_count=0,
            issues_count=0,
        )

        with (
            patch("personalscraper.library.validator.validate_library", return_value=mock_result),
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.cli.acquire_lock", return_value=True) as mock_lock,
            patch("personalscraper.cli.release_lock"),
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-validate", "--fix", "--apply"])

        assert result.exit_code == 0
        mock_lock.assert_called_once()

    def test_fix_forwards_params(self, tmp_path) -> None:
        """--fix should forward fix=True to validate_library."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryValidationResult

        mock_result = LibraryValidationResult(
            validated_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            total_items=1,
            valid_count=0,
            fixed_count=1,
            issues_count=0,
        )

        with (
            patch("personalscraper.library.validator.validate_library", return_value=mock_result) as mock_val,
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-validate", "--fix"])

        assert result.exit_code == 0
        mock_val.assert_called_once()
        _, kwargs = mock_val.call_args
        assert kwargs["fix"] is True
        assert kwargs["apply"] is False

    def test_fix_suggests_rescrape(self, tmp_path) -> None:
        """--fix with remaining issues should suggest library-rescrape."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryValidationResult

        mock_result = LibraryValidationResult(
            validated_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            total_items=2,
            valid_count=0,
            fixed_count=1,
            issues_count=1,
        )

        with (
            patch("personalscraper.library.validator.validate_library", return_value=mock_result),
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-validate", "--fix"])

        assert result.exit_code == 0
        assert "library-rescrape" in result.output


class TestLibraryAnalyze:
    """Tests for library-analyze CLI command."""

    def test_help(self) -> None:
        """library-analyze --help should display usage."""
        result = runner.invoke(app, ["library-analyze", "--help"])
        assert result.exit_code == 0
        assert "--disk" in result.output
        assert "--incremental" in result.output
        assert "--max-items" in result.output


class TestLibraryRecommend:
    """Tests for library-recommend CLI command."""

    def test_help(self) -> None:
        """library-recommend --help should display usage."""
        result = runner.invoke(app, ["library-recommend", "--help"])
        assert result.exit_code == 0
        assert "--sort" in result.output
        assert "--export" in result.output
        assert "--disk" in result.output
        assert "--category" in result.output


class TestLibraryRescrape:
    """Tests for library-rescrape CLI command."""

    def test_help(self) -> None:
        """library-rescrape --help should display usage."""
        result = runner.invoke(app, ["library-rescrape", "--help"])
        assert result.exit_code == 0
        assert "--only" in result.output
        assert "--disk" in result.output
        assert "--interactive" in result.output
        assert "--dry-run" in result.output
        assert "--max-items" in result.output

    def test_invalid_only_errors(self) -> None:
        """--only with invalid value should error."""
        from unittest.mock import MagicMock

        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
        ):
            mock_settings.return_value = MagicMock()
            result = runner.invoke(app, ["library-rescrape", "--only", "invalid"])
        assert result.exit_code == 1

    def test_dry_run_no_lock(self, tmp_path) -> None:
        """--dry-run should not acquire lock."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryRescrapeResult

        mock_result = LibraryRescrapeResult(
            rescraped_at="2026-04-17T12:00:00",
            disk_filter=None,
            category_filter=None,
            only_filter=None,
            dry_run=True,
            fixed_count=0,
            skipped_count=0,
            error_count=0,
        )

        with (
            patch("personalscraper.library.rescraper.rescrape_library", return_value=mock_result),
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.cli.acquire_lock") as mock_lock,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-rescrape", "--dry-run"])

        assert result.exit_code == 0
        mock_lock.assert_not_called()


class TestLibraryReport:
    """Tests for library-report CLI command."""

    def test_help(self) -> None:
        """library-report --help should display usage."""
        result = runner.invoke(app, ["library-report", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
