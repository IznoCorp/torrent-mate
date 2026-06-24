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
from fastapi.responses import JSONResponse, StreamingResponse

from kanbanmate.cli.init import _load_registry, _projects_path
from kanbanmate.core.profiles import SAFE_LAUNCH_PROFILES
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


def _is_native_backed(entry: Any) -> bool:
    """True when the project has a native board store ('native' or 'hybrid' backend).

    keel STEP 2: a native-backed board reads PLACEMENT from the local ``board.json`` (the board
    VIEW's source) — never gated by a GitHub call. A pure-'github' board has no native store, so it
    keeps the legacy cached-snapshot placement path.
    """
    return getattr(entry, "board_backend", "github") in ("native", "hybrid")


def _board_store(entry: Any) -> Any:
    """Open the SAME native board store the board VIEW reads (keel STEP 2 — one source of truth).

    Reuses ``board_routes._get_store`` (the daemon/CLI sub-root resolution) so Monitoring placement
    and the board view read the identical ``board.json``. Overridable via ``app.state.board_store``
    (tests).
    """
    injected = getattr(app.state, "board_store", None)
    if injected is not None:
        return injected
    from kanbanmate.http.board_routes import _get_store  # noqa: PLC0415,PLC2701

    return _get_store(entry)


def _identity_fetcher(entry: Any) -> Any:
    """Return a zero-arg callable yielding ``{item_id: (issue_number, title, is_closed)}`` from GitHub.

    Used ONLY for ticket IDENTITY in the native placement path (keel STEP 2) — its result is
    TTL-cached and a raising call degrades to last-known identity, so placement never depends on it.
    ``is_closed`` rides this identity fetch (it is GitHub-side issue metadata like the title) so the
    native board surfaces the ensign CLOSED-issue indicator. The underlying snapshot source is the
    SAME ``app.state.monitor_snapshotter`` override the legacy path uses (tests inject one
    snapshotter for both paths).
    """

    def fetch() -> dict[str, tuple[int | None, str, bool]]:
        snap = _board_snapshot_uncached(entry)
        return {t.item_id: (t.issue_number, t.title, t.is_closed) for t in snap.tickets}

    return fetch


