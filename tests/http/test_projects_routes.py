"""Tests for the bosun project onboarding routes (sub-phase 4.5).

Covers ``POST /api/projects`` validation (422 on a non-confined local path + a non-allowlisted git
URL), ``DELETE /api/projects/{id}`` (409 with a stubbed live agent, 200 on a real delete), and
``GET /api/admin/browse`` (entries inside a confined root, 422 outside). Auth is disabled, so the
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
    """Bootstrap the config API with a minimal one-project registry, auth off, routes registered."""
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.projects_routes  # noqa: F401 — register the routes

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


def test_create_local_path_outside_roots_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/projects mode=local with a path outside ONBOARD_BASE_DIRS returns 422."""
    api_mod = _setup(tmp_path)
    import kanbanmate.app.onboard as onboard

    (tmp_path / "dev").mkdir()
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/projects",
            json={"mode": "local", "repo": "O/r", "path": "/etc"},
            headers={"X-KM-CSRF": token},
        )
        assert r.status_code == 422


def test_create_clone_bad_url_422(tmp_path: Path) -> None:
    """POST /api/projects mode=clone with a scp-style (non-allowlisted) git URL returns 422."""
    api_mod = _setup(tmp_path)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/projects",
            json={"mode": "clone", "repo": "o/r", "git_url": "git@github.com:o/r.git"},
            headers={"X-KM-CSRF": token},
        )
        assert r.status_code == 422


def test_create_local_path_returns_job_with_local_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ACC-07 positive: a confined local path → job_id + type='project_add' + local-mode argv.

    Pins the happy-path argv branch (review-c2): mode=local builds ``[..., '--mode', 'local', ...,
    '--path', <path>]``. Capture the ``ops.create_job`` kwargs to assert the constructed command.
    """
    api_mod = _setup(tmp_path)
    import kanbanmate.app.onboard as onboard
    import kanbanmate.app.ops as ops

    base = tmp_path / "dev"
    proj = base / "ProjA"
    proj.mkdir(parents=True)
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(base),))

    captured: dict[str, Any] = {}

    def _capture(*_a: Any, **kw: Any) -> str:
        captured.update(kw)
        return "fake-job-id"

    monkeypatch.setattr(ops, "create_job", _capture)

    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/projects",
            json={"mode": "local", "repo": "O/r", "path": str(proj)},
            headers={"X-KM-CSRF": token},
        )
        assert r.status_code == 200
        assert r.json()["job_id"] == "fake-job-id"

    assert captured["type"] == "project_add"
    argv = captured["argv"]
    assert "--mode" in argv and argv[argv.index("--mode") + 1] == "local"
    assert "--path" in argv and argv[argv.index("--path") + 1] == str(proj)
    assert "--repo" in argv and argv[argv.index("--repo") + 1] == "O/r"
    assert "--git-url" not in argv


def test_create_clone_url_returns_job_with_clone_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ACC-07 positive: an allowlisted github.com clone URL → job_id + clone-mode argv.

    Pins the clone branch (review-c2): mode=clone builds ``[..., '--git-url', <url>]`` and does NOT
    carry ``--path`` — a swap of the two would now be caught.
    """
    api_mod = _setup(tmp_path)
    import kanbanmate.app.ops as ops

    url = "https://github.com/owner/repo.git"
    captured: dict[str, Any] = {}

    def _capture(*_a: Any, **kw: Any) -> str:
        captured.update(kw)
        return "clone-job-id"

    monkeypatch.setattr(ops, "create_job", _capture)

    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.post(
            "/api/projects",
            json={"mode": "clone", "repo": "owner/repo", "git_url": url},
            headers={"X-KM-CSRF": token},
        )
        assert r.status_code == 200
        assert r.json()["job_id"] == "clone-job-id"

    assert captured["type"] == "project_add"
    argv = captured["argv"]
    assert "--mode" in argv and argv[argv.index("--mode") + 1] == "clone"
    assert "--git-url" in argv and argv[argv.index("--git-url") + 1] == url
    assert "--path" not in argv


