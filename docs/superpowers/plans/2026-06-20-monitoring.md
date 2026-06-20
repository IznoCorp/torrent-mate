# monitoring — Monitoring tab (helm PR 2-bis) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only **Monitoring** tab to the bridge config UI showing each board's live status, ticket detail (markers + comments + timeline), and live agent observability (state + read-only terminal tail), refreshing two-speed.

**Architecture:** New pure builders in `app/monitor.py` turn already-fetched data (GitHub snapshot, persisted running states, tmux capture/liveness, ticket body/comments) into JSON payloads. New auth-guarded GET endpoints in `http/config_api.py` do the I/O (with a server-side TTL cache for the board snapshot) and call the builders. A new Monitoring tab in the React SPA polls them (agents ~3 s, board ~15 s, ticket detail on open). No daemon change; read-only.

**Tech Stack:** Python 3.12, FastAPI (`[ui]` extra), pytest. Frontend: React + the in-repo `kanbanmate-design` system + the existing i18n (`web/src/i18n`).

## Global Constraints

- Python `>=3.12`; `make check` (ruff + `mypy --strict` + pytest + size guards) must pass.
- Hexagonal layering: `core/` pure; `app/` uses adapters/core/ports, never `cli`/`daemon`; `http/` may import `app`/`adapters`/`core`/`cli.init` (`tests/test_layering.py`). Project/registry resolution stays in `http` (reuse bridge's `_resolve_entry`).
- **Read-only**: no `send_text`/`send-keys`, no card moves/comments/cancel, no config writes, no daemon change, no new runtime-root files.
- All new `/api/*` routes are auth-guarded by the existing bridge middleware (they are NOT in `_AUTH_OPEN_PATHS`).
- Google-style docstrings; inline comments explain _why_; module soft-warning ~800 LOC / hard 1000.
- `rg`/`grep` always type/glob-filtered; network commands `--connect-timeout`/`--max-time`.
- Conventional Commits, scope `monitoring`. No version prefixes / AI attribution.
- Frontend: every user-facing string via `t()` in `web/src/i18n/{en,fr}.yaml` (English default + fallback).

## File Structure

**New backend:**

- `src/kanbanmate/app/monitor.py` — pure builders: `derive_state`, `build_board`, `build_agents`, `build_ticket_detail`.
- `tests/app/test_monitor.py` — unit tests for the builders.
- `tests/http/test_monitor_api.py` — endpoint tests (TestClient + injected fakes).

**Modified backend:**

- `src/kanbanmate/http/config_api.py` — 4 new GET endpoints + a board-snapshot TTL cache + small resolution helpers (`_monitor_store`, `_monitor_github`, `_running_by_issue`).

**New frontend (`web/src/`):**

- `panels/MonitoringPanel.jsx` — the tab (master-detail board + ticket detail + agent panel + pane tail).
- `api.js` additions: `monitorBoard`, `monitorAgents`, `monitorPane`, `monitorTicket`.
- `components/AppShell.jsx` — add the `monitoring` board-nav entry.
- `App.jsx` — route the `monitoring` tab.
- `i18n/{en,fr}.yaml` — `monitor.*` strings.

**Reference (read, don't modify):**

- `core/domain.py` (`BoardSnapshot`, `Column`, `Ticket`), `ports/store.py` (`TicketState`, `list_running`), `adapters/workspace/sessions.py` (`capture`/`is_alive`, name `ticket-{issue}`), `core/ticket_fields.py` (`parse_ticket_fields`), `core/body_edit.py` (`roadmap_marker`), `adapters/github/client.py` (`snapshot`/`issue_context`/`list_issue_comments`), `core/registry_resolve.py` (`safe_project_id`).

---

## Task 1: `app/monitor.py` — pure builders

**Files:**

- Create: `src/kanbanmate/app/monitor.py`
- Test: `tests/app/test_monitor.py`

**Interfaces:**

- Produces:
  - `def derive_state(status: str) -> str` — maps a `TicketState.status` (`"RUNNING"|"WAITING"|"BLOCKED"|…`) to `"running"|"waiting"|"blocked"`; anything else → `"idle"`.
  - `def build_board(columns, tickets, running_by_issue) -> dict` where `columns: list[(key,name,column_class)]`, `tickets: list[(number,title,column_key)]`, `running_by_issue: dict[int,str]` (issue → state). Returns `{"columns": [...], "tickets": [{number,title,column_key,agent_state}], "agents_summary": {running,waiting,blocked}}`.
  - `def build_agents(states, alive_by_issue, now) -> list[dict]` where `states: list[TicketStateLike]`, `alive_by_issue: dict[int,bool]`. Each → `{issue,title,stage,state,heartbeat_age,duration_s,branch,session_alive}`.
  - `def build_ticket_detail(number, title, column_key, body, comments, progress) -> dict` → `{number,title,column_key,markers:{roadmap,codename,design,plans}, comments:[{author,created_at,body}], timeline:[{kind,at,text}]}`.

> `TicketStateLike` = the `ports.store.TicketState` shape (fields used: `item_id`, `status`, `heartbeat`, `stage`, `started`, `worktree`, and the issue number — the store keys by issue; tests pass a `SimpleNamespace` with `issue`,`status`,`heartbeat`,`stage`,`started`,`worktree`). `comments` items expose `.author`,`.created_at`,`.body` (the `CommentRef` shape).

- [ ] **Step 1: Write the failing test**

```python
# tests/app/test_monitor.py
"""Unit tests for the pure read-only monitoring builders."""

from types import SimpleNamespace

from kanbanmate.app.monitor import (
    build_agents,
    build_board,
    build_ticket_detail,
    derive_state,
)


def test_derive_state_maps_status() -> None:
    assert derive_state("RUNNING") == "running"
    assert derive_state("WAITING") == "waiting"
    assert derive_state("BLOCKED") == "blocked"
    assert derive_state("IDLE") == "idle"


def test_build_board_groups_and_summarises() -> None:
    columns = [("Backlog", "Backlog", "inert"), ("InProgress", "In Progress", "inert")]
    tickets = [(1, "First", "Backlog"), (2, "Second", "InProgress")]
    board = build_board(columns, tickets, running_by_issue={2: "running"})
    assert board["columns"][0] == {"key": "Backlog", "name": "Backlog", "column_class": "inert"}
    by_num = {t["number"]: t for t in board["tickets"]}
    assert by_num[1]["agent_state"] is None
    assert by_num[2]["agent_state"] == "running"
    assert board["agents_summary"] == {"running": 1, "waiting": 0, "blocked": 0}


def test_build_agents_computes_age_and_duration() -> None:
    states = [
        SimpleNamespace(
            issue=7, status="RUNNING", heartbeat=1000.0, stage="InProgress",
            started=900.0, worktree="/wt/kanban/ticket-7", title="Build it",
        )
    ]
    agents = build_agents(states, alive_by_issue={7: True}, now=1010.0)
    a = agents[0]
    assert a["issue"] == 7
    assert a["state"] == "running"
    assert a["heartbeat_age"] == 10.0
    assert a["duration_s"] == 110.0
    assert a["session_alive"] is True
    assert a["branch"] == "ticket-7"  # basename of the worktree path


def test_build_ticket_detail_merges_timeline_newest_first() -> None:
    comments = [
        SimpleNamespace(author="izno", created_at="2026-06-20T10:00:00Z", body="hello"),
    ]
    progress = [{"at": "2026-06-20T11:00:00Z", "text": "phase 1 done"}]
    body = "**roadmap** RP1\n**codename** monitoring\n**design** docs/d.md\n**plans** docs/p.md\nbody text"
    d = build_ticket_detail(7, "Build it", "InProgress", body, comments, progress)
    assert d["markers"]["codename"] == "monitoring"
    assert d["markers"]["design"] == "docs/d.md"
    # timeline merges comments + progress, newest first
    kinds = [e["kind"] for e in d["timeline"]]
    assert kinds == ["progress", "comment"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/app/test_monitor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kanbanmate.app.monitor'`.

> Before implementing, CONFIRM the marker accessors: open `core/ticket_fields.py` (`parse_ticket_fields(body) -> dict` with keys incl. `codename`, `design_path`, `plan_paths`) and `core/body_edit.py` (`roadmap_marker(body) -> str|None`). Map them to the `markers` dict below. If `parse_ticket_fields` uses key `design_path`/`plan_paths`, alias them to `design`/`plans` in `build_ticket_detail` (the test asserts `design`/`plans`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/kanbanmate/app/monitor.py
"""Pure read-only builders for the Monitoring tab (helm PR 2-bis).

Each function takes ALREADY-FETCHED data (GitHub snapshot, persisted running states, tmux
liveness, ticket body/comments) and returns a JSON-serialisable payload. No I/O here — the HTTP
endpoints do the fetching and call these (DESIGN §4). Pure → fully unit-testable.

Layering: ``app`` may import ``core`` (pure marker parsers); it does NOT import ``cli``/``daemon``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from typing import Any

from kanbanmate.core.body_edit import roadmap_marker
from kanbanmate.core.ticket_fields import parse_ticket_fields

_STATE_MAP = {"RUNNING": "running", "WAITING": "waiting", "BLOCKED": "blocked"}


def derive_state(status: str) -> str:
    """Map a persisted ``TicketState.status`` to a UI agent state.

    Args:
        status: The store status string (e.g. ``"RUNNING"``).

    Returns:
        ``"running"`` / ``"waiting"`` / ``"blocked"``, or ``"idle"`` for anything else.
    """
    return _STATE_MAP.get(status, "idle")


def build_board(
    columns: Sequence[tuple[str, str, str]],
    tickets: Sequence[tuple[int, str, str]],
    running_by_issue: dict[int, str],
) -> dict[str, Any]:
    """Assemble the board-overview payload.

    Args:
        columns: ``(key, name, column_class)`` triples in board order.
        tickets: ``(number, title, column_key)`` triples.
        running_by_issue: ``{issue: state}`` for tickets with a live agent.

    Returns:
        ``{"columns", "tickets", "agents_summary"}`` (see Task 1 interfaces).
    """
    summary = {"running": 0, "waiting": 0, "blocked": 0}
    for state in running_by_issue.values():
        if state in summary:
            summary[state] += 1
    return {
        "columns": [{"key": k, "name": n, "column_class": c} for (k, n, c) in columns],
        "tickets": [
            {
                "number": num,
                "title": title,
                "column_key": col,
                "agent_state": running_by_issue.get(num),
            }
            for (num, title, col) in tickets
        ],
        "agents_summary": summary,
    }


def build_agents(
    states: Iterable[Any], alive_by_issue: dict[int, bool], now: float
) -> list[dict[str, Any]]:
    """Assemble the live-agents payload from persisted states + tmux liveness.

    Args:
        states: Persisted running ``TicketState``-like objects (``.issue``, ``.status``,
            ``.heartbeat``, ``.stage``, ``.started``, ``.worktree``, ``.title``).
        alive_by_issue: ``{issue: bool}`` tmux session liveness.
        now: Wall-clock epoch (heartbeat-age + duration reference).

    Returns:
        One dict per agent (see Task 1 interfaces).
    """
    agents: list[dict[str, Any]] = []
    for s in states:
        agents.append(
            {
                "issue": s.issue,
                "title": getattr(s, "title", ""),
                "stage": s.stage,
                "state": derive_state(s.status),
                "heartbeat_age": (now - s.heartbeat) if s.heartbeat else None,
                "duration_s": (now - s.started) if s.started else None,
                "branch": os.path.basename(s.worktree) if s.worktree else "",
                "session_alive": alive_by_issue.get(s.issue, False),
            }
        )
    return agents


def build_ticket_detail(
    number: int,
    title: str,
    column_key: str,
    body: str,
    comments: Iterable[Any],
    progress: Iterable[dict[str, str]],
) -> dict[str, Any]:
    """Assemble the on-demand ticket-detail payload (markers + comments + merged timeline).

    Args:
        number: Issue number.
        title: Issue title.
        column_key: The ticket's current column.
        body: The issue body markdown (for marker parsing).
        comments: ``CommentRef``-like objects (``.author``/``.created_at``/``.body``).
        progress: ``{"at", "text"}`` progress events from the store.

    Returns:
        ``{number, title, column_key, body, markers, comments, timeline}``.
    """
    fields = parse_ticket_fields(body)
    markers = {
        "roadmap": roadmap_marker(body),
        "codename": fields.get("codename") or None,
        "design": fields.get("design_path") or None,
        "plans": fields.get("plan_paths") or None,
    }
    comment_list = [
        {"author": c.author, "created_at": c.created_at, "body": c.body} for c in comments
    ]
    timeline = [
        {"kind": "comment", "at": c["created_at"], "text": c["body"]} for c in comment_list
    ] + [{"kind": "progress", "at": p["at"], "text": p["text"]} for p in progress]
    # Newest first; entries without a timestamp sort last (stable).
    timeline.sort(key=lambda e: e["at"] or "", reverse=True)
    return {
        "number": number,
        "title": title,
        "column_key": column_key,
        "body": body,
        "markers": markers,
        "comments": comment_list,
        "timeline": timeline,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/app/test_monitor.py -v`
Expected: PASS (4 tests). If the marker keys differ, adjust the aliases in `build_ticket_detail` (Step 2 note) and re-run.

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/app/monitor.py tests/app/test_monitor.py
git commit -m "feat(monitoring): pure read-only builders (board, agents, ticket detail)"
```

---

## Task 2: Backend resolution helpers + `GET /api/monitor/agents`

**Files:**

- Modify: `src/kanbanmate/http/config_api.py`
- Test: `tests/http/test_monitor_api.py`

**Interfaces:**

- Consumes: bridge `_resolve_entry`, `_kanban_root`; `app.monitor.build_agents`; `core.registry_resolve.safe_project_id`; `adapters.store.fs_store.FsStore`; `adapters.workspace.sessions.Sessions`.
- Produces:
  - `_monitor_store(entry) -> FsStore` — opens the store at the project's sub-root (`<root>/projects/<safe(pid)>` when the registry has >1 project, else the flat `<root>`), mirroring `daemon/registry_wiring`.
  - `_running_states(entry) -> list[TicketState]` — `_monitor_store(entry).list_running()`.
  - `GET /api/monitor/agents?project=` → `{"agents": [...]}` (see Task 1).
- Injection for tests: `app.state.monitor_store` / `app.state.monitor_sessions` override the real FsStore/Sessions when set (same pattern as bridge's `app.state.seeder`).

> Grounding to confirm first: `FsStore.__init__` signature (Task uses `FsStore(<root_path>)` — read `adapters/store/fs_store.py:88`); `TicketState` carries the issue number as an attribute or is keyed by issue in `list_running()` — if `list_running()` returns states WITHOUT an `.issue`, capture the issue from the store's keying (read the method) and attach it. The session name is `ticket-{issue}` (`app/actions.py:300`).

- [ ] **Step 1: Write the failing test**

```python
# tests/http/test_monitor_api.py
"""HTTP tests for the read-only Monitoring endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402


def _single_project_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    (root).mkdir()
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
    def __init__(self, states):
        self._states = states

    def list_running(self):
        return tuple(self._states)


class _FakeSessions:
    def __init__(self, alive):
        self._alive = alive

    def is_alive(self, name):
        return self._alive.get(name, False)

    def capture(self, name):
        return f"pane of {name}"


def test_agents_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore(
        [SimpleNamespace(issue=7, status="RUNNING", heartbeat=1000.0, stage="InProgress",
                         started=900.0, worktree="/wt/ticket-7", title="X")]
    )
    api_mod.app.state.monitor_sessions = _FakeSessions({"ticket-7": True})
    with TestClient(api_mod.app) as client:
        body = client.get("/api/monitor/agents", params={"now": 1010.0}).json()
    a = body["agents"][0]
    assert a["issue"] == 7 and a["state"] == "running" and a["session_alive"] is True
    del api_mod.app.state.monitor_store
    del api_mod.app.state.monitor_sessions
```

> The endpoint computes `now` from `time.time()`; the test passes `?now=` ONLY if you add an optional `now` query param for determinism. Simpler: don't add `now` to the API — instead assert `a["heartbeat_age"] is not None` / `a["state"] == "running"` (drop the exact-age assertion). Pick the no-`now` form to keep the API clean; adjust the test accordingly.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v`
Expected: FAIL with 404 (route missing).

- [ ] **Step 3: Write minimal implementation** (add to `config_api.py`, after the `/api/files` endpoint)

```python
def _monitor_store(entry):  # type: ignore[no-untyped-def]
    """Open the per-project state store at the same sub-root the daemon uses.

    N>1 registry → ``<root>/projects/<safe(project_id)>``; N==1 → the flat ``<root>``
    (mirrors ``daemon/registry_wiring``). Overridable via ``app.state.monitor_store`` (tests).
    """
    injected = getattr(app.state, "monitor_store", None)
    if injected is not None:
        return injected
    from kanbanmate.adapters.store.fs_store import FsStore  # noqa: PLC0415
    from kanbanmate.core.registry_resolve import safe_project_id  # noqa: PLC0415

    root = _kanban_root()
    registry = _load_registry(_projects_path(root))
    multi = len(registry) > 1
    store_root = root / "projects" / safe_project_id(entry.project_id) if multi else root
    return FsStore(store_root)


def _monitor_sessions():  # type: ignore[no-untyped-def]
    """Return the tmux Sessions adapter (overridable via app.state.monitor_sessions for tests)."""
    injected = getattr(app.state, "monitor_sessions", None)
    if injected is not None:
        return injected
    from kanbanmate.adapters.workspace.sessions import Sessions  # noqa: PLC0415

    return Sessions()


@app.get("/api/monitor/agents")
def monitor_agents(project: str | None = None) -> JSONResponse:
    """List the live agents for the selected board (local: store + tmux). DESIGN §5.2."""
    import time  # noqa: PLC0415

    from kanbanmate.app.monitor import build_agents  # noqa: PLC0415

    entry = _resolve_entry(project)
    states = list(_monitor_store(entry).list_running())
    sessions = _monitor_sessions()
    alive = {s.issue: sessions.is_alive(f"ticket-{s.issue}") for s in states}
    return JSONResponse(content={"agents": build_agents(states, alive, time.time())})
```

> If `list_running()` returns states without `.issue`, read the method and adapt: it is keyed by issue — attach the issue (e.g. `replace(s, issue=k)` or a small `(issue, state)` zip) before calling `build_agents`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/http/config_api.py tests/http/test_monitor_api.py
git commit -m "feat(monitoring): GET /api/monitor/agents (store + tmux, read-only)"
```

---

## Task 3: `GET /api/monitor/board` (server-cached snapshot)

**Files:**

- Modify: `src/kanbanmate/http/config_api.py`
- Test: `tests/http/test_monitor_api.py` (append)

**Interfaces:**

- Consumes: `app.monitor.build_board`, `derive_state`; `_monitor_store`; a board GitHub snapshot.
- Produces: `GET /api/monitor/board?project=` → board payload. A module-level TTL cache `_BOARD_CACHE: dict[str, tuple[float, BoardSnapshot]]` collapses calls within ~15 s. Snapshot source overridable via `app.state.monitor_snapshotter` (a `callable(project_id) -> BoardSnapshot` for tests / a counting fake).

- [ ] **Step 1: Write the failing test** (append)

```python
class _CountingSnapshotter:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def __call__(self, project_id):
        self.calls += 1
        return self.snapshot


def test_board_endpoint_caches(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.core.domain import BoardSnapshot, Column, ColumnClass, Ticket

    snap = BoardSnapshot(
        columns=(Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),),
        tickets=(Ticket(item_id="i1", number=1, title="First", column_key="Backlog"),),
    )
    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])
    snapper = _CountingSnapshotter(snap)
    api_mod.app.state.monitor_snapshotter = snapper
    api_mod._BOARD_CACHE.clear()
    with TestClient(api_mod.app) as client:
        b1 = client.get("/api/monitor/board").json()
        b2 = client.get("/api/monitor/board").json()
    assert b1["columns"][0]["key"] == "Backlog"
    assert b1["tickets"][0]["number"] == 1
    assert snapper.calls == 1  # second call served from the TTL cache
    del api_mod.app.state.monitor_store
    del api_mod.app.state.monitor_snapshotter
```

> Confirm the `BoardSnapshot`/`Column`/`Ticket` constructor fields against `core/domain.py` before writing (the test must match the real dataclasses — `Ticket` has `item_id`, `number`, `title`, `column_key`; `Column` has `key`, `name`, `column_class`).

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v -k board`
Expected: FAIL (route missing / `_BOARD_CACHE` undefined).

- [ ] **Step 3: Write minimal implementation** (add to `config_api.py`)

```python
# Board-snapshot TTL cache for the Monitoring tab (DESIGN §4): collapse rapid /api/monitor/board
# polls to ~1 GitHub snapshot per window per project. Module-level; keyed by project_id.
_BOARD_CACHE: dict[str, tuple[float, Any]] = {}
_BOARD_TTL_SECONDS = 15.0


def _board_snapshot(entry):  # type: ignore[no-untyped-def]
    """Return a cached GitHub board snapshot for ``entry`` (TTL ~15 s).

    Snapshot source overridable via ``app.state.monitor_snapshotter`` (tests). The real source
    builds a GithubClient bound to the project and calls ``snapshot()``.
    """
    import time  # noqa: PLC0415

    now = time.time()
    hit = _BOARD_CACHE.get(entry.project_id)
    if hit is not None and (now - hit[0]) < _BOARD_TTL_SECONDS:
        return hit[1]
    snapper = getattr(app.state, "monitor_snapshotter", None)
    if snapper is None:
        from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
        from kanbanmate.adapters.github.token import load_token  # noqa: PLC0415

        def snapper(pid: str):  # type: ignore[misc]
            return GithubClient(load_token(), project_id=pid).snapshot()

    snapshot = snapper(entry.project_id)
    _BOARD_CACHE[entry.project_id] = (now, snapshot)
    return snapshot


@app.get("/api/monitor/board")
def monitor_board(project: str | None = None) -> JSONResponse:
    """Board overview: columns → tickets + per-ticket agent state (cached snapshot). DESIGN §5.1."""
    from kanbanmate.app.monitor import build_board, derive_state  # noqa: PLC0415

    entry = _resolve_entry(project)
    try:
        snap = _board_snapshot(entry)
    except Exception as exc:  # noqa: BLE001 — boundary: surface a clean error, never a 500 traceback
        raise HTTPException(status_code=502, detail=f"Board snapshot failed: {exc}") from exc
    running = {s.issue: derive_state(s.status) for s in _monitor_store(entry).list_running()}
    columns = [(c.key, c.name, c.column_class.value) for c in snap.columns]
    tickets = [(t.number, t.title, t.column_key) for t in snap.tickets]
    return JSONResponse(content=build_board(columns, tickets, running))
```

> Confirm `ColumnClass` is an enum with `.value` (`core/domain.py`); if it's already a string, drop `.value`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v -k board`
Expected: PASS (snapshotter called once across two requests).

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/http/config_api.py tests/http/test_monitor_api.py
git commit -m "feat(monitoring): GET /api/monitor/board (server-cached snapshot + agent overlay)"
```

---

## Task 4: `GET /api/monitor/agent/{issue}/pane` (read-only terminal tail)

**Files:**

- Modify: `src/kanbanmate/http/config_api.py`
- Test: `tests/http/test_monitor_api.py` (append)

**Interfaces:**

- Consumes: `_monitor_sessions`. Produces: `{"alive": bool, "lines": str}`. Session name `ticket-{issue}`. `capture` only when alive (else `{"alive": false, "lines": ""}`).

- [ ] **Step 1: Write the failing test** (append)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v -k pane`
Expected: FAIL (404).

- [ ] **Step 3: Write minimal implementation**

```python
@app.get("/api/monitor/agent/{issue}/pane")
def monitor_pane(issue: int, project: str | None = None) -> JSONResponse:
    """Read-only terminal tail of the agent's tmux session (capture-pane). DESIGN §5.3.

    Never sends keystrokes — purely a snapshot. ``alive:false`` + empty when the session is gone.
    """
    _resolve_entry(project)  # validates the board selector (404/400) even though pane is local
    sessions = _monitor_sessions()
    name = f"ticket-{issue}"
    if not sessions.is_alive(name):
        return JSONResponse(content={"alive": False, "lines": ""})
    return JSONResponse(content={"alive": True, "lines": sessions.capture(name)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v -k pane`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/http/config_api.py tests/http/test_monitor_api.py
git commit -m "feat(monitoring): GET /api/monitor/agent/{issue}/pane (read-only tmux tail)"
```

---

## Task 5: `GET /api/monitor/ticket/{number}` (on-demand detail)

**Files:**

- Modify: `src/kanbanmate/http/config_api.py`
- Test: `tests/http/test_monitor_api.py` (append)

**Interfaces:**

- Consumes: `app.monitor.build_ticket_detail`; a GitHub client for `issue_context` + `list_issue_comments`; store progress (best-effort, may be empty). Overridable via `app.state.monitor_github` (a fake exposing `issue_context(number)` → object with `.body`/`.title` and `list_issue_comments(number)` → list of `CommentRef`-like).
- Produces: `GET /api/monitor/ticket/{number}?project=` → ticket-detail payload (Task 1).

> Confirm the `GithubClient.issue_context` return shape (`core`/`adapters` — it carries the linked-issue body + comments per `app/launch_context.py:71`) and `list_issue_comments(number)` (`ports/board.py:122`). Use whichever gives body + comments; if `issue_context` already bundles comments, use it and skip the separate call. The column for the ticket comes from the cached board snapshot (look up the number); title from the snapshot or the issue context.

- [ ] **Step 1: Write the failing test** (append)

```python
def test_ticket_detail_endpoint(tmp_path: Path) -> None:
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.core.domain import BoardSnapshot, Column, ColumnClass, Ticket

    snap = BoardSnapshot(
        columns=(Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),),
        tickets=(Ticket(item_id="i7", number=7, title="Build it", column_key="InProgress"),),
    )

    class _FakeGH:
        def issue_context(self, number):
            return SimpleNamespace(
                title="Build it",
                body="**codename** monitoring\nbody",
                comments=[SimpleNamespace(author="izno", created_at="2026-06-20T10:00:00Z", body="hi")],
            )

    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_store = _FakeStore([])
    api_mod.app.state.monitor_snapshotter = _CountingSnapshotter(snap)
    api_mod.app.state.monitor_github = _FakeGH()
    api_mod._BOARD_CACHE.clear()
    with TestClient(api_mod.app) as client:
        d = client.get("/api/monitor/ticket/7").json()
    assert d["number"] == 7
    assert d["markers"]["codename"] == "monitoring"
    assert d["timeline"][0]["kind"] == "comment"
    for k in ("monitor_store", "monitor_snapshotter", "monitor_github"):
        delattr(api_mod.app.state, k)
