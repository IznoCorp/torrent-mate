"""Monitoring endpoints (helm PR 2-bis, read-only) — registered on the shared config-API app.

Split out of ``http/config_api.py`` to keep that module under the size ceiling. These routes are
auth-guarded by the config API's middleware (they live under ``/api/*`` and are not in the
open-paths set). All read-only: board snapshot (cached) + persisted store + tmux capture; no writes.

Imported once at the end of ``config_api`` (a side-effect import) so the routes attach to the same
``app`` before the static SPA mount. It imports the shared ``app`` + resolution helpers from
``config_api`` (which are fully defined by the time that end-of-module import runs).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate.cli.init import _load_registry, _projects_path
from kanbanmate.http.config_api import (
    _get_service,
    _kanban_root,
    _resolve_entry,
    app,
)

# Board-snapshot TTL cache (DESIGN §4): collapse rapid /api/monitor/board polls to ~1 GitHub
# snapshot per window per project. Module-level; keyed by project_id.
_BOARD_CACHE: dict[str, tuple[float, Any]] = {}
_BOARD_TTL_SECONDS = 15.0

# Cap for the artifact file reader (DESIGN §5.5): these are markdown docs (brainstorm/design/plan),
# not blobs — a generous ceiling that still blocks accidentally serving a huge file over HTTP.
_MAX_FILE_BYTES = 512 * 1024


def _monitor_store(entry: Any) -> Any:
    """Open the per-project state store at the same sub-root the daemon uses.

    N>1 registry → ``<root>/projects/<safe(project_id)>``; N==1 → the flat ``<root>``
    (mirrors ``daemon/registry_wiring``). Overridable via ``app.state.monitor_store`` (tests).
    """
    injected = getattr(app.state, "monitor_store", None)
    if injected is not None:
        return injected
    from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415
    from kanbanmate.core.registry_resolve import safe_project_id  # noqa: PLC0415

    root = _kanban_root()
    registry = _load_registry(_projects_path(root))
    multi = len(registry) > 1
    store_root = root / "projects" / safe_project_id(entry.project_id) if multi else root
    return FsStateStore(store_root)


def _monitor_sessions() -> Any:
    """Return the tmux Sessions adapter (overridable via ``app.state.monitor_sessions``)."""
    injected = getattr(app.state, "monitor_sessions", None)
    if injected is not None:
        return injected
    from kanbanmate.adapters.workspace.sessions import TmuxSessions  # noqa: PLC0415

    return TmuxSessions()


def _board_snapshot(entry: Any) -> Any:
    """Return a cached GitHub board snapshot for ``entry`` (TTL ~15 s).

    Snapshot source overridable via ``app.state.monitor_snapshotter`` (tests). The real source
    builds a GithubClient bound to the project and calls ``snapshot()``.
    """
    now = time.time()
    hit = _BOARD_CACHE.get(entry.project_id)
    if hit is not None and (now - hit[0]) < _BOARD_TTL_SECONDS:
        return hit[1]
    snapper = getattr(app.state, "monitor_snapshotter", None)
    if snapper is None:
        from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
        from kanbanmate.adapters.github.token import load_token  # noqa: PLC0415

        def snapper(pid: str) -> Any:
            return GithubClient(load_token(), project_id=pid).snapshot()

    snapshot = snapper(entry.project_id)
    _BOARD_CACHE[entry.project_id] = (now, snapshot)
    return snapshot


def _monitor_github(entry: Any) -> Any:
    """Return a GitHub client for monitoring reads (overridable via ``app.state.monitor_github``).

    Passes BOTH ``project_id`` and ``repo``: ``fetch_issue`` / ``issue_context`` resolve the issue
    via ``self._repo`` (``owner/name``), so omitting it makes them 404 (the original ticket-detail
    bug).
    """
    injected = getattr(app.state, "monitor_github", None)
    if injected is not None:
        return injected
    from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
    from kanbanmate.adapters.github.token import load_token  # noqa: PLC0415

    return GithubClient(load_token(), project_id=entry.project_id, repo=entry.repo)


@app.get("/api/monitor/agents")
def monitor_agents(project: str | None = None) -> JSONResponse:
    """List the live agents for the selected board (local: store + tmux). DESIGN §5.2.

    Read-only: reads persisted running states + tmux liveness; sends nothing.

    Returns:
        ``{"agents": [...]}`` (one entry per live agent).
    """
    from kanbanmate.app.monitor import build_agents  # noqa: PLC0415

    entry = _resolve_entry(project)
    states = list(_monitor_store(entry).list_running())
    sessions = _monitor_sessions()
    alive = {s.issue_number: sessions.is_alive(f"ticket-{s.issue_number}") for s in states}
    return JSONResponse(content={"agents": build_agents(states, alive, time.time())})


@app.get("/api/monitor/board")
def monitor_board(project: str | None = None) -> JSONResponse:
    """Board overview: columns (from config) + tickets (cached snapshot) + agent overlay. DESIGN §5.1.

    Columns come from the board's ``columns.yml`` (no GitHub); tickets from the cached snapshot;
    per-ticket agent state from the persisted store. Read-only.

    Returns:
        ``{"columns", "tickets", "agents_summary"}``.

    Raises:
        HTTPException: 503/404/400 (project resolution); 502 (snapshot failure).
    """
    from kanbanmate.app.monitor import build_board, derive_state  # noqa: PLC0415

    entry = _resolve_entry(project)
    draft = _get_service(project).load()
    columns = [(c.key, c.name, c.column_class) for c in draft.definition.columns]
    try:
        snap = _board_snapshot(entry)
    except Exception as exc:  # noqa: BLE001 — boundary: clean error, never a 500 traceback
        raise HTTPException(status_code=502, detail=f"Board snapshot failed: {exc}") from exc
    tickets = [
        (t.issue_number, t.title, t.column_key) for t in snap.tickets if t.issue_number is not None
    ]
    running = {s.issue_number: derive_state(s.status) for s in _monitor_store(entry).list_running()}
    return JSONResponse(content=build_board(columns, tickets, running))


@app.get("/api/monitor/agent/{issue}/pane")
def monitor_pane(issue: int, project: str | None = None) -> JSONResponse:
    """Read-only terminal tail of the agent's tmux session (capture-pane). DESIGN §5.3.

    Never sends keystrokes — purely a snapshot. ``alive:false`` + empty when the session is gone.

    Returns:
        ``{"alive": bool, "lines": str}``.
    """
    _resolve_entry(project)  # validate the board selector (404/400) — pane data is local
    sessions = _monitor_sessions()
    name = f"ticket-{issue}"
    if not sessions.is_alive(name):
        return JSONResponse(content={"alive": False, "lines": ""})
    return JSONResponse(content={"alive": True, "lines": sessions.capture(name)})


@app.get("/api/monitor/ticket/{number}")
def monitor_ticket(number: int, project: str | None = None) -> JSONResponse:
    """On-demand ticket detail: body + markers + comments + timeline. DESIGN §5.4.

    Title/body from ``fetch_issue`` (the ticket's own body carries the markers); comments from
    ``issue_context`` (chronological bodies); column from the cached snapshot (no extra call).
    Read-only.

    Returns:
        The ticket-detail payload (see :func:`kanbanmate.app.monitor.build_ticket_detail`).

    Raises:
        HTTPException: 503/404/400 (project resolution); 502 (GitHub fetch failure).
    """
    from kanbanmate.app.monitor import build_ticket_detail  # noqa: PLC0415

    entry = _resolve_entry(project)
    snap = _board_snapshot(entry)
    column_key = next((t.column_key for t in snap.tickets if t.issue_number == number), "")
    gh = _monitor_github(entry)
    try:
        ref = gh.fetch_issue(number)
        ctx = gh.issue_context(number)
    except Exception as exc:  # noqa: BLE001 — boundary: clean error in the detail pane (DESIGN §7)
        raise HTTPException(status_code=502, detail=f"Ticket fetch failed: {exc}") from exc
    detail = build_ticket_detail(
        number, ref.title, column_key, ref.body or "", ctx.comments, progress=[]
    )
    return JSONResponse(content=detail)


@app.get("/api/monitor/file")
def monitor_file(path: str, project: str | None = None) -> JSONResponse:
    """Read one text file under the board's clone, SANDBOXED to that root. Read-only. DESIGN §5.5.

    Backs the ticket-detail artifact reader: the operator clicks a design/plan marker and the UI
    renders the markdown. The sandbox mirrors ``/api/files`` — ``resolve()`` collapses ``..`` /
    symlinks, then ``is_relative_to(root)`` is the gate, so a path cannot escape the clone.

    Args:
        path: The file path relative to the clone root (a marker value, e.g. ``docs/.../DESIGN.md``).
        project: The Project v2 node id selecting the board.

    Returns:
        ``{"path": str, "content": str}`` — ``path`` normalised relative to the clone root.

    Raises:
        HTTPException: 503/404/400 (project resolution); 400 (path escapes the root); 404 (no such
        file — e.g. the artifact only exists on a feature branch, not the checked-out tree); 413
        (file exceeds the size cap).
    """
    entry = _resolve_entry(project)
    root = Path(entry.clone).resolve()
    target = (root / path).resolve()
    # SANDBOX: the resolved target must stay within the clone root (blocks ``..`` / absolute /
    # symlink escapes — resolve() collapses them, then is_relative_to is the gate).
    if not (target == root or target.is_relative_to(root)):
        raise HTTPException(status_code=400, detail="Path escapes the project root")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found in the board clone")
    size = target.stat().st_size
    if size > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size} bytes; cap {_MAX_FILE_BYTES})",
        )
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # noqa: BLE001 — boundary: clean error, never a 500 traceback
        raise HTTPException(status_code=400, detail=f"Cannot read file: {exc}") from exc
    return JSONResponse(content={"path": str(target.relative_to(root)), "content": content})
