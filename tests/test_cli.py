"""Tests for personalscraper.cli — CLI commands and global options."""

import importlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli import AppCtx, app
from personalscraper.models import PipelineReport, StepReport
from tests.fixtures.settings_stub import make_typed_settings_stub

runner = CliRunner()

# Migrated pipeline step commands (ingest/sort/scrape/verify/enforce/dispatch/
# clean/cleanup/process) acquire the lock through the ``cli_helpers.boundary``
# decorator, which imports the lock helpers into its OWN module namespace —
# patching ``personalscraper.cli.*`` alone no longer intercepts them. The
# ``run`` command still uses ``personalscraper.cli.*``. The lock fixtures below
# therefore patch BOTH seams with a single shared mock so call-count assertions
# hold regardless of which command type is under test.
_BOUNDARY_MOD = importlib.import_module("personalscraper.cli_helpers.boundary")

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
    legacy = AppCtx(config=None, config_override=None)
    assert legacy.config is None
    assert legacy.config_override is None


def test_appctx_with_path() -> None:
    """AppCtx stores config_override Path when provided."""
    p = Path("/tmp/config.json5")
    legacy = AppCtx(config=None, config_override=p)
    assert legacy.config_override == p


# Patches for standalone commands
_PATCH_CLI_RUN_INGEST = "personalscraper.cli_helpers.run_ingest"

# Patches for the `run` command (delegates to Pipeline)
_PATCH_PIPELINE_RUN = "personalscraper.pipeline.Pipeline.run"
_PATCH_NOTIFIER_CONFIGURED = "personalscraper.api.notify.telegram.TelegramNotifier.is_configured"
_PATCH_HC_CONFIGURED = "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured"
_PATCH_HC_PING_FAIL = "personalscraper.api.notify.healthchecks.HealthcheckClient.ping_fail"
_PATCH_HC_PING_SUCCESS = "personalscraper.api.notify.healthchecks.HealthcheckClient.ping_success"
_PATCH_HC_PING_START = "personalscraper.api.notify.healthchecks.HealthcheckClient.ping_start"


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


# ══════════════════════════════════════════════════════════════════════════════
# Shared fixtures — consolidate repetitive @patch decorators into reusable
# fixtures so the per-test @patch count drops from 52 → ≤ 25 (DEV #49, ACC-39).
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def _cli_lock_mocks():
    """``acquire_pipeline_lock`` (True) + ``release_lock`` mocks for step-command tests.

    Pipeline commands route through ``acquire_pipeline_lock`` (global lock +
    scrape-dir fail-closed check, webui-ux phase 4); release is unchanged. One
    shared mock backs both the ``personalscraper.cli`` seam (``run``) and the
    ``cli_helpers.boundary`` seam (migrated step commands) so the call-count
    assertions hold whichever seam the command under test uses.
    """
    acquire = MagicMock(return_value=True)
    release = MagicMock()
    with (
        patch("personalscraper.cli_helpers.acquire_pipeline_lock", acquire),
        patch("personalscraper.cli_helpers.release_lock", release),
        patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", acquire),
        patch.object(_BOUNDARY_MOD, "release_lock", release),
    ):
        yield SimpleNamespace(acquire=acquire, release=release)


@pytest.fixture
def _cli_lock_blocked():
    """``acquire_pipeline_lock`` returning False — simulates a held pipeline lock.

    Patches both the ``personalscraper.cli`` seam (``run``) and the
    ``cli_helpers.boundary`` seam (migrated step commands) with a single mock.
    """
    blocked = MagicMock(return_value=False)
    with (
        patch("personalscraper.cli_helpers.acquire_pipeline_lock", blocked),
        patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", blocked),
    ):
        yield blocked


@pytest.fixture
def _mock_release_lock():
    """Stand-alone ``release_lock`` mock for crash-recovery tests."""
    with patch("personalscraper.cli_helpers.release_lock") as mock:
        yield mock


@pytest.fixture
def _hc_for_run():
    """Healthcheck mocks wired for ``personalscraper run`` (configured=True)."""
    with (
        patch(_PATCH_HC_CONFIGURED, return_value=True) as cfg,
        patch(_PATCH_HC_PING_START) as start,
        patch(_PATCH_HC_PING_SUCCESS) as ok,
        patch(_PATCH_HC_PING_FAIL) as fail,
    ):
        yield SimpleNamespace(cfg=cfg, start=start, ok=ok, fail=fail)