def _board_snapshot_uncached(entry: Any) -> Any:
    """Fetch a fresh GitHub board snapshot (no TTL cache) for the identity JOIN.

    Source overridable via ``app.state.monitor_snapshotter`` (tests). The native path's own
    identity cache (``monitor_board_source._IDENTITY_CACHE``) provides the longer-TTL layer; the
    legacy ``_board_snapshot`` keeps its separate 15 s placement cache for pure-'github' boards.
    """
    snapper = getattr(app.state, "monitor_snapshotter", None)
    if snapper is None:
        from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
        from kanbanmate.adapters.github.token import load_token  # noqa: PLC0415

        def snapper(pid: str) -> Any:
            return GithubClient(load_token(), project_id=pid).snapshot()

    return snapper(entry.project_id)


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
    """Board overview: columns (from config) + tickets (LOCAL placement) + agent overlay. DESIGN §5.1.

    Columns come from the board's ``columns.yml`` (no GitHub). For a native-backed board (keel
    STEP 2) ticket PLACEMENT (column + order) is read from the LOCAL ``board.json`` — the SAME
    store the board view reads — so a card's column is fresh within a tick (<5 ms) and NEVER gated
    by a GitHub call; GitHub is consulted only for identity (issue number + title) under a
    longer-TTL identity cache, so an outage degrades titles, never placement. A pure-'github' board
    keeps the legacy 15 s cached-snapshot placement path. Per-ticket agent state is local
    (store + tmux). Read-only.

    Returns:
        ``{"columns", "tickets", "agents_summary"}``.

    Raises:
        HTTPException: 503/404/400 (project resolution); 502 (legacy snapshot failure, github-only).
    """
    from kanbanmate.app.monitor import build_board, derive_state  # noqa: PLC0415
    from kanbanmate.app.tick import DEFAULT_BLOCKED_COLUMN  # noqa: PLC0415

    entry = _resolve_entry(project)
    draft = _get_service(project).load()
    columns = [(c.key, c.name, c.column_class) for c in draft.definition.columns]
    if _is_native_backed(entry):
        # keel STEP 2: placement from the local board store; GitHub only for identity (TTL-cached,
        # fail-soft). A raising identity fetch degrades titles but the local placement still renders.
        # The identity fetch also carries is_closed, so the native board surfaces the ensign
        # CLOSED-issue indicator (degrades to open when identity is unavailable).
        from kanbanmate.http.monitor_board_source import native_board_triples  # noqa: PLC0415

        doc = _board_store(entry).load()
        tickets = native_board_triples(entry.project_id, doc, _identity_fetcher(entry))
    else:
        # Legacy pure-'github' board: no native store → cached GitHub snapshot drives placement.
        try:
            snap = _board_snapshot(entry)
        except Exception as exc:  # noqa: BLE001 — boundary: clean error, never a 500 traceback
            raise HTTPException(status_code=502, detail=f"Board snapshot failed: {exc}") from exc
        tickets = [
            (t.issue_number, t.title, t.column_key, t.is_closed)
            for t in snap.tickets
            if t.issue_number is not None
        ]
    running = {s.issue_number: derive_state(s.status) for s in _monitor_store(entry).list_running()}
    # Pass the Blocked column so a card parked there with NO live agent reads "blocked" — the same
    # (column + liveness) signal core.health uses for the GitHub Health chip (build_board mirrors its
    # precedence). list_running only carries RUNNING/WAITING, so without this blocked is unreachable.
    return JSONResponse(
        content=build_board(columns, tickets, running, blocked_column=DEFAULT_BLOCKED_COLUMN)
    )


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
        number,
        ref.title,
        column_key,
        ref.body or "",
        ctx.comments,
        progress=[],
        comment_dates=ctx.comment_dates,
        labels=ref.labels,
    )
    # Status-change select (tiller follow-up): the columns the operator may move this card into, with
    # the workflow-allowed ones flagged (a target is "allowed" when a transition exists from the
    # current column; the current column is flagged so the UI disables it). Fail-soft: a missing
    # config yields ``None`` and the UI falls back to a plain all-columns select.
    detail["move_targets"] = _move_targets(entry, column_key)
    return JSONResponse(content=detail)


def _move_targets(entry: Any, current_col: str) -> list[dict[str, Any]] | None:
    """Compute the per-column move affordance for a ticket's current column.

    Loads the clone's ``columns.yml`` + ``transitions.yml`` and returns one entry per column::

        {"key": str, "name": str, "allowed": bool, "current": bool}

    ``allowed`` is ``True`` when a (wildcard-aware) transition exists from the current column to that
    column — the board's configured workflow edges. The current column is ``current=True`` +
    ``allowed=False`` (a no-op). Returns ``None`` (UI falls back to a plain select) on any config error.

    Args:
        entry: The resolved registry entry (carries the clone path).
        current_col: The ticket's current column as the snapshot reports it (a NAME or KEY).

    Returns:
        The move-target list, or ``None`` when the clone config is unreadable.
    """
    try:
        from kanbanmate.cli.init import (  # noqa: PLC0415
            CLONE_COLUMNS_RELPATH,
            CLONE_TRANSITIONS_RELPATH,
        )
        from kanbanmate.core.columns import load_columns  # noqa: PLC0415
        from kanbanmate.core.transitions import load_transitions  # noqa: PLC0415

        clone = Path(entry.clone)
        columns = load_columns((clone / CLONE_COLUMNS_RELPATH).read_text(encoding="utf-8"))
        transitions = load_transitions(
            (clone / CLONE_TRANSITIONS_RELPATH).read_text(encoding="utf-8")
        )
    except Exception:  # noqa: BLE001 — fail-soft: the select degrades to all-columns-enabled
        return None

    # The snapshot column is the GitHub Status NAME; transitions key on the stable KEY. Map both.
    key_by_token: dict[str, str] = {}
    for key, col in columns.items():
        key_by_token[key] = key
        key_by_token[col.name] = key
    current_key = key_by_token.get(current_col, current_col)

    targets: list[dict[str, Any]] = []
    for key, col in columns.items():
        is_current = key == current_key
        allowed = (not is_current) and transitions.get(current_key, key) is not None
        targets.append({"key": key, "name": col.name, "allowed": allowed, "current": is_current})
    return targets


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