```

> Adapt the `_FakeGH` shape to whatever `issue_context` really returns (confirmed in Step "grounding"). If comments come from a separate `list_issue_comments`, add that method to `_FakeGH`.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v -k ticket_detail`
Expected: FAIL (404).

- [ ] **Step 3: Write minimal implementation**

```python
def _monitor_github(entry):  # type: ignore[no-untyped-def]
    """Return a GitHub client for monitoring reads (overridable via app.state.monitor_github)."""
    injected = getattr(app.state, "monitor_github", None)
    if injected is not None:
        return injected
    from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
    from kanbanmate.adapters.github.token import load_token  # noqa: PLC0415

    return GithubClient(load_token(), project_id=entry.project_id)


@app.get("/api/monitor/ticket/{number}")
def monitor_ticket(number: int, project: str | None = None) -> JSONResponse:
    """On-demand ticket detail: body + markers + comments + merged timeline. DESIGN §5.4."""
    from kanbanmate.app.monitor import build_ticket_detail  # noqa: PLC0415

    entry = _resolve_entry(project)
    # Column + title from the cached board snapshot (no extra GitHub call).
    snap = _board_snapshot(entry)
    column_key = next((t.column_key for t in snap.tickets if t.number == number), "")
    title = next((t.title for t in snap.tickets if t.number == number), "")
    try:
        ctx = _monitor_github(entry).issue_context(number)
    except Exception as exc:  # noqa: BLE001 — boundary: clean error in the detail pane (DESIGN §7)
        raise HTTPException(status_code=502, detail=f"Ticket fetch failed: {exc}") from exc
    comments = getattr(ctx, "comments", []) or []
    detail = build_ticket_detail(
        number, getattr(ctx, "title", "") or title, column_key,
        getattr(ctx, "body", "") or "", comments, progress=[],
    )
    return JSONResponse(content=detail)
```

