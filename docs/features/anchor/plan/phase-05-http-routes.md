# Phase 05 — helm HTTP API board routes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

## Gate

Phase 04 must be complete and `make check` green:
- `src/kanbanmate/app/board_import.py` exists.
- `src/kanbanmate/cli/board.py` exists with `board_app`.
- `tests/app/test_board_import.py` passes.

## Goal

Implement `http/board_routes.py` with the five `/api/board/*` endpoints, mount it in `config_api.py` (same side-effect import pattern as `monitor_routes`), and extend the `/api/schema` response to include the `board.json` JSON Schema.

## Files

- **Create:** `src/kanbanmate/http/board_routes.py` — the five `/api/board/*` routes
- **Modify:** `src/kanbanmate/http/config_api.py` — side-effect import of `board_routes`; extend `_generate_schema()` with board.json schema
- **Create:** `tests/http/test_board_routes.py` — HTTP route unit tests

## Key design facts (grounded)

- `monitor_routes.py` is mounted via a side-effect import at `config_api.py:554`: `from kanbanmate.http import monitor_routes as _monitor_routes  # noqa: E402,F401`. `board_routes.py` follows identically.
- Routes use the SAME `app` FastAPI instance from `config_api.py` (imported at the top of `board_routes.py`). All routes are registered on that shared `app`.
- `_resolve_entry(project_id)` is an existing helper in `config_api.py:119` that resolves the project registry entry. Import it via `from kanbanmate.http.config_api import app, _resolve_entry`.
- The `board_backend != "native"` check: the registry entry has `entry.board_backend`; if it's not `"native"`, return `409`.
- The daemon nudge: `IntentStore.nudge_daemon()` is the nudge path. In the HTTP server context, use `app.state.intents_store` (the pattern for injected state), or directly bump `FsIntentsStore(root).nudge_daemon()`.
- `_read_json_object(request)` is already defined in `config_api.py:199` — import it.
- Error conventions from existing routes: `ValueError` → `400`; stale `if_version` → `409`; `board_backend != native` → `409`.
- The `?project=<id>` param pattern: all existing routes use `project: str | None = None` in the function signature.
- Tests use `TestClient` from `starlette.testclient` (the pattern in `tests/http/test_config_api.py`).
- All assertions on output must parse JSON, never check raw text or ANSI.

---

### Task 1: `http/board_routes.py`

**Files:**
- Create: `src/kanbanmate/http/board_routes.py`

**Interfaces:**
- Produces: routes on the shared FastAPI `app`: `GET /api/board/state`, `POST /api/board/move`, `POST /api/board/reorder`, `POST /api/board/place`, `POST /api/board/import`
- Consumes: `FsBoardStateStore`, `import_board`, `NativeBoardBackend`, `_resolve_entry` from `config_api.py`

- [ ] **Step 1: Write the file**