class _LaunchRequest(BaseModel):
    """Request body for the ad-hoc agent-launch endpoint (tiller follow-up, 2026-06-21).

    ``prompt`` is the operator's free-form instruction delivered into the agent's REPL — OPTIONAL:
    empty launches a bare claude the operator drives by taking control of the terminal. ``profile`` is
    the permission profile the agent runs under (default ``dev`` — the ad-hoc "make a fix" case).
    """

    prompt: str = ""
    profile: str = "dev"


@app.post("/api/monitor/ticket/{number}/launch")
def launch_agent(number: int, req: _LaunchRequest, project: str | None = None) -> JSONResponse:
    """Enqueue an ad-hoc agent launch for a ticket WITHOUT moving the card (no transition).

    The daemon drains the ``launch`` intent on its next tick (nudged here for near-instant pickup),
    boots a Claude agent in the ticket's worktree under the chosen permission profile, delivers the
    prompt, and persists RUNNING state — but performs no board transition. Merge stays human-only and
    every profile keeps the §10 safety floor. Operator-authority is derived by the daemon; this
    endpoint sits behind the config-API auth middleware like the other ``/api/monitor`` writes.

    Args:
        number: The GitHub issue number to launch an agent on.
        req: ``{"prompt": str, "profile"?: str}``.
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        ``{"ok": true, "intent_id": str}`` — the enqueued intent's id (poll the board for the agent).

    Raises:
        HTTPException: 400 on a non-safe profile (e.g. ``merge``); 503/404 on project resolution.
    """
    import uuid  # noqa: PLC0415

    # Prompt is OPTIONAL (empty → bare claude the operator drives by taking control of the terminal).
    prompt = (req.prompt or "").strip()
    profile = req.profile or "dev"
    # Defense-in-depth: refuse `merge` (and any non-safe name) here too — the daemon's _execute_launch
    # is authoritative, but reject early so a direct API call (not just the UI select) gets a clear 400
    # and never even enqueues an engine-gated/merge-capable profile.
    if profile not in SAFE_LAUNCH_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"profile {profile!r} not allowed for ad-hoc launch (merge is engine-gated)",
        )

    entry = _resolve_entry(project)
    store = _monitor_store(entry)

    # Mint the operator ``op_token`` (FIX 4): an HMAC over (issue, profile) keyed by the runtime-root
    # launch secret (lazily created on first use). The daemon's _execute_launch recomputes + verifies
    # it; a bridled agent cannot forge it without the secret file. This is what makes a launch
    # provably operator-originated rather than just "operator authority because the target is idle".
    from kanbanmate.app.intents import compute_launch_token, load_launch_secret  # noqa: PLC0415

    secret = load_launch_secret(_kanban_root(), create=True)
    if secret is None:
        raise HTTPException(
            status_code=503,
            detail="cannot mint launch authorization (runtime-root launch secret unavailable)",
        )
    op_token = compute_launch_token(secret, number, profile)

    intent_id = uuid.uuid4().hex[:12]
    store.enqueue_intent(
        intent_id,
        {
            "kind": "launch",
            "issue": number,
            "args": {"prompt": prompt, "profile": profile, "op_token": op_token},
            "requested_at": time.time(),
            "caller": "operator",
        },
    )
    # Wake the daemon from its inter-tick sleep so the launch fires near-instantly. The nudge sentinel
    # is DAEMON-LEVEL (runtime root), so nudge via the runtime-root store (mirrors board_routes._nudge);
    # best-effort — a nudge failure only delays pickup to the next poll.
    try:
        from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

        FsStateStore(_kanban_root()).nudge_daemon()
    except Exception:  # noqa: BLE001
        pass
    return JSONResponse(content={"ok": True, "intent_id": intent_id})