> `progress=[]` is acceptable for v1 (the timeline still merges comments). If wiring store progress is cheap (a `read_status_events`/progress reader on the store), pass it; otherwise leave empty and note it in the PR.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/http/test_monitor_api.py -v`
Expected: PASS (all monitor endpoint tests).

- [ ] **Step 5: Backend gate + commit**

Run: `make lint && PYTHONPATH=src python -m pytest tests/app/test_monitor.py tests/http -v`
Expected: lint clean; all pass.

```bash
git add src/kanbanmate/http/config_api.py tests/http/test_monitor_api.py
git commit -m "feat(monitoring): GET /api/monitor/ticket/{n} (on-demand detail + timeline)"
```

---

## Task 6: Frontend — API client + i18n strings

**Files:**

- Modify: `web/src/api.js`, `web/src/i18n/en.yaml`, `web/src/i18n/fr.yaml`

**Interfaces:**

- Produces: `monitorBoard(project)`, `monitorAgents(project)`, `monitorPane(issue, project)`, `monitorTicket(number, project)` — fetch wrappers (the `call` helper already throws on non-2xx).

- [ ] **Step 1: Add the API methods**

```js
// web/src/api.js  (add near the other board-scoped calls)
export const monitorBoard = (project) =>
  call("GET", `/api/monitor/board${q(project)}`);
