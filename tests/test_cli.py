"""Tests for personalscraper.cli — CLI commands and global options."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import AppCtx, app
from personalscraper.models import PipelineReport, StepReport

runner = CliRunner()

# Patch targets for the eager config load in the CLI callback.
# The callback does a lazy import from personalscraper.conf.loader, so we
# patch the canonical location of load_config (the module it lives in).
# The autouse fixture in conftest.py patches these for all tests; tests
# that verify config-error paths override them inside the test body.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


# ── 5.1 AppCtx dataclass ────────────────────────────────────────────────────


def test_appctx_instantiation() -> None:
    """AppCtx can be instantiated with None values for both fields."""
    ctx = AppCtx(config=None, config_override=None)
    assert ctx.config is None
    assert ctx.config_override is None


def test_appctx_with_path() -> None:
    """AppCtx stores config_override Path when provided."""
    p = Path("/tmp/config.json5")
    ctx = AppCtx(config=None, config_override=p)
    assert ctx.config_override == p


# Patches for standalone commands
_PATCH_CLI_RUN_INGEST = "personalscraper.cli.run_ingest"

# Patches for the `run` command (delegates to Pipeline)
_PATCH_PIPELINE_RUN = "personalscraper.pipeline.Pipeline.run"
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
    # Match any semver string — avoids hardcoding the version number.
    assert re.search(r"\d+\.\d+\.\d+", result.output)


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
def test_sort_dry_run(mock_run):
    """Sort --dry-run flag is forwarded as dry_run=True to run_sort."""
    result = runner.invoke(app, ["sort", "--dry-run"])
    assert result.exit_code == 0
    call_kwargs = mock_run.call_args
    assert call_kwargs is not None
    # Verify the wiring invariant: dry_run=True must reach the service layer.
    assert call_kwargs.kwargs.get("dry_run") is True


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
def test_scrape_dry_run(mock_run):
    """Scrape --dry-run flag is forwarded as dry_run=True to run_scrape."""
    result = runner.invoke(app, ["scrape", "--dry-run"])
    assert result.exit_code == 0
    # Verify the wiring invariant: dry_run=True must reach the service layer.
    call_kwargs = mock_run.call_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("dry_run") is True


@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_scrape_lock_blocked(mock_lock):
    """Scrape command exits with error if lock is held."""
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


@patch("personalscraper.process.run.run_process")
def test_process_command(mock_run_process):
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


def test_quiet_mode():
    """--quiet flag suppresses console output."""
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0


# ── Pipeline `run` command tests ─────────────────────
# CLI run() delegates to Pipeline.run() — step-level orchestration
# is tested in tests/test_pipeline.py. These tests verify CLI wiring.


@patch(_PATCH_PIPELINE_RUN)
def test_run_delegates_to_pipeline(mock_pipeline_run):
    """Run command delegates to Pipeline and shows 7-step summary panel."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    mock_pipeline_run.assert_called_once()
    # Verify all 7 step names appear in the panel
    for step_name in ("Ingest", "Sort", "Clean", "Scrape", "Cleanup", "Verify", "Dispatch"):
        assert step_name in result.output


@patch(_PATCH_PIPELINE_RUN, autospec=True)
def test_run_dry_run_and_interactive_flags(mock_pipeline_run):
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
def test_run_sends_telegram_when_configured(mock_post, mock_notifier_cfg):
    """Telegram notification is sent when configured."""
    mock_post.return_value = MagicMock(ok=True)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    mock_post.assert_called_once()


def test_run_no_telegram_when_not_configured():
    """No Telegram call when not configured (no error)."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


@patch(_PATCH_PIPELINE_RUN)
def test_run_exit_code_1_on_errors(mock_pipeline_run):
    """Run exits with code 1 when pipeline has errors."""
    mock_pipeline_run.return_value = _make_pipeline_report(has_errors=True)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1


@patch(_PATCH_PIPELINE_RUN, side_effect=RuntimeError("pipeline crash"))
@patch("personalscraper.cli.release_lock")
def test_run_releases_lock_on_pipeline_crash(mock_release, mock_pipeline_run):
    """Lock is released even when Pipeline.run() crashes."""
    runner.invoke(app, ["run"])
    mock_release.assert_called_once()


@patch("personalscraper.pipeline.Pipeline.__init__", return_value=None)
@patch(_PATCH_PIPELINE_RUN)
def test_run_accepts_skip_trailers(mock_pipeline_run, mock_pipeline_init):
    """--skip-trailers is accepted and passed to Pipeline as skip_trailers=True."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run", "--skip-trailers"])
    assert result.exit_code == 0, result.output
    _, kwargs = mock_pipeline_init.call_args
    assert kwargs.get("skip_trailers") is True


