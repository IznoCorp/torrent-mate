"""Route tests for ``POST /api/maintenance/actions/{action_id}/run``.

Covers validation (404/422), lock conflicts (409), concurrent maintenance (409
with stale-pid guard), 428 dry-run precondition, auth (401/400), and successful
spawn (202).

Mirrors the structure of ``tests/web/test_maintenance_panels.py`` for
auth (``tm_session`` cookie via ``/api/auth/login``, ``https`` TestClient,
``tmp_path``-based ``data_dir``) and config-override idioms.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from .test_maintenance_panels import (
    _build_app,
    _build_authenticated_client,
    _login,
)

NOW = int(time.time())

WRITE_ACTION_ID = "library-repair"
DESTRUCTIVE_ACTION_ID = "library-clean"
RO_ACTION_ID = "library-status"

# Canonical JSON forms used across tests.
CANONICAL_EMPTY = "{}"
BUDGET_OPTIONS = {"budget": 30}
CANONICAL_BUDGET = '{"budget":30}'
CLEAN_EMPTY = {"only": "empty"}
CANONICAL_CLEAN_EMPTY = '{"only":"empty"}'
CLEAN_ACTORS = {"only": "actors"}
CANONICAL_CLEAN_ACTORS = '{"only":"actors"}'


# ── DB helpers ─────────────────────────────────────────────────────────────────


def _create_library_db(db_path: Path) -> sqlite3.Connection:
    """Create a minimal ``library.db`` with the ``pipeline_run`` table.

    Args:
        db_path: Absolute path where the database will be created.

    Returns:
        An open connection (caller must close).
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pipeline_run ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_uid TEXT NOT NULL,"
        "  kind TEXT NOT NULL DEFAULT 'pipeline',"
        "  command TEXT,"
        "  trigger TEXT NOT NULL DEFAULT 'web',"
        "  dry_run INTEGER NOT NULL DEFAULT 0,"
        "  options_json TEXT,"
        "  started_at REAL NOT NULL,"
        "  ended_at REAL,"
        "  outcome TEXT,"
        "  steps_json TEXT,"
        "  error TEXT,"
        "  pid INTEGER,"
        "  output_tail TEXT"
        ")"
    )
    conn.commit()
    return conn


