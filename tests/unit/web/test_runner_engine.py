"""Unit tests for the shared runner engine (``web/_runner_engine.py``).

Covers the two consolidated primitives:

* :func:`reserve_run_row` — the single ``BEGIN IMMEDIATE`` + guard + INSERT
  reservation (guard raises → rollback + propagate; DB error + ``fail_closed`` →
  409; missing DB → ``missing_db`` hook).
* :func:`run_spawn_stream` — the single spawn → stream → requeue → finalize
  lifecycle with a fake subprocess: success / crash → terminal status, a
  destructive run holds ``pipeline.lock`` for its whole lifetime, a busy lock
  enqueues visibly (202-equivalent: a ``queue`` step, never a refusal), and the
  serial re-queue drains in order once the lock frees.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web import _runner_engine as engine

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


def _row(db_path: Path, run_uid: str) -> dict | None:
    """Return the ``pipeline_run`` row as a dict, or ``None``."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
    conn.close()
    return dict(r) if r is not None else None


def _fake_popen(stdout_lines: list[str], returncode: int = 0) -> MagicMock:
    """Return a mock ``Popen`` with configurable stdout iterable and rc."""
    proc = MagicMock()
    proc.stdout = list(stdout_lines)
    proc.wait.return_value = returncode
    return proc


