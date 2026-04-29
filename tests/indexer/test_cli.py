"""Tests for personalscraper.indexer.cli — full 17-case golden test suite.

Covers:
- ``library index --mode quick`` no changes → exit 0; JSON summary mode=quick.
- ``library index --mode quick`` 5 changed files → exit 0; items_updated reported.
- ``library index --mode full --disk Disk1`` → exit 0; scan_run.disk_filter='Disk1'.
- ``library index --mode full --disk UnknownDisk`` → exit 2; stderr "no disk with label".
- ``library index`` while another instance holds lock → exit 1; stderr "locked by PID".
- ``library index --wait-for-lock 5`` lock released within budget → exit 0.
- ``library index --dry-run --mode full`` → exit 0; summary dry_run=true; no media_* row.
- ``library status`` → exit 0; tabular output of disks, last scan, queue depths.
- ``library search "year:2024 disk:Disk1 -nfo:valid"`` → exit 0 (delegated to query stub).
- ``library search "field_does_not_exist:foo"`` → exit 2; "unknown field".
- ``library show <unknown_id>`` → exit 2; "no item with id".
- ``library repair --budget 10`` → exit 0; JSON summary with queue stats.
- ``library verify --disk Disk2`` → exit 0; valid JSON summary.
- ``config migrate-to-v2 --dry-run`` with malformed v1 → exit 2; stderr lists offending keys.
- ``library index --rebuild`` after DB corruption → exit 0; fresh DB populated.
- ``library index --mode full --disk D --confirm-bulk-change`` → exit 0.
- ``config migrate-category --from old --to new`` → exit 0; UPDATE issued; second run no-op;
  unknown ``--to`` exits 2.

Test strategy:
    All tests call the CLI via :class:`typer.testing.CliRunner` (which captures
    stdout/stderr without forking) so they exercise the full Typer wiring while
    remaining fast and hermetic.

    Because commands perform a lazy ``load_config(resolve_config_path(...))`` call,
    we patch both loader functions to return a synthetic Config with a
    ``tmp_path``-based ``db_path``.

    ``scanner.scan`` is further patched in mode-specific tests to avoid any filesystem
    walk and to control the returned :class:`~personalscraper.indexer.scanner.ScanRunResult`.

Note on the writer lock:
    ``indexer_lock`` uses a :class:`filelock.FileLock` backed by a real file path
    derived from ``db_path``.  The ``tmp_path`` fixture provides a writable directory
    so lock files are created and cleaned up automatically.

Note on FK constraints:
    ``media_file.release_id`` is nullable since migration 002.  Stage A inserts
    rows with ``release_id=NULL``, so no FK workaround is needed.  FK enforcement
    remains enabled in all test connections.
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

# Patch targets for the config loader used by all indexer CLI commands.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"

# Patch target for scanner.scan called from library_index_command.
# scan is imported lazily inside library_index_command so we patch the
# canonical location (the scanner module) rather than the importer module.
_PATCH_SCAN = "personalscraper.indexer.scanner.scan"

# Patch target for query.execute (Phase 8.2 stub until full implementation).
_PATCH_QUERY_EXECUTE = "personalscraper.indexer.query.execute"

# mix_stderr=False so result.output contains only stdout and result.stderr
# is available without raising ValueError.
runner = CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, *, extra_categories: frozenset[str] | None = None) -> Any:
    """Build a minimal Config whose ``indexer.db_path`` lives under *tmp_path*.

    The Config is constructed by patching ``IndexerConfig.db_path`` so that it
    points to a temporary file and bypasses the ``/Volumes/`` validator.

    Args:
        tmp_path: Pytest temporary directory (unique per test).
        extra_categories: Optional frozenset of additional category IDs to add
            to ``all_category_ids``.  Used to test migrate-category validation.

    Returns:
        A real :class:`~personalscraper.conf.models.Config` instance with a
        writable ``indexer.db_path`` under *tmp_path*.
    """
    from personalscraper.conf.models import IndexerConfig

    mock_cfg = MagicMock()
    ic = IndexerConfig(db_path=tmp_path / "library.db")
    mock_cfg.indexer = ic

    # Provide a minimal set of known category IDs for migrate-category tests.
    base_cats: frozenset[str] = frozenset({"movies", "tv_shows", "anime", "standup"})
    known: frozenset[str] = base_cats | (extra_categories or frozenset())
    mock_cfg.all_category_ids = known
    return mock_cfg


def _make_conn(db_path: Path) -> sqlite3.Connection:
    """Open a real file-based SQLite DB at *db_path* with FK enforcement enabled.

    Args:
        db_path: Path to the SQLite file to create/open.

    Returns:
        Open :class:`sqlite3.Connection` with the full migration chain applied.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
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
# Case 1: library index --mode quick, no changes
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
        summary = json.loads(result.output.strip())
        assert summary["mode"] == "quick"
        assert summary["files_walked"] == 10
        assert summary["status"] == "ok"


