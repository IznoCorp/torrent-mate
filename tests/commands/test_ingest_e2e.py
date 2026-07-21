"""E2E tests for ``personalscraper ingest`` — CLI-level harness.

Exercises the ingest Typer command (connect to qBittorrent, copy completed
torrents to staging) via CliRunner with mocked run_ingest.
Follows the 8-section pattern.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

from personalscraper.models import StepReport
from tests.commands._e2e_helpers import (
    assert_events_emitted,
    assert_no_python_traceback,
    capture_event_bus,
    run_cli,
)
from tests.fixtures.settings_stub import make_typed_settings_stub

# The migrated ``ingest`` command takes the lock + resolves settings through the
# ``cli_helpers.boundary`` decorator, whose own module namespace is the seam to
# patch (``personalscraper.cli.*`` no longer intercepts it). ``run_ingest`` is
# still read via the ``cli`` facade, so its patch target is unchanged.
_BOUNDARY_MOD = importlib.import_module("personalscraper.cli_helpers.boundary")


def _ingest_report(**kw: int) -> StepReport:
    defaults = {"name": "ingest", "success_count": 0, "skip_count": 0, "error_count": 0}
    return StepReport(**(defaults | kw))


# ── 1. Smoke ──


def test_ingest_help_exits_zero() -> None:
    """``ingest --help`` exits 0 and mentions the command name."""
    result = run_cli(["ingest", "--help"])
    assert result.exit_code == 0, result.output
    assert "ingest" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_no_torrents(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """No completed torrents → zero ops, exit 0."""
    mock_run.return_value = StepReport(name="ingest")
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest"])

    assert result.exit_code == 0, result.output
    assert "Ingest:" in result.output
    assert "0 OK" in result.output


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_two_torrents_copied(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Two completed torrents → both copied, summary printed."""
    mock_run.return_value = StepReport(
        name="ingest",
        success_count=2,
        skip_count=1,
        details=[
            "Test.Movie.2024 → copied",
            "Test.Show.S01 → copied",
        ],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest"])

    assert result.exit_code == 0, result.output
    assert "Ingest:" in result.output
    assert "2 OK" in result.output
    assert "1 skipped" in result.output


# ── 3. Errors ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=False)
def test_ingest_lock_contention(
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Lock held → exit 1, friendly message, no traceback."""
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest"])

    assert result.exit_code == 1
    assert "Another instance" in result.output
    assert_no_python_traceback(result)


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_qbit_unreachable(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """run_ingest returns qBittorrent unreachable error → exit 0, errors in output."""
    mock_run.return_value = StepReport(
        name="ingest",
        error_count=1,
        details=["qBittorrent unreachable: Connection refused. Fix: verify qBit is running and Web UI is enabled."],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest"])

    assert result.exit_code == 0
    assert "1 errors" in result.output


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_all_content_missing(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """All torrents have missing content → not a crash, errors in report."""
    mock_run.return_value = StepReport(
        name="ingest",
        error_count=1,
        skip_count=3,
        warnings=["torrent_A: content path missing (/fake/path/A)"],
        details=["ALL 3 torrents have missing content. Check: is the source volume mounted?"],
    )
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest"])

    assert result.exit_code == 0
    assert "3 skipped" in result.output
    assert "1 errors" in result.output


# ── 4. Idempotence ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_idempotent(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Two consecutive ingest calls exit 0, run_ingest called twice."""
    mock_run.return_value = StepReport(name="ingest", skip_count=3)
    mock_settings.return_value = make_typed_settings_stub()

    r1 = run_cli(["ingest"])
    r2 = run_cli(["ingest"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert "Ingest:" in r1.output
    assert mock_run.call_count == 2


# ── 5. Dry-run ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_dry_run_forwards_flag(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """--dry-run flag is forwarded to run_ingest."""
    mock_run.return_value = StepReport(name="ingest")
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest", "--dry-run"])

    assert result.exit_code == 0
    _, kwargs = mock_run.call_args
    assert kwargs["dry_run"] is True


# ── 6. Output ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_output_no_traceback(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    mock_run.return_value = StepReport(name="ingest", success_count=1)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest"])

    assert result.exit_code == 0
    assert_no_python_traceback(result)


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.cli_helpers.run_ingest")
def test_ingest_summary_always_printed(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
) -> None:
    """Even on errors, the summary line is always printed (finally block)."""
    mock_run.return_value = StepReport(name="ingest", error_count=5)
    mock_settings.return_value = make_typed_settings_stub()

    result = run_cli(["ingest"])

    assert result.exit_code == 0
    assert "Ingest:" in result.output
    assert "5 errors" in result.output


# ── 7. Events ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
def test_ingest_emits_item_progressed_events(
    mock_lock,
    mock_release,
    mock_settings,
    monkeypatch,
) -> None:
    """run_ingest emits ItemProgressed events on the shared EventBus."""
    from personalscraper.pipeline_events import ItemProgressed

    mock_settings.return_value = make_typed_settings_stub()
    captured = capture_event_bus(monkeypatch)

    def _emit_and_return(*args, **kwargs):
        bus = kwargs.get("event_bus")
        if bus is not None:
            bus.emit(ItemProgressed(step="ingest", item="test.torrent", status="started"))
            bus.emit(
                ItemProgressed(
                    step="ingest",
                    item="test.torrent",
                    status="copied",
                    details={"action": "copied", "dest": "/tmp/staging/097-TEMP/test.torrent"},
                )
            )
        return StepReport(name="ingest", success_count=1)

    with patch("personalscraper.cli_helpers.run_ingest", side_effect=_emit_and_return):
        result = run_cli(["ingest"])

    assert result.exit_code == 0
    # Filter by domain event type — the bus may also carry a
    # ``RegistryBootValidated`` infra event since Phase 15 removed the autouse stub.
    item_events = [e for e in captured if isinstance(e, ItemProgressed)]
    assert len(item_events) == 2
    assert_events_emitted(captured, [ItemProgressed])


# ── 8. Closure-of-loop ──

# N/A: ingest writes to ingested_torrents.json (a JSON tracker file outside
# the BDD). BDD closure-of-loop doesn't apply — ingest doesn't touch the
# indexer database. The tracker file's integrity (already-ingested torrents
# are not re-copied, orphan entries detected) is tested at the module level
# (test_ingest_tracker.py). The CLI harness verifies the run_ingest contract:
# called with correct ingest_dir / staging_dir resolved from config.
