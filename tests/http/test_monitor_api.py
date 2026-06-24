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
                    # keel step 5 (A): the registry default flipped to "native", which routes the
                    # monitor board endpoint to the LOCAL board.json placement source. These tests
                    # exercise the GitHub-snapshot cached path (they inject a _CountingSnapshotter),
                    # so pin the github backend explicitly to keep testing THAT path.
                    "board_backend": "github",
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
                labels=(),  # real IssueRef always carries labels (defaults to ())
            )

        def issue_context(self, number: int) -> Any:
            return SimpleNamespace(
                comments=("hi",),
                comment_dates=("2026-06-21T08:48:01Z",),
                linked_issue_body=None,
            )

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


def test_ticket_detail_exposes_track_and_labels(tmp_path: Path) -> None:
    """The detail GET surfaces the ticket's ``track`` (from a ``track:*`` label) + raw labels."""
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
                labels=("bug", "track:lite"),
            )

        def issue_context(self, number: int) -> Any:
            return SimpleNamespace(
                comments=(),
                comment_dates=(),
                linked_issue_body=None,
            )

    api_mod.app.state.kanban_root = _root_with_clone(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])
    api_mod.app.state.monitor_snapshotter = _CountingSnapshotter(snap)
    api_mod.app.state.monitor_github = _FakeGH()
    mon_mod._BOARD_CACHE.clear()
    with TestClient(api_mod.app) as client:
        d = client.get("/api/monitor/ticket/7").json()
    assert d["track"] == "lite"
    assert d["labels"] == ["bug", "track:lite"]
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
    assert ok.json() == {
        "path": "docs/DESIGN.md",
        "content": "# Design\nhello",
        "source": "tree",
    }
    assert escape.status_code == 400  # path escapes the clone root
    assert "top secret" not in escape.text
    assert missing.status_code == 404  # absent, and no ticket given for a WIP fallback


def test_monitor_file_falls_back_to_wip_branch(tmp_path: Path) -> None:
    """An in-flight artifact absent from the checked-out tree is read from kanban/ticket-<n>."""
    import subprocess

    import kanbanmate.http.config_api as api_mod

    clone = tmp_path / "clone"
    clone.mkdir(parents=True)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(clone), *args],
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "PATH": __import__("os").environ.get("PATH", ""),
            },
        )

    # main has no design; the design is committed only on the WIP branch.
    git("init", "-q", "-b", "main")
    (clone / "README.md").write_text("root", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-qm", "init")
    git("checkout", "-q", "-b", "kanban/ticket-5")
    (clone / "docs").mkdir()
    (clone / "docs" / "DESIGN.md").write_text("# anchor design\nbody", encoding="utf-8")
    git("add", "docs/DESIGN.md")
    git("commit", "-qm", "design")
    git("checkout", "-q", "main")  # back to a tree WITHOUT the design file

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    with TestClient(api_mod.app) as client:
        no_ticket = client.get("/api/monitor/file", params={"path": "docs/DESIGN.md"})
        with_ticket = client.get(
            "/api/monitor/file", params={"path": "docs/DESIGN.md", "ticket": 5}
        )

    assert no_ticket.status_code == 404  # not on the tree, no ticket → no fallback
    assert with_ticket.status_code == 200
    body = with_ticket.json()
    assert body["content"] == "# anchor design\nbody"
    assert body["source"] == "kanban/ticket-5"


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


# ---------------------------------------------------------------------------
# PATCH /api/monitor/ticket/{number}/body — marker-safe ticket-body editing
# (tiller §3.2).
# ---------------------------------------------------------------------------


class _FakeIssueRef:
    def __init__(self, body: str, title: str = "[A1] My ticket", node_id: str = "NODE_1") -> None:
        self.body = body
        self.title = title
        self.node_id = node_id


class _FakePatchGithub:
    def __init__(
        self, body: str = "**roadmap**: A1\n\nSome freeform.", title: str = "[A1] My ticket"
    ) -> None:
        self._ref = _FakeIssueRef(body=body, title=title)
        self.updated_body: str | None = None

    def fetch_issue(self, number: int) -> _FakeIssueRef:
        return self._ref

    def update_issue_body(self, node_id: str, body: str) -> None:
        self.updated_body = body


def test_body_patch_happy_path(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    gh = _FakePatchGithub()
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"freeform": "Updated operator description."},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert gh.updated_body is not None
    assert "Updated operator description." in gh.updated_body
    assert "**roadmap**: A1" in gh.updated_body  # marker preserved


def test_body_patch_400_on_roadmap_title_incoherence(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    # Body has roadmap B2 but title has [A1] — incoherent
    gh = _FakePatchGithub(body="**roadmap**: B2\n\nDesc.", title="[A1] My ticket")
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"freeform": "New prose."},
        )
    assert resp.status_code == 400
    assert "roadmap" in str(resp.json()["detail"])


