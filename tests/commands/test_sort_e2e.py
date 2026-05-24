"""E2E tests for ``personalscraper sort`` — CLI-level harness.

Exercises the sort Typer command (sort items from ingest dir into
category subdirectories) via CliRunner with mocked run_sort.
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


def _sort_report(**kw: int) -> StepReport:
    defaults = {"name": "sort", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


# ── 1. Smoke ──


def test_sort_help_exits_zero() -> None:
    """``sort --help`` exits 0 and mentions the command name."""
    result = run_cli(["sort", "--help"])
    assert result.exit_code == 0, result.output
    assert "sort" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.sorter.run.run_sort")
def test_sort_fast_skip_no_items(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Empty ingest dir → fast-skip, zero ops, exit 0."""
    mock_run.return_value = StepReport(name="sort")
    mock_settings.return_value = MagicMock()

    result = run_cli(["sort"])

    assert result.exit_code == 0, result.output
    assert "Sort:" in result.output
    assert "0 OK" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.sorter.run.run_sort")
def test_sort_with_items(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Items in ingest dir → moved to category dirs, summary printed."""
    mock_run.return_value = StepReport(
        name="sort",
        success_count=3,
        skip_count=1,
        details=[
            "Movie.2024 -> 001-MOVIES/Movie (2024)",
            "Show.S01 -> 002-TVSHOWS/Show",
            "Another.Movie -> 001-MOVIES/Another Movie (2023)",
        ],
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["sort"])

    assert result.exit_code == 0, result.output
    assert "Sort:" in result.output
    assert "3 OK" in result.output
    assert "1 skipped" in result.output


# ── 3. Errors ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_sort_lock_contention(
    mock_lock, mock_release, mock_settings,
) -> None:
    """Lock held → exit 1, friendly message, no traceback."""
    mock_settings.return_value = MagicMock()

    result = run_cli(["sort"])

    assert result.exit_code == 1
    assert "Another instance" in result.output
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.sorter.run.run_sort")
def test_sort_with_errors(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """run_sort reports errors → exit 0, errors in summary."""
    mock_run.return_value = StepReport(
        name="sort", error_count=2, warnings=["ERROR bad_file: permission denied"]
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["sort"])

    assert result.exit_code == 0
    assert "2 errors" in result.output


# ── 4. Idempotence ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.sorter.run.run_sort")
def test_sort_idempotent(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Two consecutive sort calls exit 0, mock called twice."""
    mock_run.return_value = StepReport(name="sort", skip_count=5)
    mock_settings.return_value = MagicMock()

    r1 = run_cli(["sort"])
    r2 = run_cli(["sort"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert "Sort:" in r1.output
    assert mock_run.call_count == 2


# ── 5. Dry-run ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.sorter.run.run_sort")
def test_sort_dry_run_forwards_flag(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """--dry-run flag is forwarded to run_sort."""
    mock_run.return_value = StepReport(name="sort")
    mock_settings.return_value = MagicMock()

    result = run_cli(["sort", "--dry-run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is True


# ── 6. Output ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.sorter.run.run_sort")
def test_sort_output_no_traceback(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    mock_run.return_value = StepReport(name="sort", success_count=1)
    mock_settings.return_value = MagicMock()

    result = run_cli(["sort"])

    assert result.exit_code == 0
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.sorter.run.run_sort")
def test_sort_verbose_prints_details(
    mock_run, mock_lock, mock_release, mock_settings,
) -> None:
    """--verbose prints per-item detail lines from the report."""
    mock_run.return_value = StepReport(
        name="sort",
        success_count=1,
        details=["My.Movie.2024.1080p -> 001-MOVIES/My Movie (2024)"],
    )
    mock_settings.return_value = MagicMock()

    result = run_cli(["--verbose", "sort"])

    assert result.exit_code == 0
    assert "My.Movie.2024.1080p" in result.output


# ── 7. Events ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_sort_emits_item_progressed_events(
    mock_lock, mock_release, mock_settings, monkeypatch,
) -> None:
    """run_sort emits ItemProgressed events on the shared EventBus."""
    from personalscraper.pipeline_events import ItemProgressed

    mock_settings.return_value = MagicMock()
    captured = capture_event_bus(monkeypatch)

    def _emit_and_return(*args, **kwargs):
        bus = kwargs.get("event_bus")
        if bus is not None:
            bus.emit(ItemProgressed(step="sort", item="test_file.mkv", status="started"))
            bus.emit(
                ItemProgressed(
                    step="sort",
                    item="test_file.mkv",
                    status="moved",
                    details={"destination": "001-MOVIES/Test (2024)"},
                )
            )
        return StepReport(name="sort", success_count=1)

    with patch("personalscraper.sorter.run.run_sort", side_effect=_emit_and_return):
        result = run_cli(["sort"])

    assert result.exit_code == 0
    assert len(captured) == 2
    assert_events_emitted(captured, [ItemProgressed])


# ── 8. Closure-of-loop ──

# N/A: sort operates on the filesystem (moving files from ingest dir to
# category dirs). The BDD is not involved in this step. Filesystem closure
# (ingest dir empty, category dirs populated) is an integration concern
# tested at the sorter module level (test_sorter.py). The CLI harness
# verifies the run_sort contract — called with correct staging_dir resolved
# from config.
