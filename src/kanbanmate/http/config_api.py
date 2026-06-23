"""``kanban config serve`` — headless HTTP API for the pipeline config (DESIGN §11).

Exposes 7 endpoints (GET/POST) over a loopback FastAPI server.  The API is
backend-neutral and single-operator: no auth, no TLS (the operator fronts with
their existing reverse proxy if needed).

This file is an HTTP **entrypoint** (DESIGN §11, §17 fix #1): it lives in
``http/`` alongside the webhook receiver.  The layering guard permits ``http``
to import ``app``, ``adapters``, ``core``, and ``cli.init`` — but not ``daemon``
or ``bin`` (``tests/test_layering.py:48``).

FastAPI is imported at module top level here (the import happens only when the
module is loaded, which only happens via ``kanban config serve`` or the tests).
The ``cli/config.py`` module guards the IMPORT of this module behind a
``try/except ImportError`` so the bare ``kanban`` CLI can run without ``[ui]``.

Layering: ``http`` → ``app``, ``core``, ``cli.init`` permitted.
         ``http`` → ``daemon``, ``bin`` forbidden.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fastapi
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from kanbanmate.http.auth import AuthConfig

from kanbanmate.app.config_service import ConfigInvalid, ConfigService
from kanbanmate.cli.init import (
    CLONE_COLUMNS_RELPATH,
    CLONE_TRANSITIONS_RELPATH,
    _load_registry,
    _projects_path,
)
from kanbanmate.core.config_model import PipelineDraft
from kanbanmate.core.config_validate import Finding, ValidationResult

# Default kanban runtime root (same default as cli/app.py:72).
_DEFAULT_ROOT = Path("~/.kanban/").expanduser()

# Max accepted request body (1 MiB), mirroring the webhook receiver (``http/serve.py`` MAX_BODY_BYTES).
# A larger / absent Content-Length is rejected up front (413/411) so a single request can neither OOM
# the process nor pin a connection while a slow client streams an unbounded body. Connection-level
# slow-loris is additionally bounded by fronting with a reverse proxy in production (DESIGN §11).
_MAX_BODY_BYTES = 1 * 1024 * 1024

app = FastAPI(
    title="KanbanMate Config API",
    description=(
        "Headless HTTP API for the KanbanMate pipeline config (helm PR 1). "
        "Loopback, single-operator, optional login. See DESIGN §11."
    ),
    version="1.0.0",
)

# Paths reachable WITHOUT a session when the login is enabled: the liveness probe + the login/session
# endpoints themselves. Everything else under /api/* requires a valid session cookie.
_AUTH_OPEN_PATHS = frozenset({"/api/health", "/api/login", "/api/logout", "/api/session"})


def _auth_config() -> AuthConfig | None:
    """Return the configured :class:`~kanbanmate.http.auth.AuthConfig`, or ``None`` if unset."""
    return getattr(app.state, "auth", None)


def _actor_login(request: fastapi.Request) -> str:
    """Resolve the operator login from the session cookie, or ``"operator"`` in open mode.

    Shared by the bosun admin/ops/projects routes for the audit trail. Lives here (the base module
    both ``admin_routes`` and ``projects_routes`` already import from) so neither route module has to
    import the other — that would form an import cycle through ``config_api``'s side-effect imports.
    By the time a privileged handler runs, ``_auth_guard`` has already verified the session, so a
    valid cookie is guaranteed when auth is enabled; this only extracts the login for the audit line.

    Args:
        request: The incoming request whose session cookie carries the login.

    Returns:
        The authenticated operator login, or ``"operator"`` when auth is disabled.
    """
    from kanbanmate.http.auth import COOKIE_NAME, verify_token  # noqa: PLC0415

    config = _auth_config()
    if config is None or not config.enabled:
        return "operator"
    login = verify_token(request.cookies.get(COOKIE_NAME, ""), config.secret)
    return login or "operator"


def _request_is_secure(request: fastapi.Request) -> bool:
    """Whether the request arrived over HTTPS (directly or via a TLS-terminating proxy).

    The operator fronts the UI with Caddy/TLS (``X-Forwarded-Proto: https``); a direct loopback
    call is plain ``http``. The session cookie's ``Secure`` flag is set accordingly so it works in
    both cases (a ``Secure`` cookie is dropped by browsers over plain http).
    """
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return forwarded == "https" or request.url.scheme == "https"


@app.middleware("http")
async def _auth_guard(request: fastapi.Request, call_next):  # type: ignore[no-untyped-def]
    """Require a valid session cookie for protected ``/api/*`` routes when login is enabled.

    No-op when auth is disabled (empty password) or for the open paths / the static SPA (the SPA
    shell is served, then its own ``/api/*`` calls 401 → it renders the login screen). Reads only
    the cookie — never the request body — so it is safe as an ``http`` middleware.
    """
    from kanbanmate.http.auth import COOKIE_NAME, verify_token  # noqa: PLC0415

    config = _auth_config()
    path = request.url.path
    if (
        config is not None
        and config.enabled
        and path.startswith("/api/")
        and path not in _AUTH_OPEN_PATHS
    ):
        token = request.cookies.get(COOKIE_NAME, "")
        if not token or verify_token(token, config.secret) is None:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    response = await call_next(request)
    # The SPA shell (index.html) must NOT be heuristically cached: without this a browser keeps a
    # stale index.html that references an OLD content-hashed JS bundle after a redeploy, so the
    # operator sees no changes until a hard refresh. Force-revalidate the HTML document only — the
    # content-hashed assets under /assets/ keep their own (effectively immutable) cache.
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _kanban_root() -> Path:
    """Resolve the runtime root: the CLI ``--root`` (via app.state) or the default.

    Returns:
        The kanban runtime root holding ``projects.json``.
    """
    # The CLI --root reaches here via app.state (set in cli/config.py:serve before uvicorn.run);
    # otherwise a passed --root would be silently dropped and every request would read ~/.kanban/.
    return getattr(app.state, "kanban_root", None) or _DEFAULT_ROOT


def _resolve_entry(project_id: str | None = None):  # type: ignore[no-untyped-def]
    """Resolve the registry entry for ``project_id`` (bridge multi-board, DESIGN §13.1).

    Resolution: an explicit ``project_id`` → that entry (404 if unknown); absent + exactly one
    project → that one (back-compat); absent + N>1 → 400 carrying the project list so the SPA can
    prompt the operator to choose.

    Args:
        project_id: The Project v2 node id to edit, or ``None`` to auto-resolve.

    Returns:
        The resolved :class:`~kanbanmate.cli.init.ProjectEntry`.

    Raises:
        HTTPException: 503 (no project registered), 404 (unknown id), or 400 (ambiguous N>1).
    """
    from kanbanmate.core.registry_resolve import resolve_by_project_id  # noqa: PLC0415

    registry = _load_registry(_projects_path(_kanban_root()))
    if not registry:
        raise HTTPException(status_code=503, detail="No project registered in the kanban root")
    if project_id:
        entry = resolve_by_project_id(registry, project_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Unknown project '{project_id}'")
        return entry
    if len(registry) == 1:
        return next(iter(registry.values()))
    raise HTTPException(
        status_code=400,
        detail={
            "error": "Multiple projects registered — pass ?project=<project_id>",
            "projects": [{"project_id": e.project_id, "repo": e.repo} for e in registry.values()],
        },
    )


def _get_service(project_id: str | None = None) -> ConfigService:
    """Build a :class:`~kanbanmate.app.config_service.ConfigService` for the selected board.

    Resolves the clone config file paths from the runtime registry entry selected by
    ``project_id`` (DESIGN §13.1) and injects them into the service (DESIGN §12 — ``app`` may not
    import ``cli.init``, but ``http`` may).

    Args:
        project_id: The Project v2 node id whose config to edit; ``None`` auto-resolves
            (the single project, or 400 when ambiguous — see :func:`_resolve_entry`).

    Returns:
        A :class:`~kanbanmate.app.config_service.ConfigService` for the selected board's config.

    Raises:
        HTTPException: 503 / 404 / 400 per :func:`_resolve_entry`.
    """
    entry = _resolve_entry(project_id)
    clone = Path(entry.clone)
    return ConfigService(
        transitions_path=clone / CLONE_TRANSITIONS_RELPATH,
        columns_path=clone / CLONE_COLUMNS_RELPATH,
    )


def _draft_to_dict(draft: PipelineDraft) -> dict[str, Any]:
    """Convert a PipelineDraft to a JSON-serialisable dict."""
    return asdict(draft)


def _findings_to_list(findings: list[Finding]) -> list[dict[str, Any]]:
    """Convert a list of Finding objects to JSON-serialisable dicts."""
    return [asdict(f) for f in findings]


def _validation_result_to_dict(result: ValidationResult) -> dict[str, Any]:
    """Convert a ValidationResult to a JSON-serialisable dict."""
    return {
        "ok": result.ok,
        "findings": _findings_to_list(result.findings),
    }


async def _read_json_object(request: fastapi.Request) -> dict[str, Any]:
    """Read the request body as a bounded JSON OBJECT, failing CLEAN on bad input.

    Shared by all three POST handlers. Guards, in order:

    * BODY SIZE — ``Content-Length`` must be present (a body-carrying request with none means chunked
      transfer, which we never stream-decode → 411) and within :data:`_MAX_BODY_BYTES` (else 413),
      mirroring the webhook receiver's bounded read. Caps the OOM blast radius + how much a slow
      client can stream. Checked HERE, not in a ``BaseHTTPMiddleware`` — that wrapper deadlocks
      handlers that read the raw request body.
    * JSON — a raw Starlette ``Request.json()`` raises ``json.JSONDecodeError`` on an empty /
      non-JSON / malformed body, which FastAPI does NOT auto-convert to 422 for a raw Request →
      unguarded it is a 500 + traceback. Normalised to 422.
    * SHAPE — a non-object body (list / scalar / null) would then break the ``.get()``-based
      deserialiser with an ``AttributeError`` → 500. Rejected as 422 here.

    Returns:
        The parsed body as a ``dict``.

    Raises:
        HTTPException: 411 / 413 / 400 (Content-Length), or 422 (not valid JSON / not an object).
    """
    raw_len = request.headers.get("content-length")
    if raw_len is None:
        raise HTTPException(
            status_code=411, detail="Content-Length required (chunked not accepted)"
        )
    # ``int()`` is too permissive here: it tolerates surrounding whitespace and a leading sign, so
    # ``int(' -5 ')`` → -5 and ``int('+10')`` → 10. A negative / whitespace / sign-prefixed length
    # would slip past the ``> _MAX_BODY_BYTES`` cap (the cap is then under-reported). Require a
    # CANONICAL non-negative integer string (``str.isdigit()`` — no sign, no whitespace, ASCII
    # digits only) before parsing, so the size guard always sees the true declared length.
    if not raw_len.isdigit():
        raise HTTPException(status_code=400, detail="Invalid Content-Length")
    try:
        length = int(raw_len)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc
    if length > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail=f"Request body exceeds {_MAX_BODY_BYTES} bytes")
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")
    return body


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe — now also surfaces the deployed package version (tiller §7.4).

    Returns:
        ``{"status": "ok", "version": "<kanbanmate.__version__>"}``.
    """
    import kanbanmate  # noqa: PLC0415

    return {"status": "ok", "version": kanbanmate.__version__}


@app.get("/api/session")
def get_session(request: fastapi.Request) -> dict[str, object]:
    """Report whether login is enabled and whether this request is authenticated.

    The SPA calls this on boot to decide between the login screen and the editor.

    Returns:
        ``{"auth_enabled": bool, "authenticated": bool, "login": str|None}``.
    """
    from kanbanmate.http.auth import COOKIE_NAME, verify_token  # noqa: PLC0415

    config = _auth_config()
    if config is None or not config.enabled:
        return {"auth_enabled": False, "authenticated": True, "login": None}
    token = request.cookies.get(COOKIE_NAME, "")
    login = verify_token(token, config.secret) if token else None
    return {"auth_enabled": True, "authenticated": login is not None, "login": login}


@app.post("/api/login")
async def post_login(request: fastapi.Request) -> JSONResponse:
    """Verify credentials and set the session cookie.

    Body: ``{"login": str, "password": str}``. When auth is disabled this is a no-op success.

    Returns:
        ``{"authenticated": true, "login": str}`` (200) with a ``Set-Cookie`` on success.

    Raises:
        HTTPException: 401 on invalid credentials.
    """
    from kanbanmate.http.auth import COOKIE_NAME, make_token, verify_credentials  # noqa: PLC0415

    config = _auth_config()
    if config is None or not config.enabled:
        return JSONResponse(content={"authenticated": True, "login": None})
    body = await _read_json_object(request)
    login = str(body.get("login", ""))
    password = str(body.get("password", ""))
    if not verify_credentials(config, login, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = make_token(config.login, config.secret, config.ttl)
    response = JSONResponse(content={"authenticated": True, "login": config.login})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=config.ttl,
        httponly=True,
        # SameSite=Strict (defense-in-depth, bosun review-c3): the UI is single-operator with no
        # cross-site navigation, so the session cookie is never legitimately sent on a cross-site
        # request — Strict prevents it riding along on any cross-origin request (incl. the CSWSH
        # WebSocket handshake) even when the operator is logged in.
        samesite="strict",
        secure=_request_is_secure(request),
        path="/",
    )
    return response


@app.post("/api/logout")
def post_logout() -> JSONResponse:
    """Clear the session cookie (idempotent — safe even when not logged in)."""
    from kanbanmate.http.auth import COOKIE_NAME  # noqa: PLC0415

    response = JSONResponse(content={"authenticated": False})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/api/config")
def get_config(project: str | None = None) -> JSONResponse:
    """Return the current pipeline draft loaded from the selected board's config files.

    Args:
        project: The Project v2 node id to edit (DESIGN §13.1). Omit when a single board.

    Returns:
        The draft as a JSON object.

    Raises:
        HTTPException: 503/404/400 (project resolution); 500 on load error.
    """
    svc = _get_service(project)
    try:
        draft = svc.load()
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse(content=_draft_to_dict(draft))


@app.post("/api/config/validate")
async def post_validate(request: fastapi.Request, project: str | None = None) -> JSONResponse:
    """Validate a posted draft without writing.

    The request body must be a JSON object representing a PipelineDraft
    (same shape as GET /api/config returns).

    Args:
        request: The HTTP request carrying the draft JSON body.
        project: The Project v2 node id to validate against (DESIGN §13.1).

    Returns:
        A ``ValidationResult`` JSON object: ``{"ok": bool, "findings": [...]}``.
    """
    svc = _get_service(project)
    body = await _read_json_object(request)
    draft = _dict_to_draft(body)
    result = svc.validate(draft)
    return JSONResponse(content=_validation_result_to_dict(result))


@app.post("/api/config")
async def post_config(request: fastapi.Request, project: str | None = None) -> JSONResponse:
    """Validate a posted draft and, if valid, atomically write both config files.

    On validation error (any ``error``-severity finding), returns HTTP 422 with
    the findings list — nothing is written.

    Args:
        request: The HTTP request carrying the draft JSON body.
        project: The Project v2 node id whose config to write (DESIGN §13.1).

    Returns:
        ``{"ok": true}`` on success, or ``{"ok": false, "findings": [...]}`` with
        status 422 on validation failure.
    """
    svc = _get_service(project)
    body = await _read_json_object(request)
    draft = _dict_to_draft(body)
    try:
        svc.save(draft)
    except ConfigInvalid as exc:
        return JSONResponse(
            status_code=422,
            content=_validation_result_to_dict(exc.result),
        )
    return JSONResponse(content={"ok": True})


@app.get("/api/config/render")
def get_render(project: str | None = None) -> JSONResponse:
    """Preview the rendered YAML strings for the current draft (no write).

    Args:
        project: The Project v2 node id to render (DESIGN §13.1).

    Returns:
        ``{"transitions": "<yaml string>", "columns": "<yaml string>"}``.

    Raises:
        HTTPException: 500 on load/render error (consistent with GET /api/config).
    """
    svc = _get_service(project)
    try:
        draft = svc.load()
        rendered = svc.render(draft)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse(content={"transitions": rendered.transitions, "columns": rendered.columns})


@app.post("/api/config/resolve")
async def post_resolve(request: fastapi.Request, project: str | None = None) -> JSONResponse:
    """Simulate whitelist resolution for a (from_col, to_col) move.

    Request body: ``{"draft": {...}, "from_col": "Backlog", "to_col": "Brainstorming"}``.

    Args:
        request: The HTTP request carrying the draft + from/to JSON body.
        project: The Project v2 node id to resolve against (DESIGN §13.1).

    Returns:
        A ``ResolvedTransition`` JSON object.

    Raises:
        HTTPException: 422 when the posted draft is structurally invalid or the
            loader rejects it (resolve renders + loads the draft).
    """
    svc = _get_service(project)
    body = await _read_json_object(request)
    draft = _dict_to_draft(body.get("draft", {}))
    from_col = str(body.get("from_col", ""))
    to_col = str(body.get("to_col", ""))
    try:
        result = svc.resolve(draft, from_col, to_col)
    except ValueError as exc:
        # resolve() renders the draft and runs load_transitions; a draft the
        # loader rejects (e.g. a banned permission_mode) is a client error, not
        # a server fault — surface it as 422 rather than an opaque 500 traceback.
        raise HTTPException(status_code=422, detail=f"Cannot resolve draft: {exc}") from exc
    return JSONResponse(content=asdict(result))


@app.post("/api/board/provision")
async def provision_board_endpoint(
    request: fastapi.Request, project: str | None = None
) -> JSONResponse:
    """Diff (and optionally apply) the GitHub Status options against the saved columns.

    Body: ``{"dry_run": bool, "renames": {old: new}?}``. The desired column set is
    read from the SAVED config (not a posted draft) — bridge disables Sync while the
    editor is dirty (DESIGN §8). On apply, re-provisions Status options via
    :func:`kanbanmate.app.board_provision.provision_board` (options only — never
    cards/PRs/merges).

    Args:
        request: The HTTP request carrying ``{dry_run, renames}``.
        project: The Project v2 node id to provision (DESIGN §13.1).

    Returns:
        ``{"applied", "is_noop", "changes", "removals", "option_map"}``.

    Raises:
        HTTPException: 411/413/422 (bad body); 503/404/400 (project resolution);
            502 (board/token failure).
    """
    from kanbanmate.app.board_provision import provision_board  # noqa: PLC0415

    body = await _read_json_object(request)
    dry_run = bool(body.get("dry_run", True))
    renames = body.get("renames") or {}
    if not isinstance(renames, dict):
        raise HTTPException(status_code=422, detail="'renames' must be an object")

    # Resolve the SELECTED board's entry (project_id + option-map fallback). The resolution lives
    # HERE because ``http`` may import ``cli.init`` but ``app`` may not (test_layering FORBIDDEN).
    entry = _resolve_entry(project)
    # Desired columns come from the SAVED config (not a posted draft) — DESIGN §8.
    service = _get_service(project)
    draft = service.load()
    desired = [c.name for c in draft.definition.columns]

    injected = getattr(app.state, "seeder", None)
    try:
        result = provision_board(
            project_id=entry.project_id,
            desired_columns=desired,
            fallback_options=list(entry.option_map.keys()),
            renames={str(k): str(v) for k, v in renames.items()},
            dry_run=dry_run,
            seeder=injected,
        )
    except Exception as exc:  # noqa: BLE001 — boundary handler
        # Provisioning touches the network (GraphQL), the token file, and the GitHub
        # response parser; ANY failure (bad/absent token, GraphQLError, unreachable
        # board) must reach the Sync dialog as a clean message (DESIGN §9) rather than
        # an opaque 500 the SPA renders as "500: Internal Server Error".
        raise HTTPException(status_code=502, detail=f"Board provisioning failed: {exc}") from exc
    return JSONResponse(
        content={
            "applied": result.applied,
            "is_noop": result.diff.is_noop,
            "changes": [asdict(c) for c in result.diff.changes],
            "removals": [asdict(c) for c in result.diff.removals],
            "option_map": result.option_map,
        }
    )


@app.get("/api/files")
def get_files(project: str | None = None, path: str = "") -> JSONResponse:
    """List files/dirs under the selected board's clone, SANDBOXED to that root.

    Backs the transition ``script`` field's file picker (bridge): the operator browses the kanban
    project's own tree and cannot escape above its clone root. ``path`` is a directory relative to
    the clone; any attempt to traverse above the root (``..``, absolute, symlink escape) is rejected.

    Args:
        project: The Project v2 node id selecting the board (DESIGN §13.1).
        path: A directory relative to the clone root (default: the root itself).

    Returns:
        ``{"path": str, "entries": [{"name", "is_dir", "is_exec", "rel"}, ...]}`` — dirs first,
        then files, each sorted by name. ``rel`` is the entry path relative to the clone root.

    Raises:
        HTTPException: 503/404/400 (project resolution), 400 (path escapes the root or not a dir).
    """
    import os  # noqa: PLC0415

    entry = _resolve_entry(project)
    root = Path(entry.clone).resolve()
    target = (root / path).resolve()
    # SANDBOX: the resolved target must stay within the clone root (blocks ``..`` / absolute /
    # symlink escapes — resolve() collapses them, then is_relative_to is the gate).
    if not (target == root or target.is_relative_to(root)):
        raise HTTPException(status_code=400, detail="Path escapes the project root")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    entries: list[dict[str, object]] = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        is_dir = child.is_dir()
        entries.append(
            {
                "name": child.name,
                "is_dir": is_dir,
                "is_exec": (not is_dir) and os.access(child, os.X_OK),
                # Use the UNRESOLVED child (already ``target/<name>`` inside root): ``child.resolve()``
                # follows a symlink that points OUTSIDE root → relative_to(root) raised ValueError →
                # an unhandled 500 that broke the file picker for any dir holding such a symlink
                # (e.g. a symlinked .claude/ or node_modules). The sandbox gate above already
                # validated ``target``; listing a symlink entry by name is safe.
                "rel": str(child.relative_to(root)),
            }
        )
    rel_path = "" if target == root else str(target.relative_to(root))
    return JSONResponse(content={"path": rel_path, "entries": entries})


# Monitoring endpoints (helm PR 2-bis) live in a sibling module to keep this file under the
# size ceiling; importing it registers its routes on this ``app`` (side-effect import).
from kanbanmate.http import monitor_routes as _monitor_routes  # noqa: E402,F401

# Board state endpoints (anchor §10) live in a sibling module; same side-effect-import pattern.
from kanbanmate.http import board_routes as _board_routes  # noqa: E402,F401

# bosun read-only admin/ops routes (bosun §1). MUST register BEFORE ``install_spa_mount`` below:
# the SPA catch-all mount shadows any API route registered after it once the webui build exists,
# so these imports belong here with the sibling route modules, not at the bottom of the file.
from kanbanmate.http import admin_routes as _bosun_admin_routes  # noqa: E402,F401
from kanbanmate.http import csrf_mw as _bosun_csrf_mw  # noqa: E402,F401
from kanbanmate.http import ops_routes as _bosun_ops_routes  # noqa: E402,F401
from kanbanmate.http import projects_routes as _bosun_projects_routes  # noqa: E402,F401


@app.get("/api/schema")
def get_schema() -> JSONResponse:
    """Return a JSON Schema for the PipelineDraft model.

    The schema is generated at request time from the dataclass structure —
    there is no static schema.json asset (DESIGN §14).

    Returns:
        A JSON Schema object describing the PipelineDraft structure.
    """
    schema = _generate_schema()
    return JSONResponse(content=schema)


@app.get("/api/placeholders")
def get_placeholders() -> JSONResponse:
    """Return the engine's canonical prompt-placeholder set.

    The rich prompt editor (bridge / helm PR 2) highlights + validates
    ``{{placeholder}}`` tokens against this set, sourced from the single engine
    definition (:data:`kanbanmate.core.placeholders.KNOWN_PLACEHOLDERS`) so the UI
    can never drift from the dispatch context.

    Returns:
        ``{"placeholders": [{"name", "description"}, ...]}`` sorted by name.
    """
    from kanbanmate.core.placeholders import KNOWN_PLACEHOLDERS  # noqa: PLC0415

    items = [{"name": k, "description": v} for k, v in sorted(KNOWN_PLACEHOLDERS.items())]
    return JSONResponse(content={"placeholders": items})


# One-line summary per profile (read-only reference, DESIGN §13 operator feedback). The names + the
# real allow/deny/mode are sourced from the engine (core.profiles + adapters.perms) so the reference
# never drifts; only the prose summary lives here.
_PROFILE_SUMMARIES: dict[str, str] = {
    "docs": "Floor profile: read/write files + minimal shell + local commit. NO push, NO PR ops, "
    "NO merge. The kill-switch downgrades every profile to this, and an unknown name falls back here.",
    "prepare": "Code edits + full git incl. push (create/maintain a branch) + kanban helpers. "
    "NO gh PR operations, NO merge.",
    "dev": "The build/implementation profile: code edits + git + the kanban helpers the "
    "implement stages need. NO merge.",
    "check": "Read-only-ish: Read + git read + gh read. The script-gate profile (usually no agent). "
    "NO writes that matter, NO merge.",
    "merge": "The autonomous Review→Merge stage — the SOLE profile whose deny-list lifts "
    "`gh pr merge` (squash-merge a green, mergeable PR). Force-push + history rewrite stay banned.",
    "triage": "Read-only fast-track classifier: reads the ticket + sensitive-paths config and "
    "records the lane. NO file edits, NO git/push, NO PR ops, NO merge.",
}


@app.get("/api/profiles")
def get_profiles() -> JSONResponse:
    """Return the permission profiles as a READ-ONLY reference (DESIGN §13 operator feedback).

    Profiles are a code-defined security boundary (``core.profiles`` names + ``adapters.perms``
    allow/deny/mode), NOT editable config — the GUI surfaces them so the operator understands the
    ``profile`` dropdown, but never mutates them (editing would widen what an autonomous agent may
    do). The real allow/deny/mode are read from the engine so the reference can never drift.

    Returns:
        ``{"profiles": [{"name", "mode", "summary", "allow": [...], "deny": [...]}, ...]}``.
    """
    from kanbanmate.adapters import perms  # noqa: PLC0415
    from kanbanmate.core.profiles import PROFILES  # noqa: PLC0415

    items = [
        {
            "name": p,
            "mode": perms.pinned_mode(p),
            "summary": _PROFILE_SUMMARIES.get(p, ""),
            "allow": perms.allow_list(p),
            "deny": perms.deny_list(p),
        }
        for p in PROFILES
    ]
    return JSONResponse(content={"profiles": items})


@app.get("/api/projects")
def get_projects() -> JSONResponse:
    """List the boards the daemon manages (bridge multi-board switcher, DESIGN §13.1).

    Returns:
        ``{"projects": [{"project_id", "repo", "enabled", "ingress"}, ...]}`` (registry order).

    Raises:
        HTTPException: 503 when no project is registered.
    """
    registry = _load_registry(_projects_path(_kanban_root()))
    if not registry:
        raise HTTPException(status_code=503, detail="No project registered in the kanban root")
    projects = [
        {
            "project_id": e.project_id,
            "repo": e.repo,
            "enabled": e.enabled,
            "ingress": e.ingress,
        }
        for e in registry.values()
    ]
    return JSONResponse(content={"projects": projects})


@app.patch("/api/projects/{project_id}")
async def patch_project(project_id: str, request: fastapi.Request) -> JSONResponse:
    """Edit a board's daemon-scoped registry toggles (bridge daemon scope, DESIGN §13.2).

    Body: ``{"enabled": bool?, "ingress": "webhook"|"polling"?}`` — only these two daemon-scoped
    fields are editable; all other registry fields (repo/clone/project_id/token) are set by
    ``kanban init`` and stay read-only here. Persisted via the existing
    :func:`~kanbanmate.cli.init._upsert_project` write path. The running daemon picks the change up
    on its next config reload / restart (it builds one wiring per enabled entry — not a live swap).

    Args:
        project_id: The Project v2 node id to edit.
        request: The HTTP request carrying the toggle JSON body.

    Returns:
        The updated project row ``{"project_id", "repo", "enabled", "ingress"}``.

    Raises:
        HTTPException: 411/413/422 (bad body), 404 (unknown id), 503 (no project).
    """
    from dataclasses import replace  # noqa: PLC0415
    from kanbanmate.cli.init import _upsert_project  # noqa: PLC0415
    from kanbanmate.core.registry_resolve import resolve_by_project_id  # noqa: PLC0415

    body = await _read_json_object(request)
    registry = _load_registry(_projects_path(_kanban_root()))
    if not registry:
        raise HTTPException(status_code=503, detail="No project registered in the kanban root")
    entry = resolve_by_project_id(registry, project_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown project '{project_id}'")

    changes: dict[str, Any] = {}
    if "enabled" in body:
        changes["enabled"] = bool(body["enabled"])
    if "ingress" in body:
        ingress = str(body["ingress"])
        if ingress not in ("webhook", "polling"):
            raise HTTPException(status_code=422, detail="'ingress' must be 'webhook' or 'polling'")
        changes["ingress"] = ingress
    if not changes:
        raise HTTPException(status_code=422, detail="No editable field in body (enabled/ingress)")

    updated = replace(entry, **changes)
    _upsert_project(_projects_path(_kanban_root()), project_id, updated)
    return JSONResponse(
        content={
            "project_id": updated.project_id,
            "repo": updated.repo,
            "enabled": updated.enabled,
            "ingress": updated.ingress,
        }
    )


def _dict_to_draft(body: dict[str, Any]) -> PipelineDraft:
    """Deserialise a JSON dict into a PipelineDraft.

    Args:
        body: A dict matching the PipelineDraft dataclass structure.

    Returns:
        A :class:`~kanbanmate.core.config_model.PipelineDraft`.

    Raises:
        HTTPException: 422 when the body is structurally invalid, or when it omits ``definition`` /
            ``binding`` (refusing to silently build an EMPTY draft — a body that defaulted both away
            would otherwise validate clean and let POST /api/config WIPE the config, data-loss).
    """
    from kanbanmate.core.config_model import (  # noqa: PLC0415
        Binding,
        ColumnDef,
        Defaults,
        Definition,
        TransitionDef,
    )

    # The schema declares both REQUIRED (``_generate_schema``: required=["definition","binding"]).
    # Enforce it here so an empty / partial body is a 422, not a fully-defaulted empty draft that the
    # validator would accept and the write path would persist over the live config.
    if "definition" not in body or "binding" not in body:
        raise HTTPException(
            status_code=422,
            detail="Request body must include both 'definition' and 'binding'",
        )

    try:
        definition_raw = body.get("definition", {})
        binding_raw = body.get("binding", {})
        columns = [ColumnDef(**c) for c in definition_raw.get("columns", [])]
        transitions = [TransitionDef(**t) for t in definition_raw.get("transitions", [])]
        defaults_raw = definition_raw.get("defaults", {})
        defaults = Defaults(
            concurrency_cap=int(defaults_raw.get("concurrency_cap", 3)),
            move_rate_limit_per_hour=int(defaults_raw.get("move_rate_limit_per_hour", 10)),
        )
        binding = Binding(
            project=str(binding_raw.get("project", "")),
            option_map=dict(binding_raw.get("option_map", {})),
        )
        return PipelineDraft(
            definition=Definition(columns=columns, transitions=transitions, defaults=defaults),
            binding=binding,
        )
    except (TypeError, KeyError, ValueError, AttributeError) as exc:
        # AttributeError covers a nested non-mapping (e.g. definition/defaults/binding posted as a
        # list/scalar) whose ``.get`` would otherwise escape as a 500.
        raise HTTPException(status_code=422, detail=f"Invalid draft structure: {exc}") from exc


def _generate_schema() -> dict[str, Any]:
    """Generate a minimal JSON Schema for the PipelineDraft model.

    Returns:
        A dict representing the JSON Schema.
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PipelineDraft",
        "description": "Editable pipeline config draft (helm PR 1, DESIGN §4).",
        "type": "object",
        "required": ["definition", "binding"],
        "properties": {
            "definition": {
                "type": "object",
                "required": ["columns", "transitions", "defaults"],
                "properties": {
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["key", "name", "column_class"],
                            "properties": {
                                "key": {"type": "string"},
                                "name": {"type": "string"},
                                "column_class": {"type": "string", "enum": ["reactive", "inert"]},
                            },
                        },
                    },
                    "transitions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["from_col", "to_col"],
                            "properties": {
                                # str | list[str] — the model + loaders accept a wildcard/list
                                # source/destination (e.g. the skip-to-Done list row), and
                                # GET /api/config emits list-valued from/to, so the schema must too
                                # (string-only would reject a draft the validator + the API accept).
                                "from_col": {
                                    "anyOf": [
                                        {"type": "string"},
                                        {"type": "array", "items": {"type": "string"}},
                                    ]
                                },
                                "to_col": {
                                    "anyOf": [
                                        {"type": "string"},
                                        {"type": "array", "items": {"type": "string"}},
                                    ]
                                },
                                "profile": {"type": "string", "default": ""},
                                "prompt": {"type": ["string", "null"]},
                                "script": {"type": ["string", "null"]},
                                "advance": {"type": "string", "default": "stop"},
                                "on_fail": {"type": "string", "default": ""},
                                "permission_mode": {"type": "string", "default": "auto"},
                            },
                        },
                    },
                    "defaults": {
                        "type": "object",
                        "required": ["concurrency_cap", "move_rate_limit_per_hour"],
                        "properties": {
                            "concurrency_cap": {"type": "integer", "minimum": 1},
                            "move_rate_limit_per_hour": {"type": "integer", "minimum": 1},
                        },
                    },
                },
            },
            "binding": {
                "type": "object",
                "required": ["project"],
                "properties": {
                    "project": {"type": "string"},
                    "option_map": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
            },
        },
    }
    # anchor §10: board.json schema so the SPA can validate client-side.
    defs: dict[str, Any] = schema.setdefault("$defs", {})  # type: ignore[assignment]
    defs["BoardState"] = {
        "type": "object",
        "description": "Native board state document (board.json, anchor §6.1).",
        "required": ["version", "columns", "placement", "order"],
        "properties": {
            "version": {"type": "integer", "minimum": 0},
            "columns": {"type": "array", "items": {"type": "string"}},
            "placement": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "order": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
    }
    return schema


# --- Static SPA mount (bridge / helm PR 2) ------------------------------------------
# The built React/shadcn SPA lives in the package at ``webui/`` (Vite outDir, shipped
# under the [ui] extra). Mounted LAST so it never shadows the /api/* routes.
_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"


def install_spa_mount(target: FastAPI, webui_dir: Path) -> None:
    """Mount the built SPA at ``/`` on ``target``, or a friendly fallback when absent.

    Idempotent at module load: called once below with the package ``webui/`` dir. When
    ``webui_dir/index.html`` exists the built SPA is served (``html=True`` falls back to
    ``index.html`` for client-side routes); otherwise ``GET /`` returns a friendly
    "not built" message (a source checkout without ``npm run build``) instead of a 500,
    and ``/api/*`` keeps working (DESIGN §7/§9). Extracted as a function so both states
    are unit-testable regardless of the local build state.

    Args:
        target: The FastAPI app to mount onto.
        webui_dir: The directory holding the built ``index.html`` + ``assets/``.
    """
    if (webui_dir / "index.html").is_file():
        from fastapi.staticfiles import StaticFiles  # noqa: PLC0415

        target.mount("/", StaticFiles(directory=str(webui_dir), html=True), name="webui")
        return

    @target.get("/")
    def _no_build() -> JSONResponse:
        """Friendly placeholder when the SPA build is absent (DESIGN §9)."""
        return JSONResponse(
            content={
                "message": (
                    "Config UI not built. Run `npm --prefix web run build` (or install the "
                    "[ui] extra from a release wheel). The /api/* endpoints work regardless."
                )
            }
        )


install_spa_mount(app, _WEBUI_DIR)
