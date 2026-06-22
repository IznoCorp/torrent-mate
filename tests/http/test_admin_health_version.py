"""Tests for /api/admin/health + /api/admin/version (bosun §7.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path, *, auth_enabled: bool = False) -> Any:
    import kanbanmate.http.config_api as api_mod

    import kanbanmate.http.admin_routes  # noqa: F401
    import kanbanmate.http.ops_routes  # noqa: F401

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
    api_mod.app.state.auth = None
    return api_mod


def test_admin_health_authed_returns_rows(tmp_path: Path) -> None:
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/health")
        assert r.status_code == 200
        body = r.json()
        assert body["projects"][0]["project_id"] == "PVT_x"
        assert "pause_active" in body and "session_secret_pinned" in body


def test_admin_version_has_local(tmp_path: Path) -> None:
    from kanbanmate import __version__

    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        body = client.get("/api/admin/version").json()
        assert body["local"] == __version__
        assert "remote" in body and "update_available" in body
        # `build` is the served SHA (or "unknown" in a source checkout). `update_available` must be a
        # genuine SHA-vs-SHA comparison, so it is False whenever either side is "unknown" (no
        # always-true badge). In CI there is no BUILD_COMMIT stamp → build == "unknown".
        assert "build" in body
        if body["build"] == "unknown" or body["remote"] == "unknown":
            assert body["update_available"] is False


def test_admin_health_requires_auth_when_enabled(tmp_path: Path) -> None:
    """With auth enabled and no cookie, the dashboard is rejected (401) — NOT public."""
    from kanbanmate.http.auth import AuthConfig

    api_mod = _setup(tmp_path)
    api_mod.app.state.auth = AuthConfig(login="op", password="secret", secret="s3cr3t")
    with TestClient(api_mod.app) as client:
        assert client.get("/api/admin/health").status_code == 401


def test_admin_health_authenticated_session_returns_rows(tmp_path: Path) -> None:
    """ACC-02 positive: auth ENABLED + a valid login → GET /api/admin/health 200 with the rows.

    The existing ``test_admin_health_authed_returns_rows`` runs with auth DISABLED, so it never
    exercised the authenticated-success branch (review-c2). This pins it: enable auth, log in to
    establish a session cookie, then assert the dashboard returns 200 + the per-project row.
    """
    from kanbanmate.http.auth import AuthConfig

    api_mod = _setup(tmp_path)
    api_mod.app.state.auth = AuthConfig(login="op", password="secret", secret="s3cr3t")
    with TestClient(api_mod.app) as client:
        login = client.post("/api/login", json={"login": "op", "password": "secret"})
        assert login.status_code == 200 and login.json()["authenticated"] is True
        r = client.get("/api/admin/health")
        assert r.status_code == 200
        body = r.json()
        assert body["projects"][0]["project_id"] == "PVT_x"
        assert "pause_active" in body and "session_secret_pinned" in body


def test_admin_mutating_route_rejects_unauthenticated(tmp_path: Path) -> None:
    """ACC-10 (mutating verbs): an unauthenticated POST to a privileged mutating admin route is
    rejected. Two distinct rejections, depending on whether the CSRF header is supplied:

    * No CSRF header → 403: the CSRF middleware runs OUTERMOST (registered last) and short-circuits
      before the auth guard. So an unauthenticated mutating request surfaces as 403, NOT 401 — the
      ACCEPTANCE/DESIGN "unauthenticated POST → 401" wording is corrected to match.
    * Valid CSRF header echoed (cookie value) but NO session cookie → 401: this passes the outer
      CSRF guard and reaches the auth guard, proving the auth guard is actually exercised on a
      mutating verb (a regression that disabled it would otherwise be masked by the outer 403).

    Pins the masked auth-guard path that no prior test exercised.
    """
    import kanbanmate.http.csrf_mw  # noqa: F401  (side-effect: registers the CSRF middleware)
    from kanbanmate.http.auth import AuthConfig

    api_mod = _setup(tmp_path)
    api_mod.app.state.auth = AuthConfig(login="op", password="secret", secret="s3cr3t")
    with TestClient(api_mod.app) as client:
        # Mint the km_csrf cookie via a GET (no session established → still unauthenticated).
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token

        # No CSRF header, no session → outer CSRF guard rejects with 403 (before auth).
        no_csrf = client.post("/api/admin/pause", json={"active": True})
        assert no_csrf.status_code == 403

        # Valid CSRF header but no session → passes CSRF, hits the auth guard → 401.
        with_csrf = client.post(
            "/api/admin/pause", json={"active": True}, headers={"X-KM-CSRF": token}
        )
        assert with_csrf.status_code == 401
