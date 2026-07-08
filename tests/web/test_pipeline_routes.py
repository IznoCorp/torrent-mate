"""Tests for pipeline control REST routes (pipe-control feature).

All external side-effects (``is_lock_held``, ``subprocess.Popen``,
``os.kill``, ``sqlite3.connect``) are mocked so the tests run fast
and never spawn real subprocesses or send real signals.
"""

from __future__ import annotations

import json
import signal
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.deps import require_session


def _mount_guarded(app: FastAPI, router: APIRouter) -> None:
    """Mount *router* behind the session-guard perimeter, mirroring app.py (R14).

    Handlers no longer carry a per-route ``Depends(require_session)`` — the
    guard lives on the parent router only (web-ui.md §6), so test apps must
    reproduce the same perimeter to exercise auth.
    """
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    guarded_api.include_router(router)
    app.include_router(guarded_api)


TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "pipeline-test-secret"


def _xrw_headers() -> dict[str, str]:
    """Return headers with the required ``X-Requested-With`` value."""
    return {"X-Requested-With": "TorrentMate"}


@pytest.fixture
def pipeline_data_dir(tmp_path: Path) -> Path:
    """Create a temp data directory for sentinel files.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Absolute path to the temp ``.data/`` directory.
    """
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def pipeline_client(
    test_config,
    pipeline_data_dir: Path,
) -> TestClient:
    """Create an authenticated ``TestClient`` with pipeline routes included.

    Builds a **minimal** FastAPI app (auth + pipeline routers only) rather
    than going through ``create_app``, whose SPA catch-all
    (``GET /{full_path:path}``) would shadow any GET routes added
    post-creation.  The pipeline router will be wired into ``create_app``
    at sub-phase 2.3 via ``guarded_api``.

    Args:
        test_config: Synthetic ``Config`` fixture.
        pipeline_data_dir: Temp ``.data/`` directory.

    Returns:
        A ``TestClient`` with an active session cookie ready for
        guarded route assertions.
    """
    cfg = test_config.model_copy(
        update={
            "paths": test_config.paths.model_copy(update={"data_dir": pipeline_data_dir}),
        },
    )
    web_cfg = cfg.web.model_copy(update={"username": TEST_USERNAME})
    cfg = cfg.model_copy(update={"web": web_cfg})

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret=TEST_SECRET,
    )

    app = FastAPI()
    app.state.config = cfg
    app.state.settings = settings

    # Auth router (login/logout/me) — needed to obtain a session cookie.
    from personalscraper.web.auth.routes import router as auth_router

    app.include_router(auth_router)
    # Pipeline control routes — the subject under test.
    from personalscraper.web.routes.pipeline import router as pipeline_router

    _mount_guarded(app, pipeline_router)

    client = TestClient(app, base_url="https://testserver")
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 204
    return client


# ── POST /run ────────────────────────────────────────────────────────────────


