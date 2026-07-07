"""Integration tests for :func:`personalscraper.web.maintenance.runner.main`.

Sub-phase 3.4 — end-to-end lifecycle: real ``main()`` in-process, real child
subprocess, real on-disk SQLite DB with the ``pipeline_run`` schema, fake Redis.

Each test monkeypatches ``_build_argv`` to return a trivial command
(``sys.executable -c "..."``) so the child is deterministic and fast.
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
# Helpers — DB setup
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


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestRunnerLifecycleIntegration:
    """End-to-end runner lifecycle with a real child subprocess.

    Each test monkeypatches ``_build_argv`` to return a trivial Python one-liner
    instead of the real ``personalscraper`` CLI, so the child process is fast and
    deterministic.  The runner main() is called in-process with a real tmp SQLite
    DB and a fake (mocked) Redis client.
    """

    RUN_UID = "lifecycle-test-uid-0001"
    COMMAND = "library-gc"
    OPTIONS = {"older-than-days": 30}
    OPTIONS_JSON = json.dumps(OPTIONS, sort_keys=True, separators=(",", ":"))

    @pytest.fixture(autouse=True)
    def _env_setup_teardown(self) -> None:
        """Set mandatory env vars before each test and clean up after."""
        _set_runner_env(self.RUN_UID, self.COMMAND, self.OPTIONS_JSON, dry_run=False)
        yield
        _clear_runner_env()

    # ── Trivial argv builder helper ────────────────────────────────────────

    @staticmethod
    def _trivial_argv(code: str) -> list[str]:
        """Return an argv that runs *code* as a Python one-liner."""
        return [sys.executable, "-c", code]

    # ── Lifecycle: success ─────────────────────────────────────────────────

    def test_lifecycle_success(self, tmp_path: Path) -> None:
        """Real child prints two lines and exits 0 → outcome='success', output_tail captured.

        Verifies every field the plan specifies: kind='maintenance', command, canonical
        options_json round-trips, outcome='success', ended_at set, output_tail contains
        both lines, pid set.
        """
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        child_code = "print('line1'); print('line2')"
        argv = self._trivial_argv(child_code)

        with (
            patch(
                "personalscraper.web.maintenance.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.maintenance.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.maintenance.runner._get_redis",
                return_value=None,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None, "pipeline_run row must be inserted"

        # Metadata fields.
        assert row["kind"] == "maintenance"
        assert row["command"] == self.COMMAND
        assert row["trigger"] == "web"
        assert row["pid"] is not None
        assert isinstance(row["pid"], int)

        # options_json round-trip: the stored JSON must deserialize to the input.
        assert row["options_json"] == self.OPTIONS_JSON
        assert json.loads(row["options_json"]) == self.OPTIONS

        # Outcome.
        assert row["outcome"] == "success"
        assert row["ended_at"] is not None
        assert row["error"] is None

        # output_tail.
        assert row["output_tail"] is not None
        assert "line1" in row["output_tail"]
        assert "line2" in row["output_tail"]

    # ── Lifecycle: error ───────────────────────────────────────────────────

    def test_lifecycle_error(self, tmp_path: Path) -> None:
        """Child exits 3 after printing → outcome='error', error tail captured, rc=3."""
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        child_code = "import sys; print('before crash'); print('BOOM'); sys.exit(3)"
        argv = self._trivial_argv(child_code)

        with (
            patch(
                "personalscraper.web.maintenance.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.maintenance.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.maintenance.runner._get_redis",
                return_value=None,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 3
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None

        assert row["outcome"] == "error"
        assert row["ended_at"] is not None
        assert row["error"] is not None
        # The error tail should contain the last portion of output.
        assert "BOOM" in row["error"]
        assert "before crash" in row["error"]
        # output_tail should still have the full output.
        assert row["output_tail"] is not None
        assert "before crash" in row["output_tail"]

    # ── Lifecycle: non-UTF-8 output (Finding A) ────────────────────────────

    def test_lifecycle_non_utf8_output(self, tmp_path: Path) -> None:
        """A non-UTF-8 byte in the child output does not crash the runner.

        The library has NFD / NTFS-via-macFUSE filenames that produce non-UTF-8
        bytes on stdout. ``errors='replace'`` decodes them to the replacement
        char so the streaming loop never raises ``UnicodeDecodeError``; the row
        finalizes with a real outcome (success), never left 'running'.
        """
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        child_code = r"import sys; sys.stdout.buffer.write(b'good\xff\xfebad\n'); sys.stdout.flush()"
        argv = self._trivial_argv(child_code)

        with (
            patch("personalscraper.web.maintenance.runner._build_argv", return_value=argv),
            patch("personalscraper.web.maintenance.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.maintenance.runner._get_redis", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["outcome"] != "running"
        assert row["outcome"] == "success"
        assert row["output_tail"] is not None

    # ── Lifecycle: Redis down (fail-soft) ──────────────────────────────────

    def test_lifecycle_redis_down(self, tmp_path: Path) -> None:
        """Redis xadd raises ConnectionError → both lines still consumed, row finalizes success.

        Fail-soft verified end-to-end: the runner must NOT crash when Redis is
        unreachable.  Every output line is still captured in output_tail.
        """
        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        child_code = "print('lineA'); print('lineB')"
        argv = self._trivial_argv(child_code)

        mock_redis = MagicMock()
        mock_redis.xadd.side_effect = ConnectionError("redis down")

        with (
            patch(
                "personalscraper.web.maintenance.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.maintenance.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.maintenance.runner._get_redis",
                return_value=mock_redis,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["outcome"] == "success", "fail-soft: Redis down must not affect outcome"
        assert row["output_tail"] is not None
        assert "lineA" in row["output_tail"]
        assert "lineB" in row["output_tail"]

        # xadd was called (and raised) for each line.
        assert mock_redis.xadd.call_count >= 2

    # ── Canonical options_json round-trip ──────────────────────────────────

    def test_canonical_options_roundtrip(self, tmp_path: Path) -> None:
        """canonical_options_json(input) → row.options_json → json.loads == input.

        Uses :func:`canonical_options_json` from the registry module to produce the
        stored form, then verifies the full round-trip through the runner lifecycle.
        """
        from personalscraper.web.maintenance.registry import canonical_options_json

        input_options = {"budget": 60, "disk": "Disk1"}
        canonical = canonical_options_json(input_options)
        # Sanity: canonical form has no spaces, sorted keys.
        assert canonical == '{"budget":60,"disk":"Disk1"}'

        # Override env for this test with custom options.
        os.environ["PERSONALSCRAPER_MAINT_OPTIONS_JSON"] = canonical
        # Also use a different command so _resolve_action doesn't fail on
        # nonexistent options.
        os.environ["PERSONALSCRAPER_MAINT_COMMAND"] = "library-repair"

        mock_config = _make_mock_config(tmp_path)
        db_path = mock_config.indexer.db_path
        child_code = "print('roundtrip-ok')"
        argv = self._trivial_argv(child_code)

        with (
            patch(
                "personalscraper.web.maintenance.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.maintenance.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.maintenance.runner._get_redis",
                return_value=None,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.maintenance.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["options_json"] == canonical
        # Full round-trip: stored JSON deserializes to the original input.
        assert json.loads(row["options_json"]) == input_options

        _clear_runner_env()