def test_body_patch_422_bad_shape(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_github = _FakePatchGithub()
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"wrong_field": "oops"},
        )
    assert resp.status_code == 422


def test_body_patch_preserves_status_block(tmp_path: Path) -> None:
    from kanbanmate.core.body_edit import STATUS_BEGIN, STATUS_END

    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    status = f"{STATUS_BEGIN}\n**KanbanMate status** — Design · running\n{STATUS_END}"
    gh = _FakePatchGithub(body=f"{status}\n\n**roadmap**: A1\n\nOld prose.", title="[A1] T")
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"freeform": "New prose."},
        )
    assert resp.status_code == 200
    assert gh.updated_body is not None
    assert STATUS_BEGIN in gh.updated_body
    assert STATUS_END in gh.updated_body
    assert "**roadmap**: A1" in gh.updated_body


class _EnqStore:
    """Minimal store recording enqueued intents for the launch endpoint test."""

    def __init__(self) -> None:
        self.enq: list[tuple[str, dict[str, Any]]] = []

    def enqueue_intent(self, intent_id: str, payload: dict[str, Any]) -> None:
        self.enq.append((intent_id, dict(payload)))


def test_launch_endpoint_enqueues_intent(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    store = _EnqStore()
    api_mod.app.state.monitor_store = store
    with TestClient(api_mod.app) as client:
        resp = client.post(
            "/api/monitor/ticket/7/launch",
            json={"prompt": "fix the failing test", "profile": "dev"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["intent_id"], str) and body["intent_id"]
    assert len(store.enq) == 1
    _iid, payload = store.enq[0]
    assert payload["kind"] == "launch"
    assert payload["issue"] == 7
    assert payload["args"]["prompt"] == "fix the failing test"
    assert payload["args"]["profile"] == "dev"
    assert payload["caller"] == "operator"
    del api_mod.app.state.monitor_store


def test_launch_endpoint_accepts_empty_prompt(tmp_path: Path) -> None:
    """An empty prompt is allowed (bare claude the operator drives) — it still enqueues a launch."""
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    store = _EnqStore()
    api_mod.app.state.monitor_store = store
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/monitor/ticket/7/launch", json={"prompt": "   "})
    assert resp.status_code == 200
    assert len(store.enq) == 1
    _iid, payload = store.enq[0]
    assert payload["kind"] == "launch"
    assert payload["args"]["prompt"] == ""  # trimmed empty → daemon launches a bare claude
    del api_mod.app.state.monitor_store


def test_move_endpoint_enqueues_move_intent(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    store = _EnqStore()
    api_mod.app.state.monitor_store = store
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/monitor/ticket/7/move", json={"to_col": "Done"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert len(store.enq) == 1
    _iid, payload = store.enq[0]
    assert payload["kind"] == "move"
    assert payload["issue"] == 7
    assert payload["args"]["to_col"] == "Done"
    assert payload["caller"] == "operator"
    del api_mod.app.state.monitor_store


def test_move_endpoint_rejects_empty_destination(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    store = _EnqStore()
    api_mod.app.state.monitor_store = store
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/monitor/ticket/7/move", json={"to_col": "  "})
    assert resp.status_code == 400
    assert store.enq == []
    del api_mod.app.state.monitor_store


def test_intent_result_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None

    class _ResultStore:
        def load_intent_result(self, intent_id: str) -> dict[str, Any] | None:
            if intent_id == "known":
                return {"intent_id": "known", "state": "rejected", "detail": "nope"}
            return None

    api_mod.app.state.monitor_store = _ResultStore()
    with TestClient(api_mod.app) as client:
        hit = client.get("/api/monitor/intent/known").json()
        miss = client.get("/api/monitor/intent/unknown").json()
    assert hit == {"intent_id": "known", "state": "rejected", "detail": "nope"}
    assert miss == {"state": "pending"}
    del api_mod.app.state.monitor_store


def test_launch_endpoint_rejects_merge_profile(tmp_path: Path) -> None:
    """The launch endpoint refuses the engine-gated `merge` profile (400, nothing enqueued)."""
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    store = _EnqStore()
    api_mod.app.state.monitor_store = store
    with TestClient(api_mod.app) as client:
        resp = client.post(
            "/api/monitor/ticket/7/launch",
            json={"prompt": "do it", "profile": "merge"},
        )
    assert resp.status_code == 400
    assert store.enq == []
    del api_mod.app.state.monitor_store


# ---------------------------------------------------------------------------
# POST /api/monitor/ticket/{number}/track — set/clear the track:* override
# GET  /api/monitor/board/tracks — read the board's track:* overrides
# (skiff Task 14).
# ---------------------------------------------------------------------------


class _FakeTrackGithub:
    """Spy GH for the track endpoints: records set_issue_track_label calls; can raise ValueError."""

    def __init__(self, *, tracks: dict[int, str] | None = None) -> None:
        self.set_calls: list[tuple[int, str | None]] = []
        self._tracks = tracks or {}

    def set_issue_track_label(self, number: int, track_value: str | None) -> None:
        # Mirror the real client: an unknown lane is a ValueError BEFORE any write.
        from kanbanmate.core.transitions_defaults import TRACK_VALUES

        if track_value is not None and track_value not in TRACK_VALUES:
            raise ValueError(f"unknown track value {track_value!r}")
        self.set_calls.append((number, track_value))

    def board_item_tracks(self) -> dict[int, str]:
        return dict(self._tracks)


def test_set_track_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    gh = _FakeTrackGithub()
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/monitor/ticket/7/track?project=PVT_x", json={"track": "express"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert gh.set_calls == [(7, "express")]
    del api_mod.app.state.monitor_github


def test_set_track_endpoint_clears_with_null(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    gh = _FakeTrackGithub()
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/monitor/ticket/7/track?project=PVT_x", json={"track": None})
    assert resp.status_code == 200
    assert gh.set_calls == [(7, None)]  # null clears the override
    del api_mod.app.state.monitor_github


def test_set_track_endpoint_400_on_invalid_value(tmp_path: Path) -> None:
    """An unknown lane → the client raises ValueError → the handler maps it to 400."""
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    gh = _FakeTrackGithub()
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.post("/api/monitor/ticket/7/track?project=PVT_x", json={"track": "bogus"})
    assert resp.status_code == 400
    assert gh.set_calls == []  # nothing was written
    del api_mod.app.state.monitor_github


def test_board_tracks_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    gh = _FakeTrackGithub(tracks={7: "full", 9: "lite"})
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/monitor/board/tracks?project=PVT_x")
    assert resp.status_code == 200
    # JSON object keys are strings on the wire; the handler stringifies the int issue numbers.
    assert resp.json() == {"tracks": {"7": "full", "9": "lite"}}
    del api_mod.app.state.monitor_github


# ---------------------------------------------------------------------------
# keel STEP 2 — Monitoring board placement reads the LOCAL native board.json,
# not the GitHub snapshot; GitHub is consulted ONLY for identity (issue/title)
# under a longer-TTL identity cache that never gates placement.
# ---------------------------------------------------------------------------


class _FakeBoardStore:
    """Minimal native board store: returns a fixed board.json-shaped ``load()`` doc."""

    def __init__(self, doc: dict[str, Any]) -> None:
        self._doc = doc

    def load(self) -> dict[str, Any]:
        return dict(self._doc)


def _native_root_with_clone(tmp_path: Path) -> Path:
    """Like ``_root_with_clone`` but the registry entry is native-backed (board_backend=native)."""
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
                    "board_backend": "native",
                }
            }
        ),
        encoding="utf-8",
    )
    return root


def test_native_board_placement_comes_from_local_store_not_github_cache(tmp_path: Path) -> None:
    """Placement (column) is read from board.json; the GitHub snapshot supplies ONLY identity.

    The local store places item ``i1`` in ``InProgress``; the GitHub snapshot (identity source)
    reports a DIFFERENT, stale column (``Backlog``). The endpoint must report the LOCAL column.
    """
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.monitor_board_source as src_mod
    from kanbanmate.core.domain import BoardSnapshot, Ticket

    # GitHub snapshot is identity-only here; its column_key (Backlog) is deliberately STALE/ignored.
    snap = BoardSnapshot(
        tickets=(Ticket(item_id="i1", issue_number=42, title="First", column_key="Backlog"),),
        fetched_at=0.0,
    )
    api_mod.app.state.kanban_root = _native_root_with_clone(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])  # no live agents
    api_mod.app.state.board_store = _FakeBoardStore(
        {"version": 5, "columns": ["Backlog", "InProgress"], "order": {"InProgress": ["i1"]}}
    )
    api_mod.app.state.monitor_snapshotter = _CountingSnapshotter(snap)
    src_mod._IDENTITY_CACHE.clear()
    try:
        with TestClient(api_mod.app) as client:
            b = client.get("/api/monitor/board").json()
    finally:
        for k in ("monitor_store", "board_store", "monitor_snapshotter"):
            delattr(api_mod.app.state, k)
        src_mod._IDENTITY_CACHE.clear()

    assert len(b["tickets"]) == 1
    t = b["tickets"][0]
    assert t["number"] == 42  # identity (issue number) from GitHub
    assert t["title"] == "First"  # identity (title) from GitHub
    assert t["column_key"] == "InProgress"  # PLACEMENT from the LOCAL store, NOT the stale snapshot