def _query_row(db_path: Path, run_uid: str) -> dict | None:
    """Return the ``pipeline_run`` row for *run_uid* as a dict, or ``None``.

    Args:
        db_path: Path to the SQLite database.
        run_uid: The run identifier to look up.

    Returns:
        The row as a dict, or ``None`` when no such row exists.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
    conn.close()
    return dict(row) if row is not None else None


def _authenticated_client_with_history(test_config, tmp_path: Path, db_path: Path) -> TestClient:
    """Build an authenticated client whose app also serves the pipeline routes.

    Needed to exercise ``GET /api/pipeline/history/{run_uid}`` against a row
    reserved by ``POST /api/maintenance/actions/{id}/run`` (Finding C-c).

    Args:
        test_config: Synthetic ``Config`` fixture.
        tmp_path: Pytest temporary directory.
        db_path: Path to the seeded ``library.db``.

    Returns:
        An authenticated ``TestClient`` serving auth + maintenance + pipeline.
    """
    from personalscraper.web.routes.pipeline import router as pipeline_router

    app, _settings = _build_app(
        test_config,
        tmp_path,
        indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
    )
    app.include_router(pipeline_router)
    client = TestClient(app, base_url="https://testserver")
    _login(client)
    return client


def _seed_running_maintenance(conn: sqlite3.Connection, *, pid: int | None = None) -> None:
    """Insert a running maintenance ``pipeline_run`` row into *conn*.

    Args:
        conn: An open connection to a database with the ``pipeline_run`` table.
        pid: Optional PID to store in the row.  When ``None`` the column is
            left NULL (simulating a pre-pid-migration row or a runner that
            crashed before inserting its pid).
    """
    conn.execute(
        "INSERT INTO pipeline_run (run_uid, kind, command, trigger, dry_run, "
        "  options_json, started_at, outcome, pid) "
        "VALUES (?, 'maintenance', ?, 'web', 0, '{}', ?, 'running', ?)",
        ("deadc0de1234", WRITE_ACTION_ID, float(NOW), pid),
    )
    conn.commit()


def _seed_dry_run_row(
    conn: sqlite3.Connection,
    *,
    command: str,
    options_json: str,
    ended_at: float,
) -> None:
    """Insert a successful dry-run ``pipeline_run`` row.

    Args:
        conn: An open connection to a database with the ``pipeline_run`` table.
        command: The maintenance action id.
        options_json: Canonical JSON options string.
        ended_at: Unix timestamp for the ``ended_at`` column.
    """
    started_at = ended_at - 10.0
    conn.execute(
        "INSERT INTO pipeline_run (run_uid, kind, command, trigger, dry_run, "
        "  options_json, started_at, ended_at, outcome) "
        "VALUES (?, 'maintenance', ?, 'web', 1, ?, ?, ?, 'success')",
        ("dddd1111eeee2222", command, options_json, started_at, ended_at),
    )
    conn.commit()


# ── Test class ─────────────────────────────────────────────────────────────────


class TestActionRun:
    """``POST /api/maintenance/actions/{action_id}/run`` — validation, lock, concurrent, 428, auth, spawn."""

    # ── 404 / 422 validation tests ──────────────────────────────────────────

    def test_unknown_action_returns_404(self, test_config, tmp_path: Path) -> None:
        """404 — unknown action id."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.post(
            "/api/maintenance/actions/nonexistent-action/run",
            json={"options": {}, "dry_run": True},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 404
        assert "Unknown action" in resp.json()["detail"]

    def test_unknown_option_key_returns_422(self, test_config, tmp_path: Path) -> None:
        """422 — option key not in the action's registered options."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.post(
            f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
            json={"options": {"nonexistent": 42}, "dry_run": True},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 422
        assert "Unknown option" in resp.json()["detail"]

    def test_bad_enum_value_returns_422(self, test_config, tmp_path: Path) -> None:
        """422 — enum value outside the declared enum_values."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.post(
            f"/api/maintenance/actions/{DESTRUCTIVE_ACTION_ID}/run",
            json={"options": {"only": "invalid_enum_value"}, "dry_run": True},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "invalid_enum_value" in detail
        assert "Allowed:" in detail

    def test_missing_required_option_returns_422(self, test_config, tmp_path: Path) -> None:
        """422 — required option (``query``) not provided."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.post(
            "/api/maintenance/actions/library-search/run",
            json={"options": {}, "dry_run": False},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 422
        assert "Missing required option" in resp.json()["detail"]

    # ── Lock / concurrent maintenance 409 tests ─────────────────────────────

    def test_write_action_lock_held_returns_409(self, test_config, tmp_path: Path) -> None:
        """409 — write action when ``pipeline.lock`` is held by a live process.

        No ``pipeline_run`` table exists, so the lock guard falls through to
        the generic ``"Pipeline lock held"`` detail (non-maintenance lock).
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "pipeline.lock").write_text(str(os.getpid()))

        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.post(
            f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
            json={"options": {}, "dry_run": True},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Pipeline lock held"

    def test_running_maintenance_live_pid_returns_409(self, test_config, tmp_path: Path) -> None:
        """409 — a maintenance row with a LIVE pid blocks a second run.

        The concurrent-maintenance guard queries ``pipeline_run`` for rows with
        ``kind='maintenance' AND outcome='running'`` and checks liveness via
        ``os.kill(pid, 0)``.  A row with ``pid=os.getpid()`` (the test process
        itself) is alive → 409 ``"A maintenance action is already running"``.

        Unlike the pipeline-lock 409, this check fires even when
        ``pipeline.lock`` is NOT held, because a maintenance action may be
        genuinely running without holding the pipeline lock (e.g. a read-only
        action, or a write CLI that doesn't take the lock).
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        # Do NOT create pipeline.lock — the pid-based guard is independent.

        # Seed a DB with a running maintenance row whose pid IS alive.
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_running_maintenance(conn, pid=os.getpid())
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        resp = client.post(
            f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
            json={"options": {}, "dry_run": True},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "A maintenance action is already running"

    def test_running_maintenance_dead_pid_returns_202(self, test_config, tmp_path: Path) -> None:
        """202 — running maintenance row with a DEAD pid → stale, ignored.

        The concurrent-maintenance guard queries ``pipeline_run`` for rows with
        ``kind='maintenance' AND outcome='running'``.  A row whose ``pid`` is
        not NULL but ``os.kill(pid, 0)`` raises ``ProcessLookupError`` is stale
        (crashed runner) — the guard logs it and allows the new run through.
        We use ``pid=99999`` which is extremely unlikely to be a live process.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        # Do NOT create pipeline.lock.

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_running_maintenance(conn, pid=99999)  # dead PID
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        with patch("personalscraper.web.routes.maintenance._spawn_runner") as mock_spawn:
            resp = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )
            assert resp.status_code == 202
            assert mock_spawn.called

    def test_running_maintenance_null_pid_returns_202(self, test_config, tmp_path: Path) -> None:
        """202 — running maintenance row with NULL pid → stale, ignored.

        A row with ``pid IS NULL`` is treated as stale (pre-pid-migration or
        runner crash before inserting its pid).  The new run is allowed through.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_running_maintenance(conn, pid=None)  # NULL pid
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        with patch("personalscraper.web.routes.maintenance._spawn_runner") as mock_spawn:
            resp = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )
            assert resp.status_code == 202
            assert mock_spawn.called

    # ── 428 dry-run-first tests ─────────────────────────────────────────────

    def test_destructive_apply_no_prior_dry_run_returns_428(self, test_config, tmp_path: Path) -> None:
        """428 — destructive action with ``dry_run=False``, no prior dry-run row."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        resp = client.post(
            f"/api/maintenance/actions/{DESTRUCTIVE_ACTION_ID}/run",
            json={"options": CLEAN_EMPTY, "dry_run": False},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 428
        assert "dry-run" in resp.json()["detail"].lower()

    def test_destructive_apply_fresh_dry_run_returns_202(self, test_config, tmp_path: Path) -> None:
        """202 — destructive apply with a fresh (< 30 min) successful dry-run row.

        Seeds a matching ``pipeline_run`` row with ``ended_at`` set to 10
        minutes ago, then asserts the apply passes the 428 guard and spawns.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_dry_run_row(
            conn,
            command=DESTRUCTIVE_ACTION_ID,
            options_json=CANONICAL_CLEAN_EMPTY,
            ended_at=float(NOW - 600),
        )
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        with patch("personalscraper.web.routes.maintenance._spawn_runner") as mock_spawn:
            resp = client.post(
                f"/api/maintenance/actions/{DESTRUCTIVE_ACTION_ID}/run",
                json={"options": CLEAN_EMPTY, "dry_run": False},
                headers={"X-Requested-With": "TorrentMate"},
            )
            assert resp.status_code == 202
            assert mock_spawn.called

    def test_destructive_apply_stale_dry_run_returns_428(self, test_config, tmp_path: Path) -> None:
        """428 — stale dry-run (> 30 min ago) does not satisfy the guard.

        The dry-run row has ``ended_at`` set to 31+ minutes ago, which is
        outside the 30-minute freshness window.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_dry_run_row(
            conn,
            command=DESTRUCTIVE_ACTION_ID,
            options_json=CANONICAL_CLEAN_EMPTY,
            ended_at=float(NOW - 1860),  # 31 min ago
        )
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        resp = client.post(
            f"/api/maintenance/actions/{DESTRUCTIVE_ACTION_ID}/run",
            json={"options": CLEAN_EMPTY, "dry_run": False},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 428

    def test_destructive_apply_different_options_returns_428(self, test_config, tmp_path: Path) -> None:
        """428 — fresh dry-run row with DIFFERENT options → guard still fires.

        Seeds a dry-run with ``only="actors"`` but the request sends
        ``only="empty"`` — the options_json comparison is string-equality on
        the canonical form, so the row does not match.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_dry_run_row(
            conn,
            command=DESTRUCTIVE_ACTION_ID,
            options_json=CANONICAL_CLEAN_ACTORS,
            ended_at=float(NOW - 600),
        )
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        resp = client.post(
            f"/api/maintenance/actions/{DESTRUCTIVE_ACTION_ID}/run",
            json={"options": CLEAN_EMPTY, "dry_run": False},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 428

    # ── RO bypass tests ─────────────────────────────────────────────────────

    def test_ro_action_lock_held_returns_202(self, test_config, tmp_path: Path) -> None:
        """202 — RO action bypasses lock/concurrent/428 guards entirely.

        Even with ``pipeline.lock`` held by a live process, a read-only action
        (``risk="ro"``) skips all checks and spawns directly.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "pipeline.lock").write_text(str(os.getpid()))

        client = _build_authenticated_client(test_config, tmp_path)

        with patch("personalscraper.web.routes.maintenance._spawn_runner") as mock_spawn:
            resp = client.post(
                f"/api/maintenance/actions/{RO_ACTION_ID}/run",
                json={"options": {}, "dry_run": False},
                headers={"X-Requested-With": "TorrentMate"},
            )
            assert resp.status_code == 202
            assert mock_spawn.called

    # ── Auth tests ──────────────────────────────────────────────────────────

    def test_unauthenticated_returns_401(self, test_config, tmp_path: Path) -> None:
        """401 — no session cookie."""
        app, _settings = _build_app(test_config, tmp_path, with_auth=False)
        client = TestClient(app)
        resp = client.post(
            f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
            json={"options": {}, "dry_run": True},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 401

    def test_missing_x_requested_with_returns_400(self, test_config, tmp_path: Path) -> None:
        """400 — authenticated but no ``X-Requested-With`` header.

        The ``require_x_requested_with`` dependency raises ``400`` (NOT 403)
        when the header is missing or has the wrong value — verified by
        reading ``personalscraper/web/deps.py``.
        """
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.post(
            f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
            json={"options": {}, "dry_run": True},
        )
        assert resp.status_code == 400
        assert "X-Requested-With" in resp.json()["detail"]

    # ── Spawn verification test ─────────────────────────────────────────────

    def test_spawn_receives_correct_env(self, test_config, tmp_path: Path) -> None:
        """202 — ``_spawn_runner`` called once with the canonical environment.

        Verifies:
        * Response is ``202`` with a hex ``run_uid``.
        * ``_spawn_runner`` is called exactly once.
        * The ``run_uid`` arg matches the response body.
        * The ``action_id`` and ``options_json`` args match the request.
        * ``dry_run`` is ``True`` (the default).
        """
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        with patch("personalscraper.web.routes.maintenance._spawn_runner") as mock_spawn:
            resp = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": BUDGET_OPTIONS, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )

            assert resp.status_code == 202
            data = resp.json()
            assert "run_uid" in data
            run_uid = data["run_uid"]
            # Must be 32-char hex string (uuid4().hex).
            assert len(run_uid) == 32
            assert all(c in "0123456789abcdef" for c in run_uid)

            mock_spawn.assert_called_once()
            call_args = mock_spawn.call_args
            assert call_args[0][0] == run_uid  # First positional: run_uid
            assert call_args[0][1] == WRITE_ACTION_ID  # action_id
            assert call_args[0][2] == CANONICAL_BUDGET  # options_json
            assert call_args[0][3] is True  # dry_run

    # ── Spawn env contract test ─────────────────────────────────────────────

    def test_spawn_runner_sets_canonical_env(self) -> None:
        """``_spawn_runner`` passes env with canonical options_json and matching dry_run.

        Calls ``_spawn_runner`` directly with ``subprocess.Popen`` patched so we can
        inspect the ``env`` dict that the child process receives.  Verifies:

        * ``PERSONALSCRAPER_MAINT_OPTIONS_JSON`` is the exact canonical string.
        * ``PERSONALSCRAPER_MAINT_DRY_RUN`` matches the ``dry_run`` argument.
        """
        from personalscraper.web.routes.maintenance import _spawn_runner

        with patch("personalscraper.web.routes.maintenance.subprocess.Popen") as mock_popen:
            _spawn_runner("abc123def456abc123def456ab", WRITE_ACTION_ID, CANONICAL_BUDGET, dry_run=False)

        call_kwargs = mock_popen.call_args[1]
        env = call_kwargs.get("env", {})
        assert env["PERSONALSCRAPER_MAINT_OPTIONS_JSON"] == CANONICAL_BUDGET
        assert env["PERSONALSCRAPER_MAINT_DRY_RUN"] == "0"
        assert env["PERSONALSCRAPER_MAINT_COMMAND"] == WRITE_ACTION_ID
        assert env["PERSONALSCRAPER_RUN_UID"] == "abc123def456abc123def456ab"

        # Also verify the dry_run=True path.
        with patch("personalscraper.web.routes.maintenance.subprocess.Popen") as mock_popen:
            _spawn_runner("xyz9876543210xyz9876543210", DESTRUCTIVE_ACTION_ID, CANONICAL_CLEAN_EMPTY, dry_run=True)

        call_kwargs = mock_popen.call_args[1]
        env = call_kwargs.get("env", {})
        assert env["PERSONALSCRAPER_MAINT_OPTIONS_JSON"] == CANONICAL_CLEAN_EMPTY
        assert env["PERSONALSCRAPER_MAINT_DRY_RUN"] == "1"


class TestActionRunRowReservation:
    """Finding C — the run row is reserved synchronously + atomically before 202."""

    def test_run_reserves_row_before_202(self, test_config, tmp_path: Path) -> None:
        """The pipeline_run row exists (outcome='running') the instant 202 is returned.

        Even when the runner is never spawned (patched), the 202 ``run_uid`` maps
        to a present, finalizable row — so a runner that exit-2's before doing
        anything is never invisible to the operator (Finding C).
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        with patch("personalscraper.web.routes.maintenance._spawn_runner"):
            resp = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 202
        run_uid = resp.json()["run_uid"]

        row = _query_row(db_path, run_uid)
        assert row is not None
        assert row["outcome"] == "running"
        assert row["kind"] == "maintenance"
        assert row["command"] == WRITE_ACTION_ID
        assert row["pid"] is not None

        # The row is finalizable — simulate a runner exit-2 before any work.
        from personalscraper.pipeline_history import PipelineRunWriter

        PipelineRunWriter(db_path).finalize(run_uid, "error", error="runner exit 2")
        finalized = _query_row(db_path, run_uid)
        assert finalized is not None
        assert finalized["outcome"] == "error"

    def test_second_concurrent_post_returns_409(self, test_config, tmp_path: Path) -> None:
        """Two destructive-class POSTs in quick succession → the second gets 409.

        The first POST reserves a running row (live placeholder pid). The second
        POST's atomic concurrency check observes it → 409, closing the TOCTOU
        race where both would previously pass the guard and spawn (Finding C).
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        with patch("personalscraper.web.routes.maintenance._spawn_runner"):
            first = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )
            assert first.status_code == 202

            second = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert second.status_code == 409
        assert "already running" in second.json()["detail"]

    def test_reserved_run_queryable_via_history_detail(self, test_config, tmp_path: Path) -> None:
        """The 202 ``run_uid`` is immediately queryable via GET /api/pipeline/history/{uid}."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _authenticated_client_with_history(test_config, tmp_path, db_path)

        with patch("personalscraper.web.routes.maintenance._spawn_runner"):
            resp = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 202
        run_uid = resp.json()["run_uid"]

        detail = client.get(f"/api/pipeline/history/{run_uid}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["run_uid"] == run_uid
        assert data["kind"] == "maintenance"
        assert data["command"] == WRITE_ACTION_ID


class TestActionRunLockReProbe:
    """R11 — the pipeline lock is re-probed after the row reservation, before spawn."""

    def test_lock_appearing_after_reservation_returns_409_and_finalizes_row(self, test_config, tmp_path: Path) -> None:
        """409 — lock grabbed between the step-3 probe and the spawn.

        ``is_lock_held`` is patched to pass the early probe (``False``) and trip
        the pre-spawn re-probe (``True``), simulating a pipeline run acquiring
        ``pipeline.lock`` in the TOCTOU window. The route must 409, never spawn
        the runner, and finalize the already-reserved row ``'error'`` so it is
        not left ``'running'`` forever.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        with (
            patch(
                "personalscraper.web.routes.maintenance.is_lock_held",
                side_effect=[False, True],
            ),
            patch("personalscraper.web.routes.maintenance._spawn_runner") as mock_spawn,
        ):
            resp = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "Pipeline lock held"
        mock_spawn.assert_not_called()

        # The reserved row must be finalized 'error' — never left 'running'.
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM pipeline_run").fetchall()
        conn.close()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["outcome"] == "error"
        assert row["error"] == "Pipeline lock held"
        assert row["ended_at"] is not None


