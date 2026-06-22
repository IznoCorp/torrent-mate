"""Tests for the app-wide CSRF middleware (bosun §6, 2.3 auth-gated refinement).

The middleware enforces a double-submit CSRF check ONLY when auth is enabled (a session exists to
protect); the ``km_csrf`` cookie is always minted. These tests drive the REAL enforcement context
(auth ENABLED + a logged-in session) against a real mutating route (``PATCH /api/projects/{id}``),
and assert the auth-DISABLED control still passes (proving the gating preserves the pre-existing
auth-off behaviour relied on by the other mutating-endpoint tests).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402

from kanbanmate.http.auth import AuthConfig  # noqa: E402

_LOGIN = "admin"
_PASSWORD = "hunter2"
_SECRET = "csrf-test-secret"


def _seed_root(tmp_path: Path) -> Path:
    """Write a one-project registry so ``PATCH /api/projects/{id}`` resolves a real entry."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_x": {
                    "repo": "Org/repo",
                    "clone": str(tmp_path / "clone"),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                }
            }
        ),
        encoding="utf-8",
    )
    return root


def _setup(tmp_path: Path, *, auth_enabled: bool) -> Any:
    """Configure the shared app module with a seeded root and the requested auth state."""
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.csrf_mw  # noqa: F401  (side-effect: registers the middleware)

    api_mod.app.state.kanban_root = _seed_root(tmp_path)
    api_mod.app.state.auth = (
        AuthConfig(login=_LOGIN, password=_PASSWORD, secret=_SECRET) if auth_enabled else None
    )
    return api_mod


def test_get_mints_csrf_cookie(tmp_path: Path) -> None:
    """A GET that lacked the cookie gets a freshly minted ``km_csrf`` (minted regardless of auth)."""
    api_mod = _setup(tmp_path, auth_enabled=False)
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert "km_csrf" in resp.cookies  # minted on a GET that lacked it


def test_authenticated_mutation_requires_csrf_header(tmp_path: Path) -> None:
    """Auth ON + logged in: a mutating call is 403 without X-KM-CSRF, NOT-403 with the matching one."""
    api_mod = _setup(tmp_path, auth_enabled=True)
    with TestClient(api_mod.app) as client:
        # Establish a real session (sets the km_ui_session cookie) + mint the km_csrf cookie.
        login = client.post("/api/login", json={"login": _LOGIN, "password": _PASSWORD})
        assert login.status_code == 200 and login.json()["authenticated"] is True
        token = client.cookies.get("km_csrf")
        assert token

        # No CSRF header → 403 (the session cookie alone is insufficient — double-submit).
        no_header = client.patch("/api/projects/PVT_x", json={"enabled": True})
        assert no_header.status_code == 403

        # Matching X-KM-CSRF == km_csrf cookie → passes CSRF (200, not a 403).
        ok = client.patch(
            "/api/projects/PVT_x", json={"enabled": True}, headers={"X-KM-CSRF": token}
        )
        assert ok.status_code != 403
        assert ok.status_code == 200


def test_auth_disabled_mutation_not_csrf_blocked(tmp_path: Path) -> None:
    """Auth OFF: the same mutating call is NOT CSRF-blocked (gating preserves auth-off behaviour)."""
    api_mod = _setup(tmp_path, auth_enabled=False)
    with TestClient(api_mod.app) as client:
        resp = client.patch("/api/projects/PVT_x", json={"enabled": True})
        # No CSRF header, no session — yet NOT 403, because enforcement is gated on auth ENABLED.
        assert resp.status_code != 403
        assert resp.status_code == 200
