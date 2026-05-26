"""E2E tests for ``personalscraper torrents-list`` — CLI-level harness.

Exercises the torrent listing Typer command via CliRunner with mocked
torrent client. Follows the 4-section non-critical pattern (Smoke /
Realistic / Errors / Output).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.torrent.qbittorrent import QBitAuthLockoutError
from tests.commands._e2e_helpers import (
    assert_json_schema,
    assert_no_python_traceback,
    mock_qbit_client,
    run_cli,
)


def _fake_torrent(
    *,
    name: str = "Test.Movie.2024.1080p.AMZN",
    state: str = "completed",
    progress: float = 1.0,
    size_bytes: int = 5_000_000_000,
) -> MagicMock:
    """Build a MagicMock with the :class:`TorrentItem` attribute surface."""
    t = MagicMock()
    t.name = name
    t.state = state
    t.progress = progress
    t.size_bytes = size_bytes
    return t


# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_torrents_list_help_exits_zero() -> None:
    """``torrents-list --help`` exits 0 and mentions the command name."""
    result = run_cli(["torrents-list", "--help"])
    assert result.exit_code == 0, result.output
    assert "torrents-list" in result.output


# ── 2. Realistic scenarios ──────────────────────────────────────────────────────


def test_torrents_list_three_torrents_shows_table(monkeypatch) -> None:
    """Mocked qbit returns 3 torrents → table output with all 3 names."""
    mock = mock_qbit_client(monkeypatch)
    mock.get_completed.return_value = [
        _fake_torrent(name="Movie.One.2024.1080p"),
        _fake_torrent(name="Movie.Two.2024.720p", progress=0.75, state="downloading"),
        _fake_torrent(name="Show.S01.2024.1080p", size_bytes=15_000_000_000),
    ]
    mock.get_all_hashes.return_value = {"hash1", "hash2", "hash3"}
    mock.is_seeding.side_effect = [True, False, True]

    result = run_cli(["torrents-list"])

    assert result.exit_code == 0, result.output
    assert "Movie.One.2024.1080p" in result.output
    assert "Movie.Two.2024.720p" in result.output
    assert "Show.S01.2024.1080p" in result.output
    # Summary line should mention 3 completed.
    assert "3 completed" in result.output


# ── 3. Errors ───────────────────────────────────────────────────────────────────


def test_torrents_list_client_unreachable_exits_two(monkeypatch) -> None:
    """When qbit raises QBitAuthLockoutError → exit 2, friendly message, no traceback."""
    monkeypatch.setattr(
        "personalscraper.api.torrent.qbittorrent.QBitClient",
        MagicMock(side_effect=QBitAuthLockoutError("IP banned for 10 min")),
    )

    result = run_cli(["torrents-list"])

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.output}"
    assert "Torrent client unavailable" in result.output
    assert_no_python_traceback(result)


def test_torrents_list_listing_fails_exits_two(monkeypatch) -> None:
    """When get_completed raises after successful connection → exit 2."""
    mock = mock_qbit_client(monkeypatch)
    mock.get_completed.side_effect = ConnectionError("Connection reset")

    result = run_cli(["torrents-list"])

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.output}"
    assert "Torrent listing failed" in result.output
    assert_no_python_traceback(result)


# ── 4. Output (--format json) ────────────────────────────────────────────────────


def test_torrents_list_format_json_schema(monkeypatch) -> None:
    """``--format json`` emits JSON with torrents/completed/tracked keys."""
    mock = mock_qbit_client(monkeypatch)
    mock.get_completed.return_value = [
        _fake_torrent(name="Test.Movie.2024", size_bytes=8_000_000_000),
    ]
    mock.get_all_hashes.return_value = {"hash_a"}
    mock.is_seeding.return_value = True

    result = run_cli(["--format", "json", "torrents-list"])

    assert result.exit_code == 0, result.stdout
    data = assert_json_schema(
        result,
        required_keys=["torrents", "completed", "tracked"],
        source_attr="stdout",
    )
    assert isinstance(data["torrents"], list)
    assert len(data["torrents"]) == 1
    t0 = data["torrents"][0]
    assert t0["name"] == "Test.Movie.2024"
    assert t0["state"] == "completed"
    assert isinstance(t0["progress"], float)
    assert isinstance(t0["size_gb"], float)
    assert t0["seeding"] is True
    assert data["completed"] == 1
    assert data["tracked"] == 1