def test_delete_refused_409_with_live_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE /api/projects/{id} is refused 409 while the project has a live agent."""
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr

    monkeypatch.setattr(pr, "_project_has_live_agent", lambda pid: True)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.delete("/api/projects/PVT_x", headers={"X-KM-CSRF": token})
        assert r.status_code == 409


def test_delete_removes_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DELETE /api/projects/{id} deregisters the project when no live agent exists."""
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr

    monkeypatch.setattr(pr, "_project_has_live_agent", lambda pid: False)
    with TestClient(api_mod.app) as client:
        client.get("/api/health")
        token = client.cookies.get("km_csrf")
        assert token is not None
        r = client.delete("/api/projects/PVT_x", headers={"X-KM-CSRF": token})
        assert r.status_code == 200 and r.json()["deleted"] == "PVT_x"
    # Persisted: the key is gone from projects.json.
    on_disk = json.loads((api_mod.app.state.kanban_root / "projects.json").read_text())
    assert "PVT_x" not in on_disk


def test_project_has_live_agent_detects_real_running_state(tmp_path: Path) -> None:
    """_project_has_live_agent reads the REAL per-project store and sees a RUNNING ticket (ACC-08).

    Exercises the actual detection mechanism (not the route-level stub): seed a real RUNNING state
    under ``<root>/projects/<safe(pid)>/`` via the production FsStateStore, then assert the predicate
    returns True; a project with no state sub-root returns False.
    """
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr
    from kanbanmate.adapters.store.fs_store import FsStateStore
    from kanbanmate.core.registry_resolve import safe_project_id
    from kanbanmate.ports.store import TicketState, TicketStatus

    root = api_mod.app.state.kanban_root
    sub_root = root / "projects" / safe_project_id("PVT_x")
    store = FsStateStore(sub_root, nudge_root=root)
    store.save(
        TicketState(
            issue_number=5,
            item_id="I5",
            session_id="S5",
            status=TicketStatus.RUNNING,
            heartbeat=0.0,
        )
    )
    assert pr._project_has_live_agent("PVT_x") is True
    # A project that never ran has no sub-root → no live agent.
    assert pr._project_has_live_agent("PVT_never") is False


def test_project_has_live_agent_corrupt_state_is_failsafe_live(tmp_path: Path) -> None:
    """A corrupt/unparseable state JSON is treated as a live agent (fail-safe, review-c3).

    ``store.list_running()`` silently SKIPS poison files (H1 reaper safety), which would otherwise
    let a project whose only live agent has a corrupt state file pass the guard and be deregistered.
    The guard must instead fail SAFE: any unreadable/corrupt state ⇒ live.
    """
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr
    from kanbanmate.core.registry_resolve import safe_project_id

    root = api_mod.app.state.kanban_root
    state_dir = root / "projects" / safe_project_id("PVT_x") / "state"
    state_dir.mkdir(parents=True)
    # A garbage (non-JSON) state file — the store would drop it; the guard must keep the project live.
    (state_dir / "5.json").write_text("{not json", encoding="utf-8")
    assert pr._project_has_live_agent("PVT_x") is True