```python
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

Mutating endpoints bump the daemon-wake nudge (anchor §4.4) via the
``IntentStore`` bound to ``app.state`` so a native write wakes the daemon
within the inter-tick sleep budget.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fastapi
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate.http.config_api import (
    _read_json_object,  # noqa: PLC2701
    _resolve_entry,      # noqa: PLC2701
    app,
)


def _require_native(entry: Any) -> None:
    """Raise ``409`` when the selected project's board_backend is not 'native'.

    Args:
        entry: The resolved ``ProjectEntry``.

    Raises:
        HTTPException: 409 when ``entry.board_backend != "native"``.
    """
    backend = getattr(entry, "board_backend", "github")
    if backend != "native":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Project board_backend is {backend!r}, not 'native'. "
                "Run 'kanban board import' and set board_backend=native in projects.json first."
            ),
        )


def _get_store(entry: Any) -> Any:
    """Resolve the FsBoardStateStore for the selected entry.

    Args:
        entry: The resolved ``ProjectEntry``.

    Returns:
        A ``FsBoardStateStore`` rooted at the per-project state root.
    """
    from kanbanmate.adapters.store.fs_board import FsBoardStateStore  # noqa: PLC0415
    from kanbanmate.core.registry_resolve import safe_project_id  # noqa: PLC0415

    # Determine the per-project store root (mirrors build_deps store_root logic).
    kanban_root = _kanban_root_path()
    registry = _load_registry_for_http()
    multi = len([e for e in registry.values() if e.enabled]) > 1  # type: ignore[attr-defined]
    if multi:
        store_root = kanban_root / "projects" / safe_project_id(entry.project_id)
    else:
        store_root = kanban_root
    return FsBoardStateStore(store_root)


def _kanban_root_path() -> Path:
    """Return the kanban root from app.state or the default."""
    root = getattr(app.state, "kanban_root", None)
    if root is not None:
        return Path(root)
    from kanbanmate.cli.init import DEFAULT_KANBAN_ROOT  # noqa: PLC0415
    return DEFAULT_KANBAN_ROOT


def _load_registry_for_http() -> dict[str, Any]:
    from kanbanmate.cli.init import _load_registry, _projects_path  # noqa: PLC0415
    return _load_registry(_projects_path(_kanban_root_path()))


def _nudge() -> None:
    """Best-effort daemon nudge (fail-soft — a nudge failure is never a board error)."""
    try:
        intents = getattr(app.state, "intents_store", None)
        if intents is not None:
            intents.nudge_daemon()
        else:
            # Fallback: bump the nudge file directly.
            from kanbanmate.adapters.store.fs_intents import FsIntentsStore  # noqa: PLC0415
            FsIntentsStore(_kanban_root_path()).nudge_daemon()
    except Exception:  # noqa: BLE001
        pass  # nudge failure is observability, never a board error


# ---------------------------------------------------------------------------
# GET /api/board/state
# ---------------------------------------------------------------------------

@app.get("/api/board/state")
def board_state(project: str | None = None) -> JSONResponse:
    """Return the native board snapshot: columns, version, and per-card placement+index (anchor §10).

    Args:
        project: The Project v2 node id (required for N>1).

    Returns:
        ``{"version": int, "columns": [...], "cards": [{"item_id", "column_key", "index"}, ...]}``.

    Raises:
        HTTPException: 409 when board_backend != native.
    """
    entry = _resolve_entry(project)
    _require_native(entry)
    store = _get_store(entry)
    doc = store.load()
    cards = []
    for col in doc.get("columns", []):
        for idx, item_id in enumerate(doc.get("order", {}).get(col, [])):
            cards.append({
                "item_id": item_id,
                "column_key": col,
                "index": idx,
            })
    return JSONResponse(content={
        "version": doc.get("version", 0),
        "columns": doc.get("columns", []),
        "cards": cards,
    })


# ---------------------------------------------------------------------------
# POST /api/board/move
# ---------------------------------------------------------------------------

@app.post("/api/board/move")
async def board_move(
    request: fastapi.Request, project: str | None = None
) -> JSONResponse:
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

    store = _get_store(entry)
    try:
        version = store.place_card(item_id, to_column, if_version=if_version)
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "concurrency" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc

    _nudge()
    return JSONResponse(content={"version": version})


# ---------------------------------------------------------------------------
# POST /api/board/reorder
# ---------------------------------------------------------------------------

@app.post("/api/board/reorder")
async def board_reorder(
    request: fastapi.Request, project: str | None = None
) -> JSONResponse:
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

    store = _get_store(entry)
    try:
        version = store.reorder_column(column_key, ordered_item_ids, if_version=if_version)
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "concurrency" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc

    _nudge()
    return JSONResponse(content={"version": version})


# ---------------------------------------------------------------------------
# POST /api/board/place
# ---------------------------------------------------------------------------

@app.post("/api/board/place")
async def board_place(
    request: fastapi.Request, project: str | None = None
) -> JSONResponse:
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

    store = _get_store(entry)
    try:
        version = store.place_card(item_id, column_key, index, if_version=if_version)
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "concurrency" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc

    _nudge()
    return JSONResponse(content={"version": version})


# ---------------------------------------------------------------------------
# POST /api/board/import
# ---------------------------------------------------------------------------

@app.post("/api/board/import")
async def board_import_endpoint(
    request: fastapi.Request, project: str | None = None
) -> JSONResponse:
    """Server-side kanban board import — the SPA 'Repatriate' action (anchor §10).

    Body: ``{"project": str, "dry_run"?: bool}``.

    Args:
        request: HTTP request with JSON body.
        project: The Project v2 node id.

    Returns:
        ``{"version": int, "summary": {...}}``.

    Raises:
        HTTPException: 502 on GitHub/store failure.
    """
    body = await _read_json_object(request)
    dry_run = bool(body.get("dry_run", False))

    entry = _resolve_entry(project)
    store = _get_store(entry)

    try:
        from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
        from kanbanmate.adapters.github.token import load_entry_token  # noqa: PLC0415
        from kanbanmate.app.board_import import import_board  # noqa: PLC0415
        from kanbanmate.core.columns import load_columns  # noqa: PLC0415
        from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH  # noqa: PLC0415

        kanban_root = _kanban_root_path()
        token = load_entry_token(kanban_root, getattr(entry, "token_ref", ""))
        forge = GithubClient(token, project_id=entry.project_id, repo=entry.repo)

        columns_path = Path(entry.clone) / CLONE_COLUMNS_RELPATH
        columns_yaml = columns_path.read_text(encoding="utf-8")
        col_map = load_columns(columns_yaml)
        columns = [col.key for col in col_map.values()]

        result = import_board(forge, store, columns, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Board import failed: {exc}") from exc

    if not dry_run:
        _nudge()
    return JSONResponse(content=result)
```

