"""Regression tests for ``personalscraper library-doctor`` CLI command (sub-phase 5.6 — SH-8).

Verifies:
- ``library-doctor --help`` exits 0 (smoke test, existence proof).
- On a clean DB: all checks pass, exit 0.
- ``--format json`` emits parseable JSON with ``overall_status`` key (global flag).
- Default ``rich`` format renders a Rich table (no JSON parse required).
- On a DB with a known issue (orphan repair_queue row):
    the repair_queue_backlog check fires, output reflects it, exit non-0.
- Missing ``indexer.db_path`` exits non-zero with a clear error.
- Individual check unit tests for each health-check function.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

# ── patch targets ─────────────────────────────────────────────────────────────

_OPEN_DB = "personalscraper.indexer.db.open_db"
_APPLY_MIGRATIONS = "personalscraper.indexer.db.apply_migrations"


# ── helpers ───────────────────────────────────────────────────────────────────


def _build_clean_db(tmp_path: Path) -> Path:
    """Create a fully-migrated indexer DB with no seeded data (clean state).

    Uses the real ``open_db`` + ``apply_migrations`` so the schema is identical
    to production.

    Args:
        tmp_path: Pytest temporary directory for the SQLite file.

    Returns:
        Path to the created DB file.
    """
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

    db_file = tmp_path / "test_indexer.db"
    migrations_dir = Path(_migrations_pkg.__file__).parent
    conn = open_db(db_file, event_bus=EventBus())
    apply_migrations(conn, migrations_dir)
    conn.commit()
    conn.close()
    return db_file


# ── 1. Smoke / existence ──────────────────────────────────────────────────────


class TestLibraryDoctorHelp:
    """``library-doctor --help`` must exist and exit 0."""

    def test_help_exits_zero(self) -> None:
        """``library-doctor --help`` exits 0 — proves the command is registered."""
        result = runner.invoke(app, ["library-doctor", "--help"])
        assert result.exit_code == 0, result.output

    def test_help_mentions_repair_queue_threshold_block(self) -> None:
        """``--repair-queue-threshold`` flag is documented (global --format lives at top-level)."""
        result = runner.invoke(app, ["library-doctor", "--help"])
        assert "--repair-queue-threshold" in result.output

    def test_help_mentions_repair_queue_threshold(self) -> None:
        """``--repair-queue-threshold`` is documented in the help text."""
        result = runner.invoke(app, ["library-doctor", "--help"])
        assert "--repair-queue-threshold" in result.output


# ── 2. Clean DB: all checks pass, exit 0 ─────────────────────────────────────


class TestLibraryDoctorCleanDb:
    """On a clean, freshly-migrated DB all checks must pass and exit 0.

    Regression: without this test, a latent check that always raises an
    exception would silently elevate the exit code to non-zero on healthy DBs.
    """

    def test_clean_db_exits_zero(self, tmp_path, test_config) -> None:
        """Clean DB: exit code 0."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["--format", "json", "library-doctor"])
        assert result.exit_code == 0, result.output

    def test_clean_db_json_overall_ok(self, tmp_path, test_config) -> None:
        """Clean DB: JSON output has overall_status 'ok' or 'skip'."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["--format", "json", "library-doctor"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        start = raw.find("{")
        assert start != -1, f"No JSON in output: {raw!r}"
        data = json.loads(raw[start:])
        assert data["overall_status"] in ("ok", "skip"), f"Unexpected overall_status: {data['overall_status']}"

    def test_clean_db_json_has_checks_list(self, tmp_path, test_config) -> None:
        """JSON output includes a 'checks' list with at least one entry."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["--format", "json", "library-doctor"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        start = raw.find("{")
        assert start != -1, f"No JSON in output: {raw!r}"
        data = json.loads(raw[start:])
        assert "checks" in data
        assert len(data["checks"]) >= 1

    def test_clean_db_table_output_exits_zero(self, tmp_path, test_config) -> None:
        """Table format also exits 0 on a clean DB."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["library-doctor"])
        assert result.exit_code == 0, result.output


# ── 3. --format json and --format table ──────────────────────────────────────


class TestLibraryDoctorFormat:
    """Output format switching."""

    def test_json_format_emits_parseable_json(self, tmp_path, test_config) -> None:
        """``--format json`` emits parseable JSON."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["--format", "json", "library-doctor"])
        raw = result.output.strip()
        start = raw.find("{")
        assert start != -1, f"No JSON in output: {raw!r}"
        data = json.loads(raw[start:])
        assert "overall_status" in data
        assert "checks" in data
        assert "elapsed_s" in data

    def test_invalid_format_exits_nonzero(self, tmp_path, test_config) -> None:
        """Invalid global ``--format`` exits non-zero with an error message."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["--format", "xml", "library-doctor"])
        assert result.exit_code != 0

    def test_rich_format_prints_check_names(self, tmp_path, test_config) -> None:
        """Default rich format output contains check names (rendered as table rows)."""
        db_file = _build_clean_db(tmp_path)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(app, ["library-doctor"])
        assert "integrity_check" in result.output


# ── 4. Known issue: repair_queue backlog triggers WARN + non-zero exit ────────


class TestLibraryDoctorRepairQueueBacklog:
    """When repair_queue has >= threshold pending rows, the check fires and exit is non-zero.

    Regression: this test would FAIL if _check_repair_queue_backlog silently
    returned ``ok`` regardless of the row count. It pins that the threshold
    logic is evaluated correctly.
    """

    def _seed_repair_queue(self, db_file: Path, count: int) -> None:
        """Insert ``count`` pending repair_queue rows into the real DB.

        Uses distinct scope_id values to avoid the partial UNIQUE index on
        (scope, scope_id) WHERE status='pending' added by migration 003.

        Args:
            db_file: Path to an existing, migrated indexer DB.
            count: Number of pending rows to insert.
        """
        conn = sqlite3.connect(str(db_file))
        now = int(time.time())
        for i in range(count):
            conn.execute(
                "INSERT INTO repair_queue(scope,scope_id,reason,payload_json,enqueued_at,status)"
                " VALUES ('item',?,'test.backlog','{}',?,'pending')",
                (i + 1, now),
            )
        conn.commit()
        conn.close()

    def test_backlog_triggers_warn_exit_nonzero(self, tmp_path, test_config) -> None:
        """threshold=1, 2 pending rows → WARN → exit non-zero.

        Regression: confirms the threshold guard evaluates correctly; without
        this test a silent ``ok`` return would hide the backlog.
        """
        db_file = _build_clean_db(tmp_path)
        self._seed_repair_queue(db_file, count=2)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(
                app,
                ["--format", "json", "library-doctor", "--repair-queue-threshold", "1"],
            )
        assert result.exit_code != 0, "Expected non-zero exit when repair_queue threshold exceeded"
        raw = result.output.strip()
        start = raw.find("{")
        assert start != -1, f"No JSON in output: {raw!r}"
        data = json.loads(raw[start:])
        # Find the repair_queue_backlog check result
        rq_check = next((c for c in data["checks"] if c["name"] == "repair_queue_backlog"), None)
        assert rq_check is not None, "repair_queue_backlog check missing from output"
        assert rq_check["status"] == "warn", f"Expected warn, got: {rq_check['status']}"
        assert data["overall_status"] in ("warn", "fail")

    def test_below_threshold_exits_zero(self, tmp_path, test_config) -> None:
        """2 pending rows with threshold=10 → ok → exit 0."""
        db_file = _build_clean_db(tmp_path)
        self._seed_repair_queue(db_file, count=2)
        cfg = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )
        with patch("personalscraper.conf.loader.load_config", return_value=cfg):
            result = runner.invoke(
                app,
                ["--format", "json", "library-doctor", "--repair-queue-threshold", "10"],
            )
        assert result.exit_code == 0, f"Expected exit 0 below threshold, got {result.exit_code}: {result.output}"


# ── 5. Missing db_path guard ──────────────────────────────────────────────────


class TestLibraryDoctorMissingDbPath:
    """``library-doctor`` exits non-zero when ``indexer.db_path`` is None."""

    def test_missing_db_path_exits_nonzero(self, test_config) -> None:
        """When ``cfg.indexer.db_path`` is None the command exits with code 1."""
        cfg_no_db = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
        with patch("personalscraper.conf.loader.load_config", return_value=cfg_no_db):
            result = runner.invoke(app, ["library-doctor"])
        assert result.exit_code != 0


# ── 6. Unit tests for individual check functions ──────────────────────────────


class TestCheckFunctions:
    """Unit tests for individual health-check functions against an in-memory DB.

    Each test exercises one check in isolation using ``sqlite3.connect(':memory:')``
    with a hand-crafted schema.  This avoids the migration applier and keeps
    the tests fast.
    """

    def _open_migrated_conn(self, tmp_path: Path) -> sqlite3.Connection:
        """Return a fully-migrated in-memory-equivalent real-file connection.

        We use a real file (not ``:memory:``) because ``detect_path_missing``
        exercises ``disk.mount_path`` and needs the row_factory to work.

        Args:
            tmp_path: Pytest temporary directory for the temp DB file.

        Returns:
            Open :class:`sqlite3.Connection` with all migrations applied.
        """
        from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
        from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
        from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

        db_file = tmp_path / "unit_test.db"
        migrations_dir = Path(_migrations_pkg.__file__).parent
        conn = open_db(db_file, event_bus=EventBus())
        apply_migrations(conn, migrations_dir)
        conn.commit()
        return conn

    # ── _check_integrity ──────────────────────────────────────────────────────

    def test_integrity_ok_on_clean_db(self, tmp_path: Path) -> None:
        """PRAGMA integrity_check returns ok on a clean DB → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_integrity  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_integrity(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    # ── _check_foreign_keys_pragma ────────────────────────────────────────────

    def test_fk_pragma_ok_when_enabled(self, tmp_path: Path) -> None:
        """foreign_keys=1 after open_db → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_foreign_keys_pragma  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_foreign_keys_pragma(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    def test_fk_pragma_fail_when_disabled(self) -> None:
        """foreign_keys=OFF → status fail."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_foreign_keys_pragma  # noqa: PLC0415

        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            result = _check_foreign_keys_pragma(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.FAIL

    # ── _check_fk_orphans ─────────────────────────────────────────────────────

    def test_fk_orphans_ok_on_clean_db(self, tmp_path: Path) -> None:
        """No orphans on clean DB → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_fk_orphans  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_fk_orphans(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    # ── _check_schema_version ─────────────────────────────────────────────────

    def test_schema_version_ok_on_migrated_db(self, tmp_path: Path) -> None:
        """user_version matches schema_version after migrations → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_schema_version  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_schema_version(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    def test_schema_version_skip_on_bare_db(self) -> None:
        """schema_version table absent → status skip."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_schema_version  # noqa: PLC0415

        conn = sqlite3.connect(":memory:")
        try:
            result = _check_schema_version(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.SKIP

    def test_schema_version_fail_on_mismatch(self) -> None:
        """schema_version diverges from user_version → status fail."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_schema_version  # noqa: PLC0415

        conn = sqlite3.connect(":memory:")
        # Set user_version to 5 but schema_version to 3 → divergence.
        conn.execute("PRAGMA user_version=5")
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version VALUES (3)")
        conn.commit()
        try:
            result = _check_schema_version(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.FAIL

    # ── _check_no_stuck_scan_run ──────────────────────────────────────────────

    def test_no_stuck_scan_ok_on_clean_db(self, tmp_path: Path) -> None:
        """No scan_run rows → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_no_stuck_scan_run  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_no_stuck_scan_run(conn, stuck_threshold_s=3600)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    def test_stuck_scan_triggers_warn(self, tmp_path: Path) -> None:
        """scan_run row in 'running' started > threshold ago → status warn.

        Regression: if the stuck-scan guard always returned ok, a crashed
        scanner would go unnoticed. This test pins the detection logic.
        """
        from personalscraper.commands.library.doctor import CheckStatus, _check_no_stuck_scan_run  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        # Insert a scan_run row started 2 hours ago, still 'running'.
        two_hours_ago = int(time.time()) - 7200
        conn.execute(
            "INSERT INTO scan_run(generation, mode, disk_filter, started_at, finished_at, status)"
            " VALUES (1, 'full', NULL, ?, NULL, 'running')",
            (two_hours_ago,),
        )
        conn.commit()
        try:
            result = _check_no_stuck_scan_run(conn, stuck_threshold_s=3600)
        finally:
            conn.close()
        assert result.status == CheckStatus.WARN, f"Expected WARN for stuck scan, got {result.status}"

    # ── _check_repair_queue_backlog ───────────────────────────────────────────

    def test_repair_queue_ok_when_empty(self, tmp_path: Path) -> None:
        """Empty repair_queue → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_repair_queue_backlog  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_repair_queue_backlog(conn, threshold=100)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    def test_repair_queue_warn_above_threshold(self, tmp_path: Path) -> None:
        """repair_queue pending >= threshold → status warn."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_repair_queue_backlog  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        now = int(time.time())
        # Use distinct scope_id per row to satisfy the partial UNIQUE index
        # (scope, scope_id) WHERE status='pending' from migration 003.
        for i in range(5):
            conn.execute(
                "INSERT INTO repair_queue(scope,scope_id,reason,payload_json,enqueued_at,status)"
                " VALUES ('item',?,'test','{}',?,'pending')",
                (i + 1, now),
            )
        conn.commit()
        try:
            result = _check_repair_queue_backlog(conn, threshold=3)
        finally:
            conn.close()
        assert result.status == CheckStatus.WARN

    # ── _check_index_outbox_lag ───────────────────────────────────────────────

    def test_outbox_lag_ok_when_no_pending(self, tmp_path: Path) -> None:
        """No pending outbox rows → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_index_outbox_lag  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_index_outbox_lag(conn, lag_threshold_s=3600)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    def test_outbox_lag_warn_when_stale(self, tmp_path: Path) -> None:
        """Oldest pending outbox row > threshold → status warn.

        Regression: without this test a broken lag calculation would silently
        report ok even when the drainer is stalled.
        """
        from personalscraper.commands.library.doctor import CheckStatus, _check_index_outbox_lag  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        # Insert a pending row created 2 hours ago.
        two_hours_ago = int(time.time()) - 7200
        conn.execute(
            "INSERT INTO index_outbox(source,op,payload_json,created_at,status)"
            " VALUES ('dispatch','move','{}',?,'pending')",
            (two_hours_ago,),
        )
        conn.commit()
        try:
            result = _check_index_outbox_lag(conn, lag_threshold_s=3600)
        finally:
            conn.close()
        assert result.status == CheckStatus.WARN, f"Expected WARN for stale outbox, got {result.status}"

    # ── _check_merkle_drift ───────────────────────────────────────────────────

    def test_merkle_drift_ok_when_no_disks_with_merkle(self, tmp_path: Path) -> None:
        """No disks with merkle_root set → no drift detected → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_merkle_drift  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_merkle_drift(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    # ── _check_canonical_provider_populated ───────────────────────────────────

    def test_canonical_provider_ok_when_no_items(self, tmp_path: Path) -> None:
        """Empty media_item table → vacuously ok."""
        from personalscraper.commands.library.doctor import (  # noqa: PLC0415
            CheckStatus,
            _check_canonical_provider_populated,
        )

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_canonical_provider_populated(conn, threshold_pct=50.0)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    def test_canonical_provider_warn_when_low_pct(self, tmp_path: Path) -> None:
        """50% items lack canonical_provider with threshold=80% → status warn.

        Regression: confirms the percentage calculation is correct; without
        this test a hardcoded ``ok`` return would hide bootstrap failures.
        """
        from personalscraper.commands.library.doctor import (  # noqa: PLC0415
            CheckStatus,
            _check_canonical_provider_populated,
        )

        conn = self._open_migrated_conn(tmp_path)
        now = int(time.time())
        # media_item requires: kind, title, title_sort, category_id, date_created, date_modified.
        # Insert 2 items: 1 with canonical_provider, 1 without.
        _cols = "kind, title, title_sort, category_id, date_created, date_modified, canonical_provider"
        conn.execute(
            f"INSERT INTO media_item({_cols}) VALUES ('movie', 'Movie A', 'Movie A', 'movies', ?, ?, 'tmdb')",
            (now, now),
        )
        conn.execute(
            f"INSERT INTO media_item({_cols}) VALUES ('movie', 'Movie B', 'Movie B', 'movies', ?, ?, NULL)",
            (now, now),
        )
        conn.commit()
        try:
            # threshold 80% → 50% populated → warn
            result = _check_canonical_provider_populated(conn, threshold_pct=80.0)
        finally:
            conn.close()
        assert result.status == CheckStatus.WARN, f"Expected WARN, got {result.status}: {result.message}"

    def test_canonical_provider_ok_when_above_threshold(self, tmp_path: Path) -> None:
        """100% items have canonical_provider with threshold=50% → status ok."""
        from personalscraper.commands.library.doctor import (  # noqa: PLC0415
            CheckStatus,
            _check_canonical_provider_populated,
        )

        conn = self._open_migrated_conn(tmp_path)
        now = int(time.time())
        _cols = "kind, title, title_sort, category_id, date_created, date_modified, canonical_provider"
        conn.execute(
            f"INSERT INTO media_item({_cols}) VALUES ('movie', 'Movie A', 'Movie A', 'movies', ?, ?, 'tvdb')",
            (now, now),
        )
        conn.commit()
        try:
            result = _check_canonical_provider_populated(conn, threshold_pct=50.0)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK

    # ── _check_phantom_paths ──────────────────────────────────────────────────

    def test_phantom_paths_ok_when_no_mounted_disks(self, tmp_path: Path) -> None:
        """No mounted disks → no paths to check → status ok."""
        from personalscraper.commands.library.doctor import CheckStatus, _check_phantom_paths  # noqa: PLC0415

        conn = self._open_migrated_conn(tmp_path)
        try:
            result = _check_phantom_paths(conn)
        finally:
            conn.close()
        assert result.status == CheckStatus.OK


# ── 7. DoctorReport model ─────────────────────────────────────────────────────


class TestDoctorReport:
    """Unit tests for :class:`DoctorReport` properties."""

    def test_overall_ok_when_all_ok(self) -> None:
        """overall_status is ok when all checks pass."""
        from personalscraper.commands.library.doctor import CheckResult, CheckStatus, DoctorReport  # noqa: PLC0415

        report = DoctorReport(
            checks=[
                CheckResult("a", CheckStatus.OK, "ok"),
                CheckResult("b", CheckStatus.OK, "ok"),
            ]
        )
        assert report.overall_status == CheckStatus.OK
        assert report.exit_code == 0

    def test_overall_warn_when_any_warn(self) -> None:
        """overall_status is warn when at least one check is warn."""
        from personalscraper.commands.library.doctor import CheckResult, CheckStatus, DoctorReport  # noqa: PLC0415

        report = DoctorReport(
            checks=[
                CheckResult("a", CheckStatus.OK, "ok"),
                CheckResult("b", CheckStatus.WARN, "warn"),
            ]
        )
        assert report.overall_status == CheckStatus.WARN
        assert report.exit_code != 0

    def test_overall_fail_beats_warn(self) -> None:
        """overall_status is fail when there is both a warn and a fail."""
        from personalscraper.commands.library.doctor import CheckResult, CheckStatus, DoctorReport  # noqa: PLC0415

        report = DoctorReport(
            checks=[
                CheckResult("a", CheckStatus.WARN, "warn"),
                CheckResult("b", CheckStatus.FAIL, "fail"),
            ]
        )
        assert report.overall_status == CheckStatus.FAIL
        assert report.exit_code != 0

    def test_as_dict_structure(self) -> None:
        """as_dict() returns expected keys."""
        from personalscraper.commands.library.doctor import CheckResult, CheckStatus, DoctorReport  # noqa: PLC0415

        report = DoctorReport(checks=[CheckResult("x", CheckStatus.OK, "all good")])
        d = report.as_dict()
        assert "overall_status" in d
        assert "checks" in d
        assert "elapsed_s" in d
        assert d["checks"][0]["name"] == "x"
