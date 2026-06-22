"""Tests for POST /api/admin/redeploy route (bosun sub-phase 3.2)."""

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
    api_mod.app.state.auth = None  # auth disabled → isolate redeploy
    return api_mod


def test_redeploy_unknown_target_422(tmp_path: Path) -> None:
    """POST /api/admin/redeploy with an unknown target returns 422."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/admin/redeploy",
            json={"target": "moon"},
            headers={"X-KM-CSRF": token},
        )
        assert r.status_code == 422


def test_redeploy_prod_creates_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/admin/redeploy target=prod creates a detached redeploy job (ACC-05)."""
    api_mod = _setup(tmp_path)

    from kanbanmate.app import ops

    seen: dict[str, object] = {}

    def _fake(root: object, **k: object) -> str:
        seen.update(k)
        return "job-redeploy-1"

    monkeypatch.setattr(ops, "create_job", _fake)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/admin/redeploy",
            json={"target": "prod"},
            headers={"X-KM-CSRF": token},
        )
        assert r.status_code == 200 and r.json()["job_id"] == "job-redeploy-1"
        assert seen["type"] == "redeploy" and seen["args_summary"] == "target=prod"
        assert seen["argv"] == ["bash", "scripts/deploy.sh"]
        # cwd is load-bearing: the script must run in the prod clone, not the dev tree.
        assert str(seen["cwd"]).endswith("deploy/kanban-mate")


def test_redeploy_staging_creates_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/admin/redeploy target=staging creates a detached redeploy job (ACC-05)."""
    api_mod = _setup(tmp_path)

    from kanbanmate.app import ops

    seen: dict[str, object] = {}

    def _fake(root: object, **k: object) -> str:
        seen.update(k)
        return "job-redeploy-2"

    monkeypatch.setattr(ops, "create_job", _fake)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/admin/redeploy",
            json={"target": "staging"},
            headers={"X-KM-CSRF": token},
        )
        assert r.status_code == 200 and r.json()["job_id"] == "job-redeploy-2"
        assert seen["type"] == "redeploy" and seen["args_summary"] == "target=staging"
        assert seen["argv"] == ["bash", "scripts/deploy-staging.sh"]