export const monitorAgents = (project) =>
  call("GET", `/api/monitor/agents${q(project)}`);
export const monitorPane = (issue, project) =>
  call(
    "GET",
    `/api/monitor/agent/${encodeURIComponent(issue)}/pane${q(project)}`,
  );
export const monitorTicket = (number, project) =>
  call("GET", `/api/monitor/ticket/${encodeURIComponent(number)}${q(project)}`);
```

- [ ] **Step 2: Add i18n strings** (both files, mirroring keys)

```yaml
# web/src/i18n/en.yaml  (new top-level `monitor:` block)
monitor:
  intro_title: Monitoring
  intro_body: >-
    Live read-only view of this board — columns, tickets, and the agents currently running. Refreshes
    automatically. Read-only: to interact with an agent, `tmux attach` on the host.
  summary: "{running} running · {waiting} waiting · {blocked} blocked"
  select_hint: Select a ticket to see its detail.
  no_agent: No agent running on this ticket.
  agent_state: state
  heartbeat: heartbeat
  stage: stage
  duration: duration
  branch: branch
  terminal: terminal (read-only)
  session_ended: Session ended.
  timeline: Timeline
  description: Description
  markers: Artifacts
  updated_ago: "updated {n}s ago"
```

```yaml
# web/src/i18n/fr.yaml
monitor:
  intro_title: Monitoring
  intro_body: >-
    Vue live en lecture seule de ce board — colonnes, tickets et les agents en cours. Rafraîchi
    automatiquement. Lecture seule : pour interagir avec un agent, fais `tmux attach` sur l'hôte.
  summary: "{running} en cours · {waiting} en attente · {blocked} bloqués"
  select_hint: Sélectionne un ticket pour voir son détail.
  no_agent: Aucun agent en cours sur ce ticket.
  agent_state: état
  heartbeat: heartbeat
  stage: étape
  duration: durée
  branch: branche
  terminal: terminal (lecture seule)
  session_ended: Session terminée.
  timeline: Historique
  description: Description
  markers: Artefacts
  updated_ago: "mis à jour il y a {n}s"
