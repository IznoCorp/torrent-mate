"""HTTP tests for the read-only Monitoring endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402


def _single_project_root(tmp_path: Path) -> Path:
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


class _FakeStore:
    def __init__(self, states: list[Any]) -> None:
        self._states = states

    def list_running(self) -> tuple[Any, ...]:
        return tuple(self._states)


class _FakeSessions:
    def __init__(self, alive: dict[str, bool]) -> None:
        self._alive = alive

    def is_alive(self, name: str) -> bool:
        return self._alive.get(name, False)

    def capture(self, name: str) -> str:
        return f"pane of {name}"


def test_agents_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore(
        [
            SimpleNamespace(
                issue_number=7,
                status="running",
                heartbeat=1000.0,
                stage="InProgress",
                started=900.0,
                worktree="/wt/ticket-7",
                title="X",
            )
        ]
    )
    api_mod.app.state.monitor_sessions = _FakeSessions({"ticket-7": True})
    with TestClient(api_mod.app) as client:
        body = client.get("/api/monitor/agents").json()
    a = body["agents"][0]
    assert a["issue"] == 7
    assert a["state"] == "running"
    assert a["session_alive"] is True
    assert a["heartbeat_age"] is not None
    del api_mod.app.state.monitor_store
    del api_mod.app.state.monitor_sessions


class _CountingSnapshotter:
    def __init__(self, snapshot: Any) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def __call__(self, project_id: str) -> Any:
        self.calls += 1
        return self.snapshot


def _root_with_clone(tmp_path: Path) -> Path:
    """Registry + a clone with a real columns.yml/transitions.yml (columns come from config)."""
    import importlib.resources as r

    from kanbanmate.core.transitions_defaults import render_transitions_yaml

    root = tmp_path / "root"
    root.mkdir()
    ck = tmp_path / "clone" / ".claude" / "kanban"
    ck.mkdir(parents=True)
    ck.joinpath("transitions.yml").write_text(render_transitions_yaml("Org/repo"), encoding="utf-8")
    cols = (r.files("kanbanmate") / "assets" / "columns.yml.tmpl").read_text()
    ck.joinpath("columns.yml").write_text(cols, encoding="utf-8")
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


def test_board_endpoint_caches(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.monitor_routes as mon_mod
    from kanbanmate.core.domain import BoardSnapshot, Ticket

    snap = BoardSnapshot(
        tickets=(Ticket(item_id="i1", issue_number=1, title="First", column_key="Backlog"),),
        fetched_at=0.0,
    )
    api_mod.app.state.kanban_root = _root_with_clone(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])
    snapper = _CountingSnapshotter(snap)
    api_mod.app.state.monitor_snapshotter = snapper
    mon_mod._BOARD_CACHE.clear()
    with TestClient(api_mod.app) as client:
        b1 = client.get("/api/monitor/board").json()
        b2 = client.get("/api/monitor/board").json()
    col_keys = {c["key"] for c in b1["columns"]}
    assert "Backlog" in col_keys  # columns come from columns.yml
    assert b1["tickets"][0]["number"] == 1
    assert b2["tickets"][0]["number"] == 1
    assert snapper.calls == 1  # second call served from the TTL cache
    del api_mod.app.state.monitor_store
    del api_mod.app.state.monitor_snapshotter
    mon_mod._BOARD_CACHE.clear()


def test_pane_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_sessions = _FakeSessions({"ticket-7": True})
    with TestClient(api_mod.app) as client:
        alive = client.get("/api/monitor/agent/7/pane").json()
        gone = client.get("/api/monitor/agent/9/pane").json()
    assert alive == {"alive": True, "lines": "pane of ticket-7"}
    assert gone == {"alive": False, "lines": ""}
    del api_mod.app.state.monitor_sessions


def test_ticket_detail_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.monitor_routes as mon_mod
    from kanbanmate.core.domain import BoardSnapshot, Ticket

    snap = BoardSnapshot(
        tickets=(Ticket(item_id="i7", issue_number=7, title="Build it", column_key="InProgress"),),
        fetched_at=0.0,
    )

    class _FakeGH:
        def fetch_issue(self, number: int) -> Any:
            return SimpleNamespace(
                node_id="n",
                number=number,
                title="Build it",
                body="**codename**: monitoring\nbody",
            )

        def issue_context(self, number: int) -> Any:
            return SimpleNamespace(comments=("hi",), linked_issue_body=None)

    api_mod.app.state.kanban_root = _root_with_clone(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])
    api_mod.app.state.monitor_snapshotter = _CountingSnapshotter(snap)
    api_mod.app.state.monitor_github = _FakeGH()
    mon_mod._BOARD_CACHE.clear()
    with TestClient(api_mod.app) as client:
        d = client.get("/api/monitor/ticket/7").json()
    assert d["number"] == 7
    assert d["column_key"] == "InProgress"
    assert d["markers"]["codename"] == "monitoring"
    assert d["comments"] == ["hi"]
    for k in ("monitor_store", "monitor_snapshotter", "monitor_github"):
        delattr(api_mod.app.state, k)
    mon_mod._BOARD_CACHE.clear()


def test_monitor_file_reads_sandboxed(tmp_path: Path) -> None:
    """Happy path + sandbox: reads a clone file, rejects ``..`` escape, 404s a missing file."""
    import kanbanmate.http.config_api as api_mod

    clone = tmp_path / "clone"
    (clone / "docs").mkdir(parents=True)
    (clone / "docs" / "DESIGN.md").write_text("# Design\nhello", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")  # outside the clone

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    with TestClient(api_mod.app) as client:
        ok = client.get("/api/monitor/file", params={"path": "docs/DESIGN.md"})
        escape = client.get("/api/monitor/file", params={"path": "../secret.txt"})
        missing = client.get("/api/monitor/file", params={"path": "docs/NOPE.md"})

    assert ok.status_code == 200
    assert ok.json() == {"path": "docs/DESIGN.md", "content": "# Design\nhello"}
    assert escape.status_code == 400  # path escapes the clone root
    assert "top secret" not in escape.text
    assert missing.status_code == 404


def test_monitor_file_rejects_oversize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A file larger than the cap is refused with 413 (never streamed)."""
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.monitor_routes as mon_mod

    clone = tmp_path / "clone"
    clone.mkdir(parents=True)
    (clone / "big.md").write_text("x" * 100, encoding="utf-8")
    monkeypatch.setattr(mon_mod, "_MAX_FILE_BYTES", 10)

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/monitor/file", params={"path": "big.md"})

    assert resp.status_code == 413


def test_monitor_github_passes_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: the real GitHub client for ticket reads must carry repo (else fetch_issue 404s)."""
    import kanbanmate.adapters.github.client as gh_mod
    import kanbanmate.adapters.github.token as tok_mod
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.monitor_routes as mon_mod

    captured: dict[str, Any] = {}

    class _SpyClient:
        def __init__(self, token: str, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(gh_mod, "GithubClient", _SpyClient)
    monkeypatch.setattr(tok_mod, "load_token", lambda: "tok")
    if hasattr(api_mod.app.state, "monitor_github"):
        delattr(api_mod.app.state, "monitor_github")
    mon_mod._monitor_github(SimpleNamespace(project_id="PVT_x", repo="Org/repo"))
    assert captured["repo"] == "Org/repo"
    assert captured["project_id"] == "PVT_x"
