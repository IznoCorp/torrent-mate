"""E2E tests for ``personalscraper trailers scan`` — CLI-level harness.

Exercises the trailers scan Typer command (read-only dry-run listing of
media missing trailers) via CliRunner with mocked Scanner. Follows the
4-section non-critical pattern (Smoke / Realistic / Errors / Output).

Note (plan drift): the plan §9.6 references a nonexistent ``trailers list``
command.  The correct read-only trailers command is ``trailers scan``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.commands._e2e_helpers import assert_no_python_traceback, run_cli


def _fake_scan_item(
    *,
    path: Path | None = None,
    title: str = "Test Movie (2024)",
    media_type: str = "movie",
    year: int = 2024,
    tmdb_id: str = "123",
    season_number: int | None = None,
) -> MagicMock:
    """Build a MagicMock with the :class:`ScanItem` attribute surface."""
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


# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_trailers_scan_help_exits_zero() -> None:
    """``trailers scan --help`` exits 0 and mentions the command name."""
    result = run_cli(["trailers", "scan", "--help"])
    assert result.exit_code == 0, result.output
    assert "scan" in result.output.lower()


# ── 2. Realistic scenarios ──────────────────────────────────────────────────────


@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_scan_two_items_shows_table(mock_scanner_cls: MagicMock) -> None:
    """Mocked Scanner returns 2 ScanItems → table output with both titles."""
    mock_scanner_cls.return_value.scan_staging.return_value = [
        _fake_scan_item(title="Inception (2010)", media_type="movie"),
        _fake_scan_item(title="Breaking Bad (2008)", media_type="tv", season_number=None),
    ]

    result = run_cli(["trailers", "scan"])

    assert result.exit_code == 0, result.output
    assert "Media missing trailers" in result.output
    assert "Inception (2010)" in result.output
    assert "Breaking Bad (2008)" in result.output


@patch("personalscraper.trailers.cli.Scanner")
def test_trailers_scan_no_items_prints_green(mock_scanner_cls: MagicMock) -> None:
    """When no items missing trailers → green message, exit 0."""
    mock_scanner_cls.return_value.scan_staging.return_value = []

    result = run_cli(["trailers", "scan"])

    assert result.exit_code == 0, result.output
    assert "No media without trailers found" in result.output


# ── 3. Errors ───────────────────────────────────────────────────────────────────


def test_trailers_scan_invalid_level_exits_two() -> None:
    """``trailers scan --level invalid`` exits 2 with friendly error."""
    result = run_cli(["trailers", "scan", "--level", "invalid"])

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.output}"
    assert "invalid" in result.output.lower()
    assert_no_python_traceback(result)


# ── 4. Output (--format json) ────────────────────────────────────────────────────
# N/A — ``trailers scan`` does not support ``--format json`` (uses Rich console
# directly).  Other trailers commands (download, purge) also lack JSON output.
