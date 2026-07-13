"""Integration tests for :func:`personalscraper.web.decisions.runner.main`.

Sub-phase 5.1 — end-to-end lifecycle: real ``main()`` in-process, real child
subprocess, real on-disk SQLite DB with the ``pipeline_run`` and ``scrape_decision``
schemas, fake Redis.

Each test monkeypatches ``_build_argv`` to return a trivial command
(``sys.executable -c "..."``) so the child is deterministic and fast.

Mirrors ``tests/unit/web/maintenance/test_runner_lifecycle.py``, adapted for
the decisions-runner contract: four env vars, ``scrape_decision`` row lookup,
no pipeline-lock acquisition (``scrape-resolve`` self-acquires — R11).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
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
    """Create an on-disk SQLite DB with the ``pipeline_run`` and ``scrape_decision`` tables."""
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
    decision_id: int,
    staging_path: str,
    status: str = "pending",
    media_kind: str = "movie",
    extracted_title: str = "Test Item",
    trigger: str = "mid_band",
) -> None:
    """Insert a ``scrape_decision`` row with the given *decision_id*."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    now = time.time()
    conn.execute(
        "INSERT INTO scrape_decision "
        '(id, staging_path, media_kind, extracted_title, "trigger", '
        "candidates_json, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, '[]', ?, ?, ?)",
        (decision_id, staging_path, media_kind, extracted_title, trigger, status, now, now),
    )
    conn.commit()
    conn.close()


