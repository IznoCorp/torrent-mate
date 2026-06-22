"""Tests for the install-wizard PM2 bootstrap route (bosun sub-phase 5.3).

Covers ``POST /api/admin/wizard/bootstrap``: returns 409 when an allowlisted PM2 app already
exists (``_any_allowlisted_pm2_app_exists`` stubbed to ``True``), and 200 ``{job_id}`` when none
exist (stubbed to ``False`` + ``create_job`` monkeypatched).  Auth is disabled, so the
``X-KM-CSRF`` header is harmless when present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path) -> Any:
    """Bootstrap the config API with a minimal registry, auth off, routes registered."""
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
    api_mod.app.state.auth = None  # auth disabled → isolate this route
    return api_mod


# ── POST /api/admin/wizard/bootstrap ───────────────────────────────────────────


def test_wizard_bootstrap_409_when_apps_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/admin/wizard/bootstrap returns 409 when an allowlisted PM2 app exists."""
    api_mod = _setup(tmp_path)
    import kanbanmate.http.admin_routes as admin_routes

    monkeypatch.setattr(admin_routes, "_any_allowlisted_pm2_app_exists", lambda: True)

    with TestClient(api_mod.app) as client:
        client.get("/api/health")  # mint CSRF cookie
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/admin/wizard/bootstrap",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 409
        assert "already exist" in r.json()["detail"]


def test_wizard_bootstrap_returns_job_id_when_none_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/admin/wizard/bootstrap returns 200 {job_id} when no allowlisted app exists."""
    api_mod = _setup(tmp_path)
    import kanbanmate.http.admin_routes as admin_routes

    monkeypatch.setattr(admin_routes, "_any_allowlisted_pm2_app_exists", lambda: False)
    import kanbanmate.app.ops as ops

    monkeypatch.setattr(ops, "create_job", lambda *a, **kw: "fake-job-id")

    with TestClient(api_mod.app) as client:
        client.get("/api/health")  # mint CSRF cookie
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/admin/wizard/bootstrap",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200
        assert r.json()["job_id"] == "fake-job-id"


# ── _any_allowlisted_pm2_app_exists (the real first-run detector, ACC-12) ──────


class _FakeProc:
    """Minimal stand-in for a ``subprocess.run`` result (returncode + stdout)."""

    def __init__(self, returncode: int, stdout: str) -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_any_allowlisted_pm2_app_exists_true_when_jlist_has_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detector returns True when ``pm2 jlist`` reports an allowlisted app (real parse, no stub)."""
    import kanbanmate.http.admin_routes as admin_routes

    jlist = json.dumps([{"name": "other"}, {"name": "kanban-km"}])
    monkeypatch.setattr(
        "kanbanmate.http.admin_routes.subprocess.run", lambda *a, **k: _FakeProc(0, jlist)
    )
    assert admin_routes._any_allowlisted_pm2_app_exists() is True


def test_any_allowlisted_pm2_app_exists_false_when_jlist_has_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detector returns False when no allowlisted app is present (real parse, no stub)."""
    import kanbanmate.http.admin_routes as admin_routes

    jlist = json.dumps([{"name": "some-unrelated-app"}])
    monkeypatch.setattr(
        "kanbanmate.http.admin_routes.subprocess.run", lambda *a, **k: _FakeProc(0, jlist)
    )
    assert admin_routes._any_allowlisted_pm2_app_exists() is False


def test_any_allowlisted_pm2_app_exists_indeterminate_on_probe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detector returns None (indeterminate) on a pm2-probe failure — NOT False (bosun review-c2).

    A None return must NOT be conflated with "no apps": a transient ``jlist`` timeout while the
    daemons are live would otherwise let the first-run gate fail open. Covers a non-zero return,
    a timeout, malformed JSON, and pm2 absent.
    """
    import subprocess

    import kanbanmate.http.admin_routes as admin_routes

    # Non-zero return.
    monkeypatch.setattr(
        "kanbanmate.http.admin_routes.subprocess.run", lambda *a, **k: _FakeProc(1, "")
    )
    assert admin_routes._any_allowlisted_pm2_app_exists() is None

    # jlist times out.
    def _timeout(*_a: object, **_k: object) -> object:
        raise subprocess.TimeoutExpired(cmd="pm2 jlist", timeout=10)

    monkeypatch.setattr("kanbanmate.http.admin_routes.subprocess.run", _timeout)
    assert admin_routes._any_allowlisted_pm2_app_exists() is None

    # Malformed JSON.
    monkeypatch.setattr(
        "kanbanmate.http.admin_routes.subprocess.run", lambda *a, **k: _FakeProc(0, "not json")
    )
    assert admin_routes._any_allowlisted_pm2_app_exists() is None

    # pm2 binary absent.
    def _missing(*_a: object, **_k: object) -> object:
        raise FileNotFoundError("pm2")

    monkeypatch.setattr("kanbanmate.http.admin_routes.subprocess.run", _missing)
    assert admin_routes._any_allowlisted_pm2_app_exists() is None


def test_wizard_bootstrap_503_when_pm2_state_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/admin/wizard/bootstrap refuses 503 when the first-run state cannot be confirmed.

    A pm2-probe failure (detector returns None) must NOT proceed with bootstrap — it could
    double-start daemons that are actually live (bosun review-c2).
    """
    api_mod = _setup(tmp_path)
    import kanbanmate.http.admin_routes as admin_routes

    monkeypatch.setattr(admin_routes, "_any_allowlisted_pm2_app_exists", lambda: None)

    with TestClient(api_mod.app) as client:
        client.get("/api/health")  # mint CSRF cookie
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/admin/wizard/bootstrap",
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 503
        assert "cannot confirm first-run state" in r.json()["detail"]
