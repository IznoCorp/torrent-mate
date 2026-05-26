"""Regression tests for ``personalscraper library-scan`` CLI command (DEV #16).

Verifies:
- ``library-scan --help`` exits 0 (smoke test).
- ``library-scan`` invokes ``scan_library()`` (spy).
- ``library-scan --dry-run`` is a pure count pass — no DB writes.
- ``library-scan --disk <name>`` filters to the requested disk only.
- Unknown ``--disk`` value exits non-zero with a clear error.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

# ── fixtures ─────────────────────────────────────────────────────────────────

_LOCK_PATH = "personalscraper.cli.acquire_lock"
_RELEASE_PATH = "personalscraper.cli.release_lock"
_OPEN_DB_PATH = "personalscraper.indexer.db.open_db"
_APPLY_MIGRATIONS_PATH = "personalscraper.indexer.db.apply_migrations"
_SCAN_LIBRARY_PATH = "personalscraper.library.scanner.scan_library"


def _make_conn_mock() -> MagicMock:
    """Return a minimal sqlite3.Connection stub.

    Returns:
        MagicMock that satisfies the open_db / apply_migrations contract.
    """
    mock = MagicMock()
    mock.execute.return_value.fetchone.return_value = [0]
    mock.execute.return_value.fetchall.return_value = []
    return mock


# ── smoke test ────────────────────────────────────────────────────────────────


class TestLibraryScanHelp:
    """``library-scan --help`` must exit 0 and surface expected flags."""

    def test_help_exits_zero(self) -> None:
        """``library-scan --help`` exits 0."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert result.exit_code == 0, result.output

    def test_help_contains_disk_flag(self) -> None:
        """``--disk`` is documented in the help text."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert "--disk" in result.output

    def test_help_contains_dry_run_flag(self) -> None:
        """``--dry-run`` is documented in the help text."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert "--dry-run" in result.output


# ── scan_library() spy ────────────────────────────────────────────────────────


class TestLibraryScanInvokesScanLibrary:
    """``library-scan`` (live) calls ``scan_library()`` exactly once."""

    def test_invokes_scan_library(self, test_config) -> None:
        """``scan_library`` is called with cfg + conn + event_bus on a live run."""
        conn_mock = _make_conn_mock()
        scan_calls: list[dict] = []

        def _spy_scan(cfg, conn, *, event_bus):  # type: ignore[no-untyped-def]
            scan_calls.append({"cfg": cfg, "conn": conn, "event_bus": event_bus})

        with (
            patch(_LOCK_PATH, return_value=True),
            patch(_RELEASE_PATH),
            patch(_OPEN_DB_PATH, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS_PATH),
            patch(_SCAN_LIBRARY_PATH, side_effect=_spy_scan),
            patch("personalscraper.cli.get_settings"),
        ):
            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0, result.output
        assert len(scan_calls) == 1, f"expected 1 call to scan_library, got {len(scan_calls)}"
        # conn must be the object returned by open_db
        assert scan_calls[0]["conn"] is conn_mock
        # event_bus must be set (not None)
        assert scan_calls[0]["event_bus"] is not None

    def test_conn_commit_called_after_scan(self, test_config) -> None:
        """``conn.commit()`` is called after a successful ``scan_library`` call."""
        conn_mock = _make_conn_mock()

        with (
            patch(_LOCK_PATH, return_value=True),
            patch(_RELEASE_PATH),
            patch(_OPEN_DB_PATH, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS_PATH),
            patch(_SCAN_LIBRARY_PATH),
            patch("personalscraper.cli.get_settings"),
        ):
            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0, result.output
        conn_mock.commit.assert_called_once()

    def test_conn_close_called_on_success(self, test_config) -> None:
        """``conn.close()`` is called in the finally block even on success."""
        conn_mock = _make_conn_mock()

        with (
            patch(_LOCK_PATH, return_value=True),
            patch(_RELEASE_PATH),
            patch(_OPEN_DB_PATH, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS_PATH),
            patch(_SCAN_LIBRARY_PATH),
            patch("personalscraper.cli.get_settings"),
        ):
            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0, result.output
        conn_mock.close.assert_called_once()

    def test_lock_released_on_success(self, test_config) -> None:
        """``release_lock`` is always called after a live scan (finally guard)."""
        conn_mock = _make_conn_mock()

        with (
            patch(_LOCK_PATH, return_value=True),
            patch(_RELEASE_PATH) as mock_release,
            patch(_OPEN_DB_PATH, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS_PATH),
            patch(_SCAN_LIBRARY_PATH),
            patch("personalscraper.cli.get_settings"),
        ):
            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0, result.output
        mock_release.assert_called_once()


# ── --dry-run ─────────────────────────────────────────────────────────────────


