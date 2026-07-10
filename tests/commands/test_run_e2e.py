"""E2E tests for ``personalscraper run`` — CLI-level harness.

Exercises the run Typer command (full pipeline orchestrator) via
CliRunner with mocked Pipeline.run. Follows the 8-section pattern
plus 2 run-specific sections (SIGINT mid-run, step skip flags).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from personalscraper.models import PipelineReport, StepReport
from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    capture_event_bus,
    run_cli,
)
from tests.fixtures.settings_stub import make_typed_settings_stub


def _make_pipeline_report(*, step_count: int = 9, with_errors: bool = False) -> PipelineReport:
    """Build a minimal PipelineReport for the Pipeline.run stub.

    Args:
        step_count: Number of completed steps (1-9).
        with_errors: If True, the last step has error_count=1.

    Returns:
        A PipelineReport with *step_count* steps populated.
    """
    step_names = [
        "ingest",
        "sort",
        "clean",
        "scrape",
        "cleanup",
        "enforce",
        "verify",
        "trailers",
        "dispatch",
    ]
    report = PipelineReport(started_at=datetime(2026, 1, 1))
    for i, name in enumerate(step_names[:step_count]):
        err = 1 if (with_errors and i == step_count - 1) else 0
        report.add_step(name, StepReport(name=name, success_count=1, error_count=err))
    report.finished_at = datetime(2026, 1, 1) + timedelta(seconds=5)
    return report


# ═══════════════════════════════════════════════════════════════════
# Common mock decorator bundle — used by most tests.
# Order matters: patches are applied bottom-up, so parameters
# receive them in the same order (first decorator → last param).
# ═══════════════════════════════════════════════════════════════════

_RUN_MOCKS = (
    patch("personalscraper.logger.cleanup_old_logs"),
    patch(
        "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured",
        return_value=False,
    ),
    patch(
        "personalscraper.api.notify.telegram.TelegramNotifier.is_configured",
        return_value=False,
    ),
    patch("personalscraper.cli.get_settings"),
    patch("personalscraper.cli.release_lock"),
    patch("personalscraper.cli.acquire_pipeline_lock", return_value=True),
    patch("personalscraper.pipeline.Pipeline.run"),
)


def _apply_mocks(func):
    """Apply the standard mock stack bottom-up."""
    for dec in reversed(_RUN_MOCKS):
        func = dec(func)
    return func


# ── 1. Smoke ──


def test_run_help_exits_zero() -> None:
    """``run --help`` exits 0 and mentions the command name."""
    result = run_cli(["run", "--help"])
    assert result.exit_code == 0, result.output
    assert "run" in result.output.lower()


# ── 2. Realistic scenarios ──


@_apply_mocks
def test_run_all_steps_noop(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """All 9 steps complete with zero ops → exit 0, summary printed."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_count == 1
    # Verify run was called with expected kwargs.
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is False