def test_native_board_placement_survives_a_raising_github_identity_fetch(tmp_path: Path) -> None:
    """A GitHub outage degrades titles/identity but MUST NOT block placement (keel STEP 2)."""
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.monitor_board_source as src_mod

    class _BoomSnapshotter:
        def __call__(self, project_id: str) -> Any:
            raise RuntimeError("github is down")

    api_mod.app.state.kanban_root = _native_root_with_clone(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])
    api_mod.app.state.board_store = _FakeBoardStore(
        {"version": 1, "columns": ["Backlog", "InProgress"], "order": {"InProgress": ["i1"]}}
    )
    api_mod.app.state.monitor_snapshotter = _BoomSnapshotter()
    src_mod._IDENTITY_CACHE.clear()  # cold cache → fetch raises → identity is empty (degraded)
    try:
        with TestClient(api_mod.app) as client:
            resp = client.get("/api/monitor/board")
    finally:
        for k in ("monitor_store", "board_store", "monitor_snapshotter"):
            delattr(api_mod.app.state, k)
        src_mod._IDENTITY_CACHE.clear()

    # Placement still renders (200), the columns come from config, and a card with no resolvable
    # identity is omitted (legacy parity) — crucially the endpoint did NOT 5xx on the GitHub outage.
    assert resp.status_code == 200
    body = resp.json()
    assert "InProgress" in {c["key"] for c in body["columns"]}
    assert body["tickets"] == []  # no identity available → card omitted, but NO error