class _MoveRequest(BaseModel):
    """Request body for the Monitoring status-change (column move) endpoint (tiller follow-up)."""

    to_col: str


@app.post("/api/monitor/ticket/{number}/move")
def move_ticket(number: int, req: _MoveRequest, project: str | None = None) -> JSONResponse:
    """Enqueue an operator ``move`` intent to change a ticket's column from the Monitoring detail.

    Mirrors ``kanban move`` (the daemon is the sole board writer): enqueues a ``move`` intent and
    nudges the daemon for near-instant pickup. Operator-authority is derived by the daemon; this sits
    behind the config-API auth middleware. The daemon validates the destination and moves the card.

    Args:
        number: The GitHub issue number to move.
        req: ``{"to_col": "<column key>"}``.
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        ``{"ok": true, "intent_id": str}``.

    Raises:
        HTTPException: 400 on an empty destination; 503/404 on project resolution.
    """
    import uuid  # noqa: PLC0415

    to_col = (req.to_col or "").strip()
    if not to_col:
        raise HTTPException(status_code=400, detail="to_col is required")

    entry = _resolve_entry(project)
    store = _monitor_store(entry)
    intent_id = uuid.uuid4().hex[:12]
    store.enqueue_intent(
        intent_id,
        {
            "kind": "move",
            "issue": number,
            "args": {"to_col": to_col},
            "requested_at": time.time(),
            "caller": "operator",
        },
    )
    try:
        from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

        FsStateStore(_kanban_root()).nudge_daemon()
    except Exception:  # noqa: BLE001 — a nudge failure only delays pickup to the next poll
        pass
    return JSONResponse(content={"ok": True, "intent_id": intent_id})


class _TrackRequest(BaseModel):
    """Request body for the set-track endpoint (skiff Task 14).

    ``track`` is the fast-track lane override the operator/triage forces on a ticket — one of
    ``"full"`` / ``"lite"`` / ``"express"``, or ``None`` (also accepts ``""``) to CLEAR the
    override. An unknown value is rejected by the GitHub client (``ValueError`` → 400).
    """

    track: str | None = None


@app.post("/api/monitor/ticket/{number}/track")
def set_ticket_track(number: int, req: _TrackRequest, project: str | None = None) -> JSONResponse:
    """Set (or clear) a ticket's ``track:*`` fast-track override label (skiff Task 14).

    Stamps the manual lane override directly on the issue via the GitHub client (NOT a daemon
    intent — the label is a board read input the daemon consumes on its next snapshot). Passing
    ``track=null`` (or ``""``) CLEARS the override. Sits behind the config-API CSRF/auth
    middleware like the other ``/api/monitor`` writes. Best-effort nudges the daemon so the new
    lane is picked up near-instantly.

    Args:
        number: The GitHub issue number.
        req: ``{"track": "full"|"lite"|"express"|null}``.
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        ``{"ok": true}`` on success.

    Raises:
        HTTPException: 400 on an unknown lane value (the client raises ``ValueError``);
        503/404 on project resolution; 502 on any other GitHub error.
    """
    # Treat "" the same as null — an empty select clears the override (mirrors the client's None path).
    track = (req.track or "").strip() or None

    entry = _resolve_entry(project)
    gh = _monitor_github(entry)
    try:
        gh.set_issue_track_label(number, track)
    except ValueError as exc:  # unknown lane — fail loud as a 400, never a 500
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — boundary: clean error, never a 500 traceback
        raise HTTPException(status_code=502, detail=f"GitHub track update failed: {exc}") from exc

    # Wake the daemon so the new lane is reflected on the next tick (best-effort — mirrors launch).
    try:
        from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

        FsStateStore(_kanban_root()).nudge_daemon()
    except Exception:  # noqa: BLE001 — a nudge failure only delays pickup to the next poll
        pass
    return JSONResponse(content={"ok": True})