class TestActionRunConcurrencyFailClosed:
    """Finding E — the concurrency guard fails CLOSED for destructive actions on DB error."""

    @staticmethod
    def _db_without_pipeline_run(db_path: Path) -> None:
        """Create a DB file that exists but lacks the ``pipeline_run`` table."""
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE unrelated (x INTEGER)")
        conn.commit()
        conn.close()

    def test_destructive_concurrency_db_error_returns_409(self, test_config, tmp_path: Path) -> None:
        """A destructive action whose concurrency check errors → 409 (fail-closed).

        With the ``pipeline_run`` table missing, the concurrency SELECT raises
        ``OperationalError``. For a destructive action this must NOT silently drop
        the only concurrency protection — it returns 409 "cannot verify".
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        self._db_without_pipeline_run(db_path)

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        resp = client.post(
            f"/api/maintenance/actions/{DESTRUCTIVE_ACTION_ID}/run",
            json={"options": {"only": "empty"}, "dry_run": True},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 409
        assert "verify" in resp.json()["detail"].lower()

    def test_write_concurrency_db_error_stays_permissive_202(self, test_config, tmp_path: Path) -> None:
        """A write action whose concurrency check errors stays permissive → 202.

        Finding E scopes the fail-closed behaviour to destructive actions only;
        write / ro actions remain permissive when the guard cannot be verified.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        self._db_without_pipeline_run(db_path)

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        with patch("personalscraper.web.routes.maintenance._spawn_runner") as mock_spawn:
            resp = client.post(
                f"/api/maintenance/actions/{WRITE_ACTION_ID}/run",
                json={"options": {}, "dry_run": True},
                headers={"X-Requested-With": "TorrentMate"},
            )
        assert resp.status_code == 202
        assert mock_spawn.called


# ── Staging read-only guard ──────────────────────────────────────────────────


class TestStagingReadOnly:
    """``PERSONALSCRAPER_WEB_ROLE=staging`` → 403 on POST /actions/{id}/run."""

    def test_action_run_returns_403_when_staging(
        self,
        test_config,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /api/maintenance/actions/{id}/run → 403 read-only on staging.

        The 403 fires before action lookup — no DB setup needed.
        """
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post(
            "/api/maintenance/actions/library-status/run",
            json={"options": {}, "dry_run": False},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"