@pytest.fixture
def _mock_run_ingest():
    with patch(_PATCH_CLI_RUN_INGEST, return_value=_mock_report) as mock:
        yield mock


@pytest.fixture
def _mock_run_sort():
    with patch("personalscraper.sorter.run.run_sort", return_value=_mock_sort_report) as mock:
        yield mock


@pytest.fixture
def _mock_run_scrape():
    with patch("personalscraper.scraper.run.run_scrape", return_value=_mock_scrape_report) as mock:
        yield mock


@pytest.fixture
def _mock_run_process():
    result = (
        StepReport(name="clean", success_count=2),
        StepReport(name="scrape", success_count=5),
        StepReport(name="cleanup", success_count=1),
    )
    with patch("personalscraper.process.run.run_process", return_value=result) as mock:
        yield mock


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


def test_ingest_command(_cli_lock_mocks, _mock_run_ingest):
    """Ingest command acquires lock, runs ingest, and shows report."""
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert "2 OK" in result.output
    _cli_lock_mocks.acquire.assert_called_once()
    _mock_run_ingest.assert_called_once()
    _cli_lock_mocks.release.assert_called_once()


def test_ingest_lock_blocked(_cli_lock_blocked):
    """Ingest command exits with error if lock is held."""
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


_mock_sort_report = StepReport(name="sort", success_count=4, skip_count=1)


def test_sort_command(_cli_lock_mocks, _mock_run_sort):
    """Sort command acquires lock, runs sort, and shows report."""
    result = runner.invoke(app, ["sort"])
    assert result.exit_code == 0
    assert "4 OK" in result.output
    assert "1 skipped" in result.output
    _cli_lock_mocks.acquire.assert_called_once()
    _mock_run_sort.assert_called_once()
    _cli_lock_mocks.release.assert_called_once()


def test_sort_dry_run(_mock_run_sort):
    """Sort --dry-run flag is forwarded as dry_run=True to run_sort."""
    result = runner.invoke(app, ["sort", "--dry-run"])
    assert result.exit_code == 0
    call_kwargs = _mock_run_sort.call_args
    assert call_kwargs is not None
    # Verify the wiring invariant: dry_run=True must reach the service layer.
    assert call_kwargs.kwargs.get("dry_run") is True