def test_native_board_serves_last_known_identity_across_an_outage(tmp_path: Path) -> None:
    """Once the identity cache is warm, a later raising fetch keeps serving the cached identity."""
    import kanbanmate.http.config_api as api_mod
    import kanbanmate.http.monitor_board_source as src_mod
    from kanbanmate.core.domain import BoardSnapshot, Ticket

    snap = BoardSnapshot(
        tickets=(Ticket(item_id="i1", issue_number=7, title="Warm", column_key="Backlog"),),
        fetched_at=0.0,
    )

    class _OnceThenBoom:
        def __init__(self, ok_snap: Any) -> None:
            self._snap = ok_snap
            self.calls = 0

        def __call__(self, project_id: str) -> Any:
            self.calls += 1
            if self.calls == 1:
                return self._snap
            raise RuntimeError("github went down after the first poll")

    api_mod.app.state.kanban_root = _native_root_with_clone(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])
    api_mod.app.state.board_store = _FakeBoardStore(
        {"version": 1, "columns": ["Backlog"], "order": {"Backlog": ["i1"]}}
    )
    snapper = _OnceThenBoom(snap)
    api_mod.app.state.monitor_snapshotter = snapper
    src_mod._IDENTITY_CACHE.clear()
    # Force a TTL of 0 so the SECOND poll re-fetches (and raises), proving the cache fallback path.
    orig_ttl = src_mod._IDENTITY_TTL_SECONDS
    src_mod._IDENTITY_TTL_SECONDS = 0.0
    try:
        with TestClient(api_mod.app) as client:
            first = client.get("/api/monitor/board").json()
            second = client.get("/api/monitor/board").json()
    finally:
        src_mod._IDENTITY_TTL_SECONDS = orig_ttl
        for k in ("monitor_store", "board_store", "monitor_snapshotter"):
            delattr(api_mod.app.state, k)
        src_mod._IDENTITY_CACHE.clear()

    assert snapper.calls == 2  # the second poll DID attempt a refetch (TTL=0) and it raised
    assert first["tickets"][0]["title"] == "Warm"
    # Even though the second fetch raised, the warmed identity is still served — placement + title.
    assert second["tickets"][0]["title"] == "Warm"
    assert second["tickets"][0]["column_key"] == "Backlog"