class TestRunRoute:
    """``POST /api/pipeline/run`` — spawn a pipeline subprocess."""

    def test_run_returns_202_when_lock_free(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A free lock → 202 with a ``run_uid``."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )
        mock_popen = MagicMock(spec=subprocess.Popen)
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.subprocess.Popen",
            mock_popen,
        )

        resp = pipeline_client.post(
            "/api/pipeline/run",
            json={"dry_run": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "run_uid" in data
        assert len(data["run_uid"]) == 32  # uuid4().hex

        # Verify subprocess was spawned with correct arguments.
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert call_args[0].endswith("python") or "python" in call_args[0]
        assert "--no-console" in call_args
        assert "--trigger-reason=web" in call_args
        assert "--dry-run" not in call_args

    def test_run_with_dry_run_flag(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``dry_run: true`` adds ``--dry-run`` to the subprocess command."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )
        mock_popen = MagicMock(spec=subprocess.Popen)
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.subprocess.Popen",
            mock_popen,
        )

        resp = pipeline_client.post(
            "/api/pipeline/run",
            json={"dry_run": True},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 202
        call_args = mock_popen.call_args[0][0]
        assert "--dry-run" in call_args

    def test_run_returns_409_when_lock_held(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A held lock → 409 Conflict."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )

        resp = pipeline_client.post(
            "/api/pipeline/run",
            json={"dry_run": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Pipeline is already running"


# ── POST /pause & /resume ────────────────────────────────────────────────────


class TestPauseResumeRoutes:
    """``POST /api/pipeline/pause`` and ``/resume`` — sentinel management."""

    def test_pause_creates_sentinel(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pause creates the ``pipeline.pause`` sentinel file."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )

        resp = pipeline_client.post(
            "/api/pipeline/pause",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200
        assert (pipeline_data_dir / "pipeline.pause").exists()

    def test_resume_removes_sentinel(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Resume removes the ``pipeline.pause`` sentinel."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )
        # Create the sentinel first.
        (pipeline_data_dir / "pipeline.pause").touch()

        resp = pipeline_client.post(
            "/api/pipeline/resume",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200
        assert not (pipeline_data_dir / "pipeline.pause").exists()

    def test_pause_resume_roundtrip_state(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pause then resume returns to idle when no lock is held."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )

        pause_resp = pipeline_client.post(
            "/api/pipeline/pause",
            headers=_xrw_headers(),
        )
        assert pause_resp.json()["state"] == "idle"
        assert pause_resp.json()["paused"] is True

        resume_resp = pipeline_client.post(
            "/api/pipeline/resume",
            headers=_xrw_headers(),
        )
        assert resume_resp.json()["state"] == "idle"
        assert resume_resp.json()["paused"] is False


# ── POST /kill ───────────────────────────────────────────────────────────────


class TestKillRoute:
    """``POST /api/pipeline/kill`` — SIGTERM the run subprocess."""

    def test_kill_sends_sigterm_to_lock_pid(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Kill reads the PID from the lock file and sends SIGTERM."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )
        # Write a fake PID into the lock file.
        (pipeline_data_dir / "pipeline.lock").write_text("12345")

        mock_kill = MagicMock()
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.os.kill",
            mock_kill,
        )

        resp = pipeline_client.post(
            "/api/pipeline/kill",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_kill_clears_pause_sentinel(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Kill removes the pause sentinel alongside the SIGTERM."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )
        (pipeline_data_dir / "pipeline.lock").write_text("12345")
        (pipeline_data_dir / "pipeline.pause").touch()

        mock_kill = MagicMock()
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.os.kill",
            mock_kill,
        )

        pipeline_client.post(
            "/api/pipeline/kill",
            headers=_xrw_headers(),
        )
        assert not (pipeline_data_dir / "pipeline.pause").exists()

    def test_kill_no_lock_returns_state_without_error(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Kill when no lock exists returns idle state, not an error."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )

        resp = pipeline_client.post(
            "/api/pipeline/kill",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "idle"


# ── POST /watcher ────────────────────────────────────────────────────────────


class TestWatcherRoute:
    """``POST /api/pipeline/watcher`` — toggle the watcher daemon."""

    def test_watcher_enable_removes_sentinel(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
    ) -> None:
        """``enabled: true`` removes the ``watcher.paused`` sentinel."""
        # Create the sentinel first.
        (pipeline_data_dir / "watcher.paused").touch()

        resp = pipeline_client.post(
            "/api/pipeline/watcher",
            json={"enabled": True},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["watcher_enabled"] is True
        assert not (pipeline_data_dir / "watcher.paused").exists()

    def test_watcher_disable_creates_sentinel(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
    ) -> None:
        """``enabled: false`` creates the ``watcher.paused`` sentinel."""
        resp = pipeline_client.post(
            "/api/pipeline/watcher",
            json={"enabled": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["watcher_enabled"] is False
        assert (pipeline_data_dir / "watcher.paused").exists()


# ── GET /status ──────────────────────────────────────────────────────────────


class TestStatusRoute:
    """``GET /api/pipeline/status`` — live pipeline state snapshot."""

    def test_status_idle_when_lock_free(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No lock → state is ``idle`` with null metadata."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "idle"
        assert data["run_uid"] is None
        assert data["step"] is None
        assert data["pid"] is None
        assert data["paused"] is False
        assert "watcher_enabled" in data

    def test_status_running_when_lock_held_no_pause(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Lock held, no pause sentinel → state is ``running``."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )
        (pipeline_data_dir / "pipeline.lock").write_text("99999")

        # Mock the DB to return a run row.
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_conn.execute.return_value.fetchone.return_value = {
            "run_uid": "abc123def456",
            "steps_json": json.dumps(
                [
                    {"name": "ingest", "started_at": 1.0, "ended_at": 2.0, "status": "done"},
                    {"name": "sort", "started_at": 2.0, "ended_at": None, "status": "running"},
                ]
            ),
        }
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.sqlite3.connect",
            lambda _db_path: mock_conn,
        )

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "running"
        assert data["run_uid"] == "abc123def456"
        assert data["step"] == "sort"  # Last step in steps_json
        assert data["pid"] == 99999
        assert data["paused"] is False

    def test_status_paused_when_lock_held_and_sentinel_present(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Lock held + pause sentinel present → state is ``paused``."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )
        (pipeline_data_dir / "pipeline.lock").write_text("77777")
        (pipeline_data_dir / "pipeline.pause").touch()

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "paused"
        assert data["paused"] is True
        assert data["pid"] == 77777

    def test_status_watcher_enabled_reflects_sentinel(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``watcher_enabled`` is ``False`` when the sentinel exists."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )
        (pipeline_data_dir / "watcher.paused").touch()

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200
        assert resp.json()["watcher_enabled"] is False

    def test_status_returns_running_row_not_latest_row(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """R29 — the reported run is the one still ``'running'``, not the newest row.

        The lock holder is the run still marked ``'running'``; a finished (or
        maintenance) row started later must not shadow it. Seeds a REAL DB with
        an older running row and a newer finished row and asserts the running
        one is reported.
        """
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )
        (pipeline_data_dir / "pipeline.lock").write_text("88888")

        db = tmp_path / "status-r29.db"
        seed = sqlite3.connect(str(db))
        seed.execute("CREATE TABLE pipeline_run (run_uid TEXT, outcome TEXT, started_at REAL, steps_json TEXT)")
        seed.execute(
            "INSERT INTO pipeline_run VALUES ('running-run', 'running', 100.0, ?)",
            (json.dumps([{"name": "scrape", "started_at": 100.0, "ended_at": None, "status": "running"}]),),
        )
        seed.execute("INSERT INTO pipeline_run VALUES ('newer-finished', 'success', 200.0, '[]')")
        seed.commit()
        seed.close()

        real_connect = sqlite3.connect
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.sqlite3.connect",
            lambda _p: real_connect(str(db)),
        )

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_uid"] == "running-run"
        assert data["step"] == "scrape"

    def test_status_closes_db_connection(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """R19 — the SQLite handle is closed deterministically, not by refcount.

        The tracking list below keeps a strong reference to every connection the
        route opens, so CPython refcount finalization can never close it — only
        an explicit ``close()`` (the ``with closing(...)`` fix) can.
        """
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )
        (pipeline_data_dir / "pipeline.lock").write_text("88888")

        db = tmp_path / "status-r19.db"
        seed = sqlite3.connect(str(db))
        seed.execute("CREATE TABLE pipeline_run (run_uid TEXT, outcome TEXT, started_at REAL, steps_json TEXT)")
        seed.execute("INSERT INTO pipeline_run VALUES ('r1', 'running', 100.0, '[]')")
        seed.commit()
        seed.close()

        opened: list[sqlite3.Connection] = []
        real_connect = sqlite3.connect

        def tracking_connect(_p: str) -> sqlite3.Connection:
            conn = real_connect(str(db))
            opened.append(conn)
            return conn

        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.sqlite3.connect",
            tracking_connect,
        )

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200
        assert opened, "the route must have opened a connection"
        for conn in opened:
            with pytest.raises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")

    def test_status_db_error_fail_soft(
        self,
        pipeline_client: TestClient,
        pipeline_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A DB error during status does not crash — metadata is ``None``."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: True,
        )
        (pipeline_data_dir / "pipeline.lock").write_text("11111")

        # sqlite3.connect raises.
        def _raise(*_args, **_kwargs):
            raise sqlite3.OperationalError("no such table")

        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.sqlite3.connect",
            _raise,
        )

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "running"
        assert data["run_uid"] is None  # fail-soft
        assert data["step"] is None


# ── Guards ────────────────────────────────────────────────────────────────────


class TestGuards:
    """Auth + CSRF guards on pipeline routes."""

    def test_mutating_route_without_xrw_returns_400(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A POST without ``X-Requested-With`` → 400."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )

        resp = pipeline_client.post(
            "/api/pipeline/run",
            json={"dry_run": False},
            # No X-Requested-With header.
        )
        assert resp.status_code == 400
        assert "X-Requested-With" in resp.json()["detail"]

    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("POST", "/api/pipeline/pause", None),
            ("POST", "/api/pipeline/resume", None),
            ("POST", "/api/pipeline/kill", None),
            ("POST", "/api/pipeline/watcher", {"enabled": True}),
        ],
    )
    def test_mutating_routes_all_require_xrw(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        """Every mutating POST without X-Requested-With → 400."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )

        kwargs = {}
        if body is not None:
            kwargs["json"] = body
        resp = getattr(pipeline_client, method.lower())(path, **kwargs)
        assert resp.status_code == 400

    def test_status_does_not_require_xrw(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /status works without X-Requested-With header."""
        monkeypatch.setattr(
            "personalscraper.web.routes.pipeline.is_lock_held",
            lambda _lock_file: False,
        )

        resp = pipeline_client.get("/api/pipeline/status")
        assert resp.status_code == 200

    def test_route_without_session_returns_401(
        self,
        test_config,
        pipeline_data_dir: Path,
    ) -> None:
        """A request without a session cookie → 401."""
        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": pipeline_data_dir}),
            },
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings
        from personalscraper.web.routes.pipeline import router as pipeline_router

        _mount_guarded(app, pipeline_router)
        client = TestClient(app, base_url="https://testserver")

        resp = client.get("/api/pipeline/status")
        assert resp.status_code == 401


# ── Real create_app() wiring (sub-phase 2.3) ──────────────────────────────


class TestPipelineRoutesViaCreateApp:
    """Pipeline routes reachable through the real ``create_app()`` factory.

    The pipeline router is wired into the ``guarded_api`` block which
    sits BEFORE ``mount_spa`` — the SPA catch-all must NOT shadow
    ``/api/pipeline/*``.  These tests verify that invariant.
    """

    @pytest.fixture
    def real_app_client(self, test_config) -> TestClient:
        """Build an authenticated ``TestClient`` through ``create_app()``.

        Args:
            test_config: Synthetic ``Config`` fixture (function-scoped,
                so each test gets a fresh ``tmp_path``).

        Returns:
            Authenticated ``TestClient`` ready for guarded route assertions.
        """
        pwd = "test"
        cfg = test_config.model_copy(
            update={
                "web": test_config.web.model_copy(update={"username": "admin"}),
            },
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=hash_password(pwd),
            web_jwt_secret="pipe-control-wiring-secret",
        )
        from personalscraper.web.app import create_app

        app = create_app(cfg, settings)
        client = TestClient(app, base_url="https://testserver")
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": pwd},
        )
        assert resp.status_code == 204, f"Login failed: {resp.status_code}"
        return client

    def test_status_not_shadowed_by_spa(
        self,
        real_app_client: TestClient,
    ) -> None:
        """GET /api/pipeline/status → 200, NOT 404 from SPA catch-all.

        This is the KEY wiring assertion: the pipeline router lives inside
        ``guarded_api`` which is included BEFORE ``mount_spa``, so the
        SPA's catch-all ``GET /{full_path:path}`` never shadows it.
        """
        resp = real_app_client.get("/api/pipeline/status")
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}. SPA catch-all may be shadowing the pipeline router."
        )
        data = resp.json()
        assert data["state"] == "idle"
        assert "run_uid" in data
        assert "paused" in data
        assert "watcher_enabled" in data

    def test_401_without_session(self, test_config) -> None:
        """Unauthenticated request through ``create_app`` → 401."""
        from personalscraper.web.app import create_app

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        app = create_app(test_config, settings)
        client = TestClient(app)
        resp = client.get("/api/pipeline/status")
        assert resp.status_code == 401

    def test_400_without_xrw_on_mutating_route(
        self,
        real_app_client: TestClient,
    ) -> None:
        """POST /api/pipeline/run without ``X-Requested-With`` → 400."""
        resp = real_app_client.post(
            "/api/pipeline/run",
            json={"dry_run": False},
            # No X-Requested-With header.
        )
        assert resp.status_code == 400
        assert "X-Requested-With" in resp.json()["detail"]


# ── GET /history + /history/{run_uid} ────────────────────────────────────────


class TestHistoryRoutes:
    """``GET /api/pipeline/history`` and ``/history/{run_uid}`` routes."""

    # Pre-canned timestamps so tests can assert deterministic sort order.
    _T0 = 1750000000.0  # 2025-06-15T12:26:40+00:00
    _T1 = _T0 + 1000.0  # later run
    _T2 = _T0 + 2000.0  # still running (no ended_at)

    @pytest.fixture
    def history_db(self, tmp_path: Path) -> Path:
        """Create a temp library.db with ``pipeline_run`` table + 3 test rows.

        Args:
            tmp_path: Pytest temporary directory.

        Returns:
            Absolute path to the populated database file.
        """
        db_path = tmp_path / "history_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE pipeline_run (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_uid    TEXT    UNIQUE NOT NULL,
                trigger    TEXT    NOT NULL,
                dry_run    INTEGER NOT NULL DEFAULT 0,
                started_at REAL    NOT NULL,
                ended_at   REAL,
                outcome    TEXT,
                steps_json TEXT,
                error      TEXT,
                pid        INTEGER,
                kind         TEXT    NOT NULL DEFAULT 'pipeline',
                command      TEXT,
                options_json TEXT,
                output_tail  TEXT
            )
            """
        )

        now = self._T0
        rows = [
            (
                "aaa111",
                "cli",
                0,
                now,
                now + 120.5,
                "success",
                json.dumps(
                    [
                        {
                            "name": "ingest",
                            "status": "done",
                            "started_at": now,
                            "ended_at": now + 60.0,
                        },
                        {
                            "name": "sort",
                            "status": "done",
                            "started_at": now + 60.0,
                            "ended_at": now + 120.5,
                        },
                    ]
                ),
                None,
                12345,
                "pipeline",
                None,
                None,
                None,
            ),
            (
                "bbb222",
                "web",
                1,
                now + 1000.0,
                now + 1000.0 + 60.0,
                "error",
                json.dumps(
                    [
                        {
                            "name": "ingest",
                            "status": "error",
                            "started_at": now + 1000.0,
                            "ended_at": now + 1000.0 + 60.0,
                        }
                    ]
                ),
                "Something went wrong",
                12346,
                "pipeline",
                None,
                None,
                None,
            ),
            (
                "ccc333",
                "watcher",
                0,
                now + 2000.0,
                None,
                None,
                json.dumps(
                    [
                        {
                            "name": "ingest",
                            "status": "running",
                            "started_at": now + 2000.0,
                            "ended_at": None,
                        }
                    ]
                ),
                None,
                12347,
                "pipeline",
                None,
                None,
                None,
            ),
        ]
        conn.executemany(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, outcome, "
            "steps_json, error, pid, kind, command, options_json, output_tail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def history_client(
        self,
        test_config,
        pipeline_data_dir: Path,
        history_db: Path,
    ) -> TestClient:
        """Build an authenticated ``TestClient`` pointing at *history_db*.

        Args:
            test_config: Synthetic ``Config`` fixture.
            pipeline_data_dir: Temp ``.data/`` directory.
            history_db: Path to the pre-populated test database.

        Returns:
            Authenticated ``TestClient`` with history routes served.
        """
        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": pipeline_data_dir}),
                "indexer": test_config.indexer.model_copy(update={"db_path": history_db}),
            },
        )
        web_cfg = cfg.web.model_copy(update={"username": TEST_USERNAME})
        cfg = cfg.model_copy(update={"web": web_cfg})

        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )

        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings

        from personalscraper.web.auth.routes import router as auth_router

        app.include_router(auth_router)
        from personalscraper.web.routes.pipeline import router as pipeline_router

        _mount_guarded(app, pipeline_router)

        client = TestClient(app, base_url="https://testserver")
        resp = client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 204
        return client

    # ── /history list ────────────────────────────────────────────────────

    def test_history_returns_all_runs_with_total(self, history_client: TestClient) -> None:
        """Default query returns all 3 runs + ``total: 3``."""
        resp = history_client.get("/api/pipeline/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["runs"]) == 3
        for run in data["runs"]:
            assert "run_uid" in run
            assert "trigger" in run
            assert "dry_run" in run
            assert "started_at" in run
            assert "duration_s" in run
            assert "outcome" in run

    def test_history_pagination_limit(self, history_client: TestClient) -> None:
        """``limit=1`` returns 1 run but ``total`` stays 3."""
        resp = history_client.get("/api/pipeline/history", params={"limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["runs"]) == 1

    def test_history_pagination_offset(self, history_client: TestClient) -> None:
        """``offset=2`` skips the first 2 rows."""
        resp = history_client.get("/api/pipeline/history", params={"offset": 2, "sort": "started_at"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_uid"] == "ccc333"

    def test_history_sort_started_at_asc(self, history_client: TestClient) -> None:
        """``sort=started_at`` → oldest first."""
        resp = history_client.get("/api/pipeline/history", params={"sort": "started_at"})
        assert resp.status_code == 200
        uids = [r["run_uid"] for r in resp.json()["runs"]]
        assert uids == ["aaa111", "bbb222", "ccc333"]

    def test_history_sort_started_at_desc(self, history_client: TestClient) -> None:
        """``sort=-started_at`` (default) → newest first."""
        resp = history_client.get("/api/pipeline/history", params={"sort": "-started_at"})
        assert resp.status_code == 200
        uids = [r["run_uid"] for r in resp.json()["runs"]]
        assert uids == ["ccc333", "bbb222", "aaa111"]

    def test_history_sort_duration_asc(self, history_client: TestClient) -> None:
        """``sort=duration`` sorts by elapsed time, NULLs last."""
        resp = history_client.get("/api/pipeline/history", params={"sort": "duration"})
        assert resp.status_code == 200
        uids = [r["run_uid"] for r in resp.json()["runs"]]
        # bbb222: 60s, aaa111: 120.5s, ccc333: still running (NULL → last)
        assert uids == ["bbb222", "aaa111", "ccc333"]

    def test_history_sort_duration_desc(self, history_client: TestClient) -> None:
        """``sort=-duration`` sorts by elapsed time descending, NULLs last."""
        resp = history_client.get("/api/pipeline/history", params={"sort": "-duration"})
        assert resp.status_code == 200
        uids = [r["run_uid"] for r in resp.json()["runs"]]
        # aaa111: 120.5s, bbb222: 60s, ccc333: NULL → last
        assert uids == ["aaa111", "bbb222", "ccc333"]

    def test_history_invalid_sort_returns_400(self, history_client: TestClient) -> None:
        """An unrecognized sort value → 400."""
        resp = history_client.get("/api/pipeline/history", params={"sort": "invalid"})
        assert resp.status_code == 400
        assert "Invalid sort" in resp.json()["detail"]

    # ── empty DB ─────────────────────────────────────────────────────────

    def test_history_empty_db_returns_zero(
        self,
        test_config,
        pipeline_data_dir: Path,
        tmp_path: Path,
    ) -> None:
        """A DB with the table but zero rows → ``{runs: [], total: 0}``."""
        empty_db = tmp_path / "empty_history.db"
        conn = sqlite3.connect(str(empty_db))
        conn.execute(
            """
            CREATE TABLE pipeline_run (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_uid    TEXT    UNIQUE NOT NULL,
                trigger    TEXT    NOT NULL,
                dry_run    INTEGER NOT NULL DEFAULT 0,
                started_at REAL    NOT NULL,
                ended_at   REAL,
                outcome    TEXT,
                steps_json TEXT,
                error      TEXT,
                pid        INTEGER,
                kind         TEXT    NOT NULL DEFAULT 'pipeline',
                command      TEXT,
                options_json TEXT,
                output_tail  TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": pipeline_data_dir}),
                "indexer": test_config.indexer.model_copy(update={"db_path": empty_db}),
            },
        )
        web_cfg = cfg.web.model_copy(update={"username": TEST_USERNAME})
        cfg = cfg.model_copy(update={"web": web_cfg})

        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )

        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings

        from personalscraper.web.auth.routes import router as auth_router

        app.include_router(auth_router)
        from personalscraper.web.routes.pipeline import router as pipeline_router

        _mount_guarded(app, pipeline_router)

        client = TestClient(app, base_url="https://testserver")
        resp = client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 204

        resp = client.get("/api/pipeline/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"runs": [], "total": 0}

    # ── /history/{run_uid} detail ────────────────────────────────────────

    def test_history_detail_returns_run(self, history_client: TestClient) -> None:
        """GET /history/{run_uid} returns a full ``RunDetail``."""
        resp = history_client.get("/api/pipeline/history/aaa111")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_uid"] == "aaa111"
        assert data["trigger"] == "cli"
        assert data["dry_run"] is False
        assert data["outcome"] == "success"
        assert data["duration_s"] == pytest.approx(120.5)
        assert data["error"] is None
        assert len(data["steps"]) == 2
        assert data["steps"][0]["name"] == "ingest"
        assert data["steps"][0]["status"] == "done"
        assert data["steps"][0]["elapsed_s"] == pytest.approx(60.0)
        assert data["steps"][1]["name"] == "sort"
        assert data["steps"][1]["status"] == "done"

    def test_history_detail_dry_run(self, history_client: TestClient) -> None:
        """A dry-run row has ``dry_run: true``."""
        resp = history_client.get("/api/pipeline/history/bbb222")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["outcome"] == "error"
        assert data["error"] == "Something went wrong"
        assert len(data["steps"]) == 1

    def test_history_detail_still_running(self, history_client: TestClient) -> None:
        """A running run has no ``ended_at``, ``outcome``, or ``duration_s``."""
        resp = history_client.get("/api/pipeline/history/ccc333")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ended_at"] is None
        assert data["outcome"] is None
        assert data["duration_s"] is None
        assert len(data["steps"]) == 1
        assert data["steps"][0]["status"] == "running"
        assert data["steps"][0]["ended_at"] is None
        assert data["steps"][0]["elapsed_s"] is None

    def test_history_detail_404_unknown_uid(self, history_client: TestClient) -> None:
        """A non-existent ``run_uid`` → 404."""
        resp = history_client.get("/api/pipeline/history/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # ── auth guard ───────────────────────────────────────────────────────

    def test_history_401_without_session(
        self,
        test_config,
        pipeline_data_dir: Path,
        history_db: Path,
    ) -> None:
        """A request without a session cookie → 401."""
        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": pipeline_data_dir}),
                "indexer": test_config.indexer.model_copy(update={"db_path": history_db}),
            },
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings
        from personalscraper.web.routes.pipeline import router as pipeline_router

        _mount_guarded(app, pipeline_router)
        client = TestClient(app, base_url="https://testserver")

        resp = client.get("/api/pipeline/history")
        assert resp.status_code == 401

    def test_history_detail_401_without_session(
        self,
        test_config,
        pipeline_data_dir: Path,
        history_db: Path,
    ) -> None:
        """Detail route also returns 401 without a session."""
        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": pipeline_data_dir}),
                "indexer": test_config.indexer.model_copy(update={"db_path": history_db}),
            },
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings
        from personalscraper.web.routes.pipeline import router as pipeline_router

        _mount_guarded(app, pipeline_router)
        client = TestClient(app, base_url="https://testserver")

        resp = client.get("/api/pipeline/history/aaa111")
        assert resp.status_code == 401


# ── Staging read-only guard ──────────────────────────────────────────────────


class TestStagingReadOnly:
    """``PERSONALSCRAPER_WEB_ROLE=staging`` → 403 ``read-only`` on every mutating POST route."""

    def test_run_returns_403_when_staging(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /run → 403 read-only on staging."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = pipeline_client.post(
            "/api/pipeline/run",
            json={"dry_run": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"

    def test_pause_returns_403_when_staging(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /pause → 403 read-only on staging."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = pipeline_client.post(
            "/api/pipeline/pause",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"

    def test_resume_returns_403_when_staging(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /resume → 403 read-only on staging."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = pipeline_client.post(
            "/api/pipeline/resume",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"

    def test_kill_returns_403_when_staging(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /kill → 403 read-only on staging."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = pipeline_client.post(
            "/api/pipeline/kill",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"

    def test_watcher_returns_403_when_staging(
        self,
        pipeline_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /watcher → 403 read-only on staging."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = pipeline_client.post(
            "/api/pipeline/watcher",
            json={"enabled": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"