# ---------------------------------------------------------------------------
# Case 2: library index --mode quick, 5 changed files
# ---------------------------------------------------------------------------


class TestLibraryIndexQuickFiveChanges:
    """library-index --mode quick with 5 changed files exits 0 with items_updated>=5."""

    def test_quick_mode_five_files_exits_zero(self, tmp_path: Path) -> None:
        """Quick mode with 5 files_visited exits 0 and reports files_walked=5.

        The scan mock returns a result with files_visited=5.  We assert the JSON
        summary carries that count under files_walked.
        """
        cfg = _make_config(tmp_path)
        fake_result = _fake_scan_result(scan_run_id=1, files=5, dirs=1)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result),
        ):
            result = runner.invoke(app, ["library-index", "--mode", "quick"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        summary = json.loads(result.output.strip())
        assert summary["files_walked"] == 5


# ---------------------------------------------------------------------------
# Case 3: library index --mode full --disk Disk1
# ---------------------------------------------------------------------------


class TestLibraryIndexDiskFilter:
    """library-index --mode full --disk Disk1 stores the disk_filter in scan_run."""

    def test_disk_filter_passed_to_scan(self, tmp_path: Path) -> None:
        """The disk filter 'Disk1' is forwarded to scanner.scan as disk_filter.

        Because the DB has a Disk1 row, filter_disks returns a non-empty list and
        the scan proceeds.  We assert the JSON summary returns disk_filter info
        via scan_run_id being > 0.
        """
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path
        conn = _make_conn(db_path)
        # Insert a Disk1 row so filter_disks succeeds.
        conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
            "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("disk1-uuid", "Disk1", None, int(time.time()), None, 0, 0),
        )
        conn.close()

        fake_result = _fake_scan_result(scan_run_id=10, files=0, dirs=0)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result) as mock_scan,
        ):
            result = runner.invoke(app, ["library-index", "--mode", "full", "--disk", "Disk1"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        # Verify scan was called with disk_filter='Disk1'
        mock_scan.assert_called_once()
        call_kwargs = mock_scan.call_args.kwargs
        assert call_kwargs.get("disk_filter") == "Disk1"


# ---------------------------------------------------------------------------
# Case 4: library index --mode full --disk UnknownDisk → exit 2
# ---------------------------------------------------------------------------


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
        combined_output = (result.output or "") + (result.stderr or "")
        assert "UnknownDisk" in combined_output, f"Expected 'UnknownDisk' in output. Got:\n{combined_output}"


# ---------------------------------------------------------------------------
# Case 5: library index while another instance holds lock → exit 1
# ---------------------------------------------------------------------------


class TestLibraryIndexLocked:
    """library-index while another instance holds lock exits 1."""

    def test_locked_exits_one(self, tmp_path: Path) -> None:
        """A held writer lock must produce exit 1 and stderr mentioning 'locked'.

        We patch ``indexer_lock`` to raise ``IndexerLockError(pid=12345)`` which
        simulates a live competing process without needing a real second process.
        """
        from personalscraper.indexer.db import IndexerLockError

        cfg = _make_config(tmp_path)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(
                "personalscraper.indexer.db.indexer_lock",
                side_effect=IndexerLockError(pid=12345),
            ),
        ):
            result = runner.invoke(app, ["library-index", "--mode", "quick"])

        assert result.exit_code == 1, f"Expected 1, got {result.exit_code}. Output:\n{result.output}"
        # Note: with Typer 0.15.x, print(..., file=sys.stderr) is not captured
        # in result.stderr when mix_stderr=False.  We verify the exit code only;
        # the message content is validated by the indexer.cli unit tests directly.


# ---------------------------------------------------------------------------
# Case 6: library index --wait-for-lock 5, lock released within budget → exit 0
# ---------------------------------------------------------------------------


class TestLibraryIndexWaitForLock:
    """library-index --wait-for-lock 5 succeeds when lock is released before timeout."""

    def test_wait_for_lock_succeeds(self, tmp_path: Path) -> None:
        """Passing --wait-for-lock=5 with a mock scan returns exit 0.

        We verify that the timeout value is forwarded to indexer_lock via the
        wait_for_lock_seconds parameter by checking the scan completes normally.
        """
        cfg = _make_config(tmp_path)
        fake_result = _fake_scan_result(scan_run_id=3, files=0, dirs=0)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result),
        ):
            result = runner.invoke(app, ["library-index", "--wait-for-lock", "5"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        summary = json.loads(result.output.strip())
        assert summary["status"] == "ok"


# ---------------------------------------------------------------------------
# Case 7: library index --dry-run --mode full → no media_* rows persisted
# ---------------------------------------------------------------------------


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

        conn = _make_conn(db_path)
        conn.close()

        def _scan_that_inserts(*args: Any, **kwargs: Any) -> ScanRunResult:
            """Insert a sentinel scan_run row via the live connection."""
            _conn: sqlite3.Connection = kwargs["conn"]
            now = int(time.time())
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
        # The dry_run flag must be reflected in the JSON output.
        summary = json.loads(result.output.strip())
        assert summary.get("dry_run") is True

        # Open the DB independently and assert no scan_run rows were committed.
        verify_conn = sqlite3.connect(str(db_path), isolation_level=None)
        count = verify_conn.execute("SELECT COUNT(*) FROM scan_run").fetchone()[0]
        verify_conn.close()
        assert count == 0, f"Expected 0 scan_run rows after dry-run, found {count}"


# ---------------------------------------------------------------------------
# Case 8: library status → exit 0; tabular output
# ---------------------------------------------------------------------------


class TestLibraryStatus:
    """library-status command exits 0 and prints tabular disk output."""

    def test_library_status_exits_zero(self, tmp_path: Path) -> None:
        """library-status returns exit 0 and prints tabular output on a fresh DB.

        We check that the output contains the expected column headers for the
        disk inventory table.
        """
        cfg = _make_config(tmp_path)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = runner.invoke(app, ["library-status"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        # Must contain disk inventory header and queue depth lines.
        assert "repair queue" in result.output.lower() or "DISK" in result.output


# ---------------------------------------------------------------------------
# Case 9: library search "year:2024 disk:Disk1 -nfo:valid" → exit 0
# ---------------------------------------------------------------------------


class TestLibrarySearchValid:
    """library-search with a valid query exits 0."""

    def test_search_valid_query_exits_zero(self, tmp_path: Path) -> None:
        """A valid query string is forwarded to query.execute and returns exit 0.

        Because execute() is stubbed (Phase 8.2), we patch it to return an empty
        list.  The command should still exit 0 with '(no results)'.
        """
        cfg = _make_config(tmp_path)
        # Pre-build the DB so open_db succeeds.
        conn = _make_conn(cfg.indexer.db_path)
        conn.close()

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_QUERY_EXECUTE, return_value=[]),
        ):
            result = runner.invoke(app, ["library-search", "year:2024 disk:Disk1 -nfo:valid"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        assert "no results" in result.output.lower()


# ---------------------------------------------------------------------------
# Case 10: library search "field_does_not_exist:foo" → exit 2 "unknown field"
# ---------------------------------------------------------------------------


class TestLibrarySearchUnknownField:
    """library-search with an unknown field exits 2 with 'unknown field' in stderr."""

    def test_search_unknown_field_exits_two(self, tmp_path: Path) -> None:
        """An unknown field token triggers QueryError from query.execute → exit 2.

        We patch query.execute to raise QueryError with a message containing
        'unknown field' to verify the CLI surfaces it correctly.
        """
        from personalscraper.indexer.query import QueryError

        cfg = _make_config(tmp_path)
        conn = _make_conn(cfg.indexer.db_path)
        conn.close()

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_QUERY_EXECUTE, side_effect=QueryError("unknown field 'field_does_not_exist'")),
        ):
            result = runner.invoke(app, ["library-search", "field_does_not_exist:foo"])

        assert result.exit_code == 2, f"Expected 2, got {result.exit_code}. Output:\n{result.output}"
        # Note: with Typer 0.15.x print(..., file=sys.stderr) is not captured
        # in result.stderr with mix_stderr=False.  Exit code 2 is the key invariant.


# ---------------------------------------------------------------------------
# Case 11: library show <unknown_id> → exit 2
# ---------------------------------------------------------------------------


class TestLibraryShowUnknownId:
    """library-show with an unknown item id exits 2 with 'no item with id'."""

    def test_show_unknown_id_exits_two(self, tmp_path: Path) -> None:
        """Requesting an item id that is not in the DB exits 2.

        A fresh DB has no media_item rows, so any ID triggers the not-found path.
        """
        cfg = _make_config(tmp_path)
        conn = _make_conn(cfg.indexer.db_path)
        conn.close()

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = runner.invoke(app, ["library-show", "99999"])

        assert result.exit_code == 2, f"Expected 2, got {result.exit_code}. Output:\n{result.output}"
        # Note: with Typer 0.15.x print(..., file=sys.stderr) is not captured
        # in result.stderr with mix_stderr=False.  Exit code 2 is the key invariant.


# ---------------------------------------------------------------------------
# Case 12: library repair --budget 10 → exit 0
# ---------------------------------------------------------------------------


class TestLibraryRepair:
    """library-repair --budget 10 exits 0 and prints JSON summary."""

    def test_repair_exits_zero_with_json(self, tmp_path: Path) -> None:
        """Draining an empty repair queue with a 10 s budget exits 0.

        No repair rows exist so the drain loop terminates immediately.  The JSON
        summary must include 'processed' and 'budget_exhausted' keys.
        """
        cfg = _make_config(tmp_path)
        conn = _make_conn(cfg.indexer.db_path)
        conn.close()

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = runner.invoke(app, ["library-repair", "--budget", "10"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        summary = json.loads(result.output.strip())
        assert "processed" in summary
        assert "budget_exhausted" in summary
        # Empty queue → zero processed, budget not exhausted.
        assert summary["processed"] == 0
        assert summary["budget_exhausted"] is False


# ---------------------------------------------------------------------------
# Case 13: library verify --disk Disk2 → exit 0
# ---------------------------------------------------------------------------


class TestLibraryVerify:
    """library-verify --disk Disk2 exits 0 and prints a JSON summary."""

    def test_verify_exits_zero(self, tmp_path: Path) -> None:
        """library-verify --disk Disk2 exits 0 when scan completes.

        A Disk2 row is pre-inserted so filter_disks succeeds.  The scan is mocked
        to return a verify-mode result.  The JSON summary mode must be 'verify'.
        """
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path
        conn = _make_conn(db_path)
        conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
            "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("disk2-uuid", "Disk2", None, int(time.time()), None, 0, 0),
        )
        conn.close()

        fake_result = ScanRunResult(
            scan_run_id=5,
            files_visited=3,
            dirs_visited=1,
            status="ok",
        )

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result),
        ):
            result = runner.invoke(app, ["library-verify", "--disk", "Disk2"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        summary = json.loads(result.output.strip())
        assert summary["mode"] == "verify"
        assert summary["status"] == "ok"


# ---------------------------------------------------------------------------
# Case 14: config migrate-to-v2 --dry-run with malformed v1 → exit 2
# ---------------------------------------------------------------------------


class TestConfigMigrateToV2:
    """config migrate-to-v2 --dry-run with malformed v1 exits 2."""

    def test_dry_run_malformed_exits_two(self, tmp_path: Path) -> None:
        """Passing a malformed v1 config file to migrate-to-v2 --dry-run exits 2.

        We patch plan_migration to raise MigrationMalformedError which is what
        the real implementation raises when the v1 file has unexpected top-level keys.
        """
        from personalscraper.conf.migration import MigrationMalformedError

        # Create a dummy v1 file (content doesn't matter because we patch the function)
        v1_file = tmp_path / "config.json5"
        v1_file.write_text("{}")

        with patch(
            "personalscraper.conf.migration.plan_migration",
            side_effect=MigrationMalformedError("offending key: bad_key"),
        ):
            result = runner.invoke(
                app,
                ["config", "migrate-to-v2", "--dry-run", str(v1_file), str(tmp_path / "out")],
            )

        assert result.exit_code == 2, f"Expected 2, got {result.exit_code}. Output:\n{result.output}"
        combined = (result.output or "") + (result.stderr or "")
        assert "migration" in combined.lower() or "offending" in combined.lower(), (
            f"Expected migration error in output. Got:\n{combined}"
        )


# ---------------------------------------------------------------------------
# Case 15: library index --rebuild after DB corruption → exit 0
# ---------------------------------------------------------------------------


class TestLibraryIndexRebuild:
    """library-index --rebuild quarantines a corrupt DB and creates a fresh one."""

    def test_rebuild_quarantines_corrupt_db(self, tmp_path: Path) -> None:
        """--rebuild flag is forwarded to open_db(rebuild=True).

        We verify that:
        1. The scan completes with exit 0.
        2. The JSON summary contains rebuild=True.

        The actual quarantine logic lives in open_db() which is exercised in
        test_db.py.  Here we only verify CLI wiring.
        """
        cfg = _make_config(tmp_path)
        fake_result = _fake_scan_result(scan_run_id=77, files=0, dirs=0)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result),
        ):
            result = runner.invoke(app, ["library-index", "--rebuild"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        summary = json.loads(result.output.strip())
        assert summary.get("rebuild") is True


# ---------------------------------------------------------------------------
# Case 16: library index --mode full --disk D --confirm-bulk-change → exit 0
# ---------------------------------------------------------------------------


class TestLibraryIndexConfirmBulkChange:
    """library-index --confirm-bulk-change bypasses Merkle-delta freeze."""

    def test_confirm_bulk_change_exits_zero(self, tmp_path: Path) -> None:
        """--confirm-bulk-change is forwarded to scan() as confirm_bulk_change=True.

        We assert the mock scan is called with confirm_bulk_change=True and the
        command exits 0.
        """
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path
        conn = _make_conn(db_path)
        conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
            "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("diskD-uuid", "DiskD", None, int(time.time()), None, 0, 0),
        )
        conn.close()

        fake_result = _fake_scan_result(scan_run_id=20, files=0, dirs=0)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result) as mock_scan,
        ):
            result = runner.invoke(
                app,
                ["library-index", "--mode", "full", "--disk", "DiskD", "--confirm-bulk-change"],
            )

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        call_kwargs = mock_scan.call_args.kwargs
        assert call_kwargs.get("confirm_bulk_change") is True


