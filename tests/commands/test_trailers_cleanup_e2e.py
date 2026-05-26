"""E2E tests for ``personalscraper trailers purge`` — CLI-level harness.

Exercises the trailers purge Typer command (orphan trailer cleanup) via
CliRunner with mocked TrailerStateStore. Follows the 8-section pattern.
Note: the plan refers to this command as "trailers cleanup".
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    run_cli,
)


def _make_orphan_entry(
    media_path: str,
    trailer_path: str,
) -> MagicMock:
    """Return a MagicMock that looks like a TrailerState with orphan paths."""
    entry = MagicMock()
    entry.media_path = media_path
    entry.trailer_path = trailer_path
    return entry


def _make_healthy_entry(
    media_path: str,
    trailer_path: str,
) -> MagicMock:
    """Return a MagicMock with both paths existing (not orphan)."""
    entry = MagicMock()
    entry.media_path = media_path
    entry.trailer_path = trailer_path
    return entry


# ── 1. Smoke ──


def test_trailers_purge_help_exits_zero() -> None:
    """``trailers purge --help`` exits 0 and mentions the command name."""
    result = run_cli(["trailers", "purge", "--help"])
    assert result.exit_code == 0, result.output
    assert "purge" in result.output.lower()
    assert "orphan" in result.output.lower()


# ── 2. Realistic scenarios ──


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_deletes_orphan_trailer(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """One orphan entry with existing trailer → file deleted, summary printed."""
    trailer_file = tmp_path / "orphan-trailer.mp4"
    trailer_file.write_bytes(b"fake trailer content")

    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent-media-dir"),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge"])

    assert result.exit_code == 0, result.output
    assert "Purged 1 orphan trailer" in result.output
    assert not trailer_file.exists(), "orphan trailer file must be deleted"


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_healthy_entry_preserved(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Healthy entry (media dir exists) → trailer NOT deleted."""
    media_dir = tmp_path / "existing-media"
    media_dir.mkdir()
    trailer_file = tmp_path / "existing-trailer.mp4"
    trailer_file.write_bytes(b"fake trailer content")

    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:456": _make_healthy_entry(
            media_path=str(media_dir),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge"])

    assert result.exit_code == 0, result.output
    assert "Purged 0 orphan trailer" in result.output
    assert trailer_file.exists(), "healthy trailer file must NOT be deleted"


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_orphan_with_missing_trailer_file(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Orphan media dir but trailer file also missing → skipped (not purged)."""
    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:789": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent-media"),
            trailer_path=str(tmp_path / "already-missing-trailer.mp4"),
        ),
    }
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge"])

    assert result.exit_code == 0, result.output
    assert "Purged 0 orphan trailer" in result.output


# ── 3. Errors ──


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_state_locked_on_include_state(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """--include-state with locked store → exit 1, friendly message."""
    from personalscraper.trailers.state import TrailerStateLocked

    trailer_file = tmp_path / "orphan.mp4"
    trailer_file.write_bytes(b"fake content")

    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent"),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store.purge_orphans.side_effect = TrailerStateLocked(Path("/tmp/fake.lock"))
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge", "--include-state"])

    assert result.exit_code == 1, result.output
    assert "Another trailers process" in result.output
    assert_no_python_traceback(result)


def test_trailers_purge_invalid_level() -> None:
    """Invalid --level value → exit 2, friendly error."""
    result = run_cli(["trailers", "purge", "--level", "invalid"])

    assert result.exit_code == 2, result.output
    assert "level" in result.output.lower()
    assert_no_python_traceback(result)


def test_trailers_purge_invalid_since() -> None:
    """Invalid --since date → exit 2, friendly error."""
    result = run_cli(["trailers", "purge", "--since", "not-a-date"])

    assert result.exit_code == 2, result.output
    assert "YYYY-MM-DD" in result.output
    assert_no_python_traceback(result)


# ── 4. Idempotence ──


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_idempotent(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Second purge run finds no more orphans (already cleaned) → no-op."""
    trailer_file = tmp_path / "orphan.mp4"

    # First call: orphan present.
    trailer_file.write_bytes(b"fake content")
    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent"),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store_cls.return_value = mock_store

    r1 = run_cli(["trailers", "purge"])
    assert r1.exit_code == 0
    assert "Purged 1 orphan" in r1.output

    # Second call: trailer already deleted → no more orphans.
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent"),
            trailer_path=str(trailer_file),
        ),
    }

    r2 = run_cli(["trailers", "purge"])
    assert r2.exit_code == 0
    assert "Purged 0 orphan" in r2.output


# ── 5. Dry-run ──


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_dry_run_does_not_delete(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """--dry-run shows orphans without deleting files."""
    trailer_file = tmp_path / "orphan-dry.mp4"
    trailer_file.write_bytes(b"fake trailer content")

    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent"),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "1 orphan" in result.output
    assert trailer_file.exists(), "dry-run must NOT delete files"


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_dry_run_include_state(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """--dry-run --include-state shows state purge without executing."""
    trailer_file = tmp_path / "orphan-state.mp4"
    trailer_file.write_bytes(b"fake content")

    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent"),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge", "--dry-run", "--include-state"])

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "orphan state" in result.output.lower()
    assert trailer_file.exists(), "dry-run must NOT delete files"


# ── 6. Output ──


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_no_traceback(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    trailer_file = tmp_path / "orphan-output.mp4"
    trailer_file.write_bytes(b"fake content")

    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent"),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge"])

    assert result.exit_code == 0, result.output
    assert_no_python_traceback(result)


@patch("personalscraper.trailers.cli.TrailerStateStore")
def test_trailers_purge_include_state_success(
    mock_store_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """--include-state successfully purges orphan state entries."""
    trailer_file = tmp_path / "orphan-state-ok.mp4"
    trailer_file.write_bytes(b"fake content")

    mock_store = MagicMock()
    mock_store.all_entries.return_value = {
        "movie:tmdb:123": _make_orphan_entry(
            media_path=str(tmp_path / "nonexistent"),
            trailer_path=str(trailer_file),
        ),
    }
    mock_store.purge_orphans.return_value = 3
    mock_store_cls.return_value = mock_store

    result = run_cli(["trailers", "purge", "--include-state"])

    assert result.exit_code == 0, result.output
    assert "Purged 1 orphan trailer" in result.output
    assert "Purged 3 orphan state" in result.output


# ── 7. Events ──

# N/A: trailers purge is a read-then-delete FS operation that does not emit
# pipeline events. The purge command operates on the trailers state file
# (JSON), not on the indexer database or the pipeline EventBus. Events would
# only be relevant if purge wrote outbox entries for the indexer, which it
# does not — it only calls state_store.purge_orphans() when --include-state
# is set, which is a self-contained state-file mutation.

# ── 8. Closure-of-loop ──

# N/A: trailers purge is purely filesystem + state-file cleanup. It does not
# interact with the indexer database (no BDD cycle). The state file's integrity
# after purge (orphan entries removed, healthy entries preserved) is verified
# at the module level (test_trailers_state.py).
