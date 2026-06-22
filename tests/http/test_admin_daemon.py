"""Tests for daemon status read + control routes (bosun §7.1-7.2, sub-phase 2.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path) -> Any:
    """Bootstrap the config API with a minimal project, auth off, routes registered."""
    import kanbanmate.http.config_api as api_mod

    import kanbanmate.http.admin_routes  # noqa: F401

    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_x": {
                    "repo": "O/r",
                    "clone": str(tmp_path / "clone"),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                }
            }
        ),
        encoding="utf-8",
    )
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None  # auth disabled → isolate daemon-control
    return api_mod


# ── GET /api/admin/daemon ────────────────────────────────────────────────────


def _fake_jlist() -> str:
    """A realistic pm2 jlist with two allowlisted apps + one out-of-allowlist."""
    return json.dumps(
        [
            {
                "name": "kanban-km",
                "pid": 12345,
                "pm2_env": {
                    "status": "online",
                    "pm_uptime": 1719000000000,
                    "restart_time": 3,
                },
            },
            {
                "name": "kanban-km-config",
                "pid": 12346,
                "pm2_env": {
                    "status": "online",
                    "pm_uptime": 1719000001000,
                    "restart_time": 1,
                },
            },
            {
                "name": "kanban-autodeploy",  # out of allowlist
                "pid": 12347,
                "pm2_env": {
                    "status": "online",
                    "pm_uptime": 1719000002000,
                    "restart_time": 0,
                },
            },
        ]
    )


def test_daemon_list_filters_to_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/admin/daemon returns only allowlisted apps (kanban-autodeploy excluded)."""
    import subprocess

    api_mod = _setup(tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: type(
            "R",
            (),
            {"returncode": 0, "stdout": _fake_jlist(), "stderr": ""},
        )(),
    )
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/daemon")
        assert r.status_code == 200
        apps = r.json()["apps"]
        names = [a["app"] for a in apps]
        assert "kanban-km" in names
        assert "kanban-km-config" in names
        assert "kanban-autodeploy" not in names


def test_daemon_list_fields_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each returned app has the expected field keys."""
    import subprocess

    api_mod = _setup(tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: type(
            "R",
            (),
            {"returncode": 0, "stdout": _fake_jlist(), "stderr": ""},
        )(),
    )
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/daemon")
        assert r.status_code == 200
        app0 = r.json()["apps"][0]
        for key in ("app", "status", "pid", "uptime_s", "restarts"):
            assert key in app0, f"missing key {key!r}"


def test_daemon_list_pm2_unavailable_degrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pm2 is not found, the route degrades with an error string, not a 500."""
    import subprocess

    api_mod = _setup(tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("no pm2")),
    )
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/daemon")
        assert r.status_code == 200
        body = r.json()
        assert body["apps"] == []
        assert "no pm2" in body["error"]


# ── POST /api/admin/daemon/{app}/{action} ────────────────────────────────────


def test_daemon_restart_ui_app_refused_422(tmp_path: Path) -> None:
    """D1: standalone start/stop/restart of a UI app is refused (422)."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        # Mint a CSRF cookie so the CSRF middleware doesn't reject (auth off = CSRF skipped,
        # but the cookie must still exist for the POST to reach the handler).
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/daemon/kanban-km-config/restart",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 422
        assert "refused" in r.json()["detail"]


def test_daemon_restart_allowed_app_creates_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An allowed daemon app (kanban-km) accepts restart → creates a job (200)."""
    api_mod = _setup(tmp_path)

    from kanbanmate.app import ops

    monkeypatch.setattr(ops, "create_job", lambda *a, **k: "job-xyz")
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/daemon/kanban-km/restart",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200
        assert r.json()["job_id"] == "job-xyz"


def test_daemon_unknown_action_refused_422(tmp_path: Path) -> None:
    """An unknown action name is refused with a 422."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/daemon/kanban-km/destroy",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 422
        assert "unknown action" in r.json()["detail"]


def test_daemon_out_of_allowlist_refused_422(tmp_path: Path) -> None:
    """A non-allowlisted app name is refused with a 422."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/daemon/rm-rf/start",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 422
        assert "not in the PM2 allowlist" in r.json()["detail"]


def test_daemon_status_allowed_on_ui_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Status on a UI app is permitted (does NOT create a job — just checks the validator).

    This is a read validation test: the allowlist permits 'status' on UI apps (D1).
    We POST /api/admin/daemon/kanban-km-config/status and assert a job is created (200),
    because status is not a mutating action for UI apps per D1 — it passes validate_daemon_action.
    """
    api_mod = _setup(tmp_path)

    from kanbanmate.app import ops

    monkeypatch.setattr(ops, "create_job", lambda *a, **k: "job-status-1")
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/daemon/kanban-km-config/status",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200
        assert r.json()["job_id"] == "job-status-1"


# ── GET /api/admin/daemon/{app}/logs ──────────────────────────────────────────


def _fake_logs_output() -> str:
    """Simulate ``pm2 logs --nostream --lines N`` output with 3 log lines."""
    return (
        "2026-06-22T10:00:00: [PM2] App kanban-km online\n"
        "2026-06-22T10:01:00: Processing tick\n"
        "2026-06-22T10:02:00: Tick complete\n"
    )


def test_daemon_logs_returns_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/admin/daemon/{app}/logs returns parsed log lines from pm2 stdout."""
    import subprocess

    api_mod = _setup(tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: type(
            "R",
            (),
            {"returncode": 0, "stdout": _fake_logs_output(), "stderr": ""},
        )(),
    )
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/daemon/kanban-km/logs")
        assert r.status_code == 200
        body = r.json()
        assert "lines" in body
        assert len(body["lines"]) == 3


def test_daemon_logs_respects_lines_param(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``?lines=N`` query parameter is forwarded to the subprocess call."""
    import subprocess

    api_mod = _setup(tmp_path)

    called_args: list[list[str]] = []

    def _fake_run(args: list[str], **_kw: object) -> object:
        called_args.append(args)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/daemon/kanban-km/logs?lines=50")
        assert r.status_code == 200
        assert len(called_args) == 1
        assert "--lines" in called_args[0]
        idx = called_args[0].index("--lines")
        assert called_args[0][idx + 1] == "50"


def test_daemon_logs_out_of_allowlist_refused_422(tmp_path: Path) -> None:
    """GET /api/admin/daemon/{app}/logs on a non-allowlisted app returns 422."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/daemon/kanban-autodeploy/logs")
        assert r.status_code == 422
        assert "not allowlisted" in r.json()["detail"]


def test_daemon_logs_pm2_unavailable_degrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing pm2 (FileNotFoundError) degrades to 200 ``{lines:[], error}`` — not a 500 traceback.

    Mirrors the sibling GET /api/admin/daemon degraded contract (the logs route previously had no
    try/except, so an unavailable/slow pm2 surfaced as an opaque 500 in the logs banner).
    """
    import subprocess

    api_mod = _setup(tmp_path)

    def _boom(*_a: object, **_k: object) -> object:
        raise FileNotFoundError("no pm2")

    monkeypatch.setattr(subprocess, "run", _boom)
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/daemon/kanban-km/logs")
        assert r.status_code == 200
        body = r.json()
        assert body["lines"] == []
        assert "no pm2" in body["error"]
