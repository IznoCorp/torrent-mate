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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.web.auth.passwords import hash_password

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

    app.include_router(pipeline_router)

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

        app.include_router(pipeline_router)
        client = TestClient(app, base_url="https://testserver")

        resp = client.get("/api/pipeline/status")
        assert resp.status_code == 401