@_apply_mocks
def test_run_with_operations(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Pipeline with real operations → exit 0, mock called once."""
    mock_run.return_value = _make_pipeline_report(step_count=9, with_errors=False)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_count == 1


@_apply_mocks
def test_run_headless(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """--headless runs without crash, exit 0."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run", "--headless"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_count == 1


# ── 3. Errors ──


@patch("personalscraper.logger.cleanup_old_logs")
@patch(
    "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured",
    return_value=False,
)
@patch(
    "personalscraper.api.notify.telegram.TelegramNotifier.is_configured",
    return_value=False,
)
@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=False)
def test_run_lock_contention(
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Lock held → exit 1, friendly message, no traceback."""
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run"])

    assert result.exit_code == 1
    assert "Another instance" in result.output
    assert_no_python_traceback(result)


@_apply_mocks
def test_run_errors_in_report_exit_nonzero(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Pipeline reports errors → exit code 1."""
    mock_run.return_value = _make_pipeline_report(step_count=9, with_errors=True)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run"])

    assert result.exit_code == 1, result.output
    assert mock_run.call_count == 1


# ── 4. Idempotence ──


@_apply_mocks
def test_run_idempotent(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Two consecutive run calls exit 0, mock called twice."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    r1 = run_cli(["run"])
    r2 = run_cli(["run"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert mock_run.call_count == 2


# ── 5. Dry-run ──


@_apply_mocks
def test_run_dry_run_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """--dry-run flag is forwarded to Pipeline.run."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run", "--dry-run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is True


@_apply_mocks
def test_run_interactive_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """--interactive flag is forwarded to Pipeline.run."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run", "--interactive"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["interactive"] is True


# ── 6. Output ──


@_apply_mocks
def test_run_output_no_traceback(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Output is structured, never a raw Python traceback."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run"])

    assert result.exit_code == 0
    assert_no_python_traceback(result)


@_apply_mocks
def test_run_error_exit_nonzero_on_bad_report(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Pipeline report with errors → exit non-zero."""
    mock_run.return_value = _make_pipeline_report(step_count=9, with_errors=True)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run"])

    assert result.exit_code != 0


# ── 7. Events ──


@patch("personalscraper.logger.cleanup_old_logs")
@patch(
    "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured",
    return_value=False,
)
@patch(
    "personalscraper.api.notify.telegram.TelegramNotifier.is_configured",
    return_value=False,
)
@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
def test_run_emits_pipeline_lifecycle_events(
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
    monkeypatch,
) -> None:
    """Pipeline.run mock emits StepStarted/StepCompleted lifecycle events."""
    from personalscraper.pipeline import Pipeline
    from personalscraper.pipeline_events import (
        StepCompleted,
        StepStarted,
    )

    mock_settings.return_value = make_typed_settings_stub()
    captured = capture_event_bus(monkeypatch)

    # Use monkeypatch.setattr on the CLASS with a real function so Python's
    # descriptor protocol binds `self` correctly.  MagicMock-based patches
    # don't implement ``__get__``, so ``pipeline.run(dry_run=False)``
    # would call the mock without the ``self`` argument.
    def _emit_and_return(self, **kwargs):
        bus = self._app.event_bus
        report = _make_pipeline_report(step_count=9)
        for name in report.steps:
            bus.emit(StepStarted(step=name))
            bus.emit(StepCompleted(step=name, report=report.steps[name], elapsed_s=0.0))
        return report

    monkeypatch.setattr(Pipeline, "run", _emit_and_return)

    result = run_cli(["run"])

    assert result.exit_code == 0, result.output
    # 9 steps × 2 events each = 18 lifecycle events. The bus may also carry a
    # ``RegistryBootValidated`` event emitted by the real ``ProviderRegistry``
    # at CLI boot (since feat/registry Phase 15 removed the autouse stub) —
    # filter by relevant event type rather than asserting on the total count.
    started = [e for e in captured if isinstance(e, StepStarted)]
    completed = [e for e in captured if isinstance(e, StepCompleted)]
    assert len(started) + len(completed) == 18, (
        f"Expected 18 lifecycle events, got {len(started) + len(completed)} (total bus captures: {len(captured)})"
    )
    assert len(started) == 9
    assert len(completed) == 9
    # Verify step order: every started step also completed
    started_names = [e.step for e in started]
    completed_names = [e.step for e in completed]
    assert started_names == completed_names
    # Verify the 9 expected step names are present
    expected_steps = [
        "ingest",
        "sort",
        "clean",
        "scrape",
        "cleanup",
        "enforce",
        "verify",
        "trailers",
        "dispatch",
    ]
    assert started_names == expected_steps


# ── 8. Closure-of-loop ──

# N/A: run is a pipeline orchestrator — it delegates to per-step runners
# which each have their own BDD/FS cycle. The orchestrator's job is to
# call each step in order, collect StepReports, and emit lifecycle events.
# BDD closure is tested at the per-module level (tests/ingest/, tests/
# dispatch/, etc.). The CLI harness verifies the Pipeline.run contract —
# called with correct flags, returns PipelineReport, lock is released.


# ── 9. SIGINT mid-run (orchestrator-specific) ──


@patch("personalscraper.logger.cleanup_old_logs")
@patch(
    "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured",
    return_value=False,
)
@patch(
    "personalscraper.api.notify.telegram.TelegramNotifier.is_configured",
    return_value=False,
)
@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
def test_run_sigint_partial_completion(
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Simulate SIGINT: Pipeline.run returns partial report with error → exit 1.

    Lock is released cleanly in the finally block. No orphan,
    friendly structured output (no Python traceback).
    """
    mock_settings.return_value = make_typed_settings_stub()
    # Only 3 of 9 steps completed, and the last one errored
    # (simulates interruption mid-sort or mid-process).
    partial = _make_pipeline_report(step_count=3, with_errors=True)

    with patch(
        "personalscraper.pipeline.Pipeline.run",
        return_value=partial,
    ):
        result = run_cli(["run"])

    assert result.exit_code == 1, result.output
    mock_release.assert_called_once()
    assert_no_python_traceback(result)


@patch("personalscraper.logger.cleanup_old_logs")
@patch(
    "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured",
    return_value=False,
)
@patch(
    "personalscraper.api.notify.telegram.TelegramNotifier.is_configured",
    return_value=False,
)
@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
def test_run_sigint_lock_released_on_exception(
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """Pipeline.run raises _PipelineInterrupted → lock released, exit != 0."""
    from personalscraper.pipeline import _PipelineInterrupted

    mock_settings.return_value = make_typed_settings_stub()

    with patch(
        "personalscraper.pipeline.Pipeline.run",
        side_effect=_PipelineInterrupted("signal_SIGINT"),
    ):
        result = run_cli(["run"])

    # Unhandled exception → CliRunner captures it, exit != 0
    assert result.exit_code != 0
    # Lock is released in the outer finally block.
    mock_release.assert_called_once()


# ── 10. Step skip flags (orchestrator-specific) ──


@_apply_mocks
def test_run_skip_trailers_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """--skip-trailers flag is forwarded to Pipeline.run."""
    mock_run.return_value = _make_pipeline_report(step_count=8)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run", "--skip-trailers"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["skip_trailers"] is True


@_apply_mocks
def test_run_continue_on_trailer_error_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """--continue-on-trailer-error flag is forwarded to Pipeline.run."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["run", "--continue-on-trailer-error"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["continue_on_trailer_error"] is True


def test_run_no_skip_ingest_flag() -> None:
    """``run --help`` does NOT mention --skip-ingest (only --skip-trailers exists)."""
    result = run_cli(["run", "--help"])
    assert result.exit_code == 0
    assert "--skip-trailers" in result.output
    assert "--skip-ingest" not in result.output
    assert "--skip-sort" not in result.output


@_apply_mocks
def test_run_verbose_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    mock_tg_configured,
    mock_hc_configured,
    mock_cleanup,
) -> None:
    """--verbose flag is forwarded to Pipeline.run."""
    mock_run.return_value = _make_pipeline_report(step_count=9)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["--verbose", "run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["verbose"] is True