```

- [ ] **Step 3: Build to verify the bundles parse**

Run: `cd web && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add web/src/api.js web/src/i18n/en.yaml web/src/i18n/fr.yaml
git commit -m "feat(monitoring): SPA api client + i18n strings"
```

---

## Task 7: Frontend — Monitoring tab (master-detail) + nav wiring

**Files:**

- Create: `web/src/panels/MonitoringPanel.jsx`
- Modify: `web/src/components/AppShell.jsx` (nav entry), `web/src/App.jsx` (route)

**Interfaces:**

- Consumes: `api.monitorBoard/monitorAgents/monitorPane/monitorTicket`; `useT`; DS `HealthPill`/`KeyChip`/`Badge`/`Banner`.
- Produces: a board-scoped tab `monitoring` rendering the board overview + ticket detail + agent panel + pane tail, with two-speed polling.

- [ ] **Step 1: Add the nav entry** in `AppShell.jsx` `BOARD_NAV` (after `transitions` or at the end before `yaml`):

```jsx
{ id: "monitoring", tkey: "shell.nav.monitoring", key: "live" },
```

Add the i18n key to both bundles under `shell.nav`:

```yaml
# en.yaml shell.nav
    monitoring: Monitoring
# fr.yaml shell.nav
    monitoring: Monitoring