- [ ] **Step 2: Mount in `config_api.py`**

In `src/kanbanmate/http/config_api.py`, after the existing `monitor_routes` import (line 554):

```python
from kanbanmate.http import board_routes as _board_routes  # noqa: E402,F401
```

- [ ] **Step 3: Extend `/api/schema` with `board.json` schema**

`_generate_schema()` in `src/kanbanmate/http/config_api.py:769` returns a dict literal directly (not a local variable). Refactor it to build the dict and add the board schema as a `$defs` entry before returning. Replace the `return {` … `}` block so it looks like:

```python
def _generate_schema() -> dict[str, Any]:
    """Generate a minimal JSON Schema for the PipelineDraft model.

    Returns:
        A dict representing the JSON Schema.
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        # ... (keep ALL existing content byte-for-byte identical) ...
    }
    # anchor §10: board.json schema so the SPA can validate client-side.
    schema.setdefault("$defs", {})["BoardState"] = {
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
```

The key change: assign the existing `return { ... }` literal to `schema = { ... }`, then append the `$defs` entry, then `return schema`. Do NOT change any existing schema content — only add the `$defs` key at the end.

- [ ] **Step 4: Smoke-check imports**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -c "from kanbanmate.http.config_api import app; print('routes:', [r.path for r in app.routes if '/api/board' in getattr(r,'path','')])"
```

Expected: shows the 5 `/api/board/*` routes.

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/http/board_routes.py src/kanbanmate/http/config_api.py
git commit -m "feat(anchor): /api/board/* HTTP routes + board.json schema"
```

---

### Task 2: HTTP route tests (`tests/http/test_board_routes.py`)

**Files:**
- Create: `tests/http/test_board_routes.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for /api/board/* routes (anchor §12.7)."""

from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board
from kanbanmate.http.config_api import app

COLUMNS = ["Backlog", "InProgress", "Done"]

_FAKE_ENTRY = MagicMock()
_FAKE_ENTRY.board_backend = "native"
_FAKE_ENTRY.project_id = "pid"
_FAKE_ENTRY.repo = "o/r"
_FAKE_ENTRY.clone = "/tmp/clone"
_FAKE_ENTRY.enabled = True


@pytest.fixture()
def seeded_store(tmp_path: pathlib.Path) -> FsBoardStateStore:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=COLUMNS,
        placement={"item1": "Backlog", "item2": "InProgress"},
        order={"Backlog": ["item1"], "InProgress": ["item2"], "Done": []},
    )
    return s


@pytest.fixture()
def client(tmp_path: pathlib.Path, seeded_store: FsBoardStateStore) -> TestClient:
    """TestClient with patched entry resolution and store injection."""
    with patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY), \
         patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store), \
         patch("kanbanmate.http.board_routes._nudge"):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/board/state
# ---------------------------------------------------------------------------

def test_board_state_returns_version_and_cards(client: TestClient) -> None:
    resp = client.get("/api/board/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert "Backlog" in data["columns"]
    cards_by_id = {c["item_id"]: c for c in data["cards"]}
    assert "item1" in cards_by_id
    assert cards_by_id["item1"]["column_key"] == "Backlog"
    assert cards_by_id["item1"]["index"] == 0


def test_board_state_409_when_not_native() -> None:
    entry = MagicMock()
    entry.board_backend = "github"
    with patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry):
        with TestClient(app) as c:
            resp = c.get("/api/board/state")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/board/move
# ---------------------------------------------------------------------------

def test_board_move_happy_path(client: TestClient, seeded_store: FsBoardStateStore) -> None:
    resp = client.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    doc = seeded_store.load()
    assert doc["placement"]["item1"] == "Done"


def test_board_move_bad_column_returns_400(client: TestClient) -> None:
    resp = client.post("/api/board/move", json={"item_id": "item1", "to_column": "NoSuchCol"})
    assert resp.status_code == 400


def test_board_move_stale_version_returns_409(client: TestClient) -> None:
    resp = client.post("/api/board/move", json={
        "item_id": "item1", "to_column": "Done", "if_version": 99
    })
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/board/reorder
# ---------------------------------------------------------------------------

def test_board_reorder_happy_path(client: TestClient, seeded_store: FsBoardStateStore) -> None:
    # Seed two items in Backlog.
    seeded_store.place_card("item2", "Backlog")  # move item2 to Backlog
    resp = client.post("/api/board/reorder", json={
        "column_key": "Backlog",
        "ordered_item_ids": ["item2", "item1"],
    })
    assert resp.status_code == 200
    doc = seeded_store.load()
    assert doc["order"]["Backlog"] == ["item2", "item1"]


def test_board_reorder_bad_column_returns_400(client: TestClient) -> None:
    resp = client.post("/api/board/reorder", json={
        "column_key": "NoSuchCol", "ordered_item_ids": []
    })
    assert resp.status_code == 400


def test_board_reorder_duplicate_items_returns_400(
    client: TestClient, seeded_store: FsBoardStateStore
) -> None:
    resp = client.post("/api/board/reorder", json={
        "column_key": "Backlog",
        "ordered_item_ids": ["item1", "item1"],
    })
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/board/place
# ---------------------------------------------------------------------------

def test_board_place_at_index(client: TestClient, seeded_store: FsBoardStateStore) -> None:
    # Move item2 to Backlog first so we can reorder.
    seeded_store.place_card("item2", "Backlog")
    resp = client.post("/api/board/place", json={
        "item_id": "item2", "column_key": "Backlog", "index": 0
    })
    assert resp.status_code == 200
    doc = seeded_store.load()
    assert doc["order"]["Backlog"][0] == "item2"


# ---------------------------------------------------------------------------
# Mutations bump the nudge
# ---------------------------------------------------------------------------

def test_board_move_bumps_nudge(tmp_path: pathlib.Path, seeded_store: FsBoardStateStore) -> None:
    nudge_calls: list[int] = []
    with patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY), \
         patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store), \
         patch("kanbanmate.http.board_routes._nudge", side_effect=lambda: nudge_calls.append(1)):
        with TestClient(app) as c:
            c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert nudge_calls, "move must bump the daemon nudge"
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/http/test_board_routes.py -v
```

Expected: all PASS.

- [ ] **Step 3: Run make check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make check
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/http/test_board_routes.py
git commit -m "test(anchor): /api/board/* routes — state, move, reorder, place, 400/409, nudge"
```
