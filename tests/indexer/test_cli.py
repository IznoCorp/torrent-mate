"""Tests for personalscraper.indexer.cli — library_index_command and library_status_command.

Covers:
- ``library_index_command`` quick mode exits 0 (scanner.scan mocked).
- ``library_index_command`` with unknown --disk exits 2 with a helpful stderr message.
- ``library_index_command`` dry-run writes no media_file rows to a real in-memory DB.
- ``library_status_command`` regression check — still exits 0 with "no scans yet" on empty DB.

Test strategy:
    All four tests call the CLI via :class:`typer.testing.CliRunner` (which captures
    stdout/stderr without forking) so they exercise the full Typer wiring while
    remaining fast and hermetic.

    Because ``library_index_command`` and ``library_status_command`` perform a lazy
    ``load_config(resolve_config_path(...))`` call, we patch both loader functions to
    return a synthetic Config with a ``tmp_path``-based ``db_path``.

    ``scanner.scan`` is further patched in mode-specific tests to avoid any filesystem
    walk and to control the returned :class:`~personalscraper.indexer.scanner.ScanRunResult`.

Note on the writer lock:
    ``indexer_lock`` uses a :class:`filelock.FileLock` backed by a real file path
    derived from ``db_path``.  The ``tmp_path`` fixture provides a writable directory
    so lock files are created and cleaned up automatically.

Note on FK constraints:
    ``media_file.release_id`` has a NOT NULL FK to ``media_release``.  The scanner
    uses ``release_id=0`` as a deferred sentinel.  Tests that touch the real DB
    therefore disable FK enforcement via ``PRAGMA foreign_keys=OFF``.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner import ScanRunResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# Patch targets for the config loader used by library_index_command / library_status_command.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"

# Patch target for scanner.scan called from library_index_command.
# scan is imported lazily inside library_index_command so we patch the
# canonical location (the scanner module) rather than the importer module.
_PATCH_SCAN = "personalscraper.indexer.scanner.scan"

# mix_stderr=False so result.output contains only stdout and result.stderr
# is available without raising ValueError.
runner = CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> Any:
    """Build a minimal Config whose ``indexer.db_path`` lives under *tmp_path*.

    The Config is constructed by patching ``IndexerConfig.db_path`` so that it
    points to a temporary file and bypasses the ``/Volumes/`` validator.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        A real :class:`~personalscraper.conf.models.Config` instance with a
        writable ``indexer.db_path`` under *tmp_path*.
    """
    from personalscraper.conf.models import IndexerConfig

    # Cheap approach: patch via a MagicMock that delegates attribute access to a
    # real IndexerConfig.  This avoids instantiating the full Config hierarchy
    # (which requires all 11 category IDs, disk configs, etc.) in every test.
    mock_cfg = MagicMock()
    ic = IndexerConfig(db_path=tmp_path / "library.db")
    mock_cfg.indexer = ic
    return mock_cfg


def _make_conn(db_path: Path) -> sqlite3.Connection:
    """Open a real file-based SQLite DB at *db_path* with FK checks OFF.

    Args:
        db_path: Path to the SQLite file to create/open.

    Returns:
        Open :class:`sqlite3.Connection` with the full migration chain applied.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=OFF")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _fake_scan_result(scan_run_id: int = 1, files: int = 5, dirs: int = 2) -> ScanRunResult:
    """Return a synthetic :class:`ScanRunResult` for scan mock return values.

    Args:
        scan_run_id: PK to embed in the result.
        files: Number of files_visited to report.
        dirs: Number of dirs_visited to report.

    Returns:
        :class:`ScanRunResult` with ``status='ok'``.
    """
    return ScanRunResult(
        scan_run_id=scan_run_id,
        files_visited=files,
        dirs_visited=dirs,
        status="ok",
        disks_skipped=0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLibraryIndexQuickMode:
    """library-index --mode quick exits 0 and emits JSON."""

    def test_quick_mode_exits_zero(self, tmp_path: Path) -> None:
        """Invoking library-index --mode quick exits 0 when scan completes.

        The scanner.scan function is mocked so no real filesystem walk occurs.
        The JSON summary printed to stdout is validated for required keys.
        """
        cfg = _make_config(tmp_path)
        fake_result = _fake_scan_result(scan_run_id=42, files=10, dirs=3)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result),
        ):
            result = runner.invoke(app, ["library-index", "--mode", "quick"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        # Stdout must contain valid JSON with the expected keys.
        summary = json.loads(result.output.strip())
        assert summary["mode"] == "quick"
        assert summary["files_walked"] == 10
        assert summary["status"] == "ok"


class TestLibraryIndexUnknownDisk:
    """library-index --disk UnknownDisk exits 2 with a helpful stderr message."""

    def test_unknown_disk_exits_two(self, tmp_path: Path) -> None:
        """Specifying an unknown disk label must exit with code 2.

        The ``disk`` table in the fresh DB has no rows, so any --disk value
        triggers IndexerConfigError inside filter_disks.
        """
        cfg = _make_config(tmp_path)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = runner.invoke(app, ["library-index", "--mode", "full", "--disk", "UnknownDisk"])

        assert result.exit_code == 2, f"Expected 2, got {result.exit_code}. Output:\n{result.output}"
        # The error message must mention the unknown disk label (written to stderr).
        combined_output = (result.output or "") + (result.stderr or "")
        assert "UnknownDisk" in combined_output, f"Expected 'UnknownDisk' in output. Got:\n{combined_output}"


class TestLibraryIndexDryRun:
    """library-index --dry-run writes no media_file rows."""

    def test_dry_run_writes_no_media_rows(self, tmp_path: Path) -> None:
        """Dry-run mode must not commit any rows to the database.

        The mock scan function inserts a ``scan_run`` sentinel row (no FK deps)
        inside the same connection.  The dry_run savepoint must roll that row
        back so the table stays empty after the invocation.
        """
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path

        # Pre-build the DB (applies migrations) so open_db can open the file.
        conn = _make_conn(db_path)
        conn.close()

        def _scan_that_inserts(*args: Any, **kwargs: Any) -> ScanRunResult:
            """Insert a sentinel scan_run row via the live connection."""
            _conn: sqlite3.Connection = kwargs["conn"]
            now = int(time.time())
            # scan_run has no FK dependencies — safe to insert without FK=OFF.
            _conn.execute(
                "INSERT INTO scan_run (generation, mode, disk_filter, started_at, "
                "finished_at, last_path, status, stats_json) "
                "VALUES (99, 'full', NULL, ?, ?, NULL, 'ok', NULL)",
                (now, now),
            )
            return ScanRunResult(
                scan_run_id=99,
                files_visited=0,
                dirs_visited=0,
                status="ok",
            )

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, side_effect=_scan_that_inserts),
        ):
            result = runner.invoke(app, ["library-index", "--dry-run", "--mode", "full"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"

        # Open the DB independently and assert no scan_run rows were committed.
        verify_conn = sqlite3.connect(str(db_path), isolation_level=None)
        count = verify_conn.execute("SELECT COUNT(*) FROM scan_run").fetchone()[0]
        verify_conn.close()
        assert count == 0, f"Expected 0 scan_run rows after dry-run, found {count}"


class TestLibraryStatusRegression:
    """library-status command still works after adding library-index."""

    def test_library_status_still_works(self, tmp_path: Path) -> None:
        """library-status returns exit 0 and prints 'no scans yet' on a fresh DB.

        This is a regression check ensuring that the addition of library-index
        did not break the existing library-status wiring.
        """
        cfg = _make_config(tmp_path)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = runner.invoke(app, ["library-status"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        assert "no scans yet" in result.output
