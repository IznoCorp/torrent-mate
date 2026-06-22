"""Tests for install wizard token + first-project routes (bosun sub-phase 5.1).

Covers ``POST /api/admin/wizard/token`` (write <root>/token 0600, 422 on empty) and
``POST /api/admin/wizard/project`` (delegates to ``create_project``, returns a ``job_id``).
Auth is disabled, so the ``X-KM-CSRF`` header is harmless when present.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path) -> Any:
    """Bootstrap the config API with a minimal one-project registry, auth off, routes registered."""
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
    api_mod.app.state.auth = None  # auth disabled → isolate these routes
    return api_mod


# ── POST /api/admin/wizard/token ─────────────────────────────────────────────────


def test_wizard_token_writes_0600_file(tmp_path: Path) -> None:
    """POST /api/admin/wizard/token writes <root>/token with mode 0600 and correct content."""
    api_mod = _setup(tmp_path)
    root = api_mod.app.state.kanban_root

    with TestClient(api_mod.app) as client:
        client.get("/api/health")  # mint CSRF cookie
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/wizard/token",
            json={"token": "ghp_test123"},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

    token_file = root / "token"
    assert token_file.exists()
    assert token_file.read_text() == "ghp_test123"
    mode = oct(stat.S_IMODE(os.stat(str(token_file)).st_mode))
    assert mode == "0o600", f"expected 0o600, got {mode}"


def test_wizard_token_rejects_empty(tmp_path: Path) -> None:
    """POST /api/admin/wizard/token returns 422 when the token value is empty."""
    api_mod = _setup(tmp_path)

    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/wizard/token",
            json={"token": ""},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 422


def test_wizard_token_overwrites_existing(tmp_path: Path) -> None:
    """POST /api/admin/wizard/token overwrites an existing token file and preserves 0600."""
    api_mod = _setup(tmp_path)
    root = api_mod.app.state.kanban_root

    # Write an initial token manually.
    (root / "token").write_text("old_token")

    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/wizard/token",
            json={"token": "new_token"},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200

    assert (root / "token").read_text() == "new_token"
    mode = oct(stat.S_IMODE(os.stat(str(root / "token")).st_mode))
    assert mode == "0o600", f"expected 0o600, got {mode}"


# ── POST /api/admin/wizard/project ──────────────────────────────────────────────


def test_wizard_project_returns_job_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/admin/wizard/project delegates to create_project and returns a job_id."""
    api_mod = _setup(tmp_path)
    import kanbanmate.app.ops as ops
    import kanbanmate.http.projects_routes as pr

    monkeypatch.setattr(pr, "path_is_confined", lambda p: True)
    monkeypatch.setattr(ops, "create_job", lambda *a, **kw: "fake-job-id")
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/wizard/project",
            json={"mode": "local", "repo": "O/r", "path": str(tmp_path)},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200
        assert r.json()["job_id"] == "fake-job-id"
