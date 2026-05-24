"""E2E tests for ``personalscraper enforce`` — CLI-level harness.

Exercises the enforce Typer command (sanitize filenames, validate
structure, check coherence) via CliRunner with mocked run_enforce.
Follows the 8-section pattern.
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


def _enforce_report(**kw: int) -> StepReport:
    defaults = {"name": "enforce", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


# ── 1. Smoke ──


def test_enforce_help_exits_zero() -> None:
    """``enforce --help`` exits 0 and mentions the command name."""
    result = run_cli(["enforce", "--help"])
    assert result.exit_code == 0, result.output
    assert "enforce" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_no_issues_noop(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """No violations found → zero fixes, exit 0."""
    mock_run.return_value = StepReport(name="enforce")
    mock_settings.return_value = MagicMock()

    result = run_cli(["enforce"])

    assert result.exit_code == 0, result.output
    assert "Enforce:" in result.output
    assert "0 fixed" in result.output
    assert "0 errors" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_with_fixes(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Sanitize + structure fixes applied → summary reflects counts."""
    mock_run.return_value = StepReport(
        name="enforce",
        success_count=4,
        skip_count=2,
        error_count=0,
        details=[
            "[sanitize:renamed] bad:file_name.mkv → bad file name.mkv",
            "[sanitize:renamed] file.with..dots.mkv → file.with.dots.mkv",
            "[structure:fix] Show.S01: missing NFO added",
            "[structure:fix] Show.S01: created Season 01/",
        ],
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["enforce"])

    assert result.exit_code == 0, result.output
    assert "Enforce:" in result.output
    assert "4 fixed" in result.output
    assert "2 OK" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_with_errors(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Sanitize errors (e.g., permission denied) → errors in summary."""
    mock_run.return_value = StepReport(
        name="enforce",
        success_count=1,
        skip_count=0,
        error_count=1,
        warnings=["unfixable.mkv: permission denied"],
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["enforce"])

    assert result.exit_code == 0, result.output
    assert "1 fixed" in result.output
    assert "1 errors" in result.output


# ── 3. Errors ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_enforce_lock_contention(
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Lock held → exit 1, friendly message, no traceback."""
    mock_settings.return_value = MagicMock()

    result = run_cli(["enforce"])

    assert result.exit_code == 1
    assert "Another instance" in result.output
    assert_no_python_traceback(result)


# ── 4. Idempotence ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_idempotent(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Two consecutive enforce calls exit 0, mock called twice."""
    mock_run.return_value = StepReport(name="enforce", skip_count=5)
    mock_settings.return_value = MagicMock()

    r1 = run_cli(["enforce"])
    r2 = run_cli(["enforce"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert "Enforce:" in r1.output
    assert mock_run.call_count == 2


# ── 5. Dry-run ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_dry_run_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--dry-run flag is forwarded to run_enforce."""
    mock_run.return_value = StepReport(name="enforce")
    mock_settings.return_value = MagicMock()

    result = run_cli(["enforce", "--dry-run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is True


# ── 6. Output ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_output_no_traceback(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    mock_run.return_value = StepReport(name="enforce", success_count=1)
    mock_settings.return_value = MagicMock()

    result = run_cli(["enforce"])

    assert result.exit_code == 0
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_summary_always_printed(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Even on errors, the summary line is always printed."""
    mock_run.return_value = StepReport(name="enforce", error_count=3)
    mock_settings.return_value = MagicMock()

    result = run_cli(["enforce"])

    assert result.exit_code == 0
    assert "Enforce:" in result.output
    assert "3 errors" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_verbose_prints_details(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--verbose prints per-item detail lines from the report."""
    mock_run.return_value = StepReport(
        name="enforce",
        success_count=2,
        details=["[sanitize:renamed] bad name.mkv → bad_name.mkv", "[structure:fix] Show: created Saison 01/"],
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["--verbose", "enforce"])

    assert result.exit_code == 0
    assert "bad_name.mkv" in result.output


# ── 7. Events ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_enforce_emits_item_progressed_events(
    mock_lock,
    mock_release,
    mock_settings,
    monkeypatch,
) -> None:
    """run_enforce emits ItemProgressed events on the shared EventBus."""
    from personalscraper.pipeline_events import ItemProgressed

    mock_settings.return_value = MagicMock()
    captured = capture_event_bus(monkeypatch)

    def _emit_and_return(*args, **kwargs):
        bus = kwargs.get("event_bus")
        if bus is not None:
            bus.emit(ItemProgressed(step="enforce", item="bad name.mkv", status="started"))
            bus.emit(
                ItemProgressed(
                    step="enforce",
                    item="bad name.mkv",
                    status="fixed",
                    details={"action": "renamed", "new_name": "bad_name.mkv"},
                )
            )
            bus.emit(ItemProgressed(step="enforce", item="Good.Show", status="started"))
            bus.emit(
                ItemProgressed(
                    step="enforce",
                    item="Good.Show",
                    status="skipped",
                    details={"component": "structure", "action": "validated"},
                )
            )
        return StepReport(name="enforce", success_count=1, skip_count=1)

    with patch("personalscraper.enforce.run.run_enforce", side_effect=_emit_and_return):
        result = run_cli(["enforce"])

    assert result.exit_code == 0
    assert len(captured) == 4
    assert_events_emitted(captured, [ItemProgressed])


# ── 8. Closure-of-loop ──

# N/A: enforce operates on the filesystem (sanitizing filenames, fixing
# structure, checking coherence) in the staging area. Neither the BDD
# nor storage disks are involved. Filesystem closure (filenames fixed,
# structure corrected) is an integration concern tested at the enforcer
# module level (tests/enforce/). The CLI harness verifies the run_enforce
# contract — called with correct config + event_bus, returns StepReport
# with sanitize/structure/coherence-tagged details.
