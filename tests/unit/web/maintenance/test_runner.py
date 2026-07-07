"""Unit tests for :func:`personalscraper.web.maintenance.runner.main`.

Sub-phase 3.3 — covers the runner lifecycle: env reading, pipeline_run row
insert/finalize, CLI argv building, output streaming (ring buffer + Redis),
and fail-soft behaviour.

Mocking: ``subprocess.Popen`` (fake stdout + rc), ``redis.Redis.from_url``
(mock client), ``load_config`` (temp DB path). Uses a real on-disk SQLite DB
with the pipeline_run schema (migrations 011 + 012) so row assertions are
against a genuine sqlite3 connection.
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
# Helpers — DB setup (migrations 011 + 012)
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


def _create_db(db_path: Path) -> None:
    """Create an on-disk SQLite DB with the ``pipeline_run`` table."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.executescript(PIPELINE_RUN_DDL)
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


def _make_mock_config(tmp_path: Path) -> MagicMock:
    """Build a mock ``Config`` with a real DB path and dummy web config."""
    db_path = tmp_path / "library.db"
    _create_db(db_path)
    config = MagicMock()
    config.indexer.db_path = db_path
    config.web.enabled = True
    config.web.redis_url = "redis://127.0.0.1:6379/0"
    config.web.stream_key = "test:events"
    config.web.stream_maxlen = 10000
    return config


def _set_runner_env(run_uid: str, command: str, options_json: str, dry_run: bool) -> None:
    """Set the four mandatory env vars for the runner."""
    os.environ["PERSONALSCRAPER_RUN_UID"] = run_uid
    os.environ["PERSONALSCRAPER_MAINT_COMMAND"] = command
    os.environ["PERSONALSCRAPER_MAINT_OPTIONS_JSON"] = options_json
    os.environ["PERSONALSCRAPER_MAINT_DRY_RUN"] = "1" if dry_run else "0"