def _make_mock_config(tmp_path: Path, staging_dir: Path | None = None) -> MagicMock:
    """Build a mock ``Config`` with a real DB path and dummy web config.

    Args:
        tmp_path: Pytest temporary directory (unique per test).
        staging_dir: Optional staging directory path; if ``None``, a default
            ``tmp_path / "staging"`` is created and used.

    Returns:
        A ``MagicMock`` with ``indexer.db_path``, ``paths.data_dir``, and
        ``web.*`` attributes set to real values so the runner can open the DB
        and create Redis connections.
    """
    if staging_dir is None:
        staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
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


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestRunnerLifecycleIntegration:
    """End-to-end runner lifecycle with a real child subprocess.

    Each test monkeypatches ``_build_argv`` to return a trivial Python one-liner
    instead of the real ``personalscraper scrape-resolve`` CLI, so the child
    process is fast and deterministic.  The runner ``main()`` is called in-process
    with a real tmp SQLite DB and a fake (mocked) Redis client.
    """

    RUN_UID = "lifecycle-test-uid-0001"
    DECISION_ID = 1
    PROVIDER = "tmdb"
    PROVIDER_ID = 4242

    @pytest.fixture(autouse=True)
    def _env_setup_teardown(self) -> None:
        """Set mandatory env vars before each test and clean up after."""
        _set_runner_env(self.RUN_UID, self.DECISION_ID, self.PROVIDER, self.PROVIDER_ID)
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

        Verifies every field the plan specifies: kind='maintenance',
        command='scrape-resolve', canonical options_json round-trips,
        outcome='success', ended_at set, output_tail contains both lines,
        pid set.
        """
        staging_dir = tmp_path / "staging" / "test-item"
        staging_dir.mkdir(parents=True)
        mock_config = _make_mock_config(tmp_path, staging_dir=staging_dir)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(
            db_path,
            decision_id=self.DECISION_ID,
            staging_path=str(staging_dir.resolve()),
        )
        child_code = "print('line1'); print('line2')"
        argv = self._trivial_argv(child_code)

        with (
            patch(
                "personalscraper.web.decisions.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.decisions.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.decisions.runner._get_redis",
                return_value=None,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None, "pipeline_run row must be inserted"

        # Metadata fields.
        assert row["kind"] == "maintenance"
        assert row["command"] == "scrape-resolve"
        assert row["trigger"] == "web"
        assert row["pid"] is not None
        assert isinstance(row["pid"], int)

        # options_json round-trip: the stored JSON must carry the decision fields.
        assert row["options_json"] is not None
        options = json.loads(row["options_json"])
        assert options["decision_id"] == self.DECISION_ID
        assert options["provider"] == self.PROVIDER
        assert options["provider_id"] == self.PROVIDER_ID

        # Outcome.
        assert row["outcome"] == "success"
        assert row["ended_at"] is not None
        assert row["error"] is None

        # output_tail.
        assert row["output_tail"] is not None
        assert "line1" in row["output_tail"]
        assert "line2" in row["output_tail"]

    def test_success_triggers_pipeline_continuation(self, tmp_path: Path) -> None:
        """§4 — a successful resolve triggers a pipeline continuation run.

        Resolving must not stop at the NFO: the runner reuses the single trigger
        authority (``spawn_pipeline_run``) so the media finishes trailers → verify →
        dispatch. Guards that the continuation fires on rc==0, tagged 'scrape-resolve'.
        Fails on the old implementation, which stopped after marking the decision
        resolved and left the media stranded in staging.
        """
        staging_dir = tmp_path / "staging" / "test-item"
        staging_dir.mkdir(parents=True)
        mock_config = _make_mock_config(tmp_path, staging_dir=staging_dir)
        _insert_decision_row(
            mock_config.indexer.db_path,
            decision_id=self.DECISION_ID,
            staging_path=str(staging_dir.resolve()),
        )
        argv = self._trivial_argv("print('ok')")

        with (
            patch("personalscraper.web.decisions.runner._build_argv", return_value=argv),
            patch("personalscraper.web.decisions.runner.load_config", return_value=mock_config),
            patch("personalscraper.web.decisions.runner._get_redis", return_value=None),
            patch(
                "personalscraper.web.pipeline_trigger.spawn_pipeline_run",
                return_value="cont-uid",
            ) as mock_spawn,
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        mock_spawn.assert_called_once()
        assert mock_spawn.call_args.kwargs["trigger_reason"] == "scrape-resolve"

    # ── Lifecycle: error ───────────────────────────────────────────────────

    def test_lifecycle_error(self, tmp_path: Path) -> None:
        """Child exits 3 after printing → outcome='error', error tail captured, rc=3.

        The decision row stays 'pending' — a failed scrape-resolve does not
        resolve the decision.
        """
        staging_dir = tmp_path / "staging" / "test-item"
        staging_dir.mkdir(parents=True)
        mock_config = _make_mock_config(tmp_path, staging_dir=staging_dir)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(
            db_path,
            decision_id=self.DECISION_ID,
            staging_path=str(staging_dir.resolve()),
        )
        child_code = "import sys; print('before crash'); print('BOOM'); sys.exit(3)"
        argv = self._trivial_argv(child_code)

        with (
            patch(
                "personalscraper.web.decisions.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.decisions.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.decisions.runner._get_redis",
                return_value=None,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

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

        # Decision row must stay pending.
        decision = _select_decision_row(db_path, self.DECISION_ID)
        assert decision is not None
        assert decision["status"] == "pending"

    # ── Lifecycle: SIGTERM → 'killed' ──────────────────────────────────────

    def test_lifecycle_sigterm_killed(self, tmp_path: Path) -> None:
        """SIGTERM delivered while child runs → outcome='killed'.

        The conftest neutralizes ``signal.signal`` so the handler never leaks
        into the pytest-xdist worker.  This test nests its own capturing
        ``patch`` inside that fixture to capture the handler, then invokes it
        directly to simulate a real SIGTERM delivery — exercising the full
        finalization path without needing real OS signal delivery.
        """
        import signal as _signal

        staging_dir = tmp_path / "staging" / "test-item"
        staging_dir.mkdir(parents=True)
        mock_config = _make_mock_config(tmp_path, staging_dir=staging_dir)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(
            db_path,
            decision_id=self.DECISION_ID,
            staging_path=str(staging_dir.resolve()),
        )
        child_code = "print('running')"
        argv = self._trivial_argv(child_code)

        captured: dict[int, object] = {}

        def _fake_signal(sig: int, handler: object) -> None:
            captured[sig] = handler

        # Nest our own signal.signal patch inside the conftest's neutralization.
        with (
            patch("personalscraper.web.decisions.runner.signal.signal", _fake_signal),
            patch(
                "personalscraper.web.decisions.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.decisions.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.decisions.runner._get_redis",
                return_value=None,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        # main() completes normally (child exits 0), but the SIGTERM handler
        # was registered.
        assert exc_info.value.code == 0
        assert _signal.SIGTERM in captured
        handler = captured[_signal.SIGTERM]
        assert callable(handler)

        # Simulate SIGTERM delivery by invoking the captured handler.
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

    # ── R11: runner does NOT hold pipeline.lock ────────────────────────────

    def test_runner_does_not_acquire_lock_child_self_acquires(self, tmp_path: Path) -> None:
        """The runner never acquires ``pipeline.lock`` — the child (scrape-resolve) does.

        R11 / webui-ux phase 4 design: ``scrape-resolve`` self-acquires its own
        lock for its lifetime (now a per-staging-item scrape lock, not the global
        ``pipeline.lock``). The decisions runner must NOT acquire the global
        ``pipeline.lock`` — a double acquisition would make the child observe the
        runner's live pid and back off.

        The child stub simulates the child's self-acquire pattern with the lock
        file it controls: it creates the file, prints ``SELF_LOCKED``, then
        removes it. The test asserts the runner-side non-acquisition: the lock
        file does NOT exist before the child creates it.

        The ``tests/cli/test_scrape_resolve.py`` lock tests cover the child-side
        acquire/release contract (``test_lock_held_exits_1``). This test covers
        the runner-side decomposition — together they form the full R11 proof.
        """
        staging_dir = tmp_path / "staging" / "test-item"
        staging_dir.mkdir(parents=True)
        mock_config = _make_mock_config(tmp_path, staging_dir=staging_dir)
        db_path = mock_config.indexer.db_path
        _insert_decision_row(
            db_path,
            decision_id=self.DECISION_ID,
            staging_path=str(staging_dir.resolve()),
        )
        lock_file = tmp_path / "pipeline.lock"
        child_code = (
            "import pathlib, os\n"
            f"lock = pathlib.Path({str(lock_file)!r})\n"
            "# Assert runner did NOT acquire the lock before spawning us.\n"
            "assert not lock.exists(), 'RUNNER_ACQUIRED_LOCK'\n"
            "# Simulate scrape-resolve self-acquire.\n"
            "lock.write_text(str(os.getpid()))\n"
            "print('SELF_LOCKED')\n"
            "# Simulate scrape-resolve release.\n"
            "lock.unlink()\n"
        )
        argv = self._trivial_argv(child_code)

        with (
            patch(
                "personalscraper.web.decisions.runner._build_argv",
                return_value=argv,
            ),
            patch(
                "personalscraper.web.decisions.runner.load_config",
                return_value=mock_config,
            ),
            patch(
                "personalscraper.web.decisions.runner._get_redis",
                return_value=None,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from personalscraper.web.decisions.runner import main

            main()

        assert exc_info.value.code == 0
        row = _select_row(db_path, self.RUN_UID)
        assert row is not None
        assert row["outcome"] == "success"
        assert "SELF_LOCKED" in row["output_tail"]
        # The lock must be released after the child exits.
        assert not lock_file.exists()