def test_project_has_live_agent_detects_alive_tmux_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An IDLE-state ticket whose tmux ``ticket-<n>`` session is alive counts as live (DESIGN §9).

    The persisted status is non-LIVE (IDLE) but the agent is still attached in tmux — the DESIGN §9
    tmux belt-and-suspenders. The guard probes ``Sessions.is_alive('ticket-<n>')`` over list_all.
    """
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr
    from kanbanmate.adapters.store.fs_store import FsStateStore
    from kanbanmate.adapters.workspace import sessions as sessions_mod
    from kanbanmate.core.registry_resolve import safe_project_id
    from kanbanmate.ports.store import TicketState, TicketStatus

    root = api_mod.app.state.kanban_root
    sub_root = root / "projects" / safe_project_id("PVT_x")
    store = FsStateStore(sub_root, nudge_root=root)
    store.save(
        TicketState(
            issue_number=7,
            item_id="I7",
            session_id="S7",
            status=TicketStatus.IDLE,  # non-LIVE: only the tmux probe can catch it
            heartbeat=0.0,
        )
    )
    # Stub the tmux probe: session "ticket-7" is alive.
    monkeypatch.setattr(
        sessions_mod.TmuxSessions, "is_alive", lambda self, name: name == "ticket-7"
    )
    assert pr._project_has_live_agent("PVT_x") is True


def test_project_has_live_agent_tmux_error_is_failsafe_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tmux/runner error during the liveness probe fails SAFE (treated as live, not 'no agent')."""
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr
    from kanbanmate.adapters.store.fs_store import FsStateStore
    from kanbanmate.adapters.workspace import sessions as sessions_mod
    from kanbanmate.core.registry_resolve import safe_project_id
    from kanbanmate.ports.store import TicketState, TicketStatus

    root = api_mod.app.state.kanban_root
    sub_root = root / "projects" / safe_project_id("PVT_x")
    store = FsStateStore(sub_root, nudge_root=root)
    store.save(
        TicketState(
            issue_number=8,
            item_id="I8",
            session_id="S8",
            status=TicketStatus.IDLE,
            heartbeat=0.0,
        )
    )

    def _boom(self: Any, name: str) -> bool:
        raise OSError("tmux not reachable")

    monkeypatch.setattr(sessions_mod.TmuxSessions, "is_alive", _boom)
    assert pr._project_has_live_agent("PVT_x") is True


def test_project_has_live_agent_idle_with_dead_tmux_is_not_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An IDLE ticket with NO alive tmux session is not live → delete proceeds (no false positive)."""
    api_mod = _setup(tmp_path)
    import kanbanmate.http.projects_routes as pr
    from kanbanmate.adapters.store.fs_store import FsStateStore
    from kanbanmate.adapters.workspace import sessions as sessions_mod
    from kanbanmate.core.registry_resolve import safe_project_id
    from kanbanmate.ports.store import TicketState, TicketStatus

    root = api_mod.app.state.kanban_root
    sub_root = root / "projects" / safe_project_id("PVT_x")
    store = FsStateStore(sub_root, nudge_root=root)
    store.save(
        TicketState(
            issue_number=9,
            item_id="I9",
            session_id="S9",
            status=TicketStatus.IDLE,
            heartbeat=0.0,
        )
    )
    monkeypatch.setattr(sessions_mod.TmuxSessions, "is_alive", lambda self, name: False)
    assert pr._project_has_live_agent("PVT_x") is False


def test_browse_lists_confined_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/admin/browse lists entries for a directory under ONBOARD_BASE_DIRS."""
    api_mod = _setup(tmp_path)
    import kanbanmate.app.onboard as onboard

    base = tmp_path / "dev"
    (base / "ProjA").mkdir(parents=True)
    (base / "file.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(base),))
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/browse", params={"path": str(base)})
        assert r.status_code == 200
        names = {e["name"]: e["is_dir"] for e in r.json()["entries"]}
        assert names["ProjA"] is True and names["file.txt"] is False


def test_browse_no_path_lists_first_base_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /api/admin/browse with NO path lists the first ONBOARD_BASE_DIRS root (initial open).

    The web DirBrowser opens the picker with no path; requiring ``path`` 422'd the dir-browser on
    every first open. The route now defaults an empty path to the first base root.
    """
    api_mod = _setup(tmp_path)
    import kanbanmate.app.onboard as onboard

    base = tmp_path / "dev"
    (base / "ProjA").mkdir(parents=True)
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(base),))
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/browse")  # NO path param — the picker's first open
        assert r.status_code == 200
        body = r.json()
        assert body["path"] == str(base.resolve())
        assert any(e["name"] == "ProjA" and e["is_dir"] for e in body["entries"])


def test_browse_outside_roots_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/admin/browse for a path outside ONBOARD_BASE_DIRS returns 422."""
    api_mod = _setup(tmp_path)
    import kanbanmate.app.onboard as onboard

    (tmp_path / "dev").mkdir()
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    with TestClient(api_mod.app) as client:
        r = client.get("/api/admin/browse", params={"path": "/etc"})
        assert r.status_code == 422
