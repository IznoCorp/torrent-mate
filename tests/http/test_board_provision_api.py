"""HTTP tests for POST /api/board/provision (bridge / helm PR 2 sync-board).

Builds a real registry + clone so ``_get_service().load()`` reads the desired
columns from a real ``columns.yml``; injects a fake seeder via ``app.state`` so
no network call is made.
"""

from __future__ import annotations

import importlib.resources
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402

from kanbanmate.core.transitions_defaults import render_transitions_yaml  # noqa: E402


class _FakeSeeder:
    """A Seeder exposing status_options + ensure_columns, recording calls."""

    def __init__(self, options: dict[str, str]) -> None:
        self._options = dict(options)
        self.ensure_calls: list[list[str]] = []

    def status_options(self, project_id: str) -> dict[str, str]:
        return dict(self._options)

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        self.ensure_calls.append(list(columns))
        return {c: self._options.get(c, f"OPT_{c}") for c in columns}


def _columns_template_path() -> Path:
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    with importlib.resources.as_file(ref) as p:
        return Path(p)


def _setup(tmp_path: Path) -> tuple[Path, list[str]]:
    """Write a registry + a clone config; return (root, desired_column_names)."""
    from kanbanmate.core.config_model import PipelineDraft

    root = tmp_path / "root"
    root.mkdir()
    config_dir = tmp_path / "clone" / ".claude" / "kanban"
    config_dir.mkdir(parents=True)
    tp = config_dir / "transitions.yml"
    cp = config_dir / "columns.yml"
    tp.write_text(render_transitions_yaml("Org/repo"), encoding="utf-8")
    shutil.copy(_columns_template_path(), cp)

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
    draft = PipelineDraft.from_loaded(
        tp.read_text(encoding="utf-8"), cp.read_text(encoding="utf-8")
    )
    desired = [c.name for c in draft.definition.columns]
    return root, desired


def test_provision_dry_run(tmp_path: Path) -> None:
    root, desired = _setup(tmp_path)
    seeder = _FakeSeeder({})  # board has NO options → every desired column is an add
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = root
    api_mod.app.state.seeder = seeder
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/board/provision", json={"dry_run": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False
    added = {c["column"] for c in body["changes"] if c["kind"] == "add"}
    assert set(desired) <= added
    assert seeder.ensure_calls == []
    del api_mod.app.state.seeder


def test_provision_apply(tmp_path: Path) -> None:
    root, desired = _setup(tmp_path)
    seeder = _FakeSeeder({})
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = root
    api_mod.app.state.seeder = seeder
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/board/provision", json={"dry_run": False})
    assert resp.status_code == 200
    assert resp.json()["applied"] is True
    assert seeder.ensure_calls == [desired]
    del api_mod.app.state.seeder


class _ExplodingSeeder:
    """A Seeder whose probe raises — exercises the endpoint's 502 boundary handler."""

    def status_options(self, project_id: str) -> dict[str, str]:
        raise RuntimeError("boom: board unreachable")

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        raise RuntimeError("boom")


def test_provision_failure_is_clean_502(tmp_path: Path) -> None:
    root, _ = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = root
    api_mod.app.state.seeder = _ExplodingSeeder()
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/board/provision", json={"dry_run": True})
    assert resp.status_code == 502
    assert "boom" in resp.json()["detail"]
    del api_mod.app.state.seeder
