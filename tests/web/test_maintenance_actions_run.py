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

from fastapi.testclient import TestClient

from .test_maintenance_panels import (
    _build_app,
    _build_authenticated_client,
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
        "  pid INTEGER"
        ")"
    )
    conn.commit()
    return conn


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
