"""Project onboarding HTTP routes (bosun §9) — create/delete on the shared app.

Registered on the shared config-API ``app`` by side-effect import (from ``config_api`` BEFORE the SPA
mount). Auth-gated by ``_auth_guard`` and CSRF-protected by ``csrf_mw`` for the mutating verbs.

``POST /api/projects`` is a detached JOB (clone + ``init`` are long + network-bound) whose argv is
**server-constructed** — ``[sys.executable, "-m", "kanbanmate.cli.onboard_exec", ...]`` — never a
client path. ``DELETE /api/projects/{id}`` is synchronous, audited, and REFUSES (409) while the
project still has a live agent (any RUNNING/WAITING ticket in its store sub-root).
"""

from __future__ import annotations

import sys

import fastapi
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate.app import ops
from kanbanmate.app.audit import append_audit
from kanbanmate.app.onboard import path_is_confined
from kanbanmate.core.git_url import validate_git_url
from kanbanmate.core.registry_resolve import safe_project_id
from kanbanmate.http.config_api import _actor_login, _kanban_root, _read_json_object, app
from kanbanmate.ports.store import LIVE_STATUSES


def _project_has_live_agent(project_id: str) -> bool:
    """True if the project has any live agent (DESIGN §9 live-agent guard — fail-safe).

    Implements the DESIGN §9 contract that a project is LIVE when it has a ticket RUNNING/WAITING
    **OR** an alive tmux ``ticket-<n>`` session. The guard fails SAFE — any ambiguity counts as
    "agent present" so a delete never races a running agent (review-c3):

    1. **Corrupt/unreadable state ⇒ live.** A state JSON the store cannot parse is treated as
       INDETERMINATE → live, rather than silently skipped. ``store.list_running()`` quietly drops
       poison files (H1 reaper safety), which would otherwise let a project whose ONLY live agent
       has a corrupt state file pass the guard and be deregistered out from under that agent.
    2. **Persisted LIVE status ⇒ live.** Any tracked state whose status is in
       :data:`LIVE_STATUSES` (RUNNING/WAITING).
    3. **Alive tmux session ⇒ live.** For every tracked ticket (any status), probe
       ``Sessions.is_alive("ticket-<n>")`` — catches an agent still attached in tmux after its
       state was cleared/lost (the DESIGN §9 belt-and-suspenders).

    Resolves the project's per-project store sub-root (``<root>/projects/<safe(project_id)>/`` — the
    SAME layout the daemon's :mod:`kanbanmate.daemon.registry_wiring` and ``health_dashboard`` use).

    Args:
        project_id: The Project v2 node id of the project being removed.

    Returns:
        ``True`` when at least one live signal exists for the project (fail-safe), else ``False``.
    """
    import json  # noqa: PLC0415

    from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415
    from kanbanmate.adapters.workspace.sessions import TmuxSessions  # noqa: PLC0415

    sub_root = _kanban_root() / "projects" / safe_project_id(project_id)
    if not sub_root.exists():
        # No per-project state dir → no tracked agent (N=1 boards keep state at the runtime root,
        # but a project being deleted in an N>1 registry always has its own sub-root if it ever ran).
        return False

    # (1) Fail-safe on corrupt state: a state file the store would silently skip is treated as a live
    # signal. Scan the raw state dir directly — list_running() swallows poison files, so we cannot
    # learn about them through it. An UNREADABLE file (OSError) is also indeterminate ⇒ live.
    state_dir = sub_root / "state"
    if state_dir.is_dir():
        for path in state_dir.glob("*.json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return True

    store = FsStateStore(sub_root)
    # (2) Persisted RUNNING/WAITING status.
    if any(s.status in LIVE_STATUSES for s in store.list_running()):
        return True

    # (3) Alive tmux session for ANY tracked ticket regardless of status (the DESIGN §9 tmux clause).
    # Use list_all so an agent still attached in tmux AFTER its state was cleared to a non-LIVE
    # status (e.g. IDLE) is still caught. issue_number is the session correlation key (``ticket-<n>``).
    # is_alive shells out to ``tmux has-session`` — a runner error there must fail SAFE (treat as
    # live), never as "no agent".
    sessions = TmuxSessions()
    for s in store.list_all():
        try:
            if sessions.is_alive(f"ticket-{s.issue_number}"):
                return True
        except Exception:  # noqa: BLE001 — any tmux/runner failure is indeterminate ⇒ fail-safe live
            return True
    return False


@app.post("/api/projects")
async def create_project(request: fastapi.Request) -> JSONResponse:
    """Add a project (``mode:local|clone``) as a detached job (DESIGN §9). 422 on bad path/URL.

    Args:
        request: The FastAPI request carrying the JSON body
            (``mode`` + ``repo`` + one of ``path`` / ``git_url``).

    Returns:
        ``{"job_id": <id>}`` for the spawned ``project_add`` job.

    Raises:
        HTTPException: 422 when ``mode`` is unknown, the local ``path`` is outside the allowed roots,
            or the clone ``git_url`` fails the allowlist.
    """
    body = await _read_json_object(request)
    mode = str(body.get("mode", ""))
    root = str(_kanban_root())
    repo = str(body.get("repo", ""))  # "owner/name" for the registry entry
    # The runner is invoked as a STANDALONE module (sys.executable -m …), NOT as a ``kanban``
    # sub-command — the sibling-module pattern keeps cli/app.py under the 1000-LOC ceiling.
    runner = [sys.executable, "-m", "kanbanmate.cli.onboard_exec"]
    if mode == "local":
        path = str(body.get("path", ""))
        if not path_is_confined(path):
            raise HTTPException(status_code=422, detail="path outside allowed roots")
        argv = [*runner, "--mode", "local", "--root", root, "--repo", repo, "--path", path]
    elif mode == "clone":
        git_url = str(body.get("git_url", ""))
        reason = validate_git_url(git_url)
        if reason is not None:
            raise HTTPException(status_code=422, detail=reason)
        argv = [*runner, "--mode", "clone", "--root", root, "--repo", repo, "--git-url", git_url]
    else:
        raise HTTPException(status_code=422, detail="mode must be 'local' or 'clone'")
    login = _actor_login(request)
    job_id = ops.create_job(
        _kanban_root(),
        type="project_add",
        actor=login,
        argv=argv,
        args_summary=f"mode={mode}",
    )
    # job_id in the audit line → joinable to the durable job record's outcome (BOSUN-3).
    append_audit(_kanban_root(), login, "project_add", f"mode={mode} job={job_id}")
    return JSONResponse(content={"job_id": job_id})


@app.delete("/api/projects/{project_id}")
async def delete_project_route(project_id: str, request: fastapi.Request) -> JSONResponse:
    """Deregister a project (clone left on disk). 409 while a live agent exists (DESIGN §9).

    Args:
        project_id: The Project v2 node id (registry key) to remove.
        request: The FastAPI request (for the audit actor).

    Returns:
        ``{"deleted": <project_id>}`` once the registry entry is removed.

    Raises:
        HTTPException: 409 when the project still has a live agent; 404 when the key is absent.
    """
    if _project_has_live_agent(project_id):
        raise HTTPException(status_code=409, detail="project has a live agent — cannot remove")
    from kanbanmate.cli.init import _delete_project, _projects_path  # noqa: PLC0415

    removed = _delete_project(_projects_path(_kanban_root()), project_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"unknown project '{project_id}'")
    append_audit(_kanban_root(), _actor_login(request), "project_delete", project_id)
    return JSONResponse(content={"deleted": project_id})