def _spec(db_path: Path, run_uid: str, argv: list[str], **overrides: object) -> engine.RunnerSpec:
    """Build a minimal :class:`RunnerSpec` over a real DB, overridable per-test."""
    kwargs: dict[str, object] = {
        "writer": PipelineRunWriter(db_path),
        "run_uid": run_uid,
        "kind": "maintenance",
        "command": "library-gc",
        "options_json": "{}",
        "dry_run": False,
        "argv": argv,
        "child": {},
        "ring": engine.RingBuffer(),
        "redis": None,
        "stream_key": "t:events",
        "stream_maxlen": 100,
        "event_prefix": "test_runner",
        "queue_timeout_error": "Délai dépassé (wait).",
        "requeue_timeout_error": "Délai dépassé (requeue).",
    }
    kwargs.update(overrides)
    return engine.RunnerSpec(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# reserve_run_row
# ---------------------------------------------------------------------------


class TestReserveRunRow:
    """The single atomic reservation primitive."""

    def test_inserts_running_row_with_columns(self, tmp_path: Path) -> None:
        """A fresh reserve inserts a running row with the canonical shape."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        engine.reserve_run_row(
            db_path, run_uid="r1", kind="maintenance", command="grab", options_json='{"followed_id":7}', dry_run=False
        )
        row = _row(db_path, "r1")
        assert row is not None
        assert row["kind"] == "maintenance"
        assert row["command"] == "grab"
        assert row["outcome"] == "running"
        assert row["trigger"] == "web"
        assert row["steps_json"] == "[]"
        assert row["options_json"] == '{"followed_id":7}'

    def test_guard_rejection_rolls_back_and_propagates(self, tmp_path: Path) -> None:
        """A guard that raises HTTPException leaves NO row and re-raises."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        def guard(_conn: sqlite3.Connection) -> None:
            raise HTTPException(status_code=409, detail="dup")

        with pytest.raises(HTTPException) as exc:
            engine.reserve_run_row(
                db_path, run_uid="r2", kind="maintenance", command="grab", options_json="{}", dry_run=False, guard=guard
            )
        assert exc.value.status_code == 409
        assert _row(db_path, "r2") is None

    def test_db_error_fail_closed_returns_409(self, tmp_path: Path) -> None:
        """A missing table with fail_closed=True raises the French 409 detail."""
        db_path = tmp_path / "library.db"
        # DB file exists but has no pipeline_run table → OperationalError.
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE unrelated (x INTEGER)")
        conn.commit()
        conn.close()

        with pytest.raises(HTTPException) as exc:
            engine.reserve_run_row(
                db_path,
                run_uid="r3",
                kind="maintenance",
                command="grab",
                options_json="{}",
                dry_run=False,
                fail_closed=True,
                fail_closed_detail="Impossible de vérifier.",
            )
        assert exc.value.status_code == 409
        assert exc.value.detail == "Impossible de vérifier."

    def test_missing_db_invokes_hook(self, tmp_path: Path) -> None:
        """A missing DB file invokes missing_db (e.g. 428 dry-run-first)."""
        db_path = tmp_path / "nope.db"
        called = {"n": 0}

        def missing() -> None:
            called["n"] += 1

        engine.reserve_run_row(
            db_path,
            run_uid="r4",
            kind="maintenance",
            command="grab",
            options_json="{}",
            dry_run=False,
            missing_db=missing,
        )
        assert called["n"] == 1


# ---------------------------------------------------------------------------
# run_spawn_stream — terminal statuses
# ---------------------------------------------------------------------------


class TestLifecycleTerminalStatus:
    """The engine finalizes a real terminal status on every exit path."""

    def test_success_finalizes_success_with_tail(self, tmp_path: Path) -> None:
        """Exit 0 → outcome success, output_tail captured, exit 0."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["hello\n", "world\n"], returncode=0)
        spec = _spec(db_path, "run-ok", ["x"])
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 0
        row = _row(db_path, "run-ok")
        assert row["outcome"] == "success"
        assert row["ended_at"] is not None
        assert "hello" in row["output_tail"] and "world" in row["output_tail"]

    def test_crash_finalizes_error_and_exits_child_code(self, tmp_path: Path) -> None:
        """A child exiting non-zero (no requeue) → outcome error, exit that code."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["boom\n"], returncode=3)
        spec = _spec(db_path, "run-crash", ["x"])
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 3
        row = _row(db_path, "run-crash")
        assert row["outcome"] == "error"
        assert "boom" in row["error"]

    def test_spawn_failure_finalizes_error_exit_2(self, tmp_path: Path) -> None:
        """Popen raising OSError → outcome error, exit 2."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        spec = _spec(db_path, "run-spawnfail", ["x"])
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", side_effect=OSError("nope")),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 2
        row = _row(db_path, "run-spawnfail")
        assert row["outcome"] == "error"
        assert "nope" in row["error"]

    def test_stream_exception_finalizes_error_not_running(self, tmp_path: Path) -> None:
        """An exception mid-stream finalizes 'error', never 'running'; kills child."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["l1\n", "l2\n"], returncode=0)
        spec = _spec(db_path, "run-streamfail", ["x"])

        def boom(_line: str) -> None:
            raise RuntimeError("mid-stream boom")

        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            patch.object(spec.ring, "append", boom),
            patch("personalscraper.web._runner_engine.kill_child_group") as mock_kill,
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 1
        mock_kill.assert_called_once()
        row = _row(db_path, "run-streamfail")
        assert row["outcome"] == "error"

    def test_on_success_hook_runs_on_rc0(self, tmp_path: Path) -> None:
        """The on_success hook fires after a rc==0 finalize."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["ok\n"], returncode=0)
        called = {"n": 0}
        spec = _spec(db_path, "run-hook", ["x"], on_success=lambda: called.__setitem__("n", called["n"] + 1))
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            pytest.raises(SystemExit),
        ):
            engine.run_spawn_stream(spec)
        assert called["n"] == 1

    def test_redis_publish_per_line(self, tmp_path: Path) -> None:
        """Each output line is published to Redis with the maintenance.run_log envelope."""
        import json

        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["a\n", "b\n"], returncode=0)
        redis = MagicMock()
        spec = _spec(db_path, "run-redis", ["x"], redis=redis)
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            pytest.raises(SystemExit),
        ):
            engine.run_spawn_stream(spec)
        assert redis.xadd.call_count == 2
        envelope = json.loads(redis.xadd.call_args_list[0][0][1]["envelope"])
        assert envelope["_type"] == "maintenance.run_log"
        assert envelope["data"]["seq"] == 0


# ---------------------------------------------------------------------------
# run_spawn_stream — pipeline.lock tenure + visible queue (§6 / R11)
# ---------------------------------------------------------------------------


class TestLockTenure:
    """A destructive run holds pipeline.lock for its whole lifetime."""

    def test_hold_lock_acquires_before_spawn_releases_after(self, tmp_path: Path) -> None:
        """hold_lock acquires with (lock_file, scrape_dir) and releases in finally."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["ok\n"], returncode=0)
        acquire = MagicMock(return_value=True)
        release = MagicMock()
        lock_file = tmp_path / "pipeline.lock"
        scrape_dir = tmp_path / "locks" / "scrape"
        spec = _spec(
            db_path,
            "run-lock",
            ["x"],
            hold_lock=True,
            acquire_fn=acquire,
            release_fn=release,
            lock_file=lock_file,
            scrape_locks_dir=scrape_dir,
        )
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 0
        acquire.assert_called_once_with(lock_file, scrape_dir)
        release.assert_called_once_with(lock_file)

    def test_busy_lock_enqueues_visibly_then_proceeds(self, tmp_path: Path) -> None:
        """A held lock is never a refusal: a visible 'queue' step, then hand-over.

        202-equivalent — the acquire fails once (busy) then succeeds; the engine
        appends a ``queue`` step (status waiting_pipeline_lock), closes it 'done',
        and proceeds to spawn.
        """
        import json

        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["ok\n"], returncode=0)
        acquire = MagicMock(side_effect=[False, True])
        release = MagicMock()
        lock_file = tmp_path / "pipeline.lock"
        spec = _spec(
            db_path,
            "run-queue",
            ["x"],
            hold_lock=True,
            acquire_fn=acquire,
            release_fn=release,
            lock_file=lock_file,
            scrape_locks_dir=tmp_path / "locks" / "scrape",
        )
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            patch("personalscraper.web.run_queue.time.sleep"),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 0
        assert acquire.call_count == 2
        steps = json.loads(_row(db_path, "run-queue")["steps_json"])
        queue_steps = [s for s in steps if s.get("name") == "queue"]
        assert [s["status"] for s in queue_steps] == ["waiting_pipeline_lock", "done"]

    def test_busy_lock_deadline_finalizes_error_no_spawn(self, tmp_path: Path) -> None:
        """A lock never freed → deadline passes → finalize error, child never spawned."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        acquire = MagicMock(return_value=False)
        spec = _spec(
            db_path,
            "run-timeout",
            ["x"],
            hold_lock=True,
            acquire_fn=acquire,
            release_fn=MagicMock(),
            lock_file=tmp_path / "pipeline.lock",
            scrape_locks_dir=tmp_path / "locks" / "scrape",
            queue_timeout_s=0.01,
        )
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen") as mock_popen,
            patch("personalscraper.web.run_queue.time.sleep"),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 1
        mock_popen.assert_not_called()
        row = _row(db_path, "run-timeout")
        assert row["outcome"] == "error"
        assert "Délai dépassé (wait)." in row["error"]


class TestSerialRequeue:
    """The serial re-queue drains in order once the lock frees (resolve queue)."""

    def test_exit3_requeues_until_free_then_succeeds(self, tmp_path: Path) -> None:
        """Probe + requeue: the child exits 3 once, then the second spawn succeeds."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        # First spawn's child exits 3 (lock busy at claim); second exits 0.
        procs = [_fake_popen(["busy\n"], returncode=3), _fake_popen(["done\n"], returncode=0)]
        is_lock_held = MagicMock(return_value=False)
        spec = _spec(
            db_path,
            "run-requeue",
            ["x"],
            probe_lock_each_iter=True,
            requeue_on_exit3=True,
            is_lock_held_fn=is_lock_held,
            lock_file=tmp_path / "pipeline.lock",
        )
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", side_effect=procs),
            patch("personalscraper.web._runner_engine.time.sleep"),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 0
        row = _row(db_path, "run-requeue")
        assert row["outcome"] == "success"

    def test_exit3_requeue_deadline_finalizes_error(self, tmp_path: Path) -> None:
        """A child that exits 3 past the deadline finalizes error (never infinite spin)."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        proc = _fake_popen(["busy\n"], returncode=3)
        spec = _spec(
            db_path,
            "run-requeue-timeout",
            ["x"],
            probe_lock_each_iter=True,
            requeue_on_exit3=True,
            is_lock_held_fn=MagicMock(return_value=False),
            lock_file=tmp_path / "pipeline.lock",
            queue_timeout_s=-1.0,  # deadline already in the past
        )
        with (
            patch("personalscraper.web._runner_engine.subprocess.Popen", return_value=proc),
            patch("personalscraper.web._runner_engine.time.sleep"),
            pytest.raises(SystemExit) as exc,
        ):
            engine.run_spawn_stream(spec)
        assert exc.value.code == 1
        row = _row(db_path, "run-requeue-timeout")
        assert row["outcome"] == "error"
        assert "Délai dépassé (requeue)." in row["error"]