@app.get("/api/monitor/board/tracks")
def board_tracks(project: str | None = None) -> JSONResponse:
    """Return the board's ``track:*`` overrides as ``{"tracks": {issue_number: lane}}``. Read-only.

    Backs the board overlay that marks which cards carry a manual fast-track lane. The keys are
    stringified issue numbers (JSON object keys are always strings on the wire; we stringify
    explicitly so the shape is deterministic) and the values are the lane (``track:`` prefix
    stripped). The frontend reads ``tracks[String(number)]``.

    Args:
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        ``{"tracks": {"<issue_number>": "<lane>", ...}}`` — only cards carrying a ``track:*`` label.

    Raises:
        HTTPException: 503/404/400 (project resolution); 502 on a GitHub error.
    """
    entry = _resolve_entry(project)
    gh = _monitor_github(entry)
    try:
        tracks = gh.board_item_tracks()
    except Exception as exc:  # noqa: BLE001 — boundary: clean error, never a 500 traceback
        raise HTTPException(status_code=502, detail=f"Board tracks fetch failed: {exc}") from exc
    return JSONResponse(content={"tracks": {str(num): lane for num, lane in tracks.items()}})


@app.get("/api/monitor/intent/{intent_id}")
def intent_result(intent_id: str, project: str | None = None) -> JSONResponse:
    """Return an enqueued intent's latest result so the SPA can surface the REAL outcome.

    The launch/move endpoints return an ``intent_id``; the daemon writes a ``<id>.result.json`` as it
    processes the intent (``claimed`` → ``done`` / ``rejected`` / ``held``). The SPA polls this to show
    whether the agent actually launched / the card actually moved instead of an optimistic "queued"
    (e.g. an older daemon that does not know the ``launch`` kind rejects it — the operator must see
    that). Returns ``{"state": "pending"}`` when no result has been written yet.

    Args:
        intent_id: The intent id returned by the launch/move endpoint.
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        The persisted ``{"intent_id", "state", "detail"}`` result, or ``{"state": "pending"}``.
    """
    entry = _resolve_entry(project)
    store = _monitor_store(entry)
    res = store.load_intent_result(intent_id)
    return JSONResponse(content=res or {"state": "pending"})


def _git_blob_size(repo: Path, ref: str, rel: str) -> int | None:
    """Return the byte size of ``<ref>:<rel>`` via ``git cat-file -s``, or None if absent / git fails.

    Mirrors the on-disk ``st_size`` pre-check for the WIP-branch path: querying the blob size lets the
    caller reject an oversize artifact BEFORE materialising its content into memory (the size cap was
    previously applied only after buffering the whole ``git show`` output). No shell (arg list);
    ``ref``/``rel`` are caller-validated (int-derived ref, sandboxed rel path).
    """
    import subprocess  # noqa: PLC0415

    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-s", f"{ref}:{rel}"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        return int(out.stdout.decode("utf-8", errors="replace").strip())
    except ValueError:
        return None


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
        # Mirror the on-disk st_size pre-check: query the blob size FIRST and reject an oversize file
        # BEFORE materialising its content (the cap was previously applied only after buffering the
        # whole git-show output into memory). Same error shape as the on-disk oversize path.
        wip_size = _git_blob_size(root, ref, rel)
        if wip_size is not None and wip_size > _MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({wip_size} bytes; cap {_MAX_FILE_BYTES})",
            )
        wip = _git_show(root, ref, rel)
        if wip is not None:
            return JSONResponse(content={"path": rel, "content": wip, "source": ref})

    raise HTTPException(
        status_code=404, detail="File not found on the board tree or the ticket WIP branch"
    )