def _clear_runner_env() -> None:
    """Remove the runner env vars."""
    for var in (
        "PERSONALSCRAPER_RUN_UID",
        "PERSONALSCRAPER_MAINT_COMMAND",
        "PERSONALSCRAPER_MAINT_OPTIONS_JSON",
        "PERSONALSCRAPER_MAINT_DRY_RUN",
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

    def test_missing_all_env_exits_2(self, tmp_path: Path) -> None:
        """When no env vars are set, the runner exits with code 2."""
        _clear_runner_env()
        with pytest.raises(SystemExit) as exc_info:
            from personalscraper.web.maintenance.runner import _read_mandatory_env

            _read_mandatory_env()
        assert exc_info.value.code == 2

    def test_partial_env_exits_2(self, tmp_path: Path) -> None:
        """When only some env vars are set, the runner exits with code 2."""
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid"
        with pytest.raises(SystemExit) as exc_info:
            from personalscraper.web.maintenance.runner import _read_mandatory_env

            _read_mandatory_env()
        assert exc_info.value.code == 2
        _clear_runner_env()


# ---------------------------------------------------------------------------
# Tests — action resolution
# ---------------------------------------------------------------------------


class TestActionResolution:
    """Runner exits 2 when the command is not in the registry."""

    def test_unknown_action_exits_2(self) -> None:
        """An action not in REGISTRY causes exit code 2."""
        from personalscraper.web.maintenance.runner import _resolve_action

        with pytest.raises(SystemExit) as exc_info:
            _resolve_action("library-nonexistent")
        assert exc_info.value.code == 2

    def test_known_action_returns_entry(self) -> None:
        """A known action returns the matching MaintenanceAction."""
        from personalscraper.web.maintenance.runner import _resolve_action

        action = _resolve_action("library-clean")
        assert action.id == "library-clean"
        assert action.risk == "destructive"


# ---------------------------------------------------------------------------
# Tests — CLI argv building
# ---------------------------------------------------------------------------


class TestBuildArgv:
    """CLI argument vector covers positional, flags, bool, and dry-run styles."""

    def test_base_argv_starts_with_executable_and_module(self) -> None:
        """The argv always starts with [sys.executable, -m, personalscraper, <id>]."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-gc")
        argv = _build_argv(action, "{}", dry_run=False)
        assert argv[0] == sys.executable
        assert argv[1] == "-m"
        assert argv[2] == "personalscraper"
        assert argv[3] == "library-gc"

    def test_positional_required_option(self) -> None:
        """Required options become positional arguments (no --flag prefix)."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-search")  # query is required
        argv = _build_argv(action, json.dumps({"query": "hello world"}), dry_run=False)
        assert "hello world" in argv
        assert "--query" not in argv

    def test_optional_str_flag(self) -> None:
        """Optional str options become --name value."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-clean")  # disk is optional str
        argv = _build_argv(action, json.dumps({"disk": "Disk1"}), dry_run=False)
        idx = argv.index("--disk")
        assert argv[idx + 1] == "Disk1"

    def test_optional_bool_true_appends_flag(self) -> None:
        """Bool True → --flag; bool False → omitted."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-backfill-ids")  # ids-only is optional bool
        argv = _build_argv(action, json.dumps({"ids-only": True}), dry_run=False)
        assert "--ids-only" in argv

    def test_optional_bool_false_omitted(self) -> None:
        """Bool False → not present in argv."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-backfill-ids")
        argv = _build_argv(action, json.dumps({"ids-only": False}), dry_run=False)
        assert "--ids-only" not in argv

    def test_dry_run_flag_style_adds_flag(self) -> None:
        """Flag-style commands add --dry-run when DRY_RUN=1."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-index")  # flag style
        argv = _build_argv(action, "{}", dry_run=True)
        assert "--dry-run" in argv

    def test_dry_run_flag_style_omits_when_false(self) -> None:
        """Flag-style commands omit --dry-run when DRY_RUN=0 (already default)."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-index")
        argv = _build_argv(action, "{}", dry_run=False)
        assert "--dry-run" not in argv

    def test_dry_run_apply_style_omits_when_dry(self) -> None:
        """Apply-style commands add nothing when DRY_RUN=1 (default is dry-run)."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-clean")  # apply style
        argv = _build_argv(action, "{}", dry_run=True)
        assert "--apply" not in argv

    def test_dry_run_apply_style_adds_apply_when_not_dry(self) -> None:
        """Apply-style commands add --apply when DRY_RUN=0."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-clean")
        argv = _build_argv(action, "{}", dry_run=False)
        assert "--apply" in argv

    def test_unsupported_dry_run_omits_all_flags(self) -> None:
        """When dry_run='unsupported', no dry-run/apply flag is added."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-status")  # dry_run='unsupported'
        argv_true = _build_argv(action, "{}", dry_run=True)
        argv_false = _build_argv(action, "{}", dry_run=False)
        assert "--dry-run" not in argv_true
        assert "--apply" not in argv_true
        assert "--dry-run" not in argv_false
        assert "--apply" not in argv_false

    # ── Finding B — library-validate apply requires --fix ──────────────────

    def test_library_validate_apply_emits_fix_and_apply(self) -> None:
        """library-validate apply run emits BOTH --fix and --apply (Finding B).

        The CLI enforces ``--apply requires --fix``; without --fix the apply
        run exits 1, so a dashboard apply of library-validate always failed.
        """
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-validate")
        apply_argv = _build_argv(action, "{}", dry_run=False)
        assert "--fix" in apply_argv
        assert "--apply" in apply_argv

    def test_library_validate_dry_run_emits_neither_flag(self) -> None:
        """library-validate dry-run (the bare validation report) emits neither flag."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-validate")
        dry_argv = _build_argv(action, "{}", dry_run=True)
        assert "--fix" not in dry_argv
        assert "--apply" not in dry_argv

    def test_other_apply_command_does_not_get_fix(self) -> None:
        """A non-validate apply-style command (library-clean) gets --apply but NOT --fix."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-clean")
        apply_argv = _build_argv(action, "{}", dry_run=False)
        assert "--apply" in apply_argv
        assert "--fix" not in apply_argv

    # ── Finding H — positional flag-injection hardening ────────────────────

    def test_required_positional_placed_after_double_dash(self) -> None:
        """A required value beginning with '-' is passed after ``--`` (Finding H).

        The ``--`` sentinel prevents click from reparsing a positional value
        like ``--config=/x`` as an option.
        """
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-search")  # query is a required positional
        argv = _build_argv(action, json.dumps({"query": "--config=/x"}), dry_run=False)
        assert "--" in argv
        assert "--config=/x" in argv
        assert argv.index("--") < argv.index("--config=/x")

    def test_no_double_dash_when_no_positionals(self) -> None:
        """Commands without required positionals get no bare ``--`` sentinel."""
        from personalscraper.web.maintenance.runner import _build_argv, _resolve_action

        action = _resolve_action("library-clean")  # no required positionals
        argv = _build_argv(action, "{}", dry_run=True)
        assert "--" not in argv


