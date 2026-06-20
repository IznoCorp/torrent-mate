"""HTTP tests for the bridge multi-board endpoints (GET/PATCH /api/projects) + selector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402


def _two_project_root(tmp_path: Path) -> Path:
    """Write a registry with TWO projects + a clone config for each; return the root."""
    from kanbanmate.core.transitions_defaults import render_transitions_yaml

    root = tmp_path / "root"
    root.mkdir()
    reg: dict[str, dict[str, str]] = {}
    for pid, repo, slug in [
        ("PVT_a", "Org/alpha", "alpha"),
        ("PVT_b", "Org/beta", "beta"),
    ]:
        ck = tmp_path / slug / ".claude" / "kanban"
        ck.mkdir(parents=True)
        (ck / "transitions.yml").write_text(render_transitions_yaml(repo), encoding="utf-8")
        import importlib.resources as r

        cols = (r.files("kanbanmate") / "assets" / "columns.yml.tmpl").read_text()
        (ck / "columns.yml").write_text(cols, encoding="utf-8")
        reg[pid] = {
            "repo": repo,
            "clone": str(tmp_path / slug),
            "project_id": pid,
            "status_field_node_id": "FLD",
        }
    (root / "projects.json").write_text(json.dumps(reg), encoding="utf-8")
    return root


def test_get_projects_lists_both(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _two_project_root(tmp_path)
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/projects")
    assert resp.status_code == 200
    ids = {p["project_id"] for p in resp.json()["projects"]}
    assert ids == {"PVT_a", "PVT_b"}
    assert all("enabled" in p and "ingress" in p for p in resp.json()["projects"])


def test_get_config_ambiguous_without_project_is_400(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _two_project_root(tmp_path)
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/config")
    assert resp.status_code == 400
    assert "project" in json.dumps(resp.json()).lower()


def test_get_config_with_project_selects_board(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _two_project_root(tmp_path)
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/config?project=PVT_b")
    assert resp.status_code == 200
    assert resp.json()["binding"]["project"] == "Org/beta"


def test_get_config_unknown_project_is_404(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _two_project_root(tmp_path)
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/config?project=PVT_nope")
    assert resp.status_code == 404


def test_patch_project_toggles_enabled_and_ingress(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    root = _two_project_root(tmp_path)
    api_mod.app.state.kanban_root = root
    with TestClient(api_mod.app) as client:
        resp = client.patch("/api/projects/PVT_a", json={"enabled": False, "ingress": "polling"})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["ingress"] == "polling"
    # Persisted to disk.
    on_disk = json.loads((root / "projects.json").read_text())
    assert on_disk["PVT_a"]["enabled"] is False
    assert on_disk["PVT_a"]["ingress"] == "polling"


def test_patch_project_rejects_bad_ingress(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _two_project_root(tmp_path)
    with TestClient(api_mod.app) as client:
        resp = client.patch("/api/projects/PVT_a", json={"ingress": "carrier-pigeon"})
    assert resp.status_code == 422
