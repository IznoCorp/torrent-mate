"""E2E tests for ``personalscraper verify`` — CLI-level harness.

Exercises the verify Typer command (check media quality gates before
dispatch) via CliRunner with mocked run_verify.
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
from tests.fixtures.settings_stub import make_typed_settings_stub


def _verify_report(**kw: int) -> StepReport:
    defaults = {"name": "verify", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


# ── 1. Smoke ──


def test_verify_help_exits_zero() -> None:
    """``verify --help`` exits 0 and mentions the command name."""
    result = run_cli(["verify", "--help"])
    assert result.exit_code == 0, result.output
    assert "verify" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_no_media_noop(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """No media folders in staging → fast-skip, zero ops, exit 0."""
    mock_run.return_value = (StepReport(name="verify"), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify"])

    assert result.exit_code == 0, result.output
    assert "Verify:" in result.output
    assert "0 OK" in result.output
    assert "0 ready for dispatch" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_some_valid_some_blocked(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Some items valid, some blocked → summary reflects both counts."""
    mock_run.return_value = (
        _verify_report(success_count=3, skip_count=2, details=["[valid] Inception...", "[blocked] Bad.Movie..."]),
        [MagicMock(), MagicMock(), MagicMock()],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify"])

    assert result.exit_code == 0, result.output
    assert "Verify:" in result.output
    assert "3 OK" in result.output
    assert "2 blocked" in result.output
    assert "3 ready for dispatch" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_all_blocked(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """All items blocked → 0 OK, all blocked, 0 dispatchable."""
    mock_run.return_value = (
        _verify_report(success_count=0, skip_count=4),
        [],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify"])

    assert result.exit_code == 0, result.output
    assert "0 OK" in result.output
    assert "4 blocked" in result.output
    assert "0 ready for dispatch" in result.output


# ── 3. Errors ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=False)
def test_verify_lock_contention(
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Lock held → exit 1, friendly message, no traceback."""
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify"])

    assert result.exit_code == 1
    assert "Another instance" in result.output
    assert_no_python_traceback(result)


# ── 4. Idempotence ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_idempotent(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Two consecutive verify calls exit 0, mock called twice."""
    mock_run.return_value = (_verify_report(skip_count=5), [])
    mock_settings.return_value = make_typed_settings_stub()

    r1 = run_cli(["verify"])
    r2 = run_cli(["verify"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert "Verify:" in r1.output
    assert mock_run.call_count == 2


# ── 5. Dry-run ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_dry_run_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--dry-run flag is forwarded to run_verify."""
    mock_run.return_value = (_verify_report(), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify", "--dry-run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is True


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_movies_only_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--movies-only flag is forwarded to run_verify."""
    mock_run.return_value = (_verify_report(), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify", "--movies-only"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["movies_only"] is True


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_tvshows_only_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--tvshows-only flag is forwarded to run_verify."""
    mock_run.return_value = (_verify_report(), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify", "--tvshows-only"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["tvshows_only"] is True


# ── 6. Output ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_output_no_traceback(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    mock_run.return_value = (_verify_report(success_count=1), [MagicMock()])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify"])

    assert result.exit_code == 0
    assert_no_python_traceback(result)


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_summary_always_printed(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Even with all blocked, the summary + dispatchable count is printed."""
    mock_run.return_value = (_verify_report(success_count=0, skip_count=3), [])
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["verify"])

    assert result.exit_code == 0
    assert "Verify:" in result.output
    assert "0 OK" in result.output
    assert "3 blocked" in result.output


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_verbose_prints_details(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--verbose prints per-item detail lines from the report."""
    mock_run.return_value = (
        _verify_report(
            success_count=2,
            details=["[valid] Inception (2010) [movies]", "[fixed] The.Matrix.1999 → renamed"],
        ),
        [MagicMock(), MagicMock()],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["--verbose", "verify"])

    assert result.exit_code == 0
    assert "Inception" in result.output


# ── 7. Events ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_pipeline_lock", return_value=True)
def test_verify_emits_item_progressed_events(
    mock_lock,
    mock_release,
    mock_settings,
    monkeypatch,
) -> None:
    """run_verify emits ItemProgressed events on the shared EventBus."""
    from personalscraper.pipeline_events import ItemProgressed

    mock_settings.return_value = make_typed_settings_stub()
    captured = capture_event_bus(monkeypatch)

    def _emit_and_return(*args, **kwargs):
        bus = kwargs.get("event_bus")
        if bus is not None:
            bus.emit(ItemProgressed(step="verify", item="test_item", status="started"))
            bus.emit(
                ItemProgressed(
                    step="verify",
                    item="test_item",
                    status="ok",
                    details={"status": "valid", "category": "movies"},
                )
            )
        return StepReport(name="verify", success_count=1), []

    with patch("personalscraper.verify.run.run_verify", side_effect=_emit_and_return):
        result = run_cli(["verify"])

    assert result.exit_code == 0
    # Filter by domain event type — the bus may also carry a
    # ``RegistryBootValidated`` infra event since Phase 15 removed the autouse stub.
    item_events = [e for e in captured if isinstance(e, ItemProgressed)]
    assert len(item_events) == 2
    assert_events_emitted(captured, [ItemProgressed])


# ── 8. Closure-of-loop ──

# N/A: verify is a quality-gate step that checks NFO integrity, artwork
# presence, and naming conventions. It produces a report + dispatchable
# item list but does NOT mutate the BDD or filesystem (except for --fix
# corrections on the staging filesystem). BDD closure-of-loop is not
# applicable — the verify step's contract is "block or greenlight each
# item for dispatch," tested at the verifier module level (tests/verify/).
# The CLI harness verifies the run_verify contract: called with correct
# config + event_bus, returns StepReport + dispatchable list.
