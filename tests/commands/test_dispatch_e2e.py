"""E2E tests for ``personalscraper dispatch`` — CLI-level harness.

Exercises the dispatch Typer command (move verified media to storage
disks) via CliRunner with mocked run_dispatch.
Follows the 8-section pattern.
"""

from __future__ import annotations

from unittest.mock import patch

from personalscraper.models import StepReport
from tests.commands._e2e_helpers import (
    assert_events_emitted,
    assert_no_python_traceback,
    capture_event_bus,
    run_cli,
)
from tests.fixtures.settings_stub import make_typed_settings_stub


def _dispatch_report(**kw: int) -> StepReport:
    defaults = {"name": "dispatch", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


# ── 1. Smoke ──


def test_dispatch_help_exits_zero() -> None:
    """``dispatch --help`` exits 0 and mentions the command name."""
    result = run_cli(["dispatch", "--help"])
    assert result.exit_code == 0, result.output
    assert "dispatch" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_no_items_noop(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """No verified items → zero ops, exit 0."""
    mock_run.return_value = (StepReport(name="dispatch"), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch"])

    assert result.exit_code == 0, result.output
    assert "Dispatch:" in result.output
    assert "0 OK" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_mixed_results(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Some items dispatched, some skipped, some errors → summary reflects all."""
    mock_run.return_value = (
        StepReport(
            name="dispatch",
            success_count=2,
            skip_count=1,
            error_count=1,
            details=[
                "action=moved     Inception (2010) → Disk1",
                "action=merged    Show.S01 → Disk2",
                "action=skipped   Small.File.mkv: too small",
                "action=error     Bad.Item: no space",
            ],
        ),
        [],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch"])

    assert result.exit_code == 0, result.output
    assert "Dispatch:" in result.output
    assert "2 OK" in result.output
    assert "1 skipped" in result.output
    assert "1 errors" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_all_skipped(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """All items skipped (e.g., all duplicates) → zero dispatch, exit 0."""
    mock_run.return_value = (
        StepReport(name="dispatch", skip_count=3, details=["action=skipped  dup: already on disk"]),
        [],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch"])

    assert result.exit_code == 0, result.output
    assert "0 OK" in result.output
    assert "3 skipped" in result.output


# ── 3. Errors ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=False)
def test_dispatch_lock_contention(
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Lock held → exit 1, friendly message, no traceback."""
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch"])

    assert result.exit_code == 1
    assert "Another instance" in result.output
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_all_errors(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """run_dispatch reports all errors → exit 0, errors in summary."""
    mock_run.return_value = (
        StepReport(
            name="dispatch",
            error_count=2,
            details=["action=error    item_1: disk full", "action=error    item_2: permission denied"],
        ),
        [],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch"])

    assert result.exit_code == 0
    assert "2 errors" in result.output


# ── 4. Idempotence ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_idempotent(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Two consecutive dispatch calls exit 0, mock called twice."""
    mock_run.return_value = (StepReport(name="dispatch", skip_count=5), [])
    mock_settings.return_value = make_typed_settings_stub()

    r1 = run_cli(["dispatch"])
    r2 = run_cli(["dispatch"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert "Dispatch:" in r1.output
    assert mock_run.call_count == 2


# ── 5. Dry-run ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_dry_run_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--dry-run flag is forwarded to run_dispatch."""
    mock_run.return_value = (StepReport(name="dispatch"), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch", "--dry-run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is True


# ── 6. Output ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_output_no_traceback(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    mock_run.return_value = (StepReport(name="dispatch", success_count=1), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch"])

    assert result.exit_code == 0
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_summary_always_printed(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Even on errors, the summary line is always printed."""
    mock_run.return_value = (StepReport(name="dispatch", error_count=3), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["dispatch"])

    assert result.exit_code == 0
    assert "Dispatch:" in result.output
    assert "3 errors" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.dispatch.run.run_dispatch")
def test_dispatch_verbose_prints_details(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--verbose prints per-item detail lines from the report."""
    mock_run.return_value = (
        StepReport(
            name="dispatch",
            success_count=1,
            details=["action=moved     Inception (2010) → Disk1"],
        ),
        [],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["--verbose", "dispatch"])

    assert result.exit_code == 0
    assert "Inception" in result.output


# ── 7. Events ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_dispatch_emits_item_progressed_events(
    mock_lock,
    mock_release,
    mock_settings,
    monkeypatch,
) -> None:
    """run_dispatch emits ItemProgressed events on the shared EventBus."""
    from personalscraper.pipeline_events import ItemProgressed

    mock_settings.return_value = make_typed_settings_stub()
    captured = capture_event_bus(monkeypatch)

    def _emit_and_return(*args, **kwargs):
        bus = kwargs.get("event_bus")
        if bus is not None:
            bus.emit(ItemProgressed(step="dispatch", item="test_item", status="started"))
            bus.emit(
                ItemProgressed(
                    step="dispatch",
                    item="test_item",
                    status="moved",
                    details={"dest": "/Volumes/Disk1/001-MOVIES/Test (2024)", "disk": "Disk1"},
                )
            )
        return StepReport(name="dispatch", success_count=1), []

    with patch("personalscraper.dispatch.run.run_dispatch", side_effect=_emit_and_return):
        result = run_cli(["dispatch"])

    assert result.exit_code == 0
    # Filter by domain event type — the bus may also carry a
    # ``RegistryBootValidated`` infra event since Phase 15 removed the autouse stub.
    item_events = [e for e in captured if isinstance(e, ItemProgressed)]
    assert len(item_events) == 2
    assert_events_emitted(captured, [ItemProgressed])


# ── 8. Closure-of-loop ──

# N/A: dispatch operates on the filesystem (moving media from staging to
# storage disks) and the indexer database (outbox drain + Merkle reset).
# Filesystem closure (staging emptied, target disks populated) is an
# integration concern tested at the dispatcher module level
# (tests/dispatch/). The CLI harness verifies the run_dispatch contract
# — called with correct config + event_bus, returns StepReport with
# action-tagged details.
