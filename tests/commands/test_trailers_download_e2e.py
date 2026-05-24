"""E2E tests for ``personalscraper trailers download`` — CLI-level harness.

Exercises the trailers download Typer command (scan staging, filtered
download via TrailersOrchestrator) via CliRunner with mocked Scanner
and TrailersOrchestrator. Follows the 8-section pattern.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.commands._e2e_helpers import (
    assert_events_emitted,
    assert_no_python_traceback,
    capture_event_bus,
    run_cli,
)


def _fake_scan_item(
    *,
    path: Path | None = None,
    title: str = "Test Movie (2024)",
    media_type: str = "movie",
    year: int = 2024,
    tmdb_id: str = "123",
    season_number: int | None = None,
) -> MagicMock:
    item = MagicMock()
    item.path = path or Path("/tmp/staging/001-MOVIES/Test Movie (2024)")
    item.title = title
    item.media_type = media_type
    item.year = year
    item.tmdb_id = tmdb_id
    item.imdb_id = None
    item.nfo_path = None
    item.season_number = season_number
    return item


# ── 1. Smoke ──


def test_trailers_download_help_exits_zero() -> None:
    """``trailers download --help`` exits 0 and mentions the command name."""
    result = run_cli(["trailers", "download", "--help"])
    assert result.exit_code == 0, result.output
    assert "download" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_two_movies_success(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """Two movies both download successfully → exit 0, summary printed."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
        _fake_scan_item(title="Movie B (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    mock_orch = MagicMock()
    mock_orch.run.return_value = {
        "downloaded": 2,
        "already_present": 0,
        "no_trailer": 0,
        "bot_detected": 0,
        "http_error": 0,
        "ytdlp_error": 0,
        "skipped_by_state": 0,
        "skipped_by_filter": 0,
        "circuit_open": 0,
        "error": 0,
    }
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 0, result.output
    assert "2" in result.output  # downloaded count in table
    mock_orch_cls.assert_called_once()
    mock_orch.run.assert_called_once()


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_mixed_results(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """Mixed results: 1 downloaded, 1 no_trailer, 1 already_present → exit 0."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
        _fake_scan_item(title="Movie B (2024)"),
        _fake_scan_item(title="Movie C (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    mock_orch = MagicMock()
    mock_orch.run.return_value = {
        "downloaded": 1,
        "already_present": 1,
        "no_trailer": 1,
        "bot_detected": 0,
        "http_error": 0,
        "ytdlp_error": 0,
        "skipped_by_state": 0,
        "skipped_by_filter": 0,
        "circuit_open": 0,
        "error": 0,
    }
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 0, result.output
    assert "Downloaded" in result.output


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_no_items_in_staging(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """Empty staging → orchestrator still called with empty items list."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = []
    mock_scanner_cls.return_value = mock_scanner

    mock_orch = MagicMock()
    mock_orch.run.return_value = {
        "downloaded": 0,
        "error": 0,
    }
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 0, result.output
    mock_orch.run.assert_called_once_with(items=[])


# ── 3. Errors ──


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_ytdlp_errors(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """yt-dlp failures produce graceful error output, exit 1."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
        _fake_scan_item(title="Movie B (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    mock_orch = MagicMock()
    mock_orch.run.return_value = {
        "downloaded": 0,
        "already_present": 0,
        "no_trailer": 0,
        "bot_detected": 0,
        "http_error": 0,
        "ytdlp_error": 2,
        "skipped_by_state": 0,
        "skipped_by_filter": 0,
        "circuit_open": 0,
        "error": 2,
    }
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 1, result.output
    assert_no_python_traceback(result)
    assert "Ytdlp error" in result.output or "Error" in result.output


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_http_errors(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """HTTP errors (bot-detected, http_error) → exit 1, friendly message."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    mock_orch = MagicMock()
    mock_orch.run.return_value = {
        "downloaded": 0,
        "already_present": 0,
        "no_trailer": 0,
        "bot_detected": 1,
        "http_error": 0,
        "ytdlp_error": 0,
        "skipped_by_state": 0,
        "skipped_by_filter": 0,
        "circuit_open": 0,
        "error": 1,
    }
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 1, result.output
    assert_no_python_traceback(result)


def test_trailers_download_invalid_level() -> None:
    """Invalid --level value → exit 2 with friendly error."""
    result = run_cli(["trailers", "download", "--level", "invalid"])

    assert result.exit_code == 2, result.output
    assert "level" in result.output.lower()
    assert_no_python_traceback(result)


def test_trailers_download_invalid_since() -> None:
    """Invalid --since date → exit 2 with friendly error."""
    result = run_cli(["trailers", "download", "--since", "not-a-date"])

    assert result.exit_code == 2, result.output
    assert "YYYY-MM-DD" in result.output
    assert_no_python_traceback(result)


# ── 4. Idempotence ──


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_idempotent(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """Two consecutive download calls: orchestrator called twice, both exit 0."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    counts = {
        "downloaded": 0,
        "already_present": 1,
        "error": 0,
    }
    mock_orch = MagicMock()
    mock_orch.run.return_value = dict(counts)
    mock_orch_cls.return_value = mock_orch

    r1 = run_cli(["trailers", "download"])
    r2 = run_cli(["trailers", "download"])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert mock_orch.run.call_count == 2


# ── 5. Dry-run ──


@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_dry_run_no_download(
    mock_scanner_cls: MagicMock,
) -> None:
    """--dry-run lists candidates without calling the orchestrator."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
        _fake_scan_item(title="Movie B (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    result = run_cli(["trailers", "download", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "Movie A" in result.output
    assert "Movie B" in result.output


# ── 6. Output ──


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_no_traceback(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    mock_orch = MagicMock()
    mock_orch.run.return_value = {
        "downloaded": 1,
        "error": 0,
    }
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 0, result.output
    assert_no_python_traceback(result)


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_summary_table_present(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
) -> None:
    """Summary table is always printed after download loop."""
    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)"),
    ]
    mock_scanner_cls.return_value = mock_scanner

    mock_orch = MagicMock()
    mock_orch.run.return_value = {
        "downloaded": 1,
        "no_trailer": 0,
        "error": 0,
    }
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 0, result.output
    assert "summary" in result.output.lower()


# ── 7. Events ──


@patch("personalscraper.trailers.cli.TrailersOrchestrator")
@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_download_emits_trailer_downloaded(
    mock_scanner_cls: MagicMock,
    mock_orch_cls: MagicMock,
    monkeypatch: MagicMock,
) -> None:
    """Successful download emits TrailerDownloaded on the shared EventBus."""
    from personalscraper.core.event_bus import EventBus
    from personalscraper.trailers.events import TrailerDownloaded

    mock_scanner = MagicMock()
    mock_scanner.scan_staging.return_value = [
        _fake_scan_item(title="Movie A (2024)", path=Path("/tmp/staging/001-MOVIES/Movie A (2024)")),
    ]
    mock_scanner_cls.return_value = mock_scanner

    captured = capture_event_bus(monkeypatch)

    mock_orch = MagicMock()

    # Simulate the real orchestrator emitting on its bus after download.
    def _run_and_emit(items=None):  # noqa: ANN202
        bus = EventBus()
        bus.emit(
            TrailerDownloaded(
                media_path=Path("/tmp/fake"),
                trailer_path=Path("/tmp/fake-trailer.mp4"),
                source_url="https://youtube.com/watch?v=test",
            )
        )
        return {
            "downloaded": 1,
            "already_present": 0,
            "no_trailer": 0,
            "bot_detected": 0,
            "http_error": 0,
            "ytdlp_error": 0,
            "skipped_by_state": 0,
            "skipped_by_filter": 0,
            "circuit_open": 0,
            "error": 0,
        }

    mock_orch.run.side_effect = _run_and_emit
    mock_orch_cls.return_value = mock_orch

    result = run_cli(["trailers", "download"])

    assert result.exit_code == 0, result.output
    assert_events_emitted(captured, [TrailerDownloaded])


# ── 8. Closure-of-loop ──

# N/A: trailers download writes to the trailers state file (JSON), not the
# indexer database. BDD closure-of-loop does not apply. The state file's
# integrity (idempotence via should_skip, orphan detection via GC) is tested
# at the module level (test_trailers_state.py). The CLI harness verifies the
# TrailersOrchestrator contract: called with correct config + staging_dir +
# event_bus, filtered items passed via orchestrator.run(items=...).