```

- [ ] **Step 2: Route it** in `App.jsx` `panels` map (board-scoped, needs `project=selected`):

```jsx
monitoring: <MonitoringPanel project={selected} />,
```

(import `MonitoringPanel` at top). MonitoringPanel does its own data loading (it does not use the config `draft`), so it works regardless of the config draft state — but it lives under the board scope so the header Save/Validate still show; that's fine (they act on the config draft, not monitoring). To avoid confusion, MonitoringPanel ignores `draft`.

- [ ] **Step 3: Implement `MonitoringPanel.jsx`**

```jsx
// Monitoring tab (helm PR 2-bis) — read-only live board + ticket detail + agent panel + pane tail.
// Two-speed polling: agents+pane ~3s, board ~15s, ticket detail on open. Pauses when hidden.
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import { useT } from "../i18n/index.jsx";

const { HealthPill, KeyChip, Badge, Banner } =
  window.KanbanMateDesignSystem_2463ad;

const STATE_TONE = { running: "accent", waiting: "amber", blocked: "red" };

function usePoll(fn, ms, deps) {
  React.useEffect(() => {
    let live = true;
    const tick = () => {
      if (document.visibilityState === "visible") fn();
    };
    tick();
    const id = setInterval(tick, ms);
    return () => {
      live = false;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export default function MonitoringPanel({ project }) {
  const { t } = useT();
  const [board, setBoard] = React.useState(null);
  const [agents, setAgents] = React.useState([]);
  const [sel, setSel] = React.useState(null); // selected ticket number
  const [detail, setDetail] = React.useState(null);
  const [pane, setPane] = React.useState(null);
  const [error, setError] = React.useState(null);

  usePoll(
    () =>
      api
        .monitorBoard(project)
        .then(setBoard)
        .catch((e) => setError(e.message)),
    15000,
    [project],
  );
  usePoll(
    () =>
      api
        .monitorAgents(project)
        .then((r) => setAgents(r.agents))
        .catch(() => {}),
    3000,
    [project],
  );

  // Ticket detail on selection.
  React.useEffect(() => {
    if (sel == null) return;
    setDetail(null);
    api
      .monitorTicket(sel, project)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [sel, project]);

  // Pane tail ~3s when the selected ticket has a running agent.
  const selAgent = agents.find((a) => a.issue === sel);
  usePoll(
    () => {
      if (sel != null && selAgent)
        api
          .monitorPane(sel, project)
          .then(setPane)
          .catch(() => {});
      else setPane(null);
    },
    3000,
    [sel, project, !!selAgent],
  );

  if (error && !board)
    return (
      <Banner tone="error" title="Monitoring">
        {error}
      </Banner>
    );
  if (!board) return <div style={{ padding: 24 }}>{t("common.loading")}</div>;

  const agentByIssue = Object.fromEntries(agents.map((a) => [a.issue, a]));
  const s = board.agents_summary;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <PageIntro title={t("monitor.intro_title")} scope="board">
        {t("monitor.intro_body")}
      </PageIntro>
      <div
        style={{
          marginBottom: 12,
          fontSize: 12,
          color: "var(--muted-foreground)",
        }}
      >
        {t("monitor.summary", {
          running: s.running,
          waiting: s.waiting,
          blocked: s.blocked,
        })}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "360px 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* board overview, columns as groups */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {board.columns.map((c) => {
            const tix = board.tickets.filter((t2) => t2.column_key === c.key);
            if (!tix.length) return null;
            return (
              <div
                key={c.key}
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "8px 12px",
                    background: "var(--muted)",
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    textTransform: "uppercase",
                    color: "var(--muted-foreground)",
                  }}
                >
                  {c.name} · {tix.length}
                </div>
                {tix.map((tk) => (
                  <button
                    key={tk.number}
                    onClick={() => setSel(tk.number)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      width: "100%",
                      textAlign: "left",
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      borderLeft: `3px solid ${sel === tk.number ? "var(--primary)" : "transparent"}`,
                      background:
                        sel === tk.number ? "var(--muted)" : "transparent",
                      cursor: "pointer",
                      padding: "8px 12px",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                      }}
                    >
                      #{tk.number}
                    </span>
                    <span
                      style={{
                        flex: 1,
                        fontSize: 12.5,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {tk.title}
                    </span>
                    {tk.agent_state && (
                      <Badge
                        tone={STATE_TONE[tk.agent_state] || "neutral"}
                        size="sm"
                      >
                        {tk.agent_state}
                      </Badge>
                    )}
                  </button>
                ))}
              </div>
            );
          })}
        </div>

        {/* ticket detail */}
        <div
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            padding: 18,
            minHeight: 200,
          }}
        >
          {sel == null ? (
            <div
              style={{
                color: "var(--muted-foreground)",
                textAlign: "center",
                padding: "40px 0",
              }}
            >
              {t("monitor.select_hint")}
            </div>
          ) : !detail ? (
            <div>{t("common.loading")}</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    color: "var(--muted-foreground)",
                  }}
                >
                  #{detail.number}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 600,
                    fontSize: "var(--text-md)",
                  }}
                >
                  {detail.title}
                </span>
                <KeyChip>{detail.column_key}</KeyChip>
              </div>
              {/* markers */}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {Object.entries(detail.markers)
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <span key={k} title={v}>
                      <KeyChip>
                        {k}: {v}
                      </KeyChip>
                    </span>
                  ))}
              </div>
              {/* agent panel + pane tail */}
              {selAgent ? (
                <div
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-md)",
                    padding: 12,
                    background: "var(--muted)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      gap: 14,
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--muted-foreground)",
                      marginBottom: 8,
                    }}
                  >
                    <span>
                      {t("monitor.agent_state")}: <b>{selAgent.state}</b>
                    </span>
                    <span>
                      {t("monitor.stage")}: {selAgent.stage}
                    </span>
                    <span>
                      {t("monitor.branch")}: {selAgent.branch}
                    </span>
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--muted-foreground)",
                      marginBottom: 4,
                    }}
                  >
                    {t("monitor.terminal")}
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: 10,
                      background: "var(--surface-inverse, #1e1e1e)",
                      color: "#e2e2d6",
                      borderRadius: "var(--radius-sm)",
                      maxHeight: 300,
                      overflow: "auto",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11.5,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {pane && pane.alive
                      ? pane.lines
                      : t("monitor.session_ended")}
                  </pre>
                </div>
              ) : (
                <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
                  {t("monitor.no_agent")}
                </div>
              )}
              {/* timeline */}
              <div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    textTransform: "uppercase",
                    color: "var(--muted-foreground)",
                    marginBottom: 6,
                  }}
                >
                  {t("monitor.timeline")}
                </div>
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 6 }}
                >
                  {detail.timeline.map((e, i) => (
                    <div key={i} style={{ fontSize: 12.5, lineHeight: 1.5 }}>
                      <KeyChip>{e.kind}</KeyChip>{" "}
                      <span style={{ color: "var(--muted-foreground)" }}>
                        {e.at}
                      </span>
                      <div style={{ whiteSpace: "pre-wrap" }}>{e.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

> If the DS `Badge` lacks the `amber` tone, use `neutral` for `waiting` (check the bundle — bridge confirmed `amber` exists). `var(--surface-inverse)` is used by the YAML panel; reuse it.

- [ ] **Step 4: Build + manual smoke**

Run: `cd web && npm run build`
Expected: build succeeds.

Manual (isolated serve against a COPY of a real root, or the live read-only — monitoring writes nothing): open the Monitoring tab → board groups render, click a ticket → detail loads, a running agent shows the live pane tail; switch boards → data follows; toggle EN/FR.

- [ ] **Step 5: Commit**

```bash
git add web/src/panels/MonitoringPanel.jsx web/src/components/AppShell.jsx web/src/App.jsx web/src/i18n/en.yaml web/src/i18n/fr.yaml
git commit -m "feat(monitoring): Monitoring tab — live board + ticket detail + agent pane tail"
```

---

## Final gate (before the PR)

- [ ] `make check` — lint + mypy strict + full suite + size guards, zero errors.
- [ ] `cd web && npm run build` — succeeds.
- [ ] Residual grep: `grep -rn "monitor" src/kanbanmate/app/monitor.py src/kanbanmate/http/config_api.py --include=*.py` — references resolve.
- [ ] `python -c "import kanbanmate"` (bare import, no `[ui]`).
- [ ] Untranslated-string scan over `web/src` (the bridge scan recipe) — zero hardcoded prose.
- [ ] Manual live read of the Monitoring tab on a real board (read-only — safe).

---

## Self-Review

**1. Spec coverage:**

- §2.1 Monitoring tab per board → Tasks 3,7. ✓
- §2.2 ticket detail (markers/comments/timeline) → Tasks 1,5,7. ✓
- §2.3 live agent view + read-only terminal tail → Tasks 1,2,4,7. ✓
- §2.4 two-speed refresh (agents ~3s, board cached ~15s, ticket on-demand) → Tasks 3 (cache), 7 (polling). ✓
- §2.5 read-only + auth-guarded → all endpoints under the bridge auth middleware; no write paths. ✓
- §3 data sources reused (snapshot/store/tmux/markers/comments) → Tasks 1–5. ✓
- §4 architecture (app/monitor pure + http I/O + TTL cache) → Tasks 1–5. ✓
- §5 the 4 endpoints → Tasks 2,3,4,5. ✓
- §6 UI master-detail + summary strip + agent panel + pane → Task 7. ✓
- §7 errors (GitHub fail → 502/last-cache + banner; session gone → alive:false; no agent → metadata) → Tasks 3,4,5,7. ✓
- §8 testing (builders unit, endpoints, cache, capture) → Tasks 1–5. ✓ (SPA light — manual, per spec.)

**2. Placeholder scan:** no TBD/TODO; every code step has real code. The "confirm shape" notes point at exact files/lines to verify the real dataclass/method shapes before writing each test (grounding, not placeholders).

**3. Type consistency:** `derive_state`→`build_board`/`build_agents` state strings (`running/waiting/blocked/idle`) consistent; `_monitor_store`/`_monitor_sessions`/`_board_snapshot`/`_monitor_github` helper names used identically across Tasks 2–5; API client names (`monitorBoard/Agents/Pane/Ticket`, Task 6) match the MonitoringPanel call sites (Task 7); payload keys (`agent_state`, `agents_summary`, `alive`/`lines`, `markers`, `timeline`) consistent between builders (Task 1), endpoints (Tasks 2–5) and the UI (Task 7).
