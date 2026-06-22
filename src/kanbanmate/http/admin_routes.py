"""Authed admin read surface: health + version + daemon control (bosun §7.1-7.2).

Registered on the shared config-API ``app`` by side-effect import. Auth-gated by ``_auth_guard``
(these paths are NOT in ``_AUTH_OPEN_PATHS``). Privileged data NEVER rides the public ``/api/health``.
Daemon-control routes (GET/POST /api/admin/daemon) are allowlist-guarded (DESIGN §5.1, D1).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import fastapi
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate import __version__
from kanbanmate.app import ops
from kanbanmate.app.audit import append_audit
from kanbanmate.app.health_dashboard import build_health
from kanbanmate.app.onboard import list_dir
from kanbanmate.core.pm2_allowlist import PM2_ALLOWLIST, validate_daemon_action
from kanbanmate.core.redeploy_target import script_for_target
from kanbanmate.http.config_api import (
    _actor_login,
    _kanban_root,
    _read_json_object,
    _resolve_entry,
    app,
)


@app.get("/api/admin/health")
async def admin_health() -> JSONResponse:
    """Per-project health rows + global flags (DESIGN §7.1)."""
    return JSONResponse(content=build_health(_kanban_root()))


def _served_build_sha() -> str:
    """Return the short git SHA of the currently-served SPA build, or ``"unknown"``.

    The deploy scripts stamp the served commit into ``<package>/webui/BUILD_COMMIT``:
    ``scripts/deploy.sh`` writes a bare ``<full-sha>`` while ``scripts/deploy-staging.sh``
    writes ``<branch> @ <full-sha>``. Both forms end with the SHA, so we take the last
    whitespace-delimited token and truncate to 12 chars to make it comparable with the
    ``git ls-remote`` short SHA used for ``remote``. Returns ``"unknown"`` when the stamp
    is absent (a source checkout that never ran a deploy script) or unreadable.

    Returns:
        The first 12 chars of the served build SHA, or ``"unknown"``.
    """
    try:
        from kanbanmate.http.config_api import _WEBUI_DIR  # noqa: PLC0415

        raw = (_WEBUI_DIR / "BUILD_COMMIT").read_text().strip()
    except (OSError, ImportError):
        return "unknown"
    if not raw:
        return "unknown"
    # Last token handles both "<sha>" and "<branch> @ <sha>" stamp formats.
    return raw.split()[-1][:12]


@app.get("/api/admin/version")
async def admin_version() -> JSONResponse:
    """Served build SHA vs ``origin/main`` SHA; degraded ``"unknown"`` on fetch/stamp failure.

    ``local`` is the package ``__version__`` (a semver, for display). ``build`` is the SHA of the
    currently-served SPA (read from the deploy stamp) and ``remote`` is the ``origin/main`` SHA;
    ``update_available`` is a genuine SHA-vs-SHA comparison of those two (both are git SHAs, so the
    comparison can actually flip — unlike a semver-vs-SHA check). The UI also polls ``build`` to
    confirm a redeploy bounce actually flipped the served code (DESIGN §8).
    """
    local = __version__
    build = _served_build_sha()
    try:
        out = subprocess.run(
            ["git", "ls-remote", "origin", "refs/heads/main"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
        remote = out.split()[0][:12] if out else "unknown"
    except Exception:
        remote = "unknown"
    # Meaningful only when BOTH SHAs are known: an update is available iff the served build differs
    # from origin/main. When either side is unknown we cannot assert an update → False.
    update_available = build != "unknown" and remote != "unknown" and build != remote
    return JSONResponse(
        content={
            "local": local,
            "build": build,
            "remote": remote,
            "update_available": update_available,
        }
    )


@app.get("/api/admin/daemon")
async def admin_daemon() -> JSONResponse:
    """Return ``[{app, status, pid, uptime_s, restarts}]`` for allowlisted PM2 apps (DESIGN §7.1).

    Runs ``pm2 jlist``, filters to ``PM2_ALLOWLIST``, and extracts the fields the UI needs.
    Degrades to an empty list + error string when ``pm2`` is unavailable.
    """
    try:
        raw = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if raw.returncode != 0:
            return JSONResponse(content={"apps": [], "error": raw.stderr.strip()})
        all_apps = json.loads(raw.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        return JSONResponse(content={"apps": [], "error": str(exc)})
    now = time.time()
    result: list[dict[str, object]] = []
    for proc in all_apps:
        name = proc.get("name", "")
        if name not in PM2_ALLOWLIST:
            continue
        pm2_env = proc.get("pm2_env", {})
        uptime_ms = pm2_env.get("pm_uptime", 0)
        uptime_s = (
            int(now - uptime_ms / 1000) if uptime_ms and pm2_env.get("status") == "online" else 0
        )
        result.append(
            {
                "app": name,
                "status": pm2_env.get("status", "unknown"),
                "pid": proc.get("pid"),
                "uptime_s": uptime_s,
                "restarts": pm2_env.get("restart_time", 0),
            }
        )
    return JSONResponse(content={"apps": result})


@app.post("/api/admin/daemon/{app_name}/{action}")
async def admin_daemon_action(app_name: str, action: str, request: fastapi.Request) -> JSONResponse:
    """Spawn a job running ``pm2 <action> <app>``; 422 on allowlist/UI-app refusal (D1, DESIGN §7.2)."""
    reason = validate_daemon_action(app_name, action)
    if reason is not None:
        raise HTTPException(status_code=422, detail=reason)
    login = _actor_login(request)
    job_id = ops.create_job(
        _kanban_root(),
        type="daemon",
        actor=login,
        argv=["pm2", action, app_name],
        args_summary=f"{action} {app_name}",
    )
    # Record the job_id in the audit line so an operator can join control/audit.log to the durable
    # job record (which carries the outcome: exit code, stdout tail) — BOSUN-3.
    append_audit(_kanban_root(), login, f"daemon_{action}", f"{app_name} job={job_id}")
    return JSONResponse(content={"job_id": job_id})


@app.get("/api/admin/daemon/{app_name}/logs")
async def admin_daemon_logs(app_name: str, lines: int = 200) -> JSONResponse:
    """Return ``{"lines": [...]}`` — bounded ``pm2 logs --nostream --lines N`` (cap 1000, DESIGN §7.1).

    Poll-based (no WebSocket) for v1. The app must be in ``PM2_ALLOWLIST`` (422 otherwise).
    ``lines`` is clamped to [1, 1000]; default is 200.
    """
    if app_name not in PM2_ALLOWLIST:
        raise HTTPException(status_code=422, detail=f"app '{app_name}' is not allowlisted")
    n = max(1, min(int(lines), 1000))
    # Degrade cleanly when pm2 is unavailable (FileNotFoundError) or hangs past the 15s cap
    # (TimeoutExpired) — mirror the sibling GET /api/admin/daemon, which returns a degraded body
    # with an ``error`` string rather than surfacing an opaque 500 traceback in the logs banner.
    try:
        out = subprocess.run(
            ["pm2", "logs", app_name, "--nostream", "--lines", str(n)],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return JSONResponse(content={"lines": [], "error": str(exc)})
    return JSONResponse(content={"lines": out.splitlines()})


# ── Directory browser (bosun §9, onboarding dir-picker) ───────────────────────


@app.get("/api/admin/browse")
async def admin_browse(path: str | None = None) -> JSONResponse:
    """List a confined directory for the onboarding folder-picker (DESIGN §9, §7.1).

    Delegates to :func:`kanbanmate.app.onboard.list_dir`, which raises ``PermissionError`` for any
    path outside ``ONBOARD_BASE_DIRS``; that maps to HTTP 422 (the path is the refusal cause, not a
    server error).

    Args:
        path: The directory path to list (query param). OPTIONAL — when absent/empty the picker is
            opening for the first time, so list the FIRST ``ONBOARD_BASE_DIRS`` root. The web
            DirBrowser sends NO path on mount and expects this; making ``path`` required 422'd the
            dir-browser on every first open. Any explicit path must resolve under ONBOARD_BASE_DIRS.

    Returns:
        ``{"path": <resolved>, "entries": [{"name", "is_dir"}, ...]}``.

    Raises:
        HTTPException: 422 when the path is outside the allowed roots.
    """
    # Empty path → list_dir lists the first allowed base root (the picker's initial view).
    try:
        return JSONResponse(content=list_dir(path))
    except PermissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── PAUSE kill-switch toggle (bosun §7.3, ACC-09) ─────────────────────────────


@app.get("/api/admin/pause")
async def admin_pause_get() -> JSONResponse:
    """Return ``{"active": bool}`` — whether the PAUSE kill-switch sentinel exists (DESIGN §7.3)."""
    return JSONResponse(content={"active": (_kanban_root() / "PAUSE").exists()})


@app.post("/api/admin/pause")
async def admin_pause_set(request: fastapi.Request) -> JSONResponse:
    """Create or remove the PAUSE kill-switch sentinel; idempotent (DESIGN §7.3, ACC-09).

    Body: ``{"active": true}`` to set PAUSE, ``{"active": false}`` to clear it.
    Appends to the audit log on every toggle.
    """
    body = await _read_json_object(request)
    active = bool(body.get("active"))
    pause = _kanban_root() / "PAUSE"
    if active:
        pause.parent.mkdir(parents=True, exist_ok=True)
        pause.touch()
    else:
        pause.unlink(missing_ok=True)
    append_audit(_kanban_root(), _actor_login(request), "pause", f"active={active}")
    return JSONResponse(content={"active": pause.exists()})


# ── Redeploy route (bosun §8, ACC-05/ACC-06) ──────────────────────────────────

_CLONE_FOR_TARGET: dict[str, str] = {
    "prod": "~/deploy/kanban-mate",
    "staging": "~/staging/kanban-mate",
}


@app.post("/api/admin/redeploy")
async def admin_redeploy(request: fastapi.Request) -> JSONResponse:
    """Spawn a detached job shelling the audited deploy script for ``target`` (DESIGN §8)."""
    body = await _read_json_object(request)
    target = str(body.get("target", ""))
    script = script_for_target(target)
    if script is None:
        raise HTTPException(status_code=422, detail=f"unknown redeploy target '{target}'")
    clone = str(Path(_CLONE_FOR_TARGET[target]).expanduser())
    login = _actor_login(request)
    job_id = ops.create_job(
        _kanban_root(),
        type="redeploy",
        actor=login,
        argv=["bash", script],
        args_summary=f"target={target}",
        cwd=clone,
    )
    append_audit(_kanban_root(), login, "redeploy", f"target={target} job={job_id}")
    return JSONResponse(content={"job_id": job_id})


# ── Install wizard: token + first-project (bosun §10 steps 1-2) ──────────────────


@app.post("/api/admin/wizard/token")
async def wizard_token(request: fastapi.Request) -> JSONResponse:
    """Write the GitHub token to ``<root>/token`` mode 0600 (install wizard step 1, DESIGN §10).

    The file is written atomically (tmp + fsync + rename) so a concurrent
    :func:`kanbanmate.adapters.github.token.load_token` never sees a truncated file.

    Body: ``{"token": "<the PAT>"}``.

    Returns:
        ``{"ok": true}`` on success.

    Raises:
        HTTPException: 422 when the token value is empty.
    """
    body = await _read_json_object(request)
    token_value = str(body.get("token", ""))
    if not token_value:
        raise HTTPException(status_code=422, detail="token must not be empty")

    token_path = _kanban_root() / "token"
    token_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: tmp + fsync + rename so a concurrent reader never sees a partial file.
    tmp_path = token_path.with_name(token_path.name + ".tmp")
    fd = os.open(str(tmp_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token_value.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp_path.rename(token_path)

    login = _actor_login(request)
    append_audit(_kanban_root(), login, "wizard_token", "write")
    return JSONResponse(content={"ok": True})


@app.post("/api/admin/wizard/project")
async def wizard_project(request: fastapi.Request) -> JSONResponse:
    """Add the first project (install wizard step 2, DESIGN §10).

    Delegates to :func:`~kanbanmate.http.projects_routes.create_project` — the same
    server-constructed detached job that ``POST /api/projects`` uses. 422 on bad
    path/URL/mode (same validation).

    Returns:
        ``{"job_id": <id>}`` for the spawned ``project_add`` job.
    """
    from kanbanmate.http.projects_routes import create_project  # noqa: PLC0415

    return await create_project(request)


@app.post("/api/admin/wizard/provision")
async def wizard_provision(request: fastapi.Request) -> JSONResponse:
    """Provision the first board's Status options (install wizard step 3, DESIGN §10).

    Reads ``{"project"}`` (or ``{"project_id"}``), resolves it against the runtime registry (so an
    unknown id fails loud — 404, never the wrong board), then spawns a detached job running the
    audited :mod:`kanbanmate.cli.provision_exec` runner. That runner calls the SAME app-level
    :func:`kanbanmate.app.board_provision.provision_board` path the ``POST /api/board/provision``
    endpoint uses (options only — never cards/PRs/merges, CLAUDE.md autonomy floor) rather than
    re-implementing provisioning here.

    The argv is SERVER-CONSTRUCTED from the validated, registry-resolved project id (never the raw
    client value) — DESIGN §11.4.

    Body: ``{"project": "<Project v2 node id>"}``.

    Returns:
        ``{"job_id": <id>}`` for the spawned ``wizard_provision`` job.

    Raises:
        HTTPException: 422 (missing project), or 503/404/400 from the registry resolver.
    """
    body = await _read_json_object(request)
    project = str(body.get("project") or body.get("project_id") or "")
    if not project:
        raise HTTPException(status_code=422, detail="project must not be empty")

    # Resolve against the registry HERE (http may import cli.init; app may not). An unknown id
    # raises 404 so the wizard never provisions the wrong board; the resolved entry's canonical
    # project_id is what we hand the runner — never the raw client string.
    entry = _resolve_entry(project)

    login = _actor_login(request)
    job_id = ops.create_job(
        _kanban_root(),
        type="wizard_provision",
        actor=login,
        argv=[
            sys.executable,
            "-m",
            "kanbanmate.cli.provision_exec",
            "--root",
            str(_kanban_root()),
            "--project",
            entry.project_id,
        ],
        args_summary=f"project={entry.project_id}",
    )
    append_audit(_kanban_root(), login, "wizard_provision", f"{entry.project_id} job={job_id}")
    return JSONResponse(content={"job_id": job_id})


# ── PM2 bootstrap helper ─────────────────────────────────────────────────────


def _any_allowlisted_pm2_app_exists() -> bool | None:
    """Probe whether any ``PM2_ALLOWLIST`` app is already registered in PM2 (bosun §10).

    Parses ``pm2 jlist`` and intersects the returned names with ``PM2_ALLOWLIST``.

    Returns:
        ``True`` if at least one allowlisted app exists, ``False`` if the probe SUCCEEDED and found
        none, or ``None`` when the probe could NOT confirm the state (``pm2`` unavailable, a non-zero
        return, a ``jlist`` timeout, or malformed JSON). The ``None`` (indeterminate) case must NOT be
        treated as "no apps" — a transient flake while the four daemons are live would otherwise let
        the first-run gate fail open and double-start them (bosun review-c2).
    """
    try:
        raw = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if raw.returncode != 0:
            return None
        all_apps = json.loads(raw.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None
    for proc in all_apps:
        if proc.get("name", "") in PM2_ALLOWLIST:
            return True
    return False


# ── Install wizard: PM2 bootstrap (bosun §10 step 4) ─────────────────────────

_BOOTSTRAP_SCRIPT = str(Path(__file__).resolve().parents[3] / "scripts" / "bootstrap-pm2.sh")


@app.post("/api/admin/wizard/bootstrap")
async def wizard_bootstrap(request: fastapi.Request) -> JSONResponse:
    """First-run-only PM2 bootstrap (install wizard step 4, DESIGN §10).

    Refuses 409 if any allowlisted PM2 app already exists, and 503 when the first-run state cannot be
    confirmed (``pm2`` unreachable / ``jlist`` timeout / malformed output). Only proceeds when the
    probe SUCCEEDS and finds zero allowlisted apps. Otherwise spawns a detached job shelling
    ``scripts/bootstrap-pm2.sh``.

    A pm2-probe failure is treated as INDETERMINATE and refused rather than proceeding: a transient
    ``jlist`` timeout while the four daemons are already live would otherwise let the gate fail open
    and double-start them on the same ``~/.kanban-km`` root (bosun review-c2).

    Returns:
        ``{"job_id": <id>}`` for the spawned ``wizard_bootstrap`` job.

    Raises:
        HTTPException: 409 when a PM2 allowlisted app already exists; 503 when the first-run state
            cannot be confirmed.
    """
    exists = _any_allowlisted_pm2_app_exists()
    if exists is None:
        raise HTTPException(
            status_code=503,
            detail="cannot confirm first-run state — pm2 unreachable; bootstrap refused",
        )
    if exists:
        raise HTTPException(
            status_code=409, detail="PM2 apps already exist — bootstrap is first-run only"
        )
    login = _actor_login(request)
    job_id = ops.create_job(
        _kanban_root(),
        type="wizard_bootstrap",
        actor=login,
        argv=["bash", _BOOTSTRAP_SCRIPT, str(_kanban_root())],
        args_summary="bootstrap",
    )
    append_audit(_kanban_root(), login, "wizard_bootstrap", f"first-run job={job_id}")
    return JSONResponse(content={"job_id": job_id})