def _board_json_path(entry: Any) -> Path:
    """Resolve the per-project ``board.json`` path the daemon/board endpoints write (keel STEP 4).

    Reuses :func:`_board_store` so the SSE version reader and the board VIEW read the IDENTICAL
    ``board.json`` (the daemon/CLI sub-root resolution lives there). Overridable indirectly via
    ``app.state.board_store`` (tests inject a store whose ``root`` points at the fixture board).

    Args:
        entry: The resolved registry entry.

    Returns:
        The path to the selected board's ``board.json``.
    """
    return Path(_board_store(entry).root) / "board.json"


@app.get("/api/monitor/stream")
def monitor_stream(project: str | None = None) -> StreamingResponse:
    """SSE push of the board change signal for sub-second Monitoring + board updates (keel STEP 4).

    A long-lived ``text/event-stream`` that emits an ``event: change`` carrying the per-project
    ``board.json`` ``version`` int + the daemon ``daemon.heartbeat`` ``ts`` whenever EITHER changes
    — so an operator drag (via KanbanMateUI) OR an engine transition (the daemon's intent-drain /
    auto-advance bumps the store version) reaches the SPA sub-second instead of on the next ~4 s
    poll. The SPA refetches ``/api/monitor/board`` (+ ``/api/board/state``) on each change event and
    KEEPS a backstop poll, so a dropped/flapping stream degrades gracefully to polling.

    CONSTRAINTS honoured here: this route sits behind the SAME ``@app.middleware('http')`` auth guard
    as every other ``/api/*`` route (a streaming endpoint that bypassed auth would leak board state)
    and respects the ``?project=`` selector via ``_resolve_entry``. The stream body does only LOCAL,
    CHEAP reads (``stat`` + a tiny JSON parse of ``board.json``; a read of ``daemon.heartbeat``) on a
    BOUNDED sleep-poll loop — NO GitHub call, no busy-spin.

    Args:
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        A ``StreamingResponse`` (``text/event-stream``) of SSE frames.

    Raises:
        HTTPException: 503/404/400 (project resolution — same as the other monitor routes).
    """
    from kanbanmate.http.monitor_stream import (  # noqa: PLC0415
        monitor_event_stream,
        read_board_version,
        read_daemon_tick,
    )

    entry = _resolve_entry(project)  # auth (middleware) + selector resolution happen here
    board_path = _board_json_path(entry)
    heartbeat_path = _kanban_root() / "daemon.heartbeat"

    # Poll/keepalive cadence are overridable via app.state (tests run the loop fast; an operator
    # could tune it). Defaults: ~1 s sub-second floor, ~20 s keep-alive — see monitor_stream.
    # ``max_iterations`` is None in production (the loop runs until the client disconnects and the
    # ASGI server closes the generator); tests cap it so the bounded stream terminates.
    poll_interval = getattr(app.state, "monitor_stream_poll_interval", 1.0)
    keepalive_interval = getattr(app.state, "monitor_stream_keepalive_interval", 20.0)
    max_iterations = getattr(app.state, "monitor_stream_max_iterations", None)
    stream = monitor_event_stream(
        lambda: read_board_version(board_path),
        lambda: read_daemon_tick(heartbeat_path),
        poll_interval=poll_interval,
        keepalive_interval=keepalive_interval,
        max_iterations=max_iterations,
    )
    # Headers that keep the stream healthy through proxies (Caddy) + the browser: no-cache so a
    # stale event-stream is never served from cache; no proxy buffering so events flush immediately.
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy (nginx/Caddy) response buffering for SSE
            "Connection": "keep-alive",
        },
    )


# Side-effect import: registers the agent-terminal WS endpoint on `app` (tiller §1.3).
import kanbanmate.http.agent_terminal as _agent_terminal  # noqa: F401, E402