@patch("personalscraper.pipeline.Pipeline.__init__", return_value=None)
@patch(_PATCH_PIPELINE_RUN)
def test_run_accepts_continue_on_trailer_error(mock_pipeline_run, mock_pipeline_init):
    """--continue-on-trailer-error is accepted and passed to Pipeline as continue_on_trailer_error=True."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run", "--continue-on-trailer-error"])
    assert result.exit_code == 0, result.output
    _, kwargs = mock_pipeline_init.call_args
    assert kwargs.get("continue_on_trailer_error") is True


# ── Config error decorator tests ──────────────────────


@patch("personalscraper.cli.get_settings")
def test_invalid_config_shows_friendly_error(mock_get_settings):
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
        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
        ):
            mock_settings.return_value = MagicMock()
            result = runner.invoke(app, ["library-validate", "--apply"])
        assert result.exit_code == 1

    def test_fix_apply_acquires_lock(self, tmp_path) -> None:
        """--fix --apply should acquire pipeline lock."""
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
        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
        ):
            mock_settings.return_value = MagicMock()
            result = runner.invoke(app, ["library-rescrape", "--only", "invalid"])
        assert result.exit_code == 1

    def test_dry_run_no_lock(self, tmp_path) -> None:
        """--dry-run should not acquire lock."""
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


# ── 5.2 Callback eager load ──────────────────────────────────────────────────


def test_callback_no_config_file_exits_2() -> None:
    """Missing config.json5 causes exit code 2 with a clear error message.

    Overrides the autouse _mock_config_load to simulate missing file.
    """
    from personalscraper.conf.loader import ConfigNotFoundError

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/nonexistent/config.json5")),
        patch(_PATCH_LOAD_CONFIG, side_effect=ConfigNotFoundError("No config file at /nonexistent/config.json5")),
    ):
        result = runner.invoke(app, ["ingest"])

    assert result.exit_code == 2
    assert "Config error" in result.output


def test_callback_invalid_config_exits_2() -> None:
    """Invalid config.json5 (validation error) causes exit code 2.

    Overrides the autouse _mock_config_load to simulate a parse error.
    """
    from personalscraper.conf.loader import ConfigValidationError

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, side_effect=ConfigValidationError("JSON5 parse error")),
    ):
        result = runner.invoke(app, ["sort"])

    assert result.exit_code == 2
    assert "Config error" in result.output


def test_callback_config_flag_not_found_exits_2() -> None:
    """--config pointing to a non-existent file causes exit code 2."""
    from personalscraper.conf.loader import ConfigNotFoundError

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/bad/path.json5")),
        patch(_PATCH_LOAD_CONFIG, side_effect=ConfigNotFoundError("No config file at /bad/path.json5")),
    ):
        result = runner.invoke(app, ["--config", "/bad/path.json5", "sort"])

    assert result.exit_code == 2
    assert "Config error" in result.output


def test_callback_help_works_without_config() -> None:
    """--help short-circuits before the callback's eager config load.

    Typer handles --help before invoking the callback body, so no config
    file is needed.
    """
    # Even without the autouse patch active, --help must not try to load config.
    # The autouse fixture is active here too, but the key assertion is exit 0.
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "PersonalScraper" in result.output


# ── 5.3 init-config Typer command ───────────────────────────────────────────


def test_init_config_help_shows_flags() -> None:
    """init-config --help displays all expected flags."""
    result = runner.invoke(app, ["init-config", "--help"])
    assert result.exit_code == 0
    assert "--yes" in result.output
    assert "--force" in result.output
    assert "--output" in result.output
    assert "--example" in result.output


def test_callback_init_config_bypasses_load() -> None:
    """init-config subcommand bypasses eager config load (config may not exist yet).

    Overrides autouse to simulate missing config; init-config must not exit 2.
    """
    from personalscraper.conf.loader import ConfigNotFoundError

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/nonexistent/config.json5")),
        patch(_PATCH_LOAD_CONFIG, side_effect=ConfigNotFoundError("No config")),
        patch("personalscraper.commands.init_config.init_config") as mock_init,
    ):
        result = runner.invoke(app, ["init-config"])

    # Must not fail with exit 2 (config error) — init_config itself exits 0
    assert result.exit_code != 2
    mock_init.assert_called_once()


def test_init_config_cmd_passes_flags() -> None:
    """init-config forwards --yes and --force to init_config()."""
    with patch("personalscraper.commands.init_config.init_config") as mock_init:
        result = runner.invoke(app, ["init-config", "--yes", "--force"])

    assert result.exit_code == 0
    mock_init.assert_called_once()
    _, kwargs = mock_init.call_args
    assert kwargs["interactive"] is False
    assert kwargs["force"] is True


# ── 5.5 --category accepts ID or alias ──────────────────────────────────────


class TestCategoryResolution:
    """Tests for --category ID/alias resolution in library commands."""

    def test_category_direct_id_resolves(self) -> None:
        """--category movies (builtin ID) resolves without error."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryScanResult

        mock_result = LibraryScanResult(
            scanned_at="2026-04-21T12:00:00",
            disk_filter=None,
            category_filter=None,
            item_count=0,
            items=[],
        )

        with (
            patch("personalscraper.library.scanner.scan_library", return_value=mock_result) as mock_scan,
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = MagicMock()
            settings.data_dir.__truediv__ = lambda s, x: MagicMock()
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-scan", "--category", "movies"])

        assert result.exit_code == 0, result.output
        # Verify the resolved category_id was passed downstream (not the raw alias string)
        _, kwargs = mock_scan.call_args
        assert kwargs["category_filter"] == "movies"

    def test_category_alias_resolves(self, test_config) -> None:
        """--category with a configured alias resolves to the canonical ID."""
        from unittest.mock import MagicMock

        from personalscraper.conf.models import CategoryConfig
        from personalscraper.library.models import LibraryScanResult

        # Add an alias to the movies category in the test config
        test_config.categories["movies"] = CategoryConfig(folder_name="Films", aliases=["films", "movie"])

        mock_result = LibraryScanResult(
            scanned_at="2026-04-21T12:00:00",
            disk_filter=None,
            category_filter=None,
            item_count=0,
            items=[],
        )

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch("personalscraper.library.scanner.scan_library", return_value=mock_result) as mock_scan,
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = MagicMock()
            settings.data_dir.__truediv__ = lambda s, x: MagicMock()
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-scan", "--category", "films"])

        assert result.exit_code == 0, result.output
        _, kwargs = mock_scan.call_args
        assert kwargs["category_filter"] == "movies"

    def test_category_unknown_exits_2(self) -> None:
        """--category with an unknown value exits with code 2 and error message."""
        result = runner.invoke(app, ["library-scan", "--category", "unknown_xyz"])

        assert result.exit_code == 2
        assert "unknown_xyz" in result.output
        assert "Valid IDs" in result.output


# ── info command ─────────────────────────────────────────────────────────────


def test_info_command(test_config) -> None:
    """Info command exits 0 and output contains 'personalscraper' and version."""
    # Patch shutil.disk_usage so no real filesystem access occurs.
    import collections
    from unittest.mock import patch as _patch

    import personalscraper

    Usage = collections.namedtuple("Usage", ["total", "used", "free"])
    fake_usage = Usage(total=2_000_000_000_000, used=1_200_000_000_000, free=800_000_000_000)

    with _patch("shutil.disk_usage", return_value=fake_usage):
        result = runner.invoke(app, ["info"])

    assert result.exit_code == 0, f"exit_code={result.exit_code}\n{result.output}"
    assert "personalscraper" in result.output
    assert personalscraper.__version__ in result.output
    assert "staging:" in result.output