def test_native_board_triples_is_pure_and_keeps_build_board_signature() -> None:
    """``native_board_triples`` produces (number, title, column, is_closed) quads build_board consumes.

    Guards the keel STEP 2 contract: build_board's PARAMETER signature is UNCHANGED — the per-ticket
    tuples it receives have the same shape whether they came from the GitHub snapshot or the local
    store. The quad's 4th element (``is_closed``) is the ensign CLOSED-issue indicator, joined from
    the identity fetch.
    """
    import inspect

    from kanbanmate.app.monitor import build_board
    import kanbanmate.http.monitor_board_source as src_mod
    from kanbanmate.http.monitor_board_source import native_board_triples

    src_mod._IDENTITY_CACHE.clear()  # isolate from any HTTP-test-warmed cache (shared module state)
    # build_board parameter signature is unchanged (the documented STEP 2 invariant).
    params = list(inspect.signature(build_board).parameters)
    assert params == ["columns", "tickets", "running_by_issue", "blocked_column"]

    doc = {
        "version": 3,
        "columns": ["Backlog", "InProgress"],
        "order": {"Backlog": ["i2"], "InProgress": ["i1"]},
    }
    identity: dict[str, tuple[int | None, str, bool]] = {
        "i1": (10, "Build", False),
        "i2": (11, "Spec", True),  # CLOSED issue → is_closed rides through to the quad
        "i3": (12, "Orphan", False),
    }
    quads = native_board_triples("keel-pure-1", doc, lambda: identity)
    # Order follows the doc's column order then per-column order; i3 (not placed) is excluded.
    assert quads == [(11, "Spec", "Backlog", True), (10, "Build", "InProgress", False)]

    # The quads feed build_board with NO adaptation (proves the contract end-to-end).
    columns = [("Backlog", "Backlog", "neutral"), ("InProgress", "In progress", "active")]
    out = build_board(columns, quads, {})
    nums = {tk["number"] for tk in out["tickets"]}
    assert nums == {10, 11}
    closed_by_num = {tk["number"]: tk["is_closed"] for tk in out["tickets"]}
    assert closed_by_num == {11: True, 10: False}


def test_native_board_triples_omits_cards_with_unknown_issue_number() -> None:
    """A placed item with no resolvable issue number (draft / cold cache) is omitted (legacy parity)."""
    import kanbanmate.http.monitor_board_source as src_mod
    from kanbanmate.http.monitor_board_source import native_board_triples

    src_mod._IDENTITY_CACHE.clear()  # isolate from any HTTP-test-warmed cache (shared module state)
    doc = {"columns": ["Backlog"], "order": {"Backlog": ["draft1", "real1"]}}
    # draft1 has no identity → omitted; real1 resolves to an open issue (is_closed=False).
    identity: dict[str, tuple[int | None, str, bool]] = {"real1": (5, "Real", False)}
    quads = native_board_triples("keel-pure-2", doc, lambda: identity)
    assert quads == [(5, "Real", "Backlog", False)]


def test_move_targets_flags_mapping_and_fallback(tmp_path: Path) -> None:
    """_move_targets: current flag (allowed=False), shape, NAME->KEY mapping, fail-soft None."""
    import kanbanmate.http.monitor_routes as mon_mod
    from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH
    from kanbanmate.core.columns import load_columns

    _root_with_clone(tmp_path)  # writes a real columns.yml + transitions.yml under the clone
    clone = tmp_path / "clone"
    cols = load_columns((clone / CLONE_COLUMNS_RELPATH).read_text(encoding="utf-8"))
    first_key = next(iter(cols))
    entry = SimpleNamespace(clone=str(clone), project_id="PVT_x")

    targets = mon_mod._move_targets(entry, first_key)
    assert targets is not None
    for m in targets:
        assert set(m) == {"key", "name", "allowed", "current"}
    current = [m for m in targets if m["current"]]
    assert len(current) == 1 and current[0]["key"] == first_key
    assert current[0]["allowed"] is False  # cannot move to the column it is already in

    # NAME -> KEY seam: passing the current column's display NAME resolves to the same current KEY.
    by_name = mon_mod._move_targets(entry, cols[first_key].name)
    assert by_name is not None
    assert [m for m in by_name if m["current"]][0]["key"] == first_key

    # Fail-soft: a clone with no config yields None (UI falls back to a plain all-columns select).
    assert mon_mod._move_targets(SimpleNamespace(clone=str(tmp_path / "nope")), "X") is None
