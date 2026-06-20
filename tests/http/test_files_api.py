"""HTTP tests for GET /api/files — the sandboxed script file picker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402


def _root(tmp_path: Path) -> Path:
    """Registry + a clone tree with a nested script to browse."""
    root = tmp_path / "root"
    root.mkdir()
    clone = tmp_path / "clone"
    (clone / ".claude" / "kanban").mkdir(parents=True)
    (clone / ".claude" / "kanban" / "check.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (clone / "README.md").write_text("hi", encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_x": {
                    "repo": "Org/repo",
                    "clone": str(clone),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                }
            }
        ),
        encoding="utf-8",
    )
    return root


def _client(tmp_path: Path) -> TestClient:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _root(tmp_path)
    api_mod.app.state.auth = None
    return TestClient(api_mod.app)


def test_lists_root(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/files").json()
    names = {e["name"]: e for e in body["entries"]}
    assert names[".claude"]["is_dir"] is True
    assert names["README.md"]["is_dir"] is False
    # dirs come before files
    assert body["entries"][0]["is_dir"] is True


def test_browse_subdir_and_exec_flag(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/files", params={"path": ".claude/kanban"}).json()
    names = {e["name"]: e for e in body["entries"]}
    assert "check.sh" in names
    assert names["check.sh"]["rel"] == ".claude/kanban/check.sh"


def test_escape_is_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/files", params={"path": "../.."}).status_code == 400
        assert client.get("/api/files", params={"path": "/etc"}).status_code == 400