class TestLibraryScanDryRun:
    """``library-scan --dry-run`` counts dirs without writing to DB."""

    def test_dry_run_does_not_call_scan_library(self, test_config, tmp_path) -> None:
        """``--dry-run`` must NOT invoke ``scan_library``."""
        with (
            patch(_SCAN_LIBRARY_PATH) as mock_scan,
            patch(_LOCK_PATH, return_value=True),
            patch(_RELEASE_PATH),
        ):
            result = runner.invoke(app, ["library-scan", "--dry-run"])

        assert result.exit_code == 0, result.output
        mock_scan.assert_not_called()

    def test_dry_run_does_not_open_db(self, test_config) -> None:
        """``--dry-run`` must NOT open the indexer DB."""
        with (
            patch(_OPEN_DB_PATH) as mock_open_db,
            patch(_LOCK_PATH, return_value=True),
            patch(_RELEASE_PATH),
        ):
            result = runner.invoke(app, ["library-scan", "--dry-run"])

        assert result.exit_code == 0, result.output
        mock_open_db.assert_not_called()

    def test_dry_run_outputs_json(self, test_config) -> None:
        """``--dry-run`` prints a JSON object with ``dry_run: true``."""
        result = runner.invoke(app, ["library-scan", "--dry-run"])
        assert result.exit_code == 0, result.output
        # Strip Rich markup from output before parsing JSON
        raw = result.output.strip()
        # Find the JSON line (starts with '{')
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None, f"No JSON in output: {raw!r}"
        data = json.loads(json_line)
        assert data["dry_run"] is True

    def test_dry_run_counts_dirs(self, test_config, tmp_path) -> None:
        """``--dry-run`` counts media directories found on mounted disks."""
        # Create fake category dirs with media directories inside drive_a
        drive_a = tmp_path / "drive_a"
        cat_movies = drive_a / "cat_movies"
        cat_movies.mkdir(parents=True)
        (cat_movies / "Movie A (2020)").mkdir()
        (cat_movies / "Movie B (2021)").mkdir()
        (cat_movies / ".hidden").mkdir()  # dot-prefix dirs must NOT be counted

        result = runner.invoke(app, ["library-scan", "--dry-run"])
        assert result.exit_code == 0, result.output

        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None
        data = json.loads(json_line)
        # At least 2 non-hidden dirs counted (drive_b and drive_c are unmounted → skipped)
        assert data["media_dirs_to_scan"] >= 2

    def test_dry_run_skips_unmounted_disks(self, test_config, tmp_path) -> None:
        """``--dry-run`` silently skips disks whose paths do not exist."""
        # drive_a, drive_b, drive_c are under tmp_path but not created → not mounted
        result = runner.invoke(app, ["library-scan", "--dry-run"])
        assert result.exit_code == 0, result.output

        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None
        data = json.loads(json_line)
        assert data["media_dirs_to_scan"] == 0


# ── --disk filter ─────────────────────────────────────────────────────────────


class TestLibraryScanDiskFilter:
    """``library-scan --disk <name>`` restricts the scan to one disk."""

    def test_disk_filter_restricts_to_single_disk(self, test_config) -> None:
        """When ``--disk drive_a`` is passed, only drive_a is scanned."""
        conn_mock = _make_conn_mock()
        scan_calls: list[dict] = []

        def _spy_scan(cfg, conn, *, event_bus):  # type: ignore[no-untyped-def]
            scan_calls.append({"cfg": cfg})

        with (
            patch(_LOCK_PATH, return_value=True),
            patch(_RELEASE_PATH),
            patch(_OPEN_DB_PATH, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS_PATH),
            patch(_SCAN_LIBRARY_PATH, side_effect=_spy_scan),
            patch("personalscraper.cli.get_settings"),
        ):
            result = runner.invoke(app, ["library-scan", "--disk", "drive_a"])

        assert result.exit_code == 0, result.output
        assert len(scan_calls) == 1
        cfg_used = scan_calls[0]["cfg"]
        disk_ids = [d.id for d in cfg_used.disks]
        assert disk_ids == ["drive_a"], f"Expected only drive_a, got {disk_ids}"

    def test_disk_filter_dry_run(self, test_config, tmp_path) -> None:
        """``--disk drive_a --dry-run`` reports disk_filter in JSON output."""
        result = runner.invoke(app, ["library-scan", "--disk", "drive_a", "--dry-run"])
        assert result.exit_code == 0, result.output

        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None
        data = json.loads(json_line)
        assert data["disk_filter"] == "drive_a"

    def test_unknown_disk_exits_nonzero(self, test_config) -> None:
        """``--disk unknown_disk`` exits non-zero with an error message."""
        result = runner.invoke(app, ["library-scan", "--disk", "unknown_disk"])
        assert result.exit_code != 0
        assert (
            "unknown_disk" in (result.output + (result.stderr or "")).lower()
            or "unknown" in (result.output + (result.stderr or "")).lower()
        )

    def test_unknown_disk_dry_run_exits_nonzero(self, test_config) -> None:
        """``--disk unknown_disk --dry-run`` also exits non-zero."""
        result = runner.invoke(app, ["library-scan", "--disk", "unknown_disk", "--dry-run"])
        assert result.exit_code != 0