# ---------------------------------------------------------------------------
# Tests — ring buffer
# ---------------------------------------------------------------------------


class TestRingBuffer:
    """Append-only ring buffer with byte-cap eviction."""

    def test_append_then_to_str(self) -> None:
        """Appended lines are concatenated in FIFO order."""
        from personalscraper.web.maintenance.runner import _RingBuffer

        rb = _RingBuffer(max_bytes=1024)
        rb.append("line1\n")
        rb.append("line2\n")
        assert rb.to_str() == "line1\nline2\n"

    def test_eviction_when_over_cap(self) -> None:
        """Oldest lines are evicted when total size exceeds max_bytes."""
        from personalscraper.web.maintenance.runner import _RingBuffer

        rb = _RingBuffer(max_bytes=20)
        rb.append("a" * 10 + "\n")  # 11 bytes
        rb.append("b" * 10 + "\n")  # 11 bytes, total 22 → first line evicted
        rb.append("c" * 5 + "\n")  # 6 bytes
        result = rb.to_str()
        # First 11-byte line should be gone.
        assert "a" * 10 not in result
        assert "b" * 10 in result


# ---------------------------------------------------------------------------
# Tests — full runner lifecycle (integration-style with mocks)
# ---------------------------------------------------------------------------


class TestRunnerLifecycle:
    """End-to-end runner tests with mocked subprocess and Redis."""

    RUN_UID = "abc123def456"
    COMMAND = "library-gc"
    OPTIONS_JSON = json.dumps({"older-than-days": 60}, sort_keys=True, separators=(",", ":"))

    @pytest.fixture(autouse=True)
    def _env_setup_teardown(self) -> None:
        """Set mandatory env vars before each test and clean up after."""
        _set_runner_env(self.RUN_UID, self.COMMAND, self.OPTIONS_JSON, dry_run=False)
        yield
        _clear_runner_env()

    # ------------------------------------------------------------------
    # Row lifecycle
    # ------------------------------------------------------------------

    def test_insert_creates_row_with_kind_command_options_json(self, tmp_path: Path) -> None:
        """After insert() the row has kind='maintenance', command, options_json."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        mock_proc = _fake_popen(["output line\n"], returncode=0)

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["kind"] == "maintenance"
        assert row["command"] == self.COMMAND
        assert row["options_json"] == self.OPTIONS_JSON
        assert row["trigger"] == "web"
        assert row["pid"] is not None

    def test_final_outcome_success_on_rc_0(self, tmp_path: Path) -> None:
        """Exit code 0 → outcome='success'."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        mock_proc = _fake_popen(["ok\n"], returncode=0)

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

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
        stderr_output = ["Traceback (most recent call last):\n", "ValueError: bad input\n"]
        mock_proc = _fake_popen(stderr_output, returncode=1)

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

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
        lines = [f"line {i:04d}\n" for i in range(10)]
        mock_proc = _fake_popen(lines, returncode=0)

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

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

        # Generate ~100 KiB of output (1000 lines × ~100 bytes each).
        lines = [f"LINE[{i:06d}] " + "X" * 90 + "\n" for i in range(1000)]
        mock_proc = _fake_popen(lines, returncode=0)

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

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
        lines = ["a\n", "b\n", "c\n"]
        mock_proc = _fake_popen(lines, returncode=0)
        mock_redis = MagicMock()

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=mock_redis),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 0
        assert mock_redis.xadd.call_count == 3

        # Verify the envelope shape for the first call.
        first_call_args = mock_redis.xadd.call_args_list[0]
        # call_args = ((stream_key, fields_dict), {maxlen: ..., approximate: ...})
        pos_args, kwargs = first_call_args
        fields = pos_args[1]  # second positional arg is the fields dict
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
        mock_proc = _fake_popen(["output\n"], returncode=0)
        mock_redis = MagicMock()
        mock_redis.xadd.side_effect = ConnectionError("redis down")

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=mock_redis),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row["outcome"] == "success"
        assert row["output_tail"] == "output\n"

    def test_redis_disabled_config_skips_publish(self, tmp_path: Path) -> None:
        """When web.enabled is False, no Redis connection is created."""
        mock_config = _make_mock_config(tmp_path)
        mock_config.web.enabled = False
        mock_proc = _fake_popen(["output\n"], returncode=0)

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()
        assert exc_info.value.code == 0
        # If we got here without error, the test passes — Redis was never
        # touched because _get_redis returns None when web.enabled=False.

    # ------------------------------------------------------------------
    # Config failure
    # ------------------------------------------------------------------

    def test_config_load_failure_exits_2(self, tmp_path: Path) -> None:
        """When load_config raises, the runner exits with code 2."""
        with (
            patch("personalscraper.web.maintenance.runner.load_config", side_effect=RuntimeError("no config")),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()
        assert exc_info.value.code == 2

    # ------------------------------------------------------------------
    # Popen OSError
    # ------------------------------------------------------------------

    def test_popen_oserror_finalizes_error_and_exits_2(self, tmp_path: Path) -> None:
        """When Popen raises OSError, the row is finalized with error and exit 2."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", side_effect=OSError("spawn failed")),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

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

    RUN_UID = "guard-uid-000111"
    COMMAND = "library-gc"
    OPTIONS_JSON = json.dumps({"older-than-days": 30}, sort_keys=True, separators=(",", ":"))

    @pytest.fixture(autouse=True)
    def _env_setup_teardown(self) -> None:
        """Set mandatory env vars before each test and clean up after."""
        _set_runner_env(self.RUN_UID, self.COMMAND, self.OPTIONS_JSON, dry_run=False)
        yield
        _clear_runner_env()

    def test_stream_exception_finalizes_error_not_running(self, tmp_path: Path) -> None:
        """An exception raised mid-stream finalizes the row 'error', never 'running'."""
        from personalscraper.web.maintenance import runner as runner_mod

        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        mock_proc = _fake_popen(["l1\n", "l2\n", "l3\n"], returncode=0)

        original_append = runner_mod._RingBuffer.append
        state = {"n": 0}

        def boom(self: runner_mod._RingBuffer, line: str) -> None:
            state["n"] += 1
            if state["n"] == 2:
                raise RuntimeError("mid-stream boom")
            original_append(self, line)

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
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

        from personalscraper.web.maintenance import runner as runner_mod

        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        mock_proc = _fake_popen(["out\n"], returncode=0)

        captured: dict[int, object] = {}

        def fake_signal(sig: int, handler: object) -> None:
            captured[sig] = handler

        with (
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner.subprocess.Popen", return_value=mock_proc),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            patch("personalscraper.web.maintenance.runner.signal.signal", fake_signal),
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
            patch("personalscraper.web.maintenance.runner.os._exit") as mock_exit,
            patch("personalscraper.web.maintenance.runner._kill_child_group") as mock_kill,
        ):
            handler(_signal.SIGTERM, None)

        mock_kill.assert_called_once()
        mock_exit.assert_called_once_with(143)
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["outcome"] == "killed"