def test_sort_lock_blocked(_cli_lock_blocked):
    """Sort command exits with error if lock is held."""
    result = runner.invoke(app, ["sort"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


_mock_scrape_report = StepReport(name="scrape", success_count=3, skip_count=2, error_count=1)


def test_scrape_command(_cli_lock_mocks, _mock_run_scrape):
    """Scrape command acquires lock, runs scrape, and shows report."""
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 0
    assert "3 OK" in result.output
    assert "2 skipped" in result.output
    _cli_lock_mocks.acquire.assert_called_once()
    _cli_lock_mocks.release.assert_called_once()


def test_scrape_dry_run(_mock_run_scrape):
    """Scrape --dry-run flag is forwarded as dry_run=True to run_scrape."""
    result = runner.invoke(app, ["scrape", "--dry-run"])
    assert result.exit_code == 0
    # Verify the wiring invariant: dry_run=True must reach the service layer.
    call_kwargs = _mock_run_scrape.call_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("dry_run") is True


def test_scrape_lock_blocked(_cli_lock_blocked):
    """Scrape command exits with error if lock is held."""
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


def test_process_command(_mock_run_process):
    """Process command runs and shows 3 step reports."""
    result = runner.invoke(app, ["process"])
    assert result.exit_code == 0
    assert "Clean" in result.output
    assert "Scrape" in result.output
    assert "Cleanup" in result.output


def test_quiet_mode():
    """--quiet flag suppresses console output."""
    result = runner.invoke(app, ["--quiet", "ingest"])
    assert result.exit_code == 0


def test_torrents_list_command_help_advertises_command():
    """Regression for the BDD audit (P1): ``torrents-list`` is registered.

    The pipeline-monitor skill calls ``personalscraper torrents-list`` in
    its GATE 0 inventory ; without it the skill aborts with
    "No such command 'torrents-list'".
    """
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "torrents-list" in result.output


def test_torrents_list_unreachable_exits_2(monkeypatch):
    """Listing failure on a boot-wired client → exit code 2 with friendly message.

    Matches the skill's pipeline-monitor expectation for an OPERATIONAL
    classification (qBit ban / daemon down). Since DESIGN D3 the client is
    boot-wired into ``AppContext``; the command reports a friendly listing
    failure when ``get_completed()`` raises a transient torrent error.
    """
    from personalscraper.api.torrent._errors import QBitAuthLockoutError  # noqa: PLC0415
    from tests.commands._e2e_helpers import mock_boundary_torrent_client  # noqa: PLC0415

    client = MagicMock()
    client.get_completed.side_effect = QBitAuthLockoutError("auth lockout active")
    mock_boundary_torrent_client(monkeypatch, client)

    result = runner.invoke(app, ["torrents-list"])

    assert result.exit_code == 2
    assert "Torrent listing failed" in result.output


# ── Pipeline `run` command tests ─────────────────────
# CLI run() delegates to Pipeline.run() — step-level orchestration
# is tested in tests/test_pipeline.py. These tests verify CLI wiring.


@patch(_PATCH_PIPELINE_RUN)
def test_run_delegates_to_pipeline(mock_pipeline_run):
    """Run command delegates to Pipeline and completes successfully."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    mock_pipeline_run.assert_called_once()


@patch(_PATCH_PIPELINE_RUN, autospec=True)
def test_run_dry_run_and_interactive_flags(mock_pipeline_run):
    """--dry-run and --interactive flags reach ``Pipeline.run`` as kwargs.

    Sub-phase 2.3 contract: ``dry_run`` and ``interactive`` are keyword-only
    parameters of :meth:`Pipeline.run`, not attributes set by
    ``__init__``. ``autospec=True`` makes the mock receive ``self`` as
    the first positional arg, so the run-scope flags appear in
    ``call_args.kwargs``.
    """
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run", "--dry-run", "--interactive"])
    assert result.exit_code == 0
    kwargs = mock_pipeline_run.call_args.kwargs
    assert kwargs.get("dry_run") is True
    assert kwargs.get("interactive") is True


def test_run_lock_blocked(_cli_lock_blocked):
    """Run command exits with error if lock is held."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert "Another instance" in result.output


@patch("personalscraper.subscribers.telegram.TelegramSubscriber.__init__", return_value=None)
@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=True)
@patch(_PATCH_PIPELINE_RUN)
def test_run_sends_telegram_when_configured(mock_pipeline_run, mock_notifier_cfg, mock_tg_sub_init):
    """TelegramSubscriber is constructed on the event bus when notifier is configured.

    ``TelegramSubscriber`` self-subscribes in ``__init__`` against the
    AppContext bus. The CLI bootstrap should build it when
    ``TelegramNotifier.is_configured`` is True. ``Pipeline.run`` has no
    ``observers`` kwarg — the bus is the sole emit substrate.
    """
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0, result.output
    assert mock_tg_sub_init.called, "TelegramSubscriber was not constructed"
    _, kwargs = mock_pipeline_run.call_args
    assert "observers" not in kwargs, "Pipeline.run must not accept an observers kwarg"


@patch("personalscraper.subscribers.telegram.TelegramSubscriber.__init__", return_value=None)
@patch(_PATCH_PIPELINE_RUN)
def test_run_no_telegram_when_not_configured(mock_pipeline_run, mock_tg_sub_init):
    """is_configured gating: when notifier is not configured, no TelegramSubscriber is wired."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert not mock_tg_sub_init.called, "TelegramSubscriber must not be constructed when notifier is not configured"


@patch("personalscraper.subscribers.telegram.TelegramSubscriber.__init__", return_value=None)
@patch(_PATCH_NOTIFIER_CONFIGURED, return_value=True)
@patch(_PATCH_PIPELINE_RUN)
def test_run_headless_disables_all_observers(mock_pipeline_run, mock_cfg, mock_tg_sub_init):
    """``--headless`` skips subscriber construction and Pipeline.run still has no ``observers`` kwarg."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run", "--headless"])
    assert result.exit_code == 0
    assert not mock_tg_sub_init.called, "--headless must skip TelegramSubscriber construction"
    _, kwargs = mock_pipeline_run.call_args
    assert "observers" not in kwargs, "Pipeline.run must not accept an observers kwarg"


