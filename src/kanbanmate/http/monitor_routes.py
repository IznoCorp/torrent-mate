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

from pydantic import BaseModel

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


class _BodyPatchRequest(BaseModel):
    """Request body for the PATCH ticket body endpoint (tiller §6.2).

    ``freeform`` is the operator's edited description prose — it replaces only the
    freeform region of the issue body; protected regions (status block, markers,
    brainstorm) are preserved byte-identically by the split/merge pipeline.
    """

    freeform: str


@app.patch("/api/monitor/ticket/{number}/body")
def patch_ticket_body(
    number: int, req: _BodyPatchRequest, project: str | None = None
) -> JSONResponse:
    """Marker-safe rewrite of a ticket's issue body (tiller §6.2).

    Fetches the current body, splits into protected regions + freeform, merges
    with the operator's new freeform, validates coherence, and patches GitHub.
    Protected regions (status block, markers, brainstorm) are NEVER altered.

    Args:
        number: The GitHub issue number.
        req: ``{"freeform": "<edited prose>"}`` — 1 MiB cap enforced by FastAPI.
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        ``{"ok": true}`` on success.

    Raises:
        HTTPException: 400 on roadmap/title incoherence; 404 issue not found; 502 GitHub error.
    """
    from kanbanmate.core.body_edit import validate_roadmap_matches_title  # noqa: PLC0415
    from kanbanmate.core.body_regions import merge_body_regions, split_body_regions  # noqa: PLC0415

    entry = _resolve_entry(project)
    gh = _monitor_github(entry)

    try:
        issue_ref = gh.fetch_issue(number)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Issue #{number} not found: {exc}") from exc

    current_body = issue_ref.body or ""
    title = issue_ref.title or ""

    regions = split_body_regions(current_body)
    merged = merge_body_regions(regions, new_freeform=req.freeform)

    coherence_error = validate_roadmap_matches_title(merged, title)
    if coherence_error:
        raise HTTPException(status_code=400, detail=coherence_error)

    try:
        gh.update_issue_body(issue_ref.node_id, merged)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub update failed: {exc}") from exc

    return JSONResponse(content={"ok": True})


def _git_show(repo: Path, ref: str, rel: str) -> str | None:
    """Return ``<ref>:<rel>`` from ``repo`` via ``git show``, or None if it is absent / git fails.

    The clone shares its ``.git`` with the per-ticket worktrees, so an in-flight artifact committed
    to the ``kanban/ticket-<n>`` WIP branch is readable even though it is not on the checked-out tree.
    No shell (arg list); ``ref``/``rel`` are caller-validated (int-derived ref, sandboxed rel path).
    """
    import subprocess  # noqa: PLC0415

    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "show", f"{ref}:{rel}"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


@app.get("/api/monitor/file")
def monitor_file(path: str, project: str | None = None, ticket: int | None = None) -> JSONResponse:
    """Read one text file for the board's clone, SANDBOXED to that root. Read-only. DESIGN §5.5.

    Backs the ticket-detail artifact reader: the operator clicks a design/plan marker and the UI
    renders the markdown. The sandbox mirrors ``/api/files`` — ``resolve()`` collapses ``..`` /
    symlinks, then ``is_relative_to(root)`` is the gate, so a path cannot escape the clone.

    Resolution order: (1) the checked-out tree (merged artifacts live on the clone's branch); then
    (2) if ``ticket`` is given, the per-ticket WIP branch ``kanban/ticket-<ticket>`` via ``git show``
    — in-flight design/plan files are committed there, not on the clone's branch, so without this an
    active ticket's artifacts read as "file not found".

    Args:
        path: The file path relative to the clone root (a marker value, e.g. ``docs/.../DESIGN.md``).
        project: The Project v2 node id selecting the board.
        ticket: Issue number, enabling the WIP-branch fallback for in-flight artifacts.

    Returns:
        ``{"path": str, "content": str, "source": "tree" | "kanban/ticket-<n>"}``.

    Raises:
        HTTPException: 503/404/400 (project resolution); 400 (path escapes the root); 404 (absent
        on both the tree and the WIP branch); 413 (file exceeds the size cap).
    """
    entry = _resolve_entry(project)
    root = Path(entry.clone).resolve()
    target = (root / path).resolve()
    # SANDBOX: the resolved target must stay within the clone root (blocks ``..`` / absolute /
    # symlink escapes — resolve() collapses them, then is_relative_to is the gate).
    if not (target == root or target.is_relative_to(root)):
        raise HTTPException(status_code=400, detail="Path escapes the project root")
    rel = str(target.relative_to(root))

    # (1) on-disk: the checked-out tree (merged / current-branch artifacts).
    if target.is_file():
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
        return JSONResponse(content={"path": rel, "content": content, "source": "tree"})

    # (2) fallback: the per-ticket WIP branch (in-flight artifacts the agent committed there).
    if ticket is not None:
        ref = f"kanban/ticket-{ticket}"
        wip = _git_show(root, ref, rel)
        if wip is not None:
            if len(wip.encode("utf-8")) > _MAX_FILE_BYTES:
                raise HTTPException(
                    status_code=413, detail=f"File too large (cap {_MAX_FILE_BYTES})"
                )
            return JSONResponse(content={"path": rel, "content": wip, "source": ref})

    raise HTTPException(
        status_code=404, detail="File not found on the board tree or the ticket WIP branch"
    )


# Side-effect import: registers the agent-terminal WS endpoint on `app` (tiller §1.3).
import kanbanmate.http.agent_terminal as _agent_terminal  # noqa: F401, E402
