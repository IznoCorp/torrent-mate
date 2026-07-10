"""Unit tests for :func:`personalscraper.web.decisions.runner.main`.

Sub-phase 2.2 — covers the runner lifecycle: env reading, decision-row validation,
pipeline_run row insert/finalize, CLI argv building, output streaming (ring buffer
+ Redis), and fail-soft behaviour.

Mirrors ``tests/unit/web/maintenance/test_runner.py``, adapted for the
decisions-runner contract: four env vars, scrape_decision row lookup,
no pipeline-lock acquisition, simpler argv (no registry).

Mocking: ``subprocess.Popen`` (fake stdout + rc), ``redis.Redis.from_url``
(mock client), ``load_config`` (temp DB path). Uses a real on-disk SQLite DB
with the ``pipeline_run`` and ``scrape_decision`` schemas so row assertions
are against a genuine sqlite3 connection.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.sqlite._pragmas import apply_pragmas

# ---------------------------------------------------------------------------
# Helpers — DB setup (migrations 011 + 012 + 013)
# ---------------------------------------------------------------------------

PIPELINE_RUN_DDL = """
CREATE TABLE pipeline_run (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_uid      TEXT    UNIQUE NOT NULL,
    trigger      TEXT    NOT NULL,
    dry_run      INTEGER NOT NULL DEFAULT 0,
    started_at   REAL    NOT NULL,
    ended_at     REAL,
    outcome      TEXT,
    steps_json   TEXT,
    error        TEXT,
    pid          INTEGER,
    kind         TEXT    NOT NULL DEFAULT 'pipeline',
    command      TEXT    NULL,
    options_json TEXT    NULL,
    output_tail  TEXT    NULL
);

CREATE INDEX idx_pipeline_run_started ON pipeline_run(started_at);
CREATE INDEX idx_pipeline_run_kind ON pipeline_run(kind);
"""

SCRAPE_DECISION_DDL = """
CREATE TABLE scrape_decision (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    staging_path    TEXT    UNIQUE NOT NULL,
    media_kind      TEXT    NOT NULL,
    extracted_title TEXT    NOT NULL,
    extracted_year  INTEGER,
    "trigger"       TEXT    NOT NULL,
    candidates_json TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',
    resolution_json TEXT,
    run_uid         TEXT,
    created_at      REAL    NOT NULL,
    updated_at      REAL    NOT NULL,
    resolved_at     REAL
);

CREATE INDEX idx_scrape_decision_status ON scrape_decision(status);
"""


def _create_db(db_path: Path) -> None:
    """Create an on-disk SQLite DB with ``pipeline_run`` and ``scrape_decision`` tables."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.executescript(PIPELINE_RUN_DDL)
    conn.executescript(SCRAPE_DECISION_DDL)
    conn.commit()
    conn.close()


