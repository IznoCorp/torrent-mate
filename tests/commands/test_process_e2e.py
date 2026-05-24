"""E2E tests for ``personalscraper process`` — CLI-level harness.

Exercises the process Typer command (reclean + dedup + scrape + cleanup)
via CliRunner with mocked sub-steps. Follows the 8-section pattern.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.models import StepReport
from tests.commands._e2e_helpers import (
    assert_events_emitted,
    assert_no_python_traceback,
    capture_event_bus,
    run_cli,
)


def _clean_report(**kw: int) -> StepReport:
    defaults = {"name": "clean", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


def _scrape_report(**kw: int) -> StepReport:
    defaults = {"name": "scrape", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


def _cleanup_report(**kw: int) -> StepReport:
    defaults = {"name": "cleanup", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


# ── 1. Smoke ──


def test_process_help_exits_zero() -> None:
    """``process --help`` exits 0 and mentions the command name."""
    result = run_cli(["process", "--help"])
    assert result.exit_code == 0, result.output
    assert "process" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.process.run.run_process")
def test_process_empty_staging_noop(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Empty staging → all three sub-reports show zero operations."""
    mock_run.return_value = (
        _clean_report(),
        _scrape_report(),
        _cleanup_report(),
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["process"])

    assert result.exit_code == 0, result.output
    assert "Clean:" in result.output
    assert "Scrape:" in result.output
    assert "Cleanup:" in result.output
    assert "0 OK" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.process.run.run_process")
def test_process_with_operations(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Staging with items → each sub-step reports its counts."""
    mock_run.return_value = (
        _clean_report(success_count=1),
        _scrape_report(success_count=3, skip_count=1),
        _cleanup_report(success_count=2),
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["process"])

    assert result.exit_code == 0, result.output
    assert "1 OK" in result.output
    assert "3 OK" in result.output
    assert "2 OK" in result.output


# ── 3. Errors ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_process_lock_contention(
    mock_lock, mock_release, mock_settings,
) -> None:
    """Lock held → exit 1, friendly message, no traceback."""
    mock_settings.return_value = MagicMock()

    result = run_cli(["process"])

    assert result.exit_code == 1
    assert "Another instance" in result.output
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.process.run.run_process")
def test_process_runtime_error(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """run_process raises RuntimeError → exit 1, friendly message."""
    mock_run.side_effect = RuntimeError("disk full")
    mock_settings.return_value = MagicMock()

    result = run_cli(["process"])

    assert result.exit_code == 1
    assert "Process failed" in result.output
    assert_no_python_traceback(result)


# ── 4. Idempotence ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.process.run.run_process")
def test_process_idempotent(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Two consecutive process calls exit 0, mock called twice."""
    mock_run.return_value = (
        _clean_report(skip_count=5),
        _scrape_report(skip_count=5),
        _cleanup_report(skip_count=5),
    )
    mock_settings.return_value = MagicMock()

    r1 = run_cli(["process"])
    r2 = run_cli(["process"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    # Both calls should produce summary lines for all 3 sub-steps.
    assert "Clean:" in r1.output
    assert "Clean:" in r2.output
    assert mock_run.call_count == 2


# ── 5. Dry-run ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.process.run.run_process")
def test_process_dry_run_forwards_flag(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """--dry-run flag is forwarded to run_process."""
    mock_run.return_value = (_clean_report(), _scrape_report(), _cleanup_report())
    mock_settings.return_value = MagicMock()

    result = run_cli(["process", "--dry-run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is True


# ── 6. Output ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.process.run.run_process")
def test_process_output_no_traceback(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    mock_run.return_value = (_clean_report(), _scrape_report(), _cleanup_report())
    mock_settings.return_value = MagicMock()

    result = run_cli(["process"])

    assert result.exit_code == 0
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.process.run.run_process")
def test_process_error_exit_code_nonzero(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """run_process raises → exit code non-zero."""
    mock_run.side_effect = RuntimeError("boom")
    mock_settings.return_value = MagicMock()

    result = run_cli(["process"])

    assert result.exit_code != 0


# ── 7. Events ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_process_emits_item_progressed_events(
    mock_lock, mock_release, mock_settings, monkeypatch,
) -> None:
    """run_process emits ItemProgressed events on the shared EventBus."""
    from personalscraper.pipeline_events import ItemProgressed

    mock_settings.return_value = MagicMock()
    captured = capture_event_bus(monkeypatch)

    def _emit_and_return(*args, **kwargs):
        bus = kwargs.get("event_bus")
        if bus is not None:
            bus.emit(ItemProgressed(step="clean", item="movies", status="started"))
            bus.emit(ItemProgressed(step="clean", item="movies", status="skipped"))
            bus.emit(ItemProgressed(step="cleanup", item="movies", status="skipped"))
        return (_clean_report(), _scrape_report(), _cleanup_report())

    with patch("personalscraper.process.run.run_process", side_effect=_emit_and_return):
        result = run_cli(["process"])

    assert result.exit_code == 0
    assert len(captured) == 3
    assert_events_emitted(captured, [ItemProgressed])


# ── 8. Closure-of-loop ──

# N/A: process is a pass-through orchestrator (calls clean → scrape → cleanup).
# There is no BDD cycle: clean/cleanup operate on the filesystem only, and
# scrape's BDD writes are tested at the scraper module level. The CLI harness
# verifies the orchestrator contract (run_process called with correct args,
# three StepReports printed).