def test_run_pings_healthcheck_success_on_clean_run(_hc_for_run):
    """Clean pipeline → ping_start + ping_success, no ping_fail."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    _hc_for_run.start.assert_called_once()
    _hc_for_run.ok.assert_called_once()
    _hc_for_run.fail.assert_not_called()


@patch(_PATCH_PIPELINE_RUN, side_effect=RuntimeError("pipeline crash"))
def test_run_pings_healthcheck_fail_on_exception(mock_pipeline_run, _hc_for_run, _mock_release_lock):
    """Pipeline.run() raising → ping_start + ping_fail (dead-man's-switch contract)."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0  # crash propagated
    _hc_for_run.start.assert_called_once()
    _hc_for_run.fail.assert_called_once()
    _hc_for_run.ok.assert_not_called()


@patch(_PATCH_PIPELINE_RUN)
def test_run_pings_healthcheck_fail_on_report_errors(mock_pipeline_run, _hc_for_run):
    """Report with has_errors() → ping_fail (not ping_success)."""
    mock_pipeline_run.return_value = _make_pipeline_report(has_errors=True)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    _hc_for_run.start.assert_called_once()
    _hc_for_run.fail.assert_called_once()
    _hc_for_run.ok.assert_not_called()


@patch(_PATCH_PIPELINE_RUN)
def test_run_exit_code_1_on_errors(mock_pipeline_run):
    """Run exits with code 1 when pipeline has errors."""
    mock_pipeline_run.return_value = _make_pipeline_report(has_errors=True)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1


@patch(_PATCH_PIPELINE_RUN, side_effect=RuntimeError("pipeline crash"))
def test_run_releases_lock_on_pipeline_crash(mock_pipeline_run, _mock_release_lock):
    """Lock is released even when Pipeline.run() crashes."""
    runner.invoke(app, ["run"])
    _mock_release_lock.assert_called_once()


@patch(_PATCH_PIPELINE_RUN)
def test_run_accepts_skip_trailers(mock_pipeline_run):
    """--skip-trailers is accepted and passed to Pipeline.run as skip_trailers=True."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run", "--skip-trailers"])
    assert result.exit_code == 0, result.output
    _, kwargs = mock_pipeline_run.call_args
    assert kwargs.get("skip_trailers") is True


@patch(_PATCH_PIPELINE_RUN)
def test_run_accepts_continue_on_trailer_error(mock_pipeline_run):
    """--continue-on-trailer-error reaches Pipeline.run as continue_on_trailer_error=True."""
    mock_pipeline_run.return_value = _make_pipeline_report()
    result = runner.invoke(app, ["run", "--continue-on-trailer-error"])
    assert result.exit_code == 0, result.output
    _, kwargs = mock_pipeline_run.call_args
    assert kwargs.get("continue_on_trailer_error") is True


# ── Config error decorator tests ──────────────────────


@patch.object(_BOUNDARY_MOD, "get_settings")
def test_invalid_config_shows_friendly_error(mock_get_settings):
    """ValidationError from get_settings() is shown as friendly 'Configuration error'.

    The migrated ``ingest`` command resolves settings through the
    ``cli_helpers.boundary`` decorator, so the ``get_settings`` seam to patch is
    the boundary module's namespace; ``handle_cli_errors`` still catches the
    ``ValidationError`` and renders the friendly message.
    """
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
        from personalscraper.maintenance.disk_cleaner import CleanResult

        mock_result = CleanResult(dry_run=True, deleted_count=5, freed_bytes=1024)

        with (
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.maintenance.disk_cleaner.clean_library", return_value=mock_result),
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-clean"])

        assert result.exit_code == 0
        assert "DRY-RUN" in result.output

    def test_apply_acquires_lock(self, tmp_path) -> None:
        """library-clean --apply should acquire pipeline lock."""
        from personalscraper.maintenance.disk_cleaner import CleanResult

        mock_result = CleanResult(dry_run=False, deleted_count=0)

        with (
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.maintenance.disk_cleaner.clean_library", return_value=mock_result),
            patch("personalscraper.cli_helpers.acquire_pipeline_lock", return_value=True) as mock_lock,
            patch("personalscraper.cli_helpers.release_lock"),
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
        from personalscraper.verify.library_checks import LibraryValidationResult

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
            patch("personalscraper.verify.library_checks.validate_library", return_value=mock_result),
            patch("personalscraper.io_utils.write_json") as mock_write,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
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
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
        ):
            mock_settings.return_value = make_typed_settings_stub()
            result = runner.invoke(app, ["library-validate", "--apply"])
        assert result.exit_code == 1

    def test_fix_apply_acquires_lock(self, tmp_path) -> None:
        """--fix --apply should acquire pipeline lock."""
        from personalscraper.verify.library_checks import LibraryValidationResult

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
            patch("personalscraper.verify.library_checks.validate_library", return_value=mock_result),
            patch("personalscraper.io_utils.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
            patch("personalscraper.cli_helpers.acquire_pipeline_lock", return_value=True) as mock_lock,
            patch("personalscraper.cli_helpers.release_lock"),
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-validate", "--fix", "--apply"])

        assert result.exit_code == 0
        mock_lock.assert_called_once()

    def test_fix_forwards_params(self, tmp_path) -> None:
        """--fix should forward fix=True to validate_library."""
        from personalscraper.verify.library_checks import LibraryValidationResult

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
            patch("personalscraper.verify.library_checks.validate_library", return_value=mock_result) as mock_val,
            patch("personalscraper.io_utils.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
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
        from personalscraper.verify.library_checks import LibraryValidationResult

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
            patch("personalscraper.verify.library_checks.validate_library", return_value=mock_result),
            patch("personalscraper.io_utils.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
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
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
        ):
            mock_settings.return_value = make_typed_settings_stub()
            result = runner.invoke(app, ["library-rescrape", "--only", "invalid"])
        assert result.exit_code == 1

    def test_dry_run_no_lock(self, tmp_path) -> None:
        """--dry-run should not acquire lock."""
        from personalscraper.maintenance.rescraper import LibraryRescrapeResult

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
            patch("personalscraper.maintenance.rescraper.rescrape_library", return_value=mock_result),
            patch("personalscraper.io_utils.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
            patch("personalscraper.cli_helpers.acquire_pipeline_lock") as mock_lock,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-rescrape", "--dry-run"])

        assert result.exit_code == 0
        mock_lock.assert_not_called()

    def test_cli_library_rescrape_item_id_passed(self, tmp_path) -> None:
        """--item-id is forwarded to rescrape_library as item_id=99.

        Invokes ``library-rescrape --item-id 99 --dry-run`` via CliRunner,
        mocking out ``rescrape_library``, ``open_db``, and ``apply_migrations``
        so no real DB is needed.  Asserts that ``rescrape_library`` was called
        with ``item_id=99``.

        A placeholder DB file is created at the path ``config.indexer.db_path``
        resolves to (``tmp_path/.data/library.db``) so the ``db_path.exists()``
        guard in the CLI passes before ``open_db`` is reached.
        """
        from personalscraper.maintenance.rescraper import LibraryRescrapeResult

        # Create the DB file so the exists() guard introduced by RT-3 passes.
        db_file = tmp_path / ".data" / "library.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.touch()

        mock_result = LibraryRescrapeResult(
            rescraped_at="2026-04-17T12:00:00",
            disk_filter=None,
            category_filter=None,
            only_filter=None,
            dry_run=True,
            fixed_count=1,
            skipped_count=0,
            error_count=0,
            candidate_count=1,  # item resolved → the not-found guard must not fire
        )
        mock_conn = MagicMock()

        with (
            patch("personalscraper.maintenance.rescraper.rescrape_library", return_value=mock_result) as mock_rescrape,
            patch("personalscraper.indexer.db.open_db", return_value=mock_conn),
            patch("personalscraper.indexer.db.apply_migrations"),
            patch("personalscraper.io_utils.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-rescrape", "--item-id", "99", "--dry-run"])

        assert result.exit_code == 0, result.output
        # Verify item_id=99 was forwarded to rescrape_library.
        mock_rescrape.assert_called_once()
        _, call_kwargs = mock_rescrape.call_args
        assert call_kwargs.get("item_id") == 99, (
            f"Expected item_id=99 in rescrape_library call kwargs, got: {call_kwargs}"
        )

    def test_item_id_found_no_work_does_not_warn(self, tmp_path) -> None:
        """0.36.1 regression: a FOUND item with 0 work must NOT report not-found.

        The 0.36.0 guard fired ``not found`` whenever ``fixed+skipped+error == 0``,
        wrongly flagging a resolved item that simply had nothing to do (e.g.
        ``--item-id N --only artwork`` when artwork already exists — observed live
        on La Linea). The guard now keys on ``candidate_count``: candidate_count=1
        (resolved) + 0 work → exit 0, no warning.
        """
        from personalscraper.maintenance.rescraper import LibraryRescrapeResult

        db_file = tmp_path / ".data" / "library.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.touch()

        mock_result = LibraryRescrapeResult(
            rescraped_at="2026-04-17T12:00:00",
            disk_filter=None,
            category_filter=None,
            only_filter="artwork",
            dry_run=True,
            fixed_count=0,
            skipped_count=0,
            error_count=0,
            candidate_count=1,  # item WAS resolved; just no artwork work to do
        )

        with (
            patch("personalscraper.maintenance.rescraper.rescrape_library", return_value=mock_result),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.indexer.db.apply_migrations"),
            patch("personalscraper.io_utils.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings
            result = runner.invoke(app, ["library-rescrape", "--item-id", "1600", "--only", "artwork", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "not found" not in result.output

    def test_item_id_not_resolved_warns_exit_1(self, tmp_path) -> None:
        """A genuinely unresolved --item-id (candidate_count=0) → exit 1 + clear warning."""
        from personalscraper.maintenance.rescraper import LibraryRescrapeResult

        db_file = tmp_path / ".data" / "library.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.touch()

        mock_result = LibraryRescrapeResult(
            rescraped_at="2026-04-17T12:00:00",
            disk_filter=None,
            category_filter=None,
            only_filter=None,
            dry_run=True,
            fixed_count=0,
            skipped_count=0,
            error_count=0,
            candidate_count=0,  # item not in DB / dispatch path missing / dir gone
        )

        with (
            patch("personalscraper.maintenance.rescraper.rescrape_library", return_value=mock_result),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.indexer.db.apply_migrations"),
            patch("personalscraper.io_utils.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings
            result = runner.invoke(app, ["library-rescrape", "--item-id", "99999", "--dry-run"])

        assert result.exit_code == 1
        assert "not found" in result.output
        assert "Traceback" not in result.output

    def test_item_id_missing_db_exits_1(self) -> None:
        """--item-id when the indexer DB file does not exist → exit 1, clear message, no traceback.

        RT-3: the dead ``db_path is None`` guard was replaced with a
        ``db_path.exists()`` check.  The test config's DB path points to
        ``tmp_path/.data/library.db`` which is never created, so ``exists()``
        returns ``False`` and the command must exit 1 with an actionable message
        rather than silently creating an empty DB.
        """
        with patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]):
            result = runner.invoke(app, ["library-rescrape", "--item-id", "42", "--dry-run"])

        assert result.exit_code == 1, result.output
        assert "library-index" in result.output, f"Expected hint to run library-index in output, got: {result.output!r}"
        assert "Traceback" not in result.output, f"Expected no traceback in output, got: {result.output!r}"

    def test_item_id_with_disk_exits_1_clean_message(self, tmp_path) -> None:
        """--item-id combined with --disk → exit 1, clean mutual-exclusion message, no traceback.

        RT-4 / RT-2: ``_collect_rescrape_candidates`` raises ``ValueError`` when
        both ``item_id`` and ``disk_filter`` are provided.  The CLI must catch it
        cleanly and surface a human-readable message instead of a raw traceback.
        A real DB file is created so the ``db_path.exists()`` guard passes.
        """
        # Simulate the ValueError that the mutual-exclusion guard raises inside
        # rescrape_library / _collect_rescrape_candidates.
        mutual_exc = ValueError("item_id=42 is mutually exclusive with disk_filter and category_filter.")

        mock_conn = MagicMock()
        # Create the DB file so the exists() guard in the CLI passes.
        db_file = tmp_path / ".data" / "library.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.touch()

        with (
            patch("personalscraper.maintenance.rescraper.rescrape_library", side_effect=mutual_exc),
            patch("personalscraper.indexer.db.open_db", return_value=mock_conn),
            patch("personalscraper.indexer.db.apply_migrations"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli_helpers.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-rescrape", "--item-id", "42", "--disk", "drive_a", "--dry-run"])

        assert result.exit_code == 1, result.output
        assert "Traceback" not in result.output, f"Expected no traceback in output, got: {result.output!r}"
        # The CLI must surface something intelligible about the conflict.
        assert "mutually exclusive" in result.output.lower() or "invalid" in result.output.lower(), (
            f"Expected mutual-exclusion message in output, got: {result.output!r}"
        )


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