def _select_row(db_path: Path, run_uid: str) -> dict | None:
    """Return the ``pipeline_run`` row as a dict, or ``None``."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _select_decision_row(db_path: Path, decision_id: int) -> dict | None:
    """Return the ``scrape_decision`` row as a dict, or ``None``."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM scrape_decision WHERE id = ?", (decision_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _insert_decision_row(
    db_path: Path,
    decision_id: int | None = None,
    staging_path: str = "/tmp/staging/test-item",
    status: str = "pending",
) -> int:
    """Insert a ``scrape_decision`` row and return its id."""
    import time

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    now = time.time()
    if decision_id is not None:
        conn.execute(
            "INSERT INTO scrape_decision "
            '(id, staging_path, media_kind, extracted_title, "trigger", '
            "candidates_json, status, created_at, updated_at) "
            "VALUES (?, ?, 'movie', 'Test Item', 'mid_band', '[]', ?, ?, ?)",
            (decision_id, staging_path, status, now, now),
        )
    else:
        cursor = conn.execute(
            "INSERT INTO scrape_decision "
            '(staging_path, media_kind, extracted_title, "trigger", '
            "candidates_json, status, created_at, updated_at) "
            "VALUES (?, 'movie', 'Test Item', 'mid_band', '[]', ?, ?, ?)",
            (staging_path, status, now, now),
        )
        decision_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return decision_id


def _make_mock_config(tmp_path: Path) -> MagicMock:
    """Build a mock ``Config`` with a real DB path and dummy web config."""
    db_path = tmp_path / "library.db"
    _create_db(db_path)
    config = MagicMock()
    config.indexer.db_path = db_path
    config.paths.data_dir = tmp_path
    config.web.enabled = True
    config.web.redis_url = "redis://127.0.0.1:6379/0"
    config.web.stream_key = "test:events"
    config.web.stream_maxlen = 10000
    return config


def _set_runner_env(
    run_uid: str,
    decision_id: int,
    provider: str,
    provider_id: int,
) -> None:
    """Set the four mandatory env vars for the decisions runner."""
    os.environ["PERSONALSCRAPER_RUN_UID"] = run_uid
    os.environ["PERSONALSCRAPER_DECISION_ID"] = str(decision_id)
    os.environ["PERSONALSCRAPER_DECISION_PROVIDER"] = provider
    os.environ["PERSONALSCRAPER_DECISION_PROVIDER_ID"] = str(provider_id)


def _clear_runner_env() -> None:
    """Remove the runner env vars."""
    for var in (
        "PERSONALSCRAPER_RUN_UID",
        "PERSONALSCRAPER_DECISION_ID",
        "PERSONALSCRAPER_DECISION_PROVIDER",
        "PERSONALSCRAPER_DECISION_PROVIDER_ID",
    ):
        os.environ.pop(var, None)


def _fake_popen(stdout_lines: list[str], returncode: int = 0) -> MagicMock:
    """Return a mock ``Popen`` instance with configurable stdout and rc."""
    mock_proc = MagicMock()
    mock_proc.stdout = stdout_lines
    mock_proc.wait.return_value = returncode
    return mock_proc


# ---------------------------------------------------------------------------
# Tests — env validation
# ---------------------------------------------------------------------------


class TestEnvValidation:
    """Runner exits 2 when mandatory env vars are missing."""

    def test_missing_all_env_exits_2(self) -> None:
        """When no env vars are set, the runner exits with code 2."""
        _clear_runner_env()
        with pytest.raises(SystemExit) as exc_info:
            from personalscraper.web.decisions.runner import _read_mandatory_env

            _read_mandatory_env()
        assert exc_info.value.code == 2

    def test_partial_env_exits_2(self) -> None:
        """When only some env vars are set, the runner exits with code 2."""
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid"
        with pytest.raises(SystemExit) as exc_info:
            from personalscraper.web.decisions.runner import _read_mandatory_env

            _read_mandatory_env()
        assert exc_info.value.code == 2
        _clear_runner_env()


# ---------------------------------------------------------------------------
# Tests — CLI argv building
# ---------------------------------------------------------------------------


class TestBuildArgv:
    """CLI argument vector covers staging_path, provider, and provider_id."""

    def test_base_argv_starts_with_executable_and_module(self) -> None:
        """The argv always starts with [sys.executable, -m, personalscraper, scrape-resolve]."""
        from personalscraper.web.decisions.runner import _build_argv

        argv = _build_argv("/tmp/staging/test", "tmdb", 12345, "pick")
        assert argv[0] == sys.executable
        assert argv[1] == "-m"
        assert argv[2] == "personalscraper"
        assert argv[3] == "scrape-resolve"

    def test_staging_path_is_positional(self) -> None:
        """The staging_path is the first positional argument after the command."""
        from personalscraper.web.decisions.runner import _build_argv

        argv = _build_argv("/tmp/staging/test-item", "tmdb", 42, "pick")
        assert argv[4] == "/tmp/staging/test-item"

    def test_provider_and_id_are_flags(self) -> None:
        """Provider and provider_id are passed as --provider and --id flags."""
        from personalscraper.web.decisions.runner import _build_argv

        argv = _build_argv("/tmp/staging/test", "tvdb", 999, "pick")
        idx_provider = argv.index("--provider")
        assert argv[idx_provider + 1] == "tvdb"
        idx_id = argv.index("--id")
        assert argv[idx_id + 1] == "999"

    def test_via_is_a_flag(self) -> None:
        """The resolution provenance is passed as --via (F09)."""
        from personalscraper.web.decisions.runner import _build_argv

        argv = _build_argv("/tmp/staging/test", "tmdb", 5, "search_override")
        idx_via = argv.index("--via")
        assert argv[idx_via + 1] == "search_override"


# ---------------------------------------------------------------------------
# Tests — decision row validation
# ---------------------------------------------------------------------------


class TestDecisionRowValidation:
    """Runner exits 2 when the decision row is missing or not pending."""

    def test_missing_decision_exits_2(self, tmp_path: Path) -> None:
        """When the decision row does not exist, exit 2 with error finalization."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _set_runner_env("run-uid-01", 9999, "tmdb", 12345)
        mock_proc = _fake_popen(["ok\n"], returncode=0)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        _clear_runner_env()
        assert exc_info.value.code == 2
        row = _select_row(db_path, "run-uid-01")
        assert row is not None
        assert row["outcome"] == "error"
        assert "not found" in row["error"]

    def test_non_pending_decision_exits_2(self, tmp_path: Path) -> None:
        """When the decision status is not 'pending', exit 2 with error."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        decision_id = _insert_decision_row(db_path, status="resolved")
        _set_runner_env("run-uid-02", decision_id, "tmdb", 12345)
        mock_proc = _fake_popen(["ok\n"], returncode=0)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        _clear_runner_env()
        assert exc_info.value.code == 2
        row = _select_row(db_path, "run-uid-02")
        assert row is not None
        assert row["outcome"] == "error"
        assert "resolved" in row["error"]

    def test_decision_read_db_error_finalizes_error_not_orphan(self, tmp_path: Path) -> None:
        """F06 — a sqlite error on the pre-region decision read finalizes 'error', exits 2.

        The read happens on the contended library.db before the guarded stream
        region; an unguarded error there would kill the process and leave the
        route-reserved 'running' row orphaned forever.
        """
        import sqlite3

        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _set_runner_env("run-uid-06", 1, "tmdb", 12345)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch(
                "personalscraper.web.decisions.runner._read_decision_row",
                side_effect=sqlite3.OperationalError("database is locked"),
            ),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        _clear_runner_env()
        assert exc_info.value.code == 2
        row = _select_row(db_path, "run-uid-06")
        assert row is not None
        assert row["outcome"] == "error", "the reserved row must be finalized, never left 'running'"
        assert "read failed" in row["error"]


# ---------------------------------------------------------------------------
# Tests — full runner lifecycle (integration-style with mocks)
# ---------------------------------------------------------------------------


class TestRunnerLifecycle:
    """End-to-end runner tests with mocked subprocess and Redis."""

    RUN_UID = "abc123def456"
    DECISION_ID = 1
    PROVIDER = "tmdb"
    PROVIDER_ID = 4242

    @pytest.fixture(autouse=True)
    def _env_setup_teardown(self) -> None:
        """Set mandatory env vars before each test and clean up after."""
        _set_runner_env(self.RUN_UID, self.DECISION_ID, self.PROVIDER, self.PROVIDER_ID)
        yield
        _clear_runner_env()

    # ------------------------------------------------------------------
    # Row lifecycle
    # ------------------------------------------------------------------

    def test_insert_creates_row_with_kind_command_options_json(self, tmp_path: Path) -> None:
        """After insert() the row has kind='maintenance', command='scrape-resolve', options_json."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")
        mock_proc = _fake_popen(["output line\n"], returncode=0)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["kind"] == "maintenance"
        assert row["command"] == "scrape-resolve"
        options = json.loads(row["options_json"])
        assert options["decision_id"] == self.DECISION_ID
        assert options["provider"] == self.PROVIDER
        assert options["provider_id"] == self.PROVIDER_ID
        assert row["trigger"] == "web"
        assert row["pid"] is not None

    def test_final_outcome_success_on_rc_0(self, tmp_path: Path) -> None:
        """Exit code 0 → outcome='success'."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")
        mock_proc = _fake_popen(["ok\n"], returncode=0)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row["outcome"] == "success"
        assert row["ended_at"] is not None
        assert row["error"] is None

    def test_final_outcome_error_on_rc_1_with_error_tail(self, tmp_path: Path) -> None:
        """Exit code 1 → outcome='error' with error tail."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")
        stderr_output = ["Traceback (most recent call last):\n", "ValueError: bad input\n"]
        mock_proc = _fake_popen(stderr_output, returncode=1)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 1
        row = _select_row(db_path, self.RUN_UID)
        assert row["outcome"] == "error"
        assert row["ended_at"] is not None
        assert row["error"] is not None
        assert "ValueError" in row["error"]

    # ------------------------------------------------------------------
    # output_tail
    # ------------------------------------------------------------------

    def test_output_tail_stored_on_success(self, tmp_path: Path) -> None:
        """The full output is stored as output_tail on success."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")
        lines = [f"line {i:04d}\n" for i in range(10)]
        mock_proc = _fake_popen(lines, returncode=0)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row["output_tail"] is not None
        assert "line 0000" in row["output_tail"]
        assert "line 0009" in row["output_tail"]

    def test_output_tail_truncated_to_64_kib(self, tmp_path: Path) -> None:
        """When output exceeds 64 KiB, only the tail is retained."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")

        # Generate ~100 KiB of output (1000 lines × ~100 bytes each).
        lines = [f"LINE[{i:06d}] " + "X" * 90 + "\n" for i in range(1000)]
        mock_proc = _fake_popen(lines, returncode=0)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        output_tail = row["output_tail"]
        assert output_tail is not None
        assert len(output_tail) <= 64 * 1024
        # Early lines should be gone.
        assert "LINE[000000]" not in output_tail
        # Late lines should be present.
        assert "LINE[000999]" in output_tail

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------

    def test_redis_publish_called_per_line(self, tmp_path: Path) -> None:
        """Each output line triggers an XADD call to Redis."""
        mock_config = _make_mock_config(tmp_path)
        _insert_decision_row(mock_config.indexer.db_path, decision_id=self.DECISION_ID, status="pending")
        lines = ["a\n", "b\n", "c\n"]
        mock_proc = _fake_popen(lines, returncode=0)
        mock_redis = MagicMock()

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=mock_redis),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        assert mock_redis.xadd.call_count == 3

        # Verify the envelope shape for the first call.
        first_call_args = mock_redis.xadd.call_args_list[0]
        pos_args, kwargs = first_call_args
        fields = pos_args[1]
        envelope = json.loads(fields["envelope"])
        assert envelope["_type"] == "maintenance.run_log"
        assert envelope["data"]["run_uid"] == self.RUN_UID
        assert envelope["data"]["line"] == "a\n"
        assert envelope["data"]["seq"] == 0
        assert fields["type"] == "maintenance.run_log"
        assert kwargs["maxlen"] == 10000

    def test_redis_failure_does_not_crash_runner(self, tmp_path: Path) -> None:
        """When Redis raises, the runner still completes and finalizes the row."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")
        mock_proc = _fake_popen(["output\n"], returncode=0)
        mock_redis = MagicMock()
        mock_redis.xadd.side_effect = ConnectionError("redis down")

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=mock_redis),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row["outcome"] == "success"
        assert row["output_tail"] == "output\n"

    def test_redis_disabled_config_skips_publish(self, tmp_path: Path) -> None:
        """When web.enabled is False, no Redis connection is created."""
        mock_config = _make_mock_config(tmp_path)
        _insert_decision_row(mock_config.indexer.db_path, decision_id=self.DECISION_ID, status="pending")
        mock_config.web.enabled = False
        mock_proc = _fake_popen(["output\n"], returncode=0)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()
        assert exc_info.value.code == 0

    # ------------------------------------------------------------------
    # Config failure
    # ------------------------------------------------------------------

    def test_config_load_failure_exits_2(self, tmp_path: Path) -> None:
        """When load_config raises, the runner exits with code 2."""
        _insert_decision_row(
            _make_mock_config(tmp_path).indexer.db_path,
            decision_id=self.DECISION_ID,
            status="pending",
        )
        with (
            patch(
                "personalscraper.web.decisions.runner.load_config",
                side_effect=RuntimeError("no config"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()
        assert exc_info.value.code == 2

    # ------------------------------------------------------------------
    # Popen OSError
    # ------------------------------------------------------------------

    def test_popen_oserror_finalizes_error_and_exits_2(self, tmp_path: Path) -> None:
        """When Popen raises OSError, the row is finalized with error and exit 2."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch(
                "personalscraper.web.decisions.runner.subprocess.Popen",
                side_effect=OSError("spawn failed"),
            ),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 2
        row = _select_row(db_path, self.RUN_UID)
        assert row["outcome"] == "error"
        assert "spawn failed" in row["error"]


# ---------------------------------------------------------------------------
# Tests — Finding A: the row is never left 'running' on failure / SIGTERM
# ---------------------------------------------------------------------------


class TestRunnerFinalizeGuards:
    """Finding A — insert→stream→finalize is guarded; the row never stays 'running'."""

    RUN_UID = "guard-uid-000222"
    DECISION_ID = 1
    PROVIDER = "tmdb"
    PROVIDER_ID = 4242

    @pytest.fixture(autouse=True)
    def _env_setup_teardown(self) -> None:
        """Set mandatory env vars before each test and clean up after."""
        _set_runner_env(self.RUN_UID, self.DECISION_ID, self.PROVIDER, self.PROVIDER_ID)
        yield
        _clear_runner_env()

    def test_stream_exception_finalizes_error_not_running(self, tmp_path: Path) -> None:
        """An exception raised mid-stream finalizes the row 'error', never 'running'."""
        from personalscraper.web.decisions import runner as runner_mod

        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")
        mock_proc = _fake_popen(["l1\n", "l2\n", "l3\n"], returncode=0)

        original_append = runner_mod._RingBuffer.append
        state = {"n": 0}

        def boom(self: runner_mod._RingBuffer, line: str) -> None:
            state["n"] += 1
            if state["n"] == 2:
                raise RuntimeError("mid-stream boom")
            original_append(self, line)

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            patch.object(runner_mod._RingBuffer, "append", boom),
            pytest.raises(SystemExit) as exc_info,
        ):
            runner_mod.main()

        assert exc_info.value.code == 1
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["outcome"] == "error"
        assert row["outcome"] != "running"
        assert row["ended_at"] is not None

    def test_sigterm_handler_registered_and_finalizes_killed(self, tmp_path: Path) -> None:
        """The runner installs a SIGTERM handler that kills the child + finalizes 'killed'."""
        import signal as _signal

        from personalscraper.web.decisions import runner as runner_mod

        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(db_path, decision_id=self.DECISION_ID, status="pending")
        mock_proc = _fake_popen(["out\n"], returncode=0)

        captured: dict[int, object] = {}

        def fake_signal(sig: int, handler: object) -> None:
            captured[sig] = handler

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            patch("personalscraper.web.decisions.runner.signal.signal", fake_signal),
            pytest.raises(SystemExit) as exc_info,
        ):
            runner_mod.main()

        # main() completes normally, but the SIGTERM handler was registered.
        assert exc_info.value.code == 0
        assert _signal.SIGTERM in captured
        handler = captured[_signal.SIGTERM]
        assert callable(handler)

        # Invoke the captured handler to simulate a SIGTERM delivery.
        with (
            patch("personalscraper.web.decisions.runner.os._exit") as mock_exit,
            patch("personalscraper.web.decisions.runner._kill_child_group") as mock_kill,
        ):
            handler(_signal.SIGTERM, None)

        mock_kill.assert_called_once()
        mock_exit.assert_called_once_with(143)
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["outcome"] == "killed"

    def test_main_does_not_leak_sigterm_handler_into_worker(self, tmp_path: Path) -> None:
        """Regression: an in-process ``main()`` must not leave a ``SIGTERM`` handler installed.

        ``main()`` registers a handler that calls ``os._exit``; leaked into a
        pytest-xdist worker it fires when xdist / the CI runner later sends the
        worker ``SIGTERM`` at shutdown, killing it abruptly (green locally, but
        it cancels the whole ``test`` job on Linux CI: "runner received a
        shutdown signal"). The dir-level autouse ``conftest`` fixture neutralizes
        ``signal.signal`` so the worker's disposition survives — this asserts it.
        """
        import signal as _signal

        from personalscraper.web.decisions import runner as runner_mod

        mock_config = _make_mock_config(tmp_path)
        _insert_decision_row(
            mock_config.indexer.db_path,
            decision_id=self.DECISION_ID,
            status="pending",
        )
        mock_proc = _fake_popen(["ok\n"], returncode=0)

        before = _signal.getsignal(_signal.SIGTERM)
        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit),
        ):
            runner_mod.main()

        after = _signal.getsignal(_signal.SIGTERM)
        assert after == before, (
            "main() leaked a SIGTERM handler into the worker — the conftest signal.signal neutralization is not active"
        )


# ---------------------------------------------------------------------------
# Tests — R11: pipeline.lock is NEVER acquired by the decisions runner
# ---------------------------------------------------------------------------


class TestRunnerPipelineLock:
    """R11 / webui-ux phase 4 — the decisions runner never acquires ``pipeline.lock``.

    ``scrape-resolve`` self-acquires its own lock for its lifetime — now a
    per-staging-item scrape lock (not the global ``pipeline.lock``, which it only
    read-checks). The runner must NOT acquire the global ``pipeline.lock`` —
    doing so would make the child observe the runner's live pid and back off.
    """

    RUN_UID = "lock-uid-000333"
    DECISION_ID = 1
    PROVIDER = "tmdb"
    PROVIDER_ID = 4242

    @pytest.fixture(autouse=True)
    def _env_teardown(self) -> None:
        """Clear the runner env vars after each test (tests set their own)."""
        yield
        _clear_runner_env()

    def _run_main(self, mock_config: MagicMock, mock_proc: MagicMock) -> SystemExit:
        """Invoke ``main()`` with config/Popen/Redis patched; return the exit."""
        from personalscraper.web.decisions import runner as runner_mod

        with (
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch(
                "personalscraper.web.decisions.runner.subprocess.Popen",
                return_value=mock_proc,
            ),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            runner_mod.main()
        return exc_info.value

    def test_runner_never_calls_acquire_lock(self, tmp_path: Path) -> None:
        """The decisions runner must never touch pipeline.lock (scrape-resolve self-acquires)."""
        _set_runner_env(self.RUN_UID, self.DECISION_ID, self.PROVIDER, self.PROVIDER_ID)
        mock_config = _make_mock_config(tmp_path)
        _insert_decision_row(
            mock_config.indexer.db_path,
            decision_id=self.DECISION_ID,
            status="pending",
        )
        mock_proc = _fake_popen(["ok\n"], returncode=0)

        with patch("personalscraper.web.decisions.runner.AcquireLockError", create=True):
            pass  # no-op — just ensure the module doesn't import lock utilities

        with patch("personalscraper.lock.acquire_lock") as mock_acquire:
            exit_exc = self._run_main(mock_config, mock_proc)

        assert exit_exc.code == 0
        mock_acquire.assert_not_called()

    def test_runner_does_not_import_acquire_lock(self) -> None:
        """The decisions runner module must not import or call acquire_lock.

        The only allowed references to acquire_lock are in the module docstring
        (R11 explanation). Check for actual import/call patterns in the source,
        not mere mentions in documentation.
        """
        import inspect

        from personalscraper.web.decisions import runner as runner_mod

        source = inspect.getsource(runner_mod)
        # Among code lines, only look for import/call patterns.
        violations = [
            line.strip()
            for line in source.split("\n")
            if "acquire_lock" in line
            and not line.strip().startswith(("#", '"', "'"))
            and ("import" in line or "acquire_lock(" in line)
        ]
        assert not violations, f"Runner source must not import/call acquire_lock; found: {violations}"