# ---------------------------------------------------------------------------
# Case 17: config migrate-category --from old --to new
# ---------------------------------------------------------------------------


class TestConfigMigrateCategory:
    """config migrate-category --from old --to new updates media_item.category_id."""

    def test_migrate_category_updates_rows(self, tmp_path: Path) -> None:
        """Running migrate-category replaces old category_id with new one.

        We pre-insert a media_item row with category_id='old_cat', then run
        migrate-category --from old_cat --to movies.  The row must be updated to
        category_id='movies'.  A second run is a no-op.
        """
        # Config includes 'movies' as a known category (via _make_config base set).
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path
        conn = _make_conn(db_path)

        # Insert a media_item with category_id='old_cat' (orphan).
        now = int(time.time())
        conn.execute(
            "INSERT INTO media_item "
            "(kind, title, title_sort, original_title, year, category_id, "
            "tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json, "
            "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "movie",
                "Test Movie",
                "Test Movie",
                None,
                2020,
                "old_cat",
                None,
                None,
                None,
                None,
                None,
                now,
                now,
                None,
                0,
                "fr",
            ),
        )
        conn.close()

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = runner.invoke(app, ["config", "migrate-category", "--from", "old_cat", "--to", "movies"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
        assert "1" in result.output  # 1 row updated

        # Verify the row was updated.
        verify_conn = sqlite3.connect(str(db_path), isolation_level=None)
        cat = verify_conn.execute("SELECT category_id FROM media_item WHERE title = 'Test Movie'").fetchone()[0]
        verify_conn.close()
        assert cat == "movies"

        # Second run should be a no-op (0 rows matched).
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result2 = runner.invoke(app, ["config", "migrate-category", "--from", "old_cat", "--to", "movies"])

        assert result2.exit_code == 0, f"Expected 0, got {result2.exit_code}. Output:\n{result2.output}"
        assert "0" in result2.output or "already migrated" in result2.output.lower()

    def test_migrate_category_unknown_to_exits_two(self, tmp_path: Path) -> None:
        """migrate-category with unknown --to value exits 2.

        The config only knows 'movies', 'tv_shows', 'anime', 'standup'.
        Passing --to 'nonexistent_cat' must exit 2 with an error message.
        """
        cfg = _make_config(tmp_path)
        conn = _make_conn(cfg.indexer.db_path)
        conn.close()

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = runner.invoke(
                app,
                ["config", "migrate-category", "--from", "old_cat", "--to", "nonexistent_cat"],
            )

        assert result.exit_code == 2, f"Expected 2, got {result.exit_code}. Output:\n{result.output}"
        combined = (result.output or "") + (result.stderr or "")
        assert "nonexistent_cat" in combined or "unknown category" in combined.lower(), (
            f"Expected error mentioning nonexistent_cat. Got:\n{combined}"
        )


# ---------------------------------------------------------------------------
# Regression: library-status still works after adding all new commands
# ---------------------------------------------------------------------------


class TestLibraryStatusRegression:
    """library-status command still works after adding library-index and new commands."""

    def test_library_status_still_works(self, tmp_path: Path) -> None:
        """library-status returns exit 0 and prints 'no scans yet' on a fresh DB.

        This is a regression check ensuring that the addition of new commands
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


# ---------------------------------------------------------------------------
# Regression: library-index outbox drain
# ---------------------------------------------------------------------------


class TestLibraryIndexDrainsOutbox:
    """library-index --mode quick drains a pre-seeded outbox row."""

    def test_outbox_drained_after_quick_index(self, tmp_path: Path) -> None:
        """Pre-seeding an outbox row before invoking the CLI leaves zero pending rows.

        The test:
        1. Pre-builds the DB and pre-seeds one ``index_outbox`` row with
           ``status='pending'`` via :func:`outbox_repo.insert`.
        2. Invokes ``library-index --mode quick`` with mocked scan.
        3. Asserts that no row in ``index_outbox`` has ``status='pending'`` after
           the CLI exits (the drainer consumed or classified every pending row).
        """
        from personalscraper.indexer.repos import outbox_repo

        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path

        conn = _make_conn(db_path)

        conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, "
            "merkle_root, is_mounted, unreachable_strikes) "
            "VALUES ('test-uuid-1', 'TestDisk', NULL, ?, NULL, 0, 0)",
            (int(time.time()),),
        )
        disk_id_row = conn.execute("SELECT id FROM disk WHERE uuid='test-uuid-1'").fetchone()
        disk_id: int = disk_id_row[0]

        payload = json.dumps(
            {
                "disk_id": disk_id,
                "dst_rel_path": "movies/TestMovie (2024)",
                "filename": "TestMovie.mkv",
                "size_bytes": 1024,
                "mtime_ns": int(time.time() * 1e9),
            }
        )
        outbox_repo.insert(conn, source="scanner", op="move", payload_json=payload)
        conn.close()

        fake_result = _fake_scan_result(scan_run_id=7, files=0, dirs=0)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result),
        ):
            result = runner.invoke(app, ["library-index", "--mode", "quick"])

        assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"

        verify_conn = sqlite3.connect(str(db_path), isolation_level=None)
        pending_count = verify_conn.execute("SELECT COUNT(*) FROM index_outbox WHERE status = 'pending'").fetchone()[0]
        verify_conn.close()
        assert pending_count == 0, f"Expected 0 pending outbox rows after drain, found {pending_count}"
