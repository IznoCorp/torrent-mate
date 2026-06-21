"""Board API routes: /api/board/* (anchor §10).

Extends the helm HTTP API with native board state endpoints. All routes
live on the SAME FastAPI ``app`` imported from ``config_api`` — mounted via
a side-effect import at the bottom of ``config_api.py`` (the proven
``monitor_routes`` pattern, ``config_api.py:554``).

Error conventions (mirror the config routes):
- ``board_backend != "native"`` for the selected project → ``409``
  (the board is not yet repatriated; use ``/api/board/import`` first).
- Unknown ``column_key`` / ``item_id``, or an item not in the named column → ``400``.
- Stale ``if_version`` (optimistic concurrency, anchor §6.2) → ``409``.

Mutating endpoints bump the daemon-wake nudge (anchor §4.4) via
``FsStateStore.nudge_daemon()`` (the proven ``http/serve.py:237`` pattern) so a
native write wakes the daemon within the inter-tick sleep budget.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import fastapi
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate.adapters.store.fs_board import VersionConflict
from kanbanmate.cli.init import _load_registry, _projects_path
from kanbanmate.http.config_api import (
    _kanban_root,  # noqa: PLC2701
    _read_json_object,  # noqa: PLC2701
    _resolve_entry,  # noqa: PLC2701
    app,
)

logger = logging.getLogger(__name__)


def _require_native(entry: Any) -> None:
    """Raise ``409`` when the project's board_backend is not native-backed ('native' or 'hybrid').

    The native board store backs both 'native' (one-way mirror) and 'hybrid' (bidirectional), so the
    ``/api/board/*`` placement API applies to both. Only the pure-GitHub backend has no native store.

    Args:
        entry: The resolved ``ProjectEntry``.

    Raises:
        HTTPException: 409 when ``entry.board_backend`` is neither 'native' nor 'hybrid'.
    """
    backend = getattr(entry, "board_backend", "github")
    if backend not in ("native", "hybrid"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Project board_backend is {backend!r}, not native-backed. "
                "Set board_backend=native (or hybrid) in projects.json and run 'kanban board import'."
            ),
        )


def _get_store(entry: Any) -> Any:
    """Resolve the FsBoardStateStore for the selected entry.

    Resolves the per-project sub-root EXACTLY as the daemon/CLI do so this module reads + writes the
    SAME ``board.json`` the daemon writes. The store layout is keyed off the ENABLED-project count
    (``wiring_for_entry``: ``state_root = <root>/projects/<safe> iff len(enabled) > 1``, flat root
    otherwise) — NOT the registered count. Using the registered count would split the daemon (flat
    root) and the HTTP API (sub-root) onto different files when a 2nd project is registered but
    disabled, defeating the dual-writer ``flock`` guarantee (DESIGN §6.3).

    Args:
        entry: The resolved ``ProjectEntry``.

    Returns:
        A ``FsBoardStateStore`` rooted at the per-project state root.
    """
    from kanbanmate.adapters.store.fs_board import FsBoardStateStore  # noqa: PLC0415
    from kanbanmate.core.registry_resolve import enabled_entries, safe_project_id  # noqa: PLC0415

    root = _kanban_root()
    registry = _load_registry(_projects_path(root))
    multi = len(enabled_entries(registry)) > 1
    store_root = root / "projects" / safe_project_id(entry.project_id) if multi else root
    return FsBoardStateStore(store_root)


def _get_forge(entry: Any) -> Any:
    """Construct a ``GithubClient`` for the entry's project (issue identity for the §4.5 JOIN).

    The forge supplies the issue identity (``issue_number`` + ``title``) the native store does not
    hold — used by ``GET /api/board/state`` to deliver the DESIGN §10 card shape, and by the import.

    Args:
        entry: The resolved ``ProjectEntry``.

    Returns:
        A ``GithubClient`` bound to the entry's project id + repo, authed via its ``token_ref``.
    """
    from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
    from kanbanmate.adapters.github.token import load_entry_token  # noqa: PLC0415

    token = load_entry_token(_kanban_root(), getattr(entry, "token_ref", ""))
    return GithubClient(token, project_id=entry.project_id, repo=entry.repo)


def _mirror_to_github(entry: Any, item_id: str, column_key: str) -> dict[str, Any]:
    """Mirror a native placement to the GitHub Status AND verify the remote state (one-way, fail-soft).

    The native store is the placement authority; GitHub is a mirror so the Projects board / status
    pill / Health keep reflecting reality (DESIGN §5). The HTTP move/place endpoints write the store
    directly (not via ``NativeBoardBackend.move_card``), so without this a UI move would never reach
    GitHub. Maps the column KEY → Status display NAME via the clone's ``columns.yml`` and calls the
    forge ``move_card``.

    Beyond firing the mutation, this VERIFIES THE REMOTE STATE — so the SPA reports verified
    completion, not merely "our HTTP call returned 200" (operator request). Verification reads the
    resulting Status name out of the SAME mutation response (``move_card_confirmed`` —
    read-your-write): no second query, and no eventual-consistency lag that a separate read-back
    would suffer (which could cry wolf on a move that actually succeeded). A returned name equal to
    the target proves GitHub applied the change; a different name / ``None`` is a silent no-op (e.g.
    an option-mapping drift) → ``unconfirmed``.

    The native write has already landed when this runs, so every failure mode is non-fatal — it is
    reported as a degraded mirror, never raised.

    Args:
        entry: The resolved ``ProjectEntry``.
        item_id: The ``ProjectV2Item`` node id that moved.
        column_key: The native destination column key.

    Returns:
        A status dict ``{"state": str, "detail": str | None}`` where ``state`` is one of:
        ``"synced"`` (mirrored AND the mutation response confirms the new Status),
        ``"disabled"`` (``board_mirror=False`` — intentionally off, not degraded),
        ``"failed"`` (the mirror mutation raised — GitHub was NOT updated),
        ``"unconfirmed"`` (the mutation returned but the confirmed Status differs / is absent — the
        move may not have taken; the operator should Refresh / retry).
    """
    if not getattr(entry, "board_mirror", True):
        return {"state": "disabled", "detail": None}
    try:
        from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH  # noqa: PLC0415
        from kanbanmate.core.columns import load_columns  # noqa: PLC0415

        columns_yaml = (Path(entry.clone) / CLONE_COLUMNS_RELPATH).read_text(encoding="utf-8")
        name_for_key = {c.key: c.name for c in load_columns(columns_yaml).values()}
        target_name = name_for_key.get(column_key, column_key)
        confirmed = _get_forge(entry).move_card_confirmed(item_id, target_name)
    except Exception as exc:  # noqa: BLE001 — mirror is observability, not authority (§5.2)
        logger.warning(
            "board mirror: failed to mirror %s → %s to GitHub", item_id, column_key, exc_info=True
        )
        return {"state": "failed", "detail": str(exc)}
    if confirmed == target_name:
        return {"state": "synced", "detail": None}
    return {
        "state": "unconfirmed",
        "detail": f"GitHub confirmed {confirmed!r}, expected {target_name!r}",
    }


_EXCERPT_MAX = 160


def _body_excerpt(body: str) -> str:
    """Derive a short, human-readable card excerpt from a raw issue body (Item 2 — richer cards).

    The issue body is full of machinery the SPA must not show on a card: the delimited status-header
    block, ``**key**: value`` markers (roadmap / codename / design / plans), HTML comments, and
    markdown headings. This keeps the FIRST meaningful prose line(s), so a card carries a glimpse of
    what the ticket is about without rendering markdown or leaking the bookkeeping.

    Args:
        body: The raw GitHub issue markdown body (may be empty).

    Returns:
        A single-line excerpt (<= ``_EXCERPT_MAX`` chars, ellipsised), or ``""`` when the body has no
        prose (e.g. a draft item or a body that is all markers).
    """
    from kanbanmate.core.body_edit import _STATUS_BLOCK  # noqa: PLC0415,PLC2701

    if not body:
        return ""
    # Drop the delimited status-header block wholesale, reusing the SAME non-greedy regex the writer
    # uses (handles any malformed/duplicate block consistently rather than a bespoke find()).
    text = _STATUS_BLOCK.sub("", body)
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        # Skip a ``**key**: value`` marker line (bookkeeping, not prose).
        if line.startswith("**") and "**:" in line:
            continue
        out.append(line)
        if len(" ".join(out)) >= _EXCERPT_MAX:
            break
    excerpt = " ".join(out).strip()
    return excerpt[: _EXCERPT_MAX - 1] + "…" if len(excerpt) > _EXCERPT_MAX else excerpt


def _nudge() -> None:
    """Best-effort daemon nudge (fail-soft — a nudge failure is never a board error).

    Uses ``FsStateStore.nudge_daemon()`` (the proven ``http/serve.py:237`` pattern).
    """
    try:
        from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

        FsStateStore(_kanban_root()).nudge_daemon()
    except Exception:  # noqa: BLE001
        # Nudge failure is observability, never a board error — the write already landed and the
        # daemon polls regardless. Logged (not silently swallowed) so a dead fast-wake path is
        # diagnosable rather than every SPA write quietly waiting a full poll interval.
        logger.debug(
            "board nudge failed (daemon will pick up the write on its next poll)", exc_info=True
        )


# ---------------------------------------------------------------------------
# GET /api/board/state
# ---------------------------------------------------------------------------


@app.get("/api/board/state")
def board_state(project: str | None = None) -> JSONResponse:
    """Return the JOINed native board snapshot (anchor §4.5, §10).

    The card shape the SPA consumes is ``{item_id, issue_number, title, excerpt, column_key, index}``.
    ``column_key`` + ``index`` come from the native store (authority); ``issue_number`` + ``title`` +
    ``excerpt`` (a short body glimpse, Item 2) are JOINed from the live GitHub issue set (the store
    does not hold them). The JOIN is **fail-soft**: a forge outage must not break the local board read
    — the SPA still gets placement + order, with ``issue_number``/``title`` ``null`` and ``excerpt``
    empty.

    Args:
        project: The Project v2 node id (required for N>1).

    Returns:
        ``{"version": int, "columns": [...], "cards": [{item_id, issue_number, title, column_key,
        index}, ...]}``.

    Raises:
        HTTPException: 409 when board_backend != native.
    """
    entry = _resolve_entry(project)
    _require_native(entry)
    store = _get_store(entry)
    doc = store.load()

    # JOIN the forge issue set for identity (issue_number + title). Fail-soft: GitHub unreachable →
    # serve placement/order without identity rather than 5xx-ing a local read.
    # identity maps item_id → (issue_number, title, body_excerpt) — the card-display fields the native
    # store does not hold. body_excerpt (Item 2) gives the card a glimpse of the ticket's content.
    identity: dict[str, tuple[int | None, str | None, str]] = {}
    identity_degraded = False
    try:
        forge_snap = _get_forge(entry).snapshot()
        identity = {
            t.item_id: (t.issue_number, t.title, _body_excerpt(t.body)) for t in forge_snap.tickets
        }
    except Exception:  # noqa: BLE001 — fail-soft: a local read must not 5xx on a forge outage
        identity_degraded = True
        logger.warning(
            "board/state: forge JOIN failed; serving placement without issue identity",
            exc_info=True,
        )

    cards = []
    for col in doc.get("columns", []):
        for idx, item_id in enumerate(doc.get("order", {}).get(col, [])):
            issue_number, title, excerpt = identity.get(item_id, (None, None, ""))
            cards.append(
                {
                    "item_id": item_id,
                    "issue_number": issue_number,
                    "title": title,
                    "excerpt": excerpt,
                    "column_key": col,
                    "index": idx,
                }
            )
    return JSONResponse(
        content={
            "version": doc.get("version", 0),
            "columns": doc.get("columns", []),
            "cards": cards,
            # True when the forge JOIN failed → issue_number/title are null because GitHub was
            # unreachable, NOT because the cards lack identity. Lets the SPA show "titles
            # unavailable" instead of rendering a board full of untitled cards.
            "identity_degraded": identity_degraded,
        }
    )


# ---------------------------------------------------------------------------
# POST /api/board/move
# ---------------------------------------------------------------------------


@app.post("/api/board/move")
async def board_move(request: fastapi.Request, project: str | None = None) -> JSONResponse:
    """Cross-column move → native place_card(tail) + mirror (anchor §10).

    Body: ``{"item_id": str, "to_column": str, "if_version"?: int}``.

    Args:
        request: HTTP request with JSON body.
        project: The Project v2 node id.

    Returns:
        ``{"version": int}`` after the move.

    Raises:
        HTTPException: 409 (not native or stale version); 400 (bad column/item).
    """
    entry = _resolve_entry(project)
    _require_native(entry)
    body = await _read_json_object(request)
    item_id = body.get("item_id", "")
    to_column = body.get("to_column", "")
    if_version = body.get("if_version")
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")
    if not to_column:
        raise HTTPException(status_code=400, detail="to_column is required")

    store = _get_store(entry)
    try:
        version = store.place_card(item_id, to_column, if_version=if_version)
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mirror = _mirror_to_github(entry, item_id, to_column)
    _nudge()
    return JSONResponse(
        content={
            "version": version,
            "mirror_state": mirror["state"],
            "mirror_detail": mirror["detail"],
            # Back-compat boolean: True when the GitHub mirror is not fully verified-synced.
            "mirror_degraded": mirror["state"] in ("failed", "unconfirmed"),
        }
    )


# ---------------------------------------------------------------------------
# POST /api/board/reorder
# ---------------------------------------------------------------------------


@app.post("/api/board/reorder")
async def board_reorder(request: fastapi.Request, project: str | None = None) -> JSONResponse:
    """Set a column's full ordered card list — native only, NOT mirrored (anchor §10).

    Body: ``{"column_key": str, "ordered_item_ids": [...], "if_version"?: int}``.

    Args:
        request: HTTP request with JSON body.
        project: The Project v2 node id.

    Returns:
        ``{"version": int}`` after the reorder.

    Raises:
        HTTPException: 409 (not native or stale version); 400 (bad column/ids).
    """
    entry = _resolve_entry(project)
    _require_native(entry)
    body = await _read_json_object(request)
    column_key = body.get("column_key", "")
    ordered_item_ids = body.get("ordered_item_ids", [])
    if_version = body.get("if_version")
    if not column_key:
        raise HTTPException(status_code=400, detail="column_key is required")

    store = _get_store(entry)
    try:
        version = store.reorder_column(column_key, ordered_item_ids, if_version=if_version)
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _nudge()
    return JSONResponse(content={"version": version})


# ---------------------------------------------------------------------------
# POST /api/board/place
# ---------------------------------------------------------------------------


@app.post("/api/board/place")
async def board_place(request: fastapi.Request, project: str | None = None) -> JSONResponse:
    """Place a card at an explicit (column, index) (anchor §10).

    Body: ``{"item_id": str, "column_key": str, "index": int|null, "if_version"?: int}``.

    Args:
        request: HTTP request with JSON body.
        project: The Project v2 node id.

    Returns:
        ``{"version": int}``.

    Raises:
        HTTPException: 409 (not native or stale version); 400 (bad column/item).
    """
    entry = _resolve_entry(project)
    _require_native(entry)
    body = await _read_json_object(request)
    item_id = body.get("item_id", "")
    column_key = body.get("column_key", "")
    index = body.get("index")  # None → append
    if_version = body.get("if_version")
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")
    if not column_key:
        raise HTTPException(status_code=400, detail="column_key is required")

    store = _get_store(entry)
    try:
        version = store.place_card(item_id, column_key, index, if_version=if_version)
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mirror = _mirror_to_github(entry, item_id, column_key)
    _nudge()
    return JSONResponse(
        content={
            "version": version,
            "mirror_state": mirror["state"],
            "mirror_detail": mirror["detail"],
            "mirror_degraded": mirror["state"] in ("failed", "unconfirmed"),
        }
    )


# ---------------------------------------------------------------------------
# POST /api/board/import
# ---------------------------------------------------------------------------


@app.post("/api/board/import")
async def board_import_endpoint(
    request: fastapi.Request, project: str | None = None
) -> JSONResponse:
    """Server-side kanban board import — the SPA 'Repatriate' action (anchor §10).

    Body: ``{"dry_run"?: bool}``.

    Args:
        request: HTTP request with JSON body.
        project: The Project v2 node id.

    Returns:
        ``{"version": int, "summary": {...}}``.

    Raises:
        HTTPException: 400 on a local columns-config error (missing/malformed ``columns.yml``);
        502 on a GitHub/store failure.
    """
    body = await _read_json_object(request)
    dry_run = bool(body.get("dry_run", False))

    entry = _resolve_entry(project)
    store = _get_store(entry)

    # Local config first: a missing / unreadable / malformed columns.yml is a 400 (operator config
    # error), NOT a 502 (which would wrongly blame GitHub). Logged server-side for diagnosis.
    try:
        from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH  # noqa: PLC0415
        from kanbanmate.core.columns import load_columns  # noqa: PLC0415

        columns_path = Path(entry.clone) / CLONE_COLUMNS_RELPATH
        columns_yaml = columns_path.read_text(encoding="utf-8")
        columns = [col.key for col in load_columns(columns_yaml).values()]
    except (OSError, ValueError) as exc:
        logger.error("board/import: local columns config unreadable", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Board columns config error: {exc}") from exc

    # Forge import: a GitHub / token / store failure is a 502. Logged server-side (was only echoed
    # into the HTTP detail string before).
    try:
        from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
        from kanbanmate.adapters.github.token import load_entry_token  # noqa: PLC0415
        from kanbanmate.app.board_import import import_board  # noqa: PLC0415

        token = load_entry_token(_kanban_root(), getattr(entry, "token_ref", ""))
        forge = GithubClient(token, project_id=entry.project_id, repo=entry.repo)
        result = import_board(forge, store, columns, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001 — boundary: clean 502, never a raw traceback
        logger.error("board/import: forge import failed", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Board import failed: {exc}") from exc

    if not dry_run:
        _nudge()
    return JSONResponse(content=result)
