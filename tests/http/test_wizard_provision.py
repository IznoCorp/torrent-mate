"""Tests for the install-wizard board-provisioning route (bosun sub-phase 5.2).

Covers ``POST /api/admin/wizard/provision``: returns a ``job_id`` for a known project (job creation
monkeypatched so no real subprocess spawns), and 404 for an unknown project (the registry resolver's
verdict). Auth is disabled, so the ``X-KM-CSRF`` header is harmless when present.
"""

from __future__ import annotations

import json
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
                    "option_map": {"Backlog": "opt1", "Done": "opt2"},
                }
            }
        ),
        encoding="utf-8",
    )
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None  # auth disabled → isolate this route
    return api_mod


def test_wizard_provision_returns_job_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/admin/wizard/provision returns a job_id for a registered project."""
    api_mod = _setup(tmp_path)
    import kanbanmate.app.ops as ops

    captured: dict[str, Any] = {}

    def _fake_create_job(*_a: Any, **kw: Any) -> str:
        captured.update(kw)
        return "fake-job-id"

    monkeypatch.setattr(ops, "create_job", _fake_create_job)

    with TestClient(api_mod.app) as client:
        client.get("/api/health")  # mint CSRF cookie
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/wizard/provision",
            json={"project": "PVT_x"},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 200
        assert r.json()["job_id"] == "fake-job-id"

    # The job is a wizard_provision job whose server-constructed argv invokes the runner with the
    # canonical (registry-resolved) project id — never the raw client string blindly.
    assert captured["type"] == "wizard_provision"
    assert "kanbanmate.cli.provision_exec" in captured["argv"]
    assert "PVT_x" in captured["argv"]


def test_wizard_provision_unknown_project_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/admin/wizard/provision returns 404 when the project is not in the registry."""
    api_mod = _setup(tmp_path)
    import kanbanmate.app.ops as ops

    # Guard: create_job must NEVER run for an unknown project (resolver rejects first).
    monkeypatch.setattr(
        ops, "create_job", lambda *a, **kw: pytest.fail("create_job should not run for unknown")
    )

    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/wizard/provision",
            json={"project": "PVT_does_not_exist"},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 404


def test_wizard_provision_missing_project_422(tmp_path: Path) -> None:
    """POST /api/admin/wizard/provision returns 422 when no project is supplied."""
    api_mod = _setup(tmp_path)

    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        r = client.post(
            "/api/admin/wizard/provision",
            json={},
            headers={"X-KM-CSRF": token} if token else {},
        )
        assert r.status_code == 422
