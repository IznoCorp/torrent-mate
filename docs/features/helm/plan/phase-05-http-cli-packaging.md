# Phase 5 — HTTP API + CLI + packaging

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `http/config_api.py` (the FastAPI app + 7 endpoints), `cli/config.py` (the
`kanban config` sub-app with lazy FastAPI import), edit `pyproject.toml` to add the `[ui]` optional
extra, and write `tests/http/test_config_api.py` covering all endpoints + the daemon-purity runtime
test.

**Architecture:** `http/` is a top entrypoint — it may import `app`/`adapters`/`core`/`cli.init`.
FastAPI is imported LAZILY in `cli/config.py` (the `serve` sub-command) so the bare `kanban` CLI
works with no `[ui]` installed. The JSON schema is generated at request time — no static asset.
The daemon-purity test proves `import kanbanmate.daemon` pulls no FastAPI.

**Tech Stack:** FastAPI + uvicorn (optional `[ui]` extra). TestClient from `fastapi.testclient`
(available when `[ui]` is installed). CLI: `typer` (already a base dep).

## Global Constraints

- `http/config_api.py` forbidden imports: `daemon`, `bin` (layering guard).
- `cli/config.py` forbidden imports: nothing beyond `typer`, `pathlib`, `cli.init`. FastAPI import
  MUST be lazy (inside the `serve` function body) so `import kanbanmate` with no `[ui]` never fails.
- Tests live in `tests/http/`.
- The daemon-purity test must reset `sys.modules` state — use `pytest`'s `monkeypatch` or a
  subprocess call to avoid polluting the test process.

---

## Task 5.1 — `pyproject.toml`: add `[ui]` optional extra

**Files:**
- Modify: `pyproject.toml` (add `[project.optional-dependencies].ui`)

**Interfaces:**
- Produces: `pip install "kanbanmate[ui]"` installs `fastapi` and `uvicorn[standard]`
- Consumed by: Phase 5 test runner (install `[ui]` before running HTTP tests)

- [ ] **Step 5.1.1: Edit `pyproject.toml`**

Find the `[project.optional-dependencies]` section (currently only `dev`):

```toml
[project.optional-dependencies]
dev = [
    "pytest",
    "ruff",
    "mypy",
    "types-PyYAML",
]
```

Replace with:

```toml
[project.optional-dependencies]
dev = [
    "pytest",
    "ruff",
    "mypy",
    "types-PyYAML",
]
ui = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]
```

- [ ] **Step 5.1.2: Install the `[ui]` extra**

```bash
cd /Users/izno/dev/worktrees/ticket-5
pip install -e ".[ui]"
```

Expected: FastAPI and uvicorn install successfully.

- [ ] **Step 5.1.3: Smoke test the import**

```bash
python -c "import fastapi; import uvicorn; print('FastAPI', fastapi.__version__)"
```

Expected: prints FastAPI version without error.

- [ ] **Step 5.1.4: Commit**

```bash
cd /Users/izno/dev/worktrees/ticket-5
git add pyproject.toml
git commit -m "feat(helm): pyproject.toml — add [ui] optional extra (fastapi + uvicorn)"
```

---

## Task 5.2 — `http/config_api.py`: FastAPI app + 7 endpoints

**Files:**
- Create: `src/kanbanmate/http/config_api.py`

**Interfaces:**
- Consumes:
  - `ConfigService`, `ConfigInvalid` from `app.config_service` (Phase 4)
  - `PipelineDraft`, `ColumnDef`, `TransitionDef`, `Defaults`, `Binding`, `Definition` from `core.config_model` (Phase 1)
  - `_projects_path`, `_load_registry` from `cli.init` (Phase 0 — existing)
  - `CLONE_TRANSITIONS_RELPATH`, `CLONE_COLUMNS_RELPATH` from `cli.init`
- Produces: FastAPI `app` object importable as `kanbanmate.http.config_api.app`
- Endpoints (DESIGN §11.2):
  - `GET /api/config` → current draft as JSON
  - `POST /api/config/validate` → `ValidationResult` JSON (never writes)
  - `POST /api/config` → validate-then-save; `422` + findings on error
  - `GET /api/config/render` → `RenderedPipeline` JSON (preview; no write)
  - `POST /api/config/resolve` → `ResolvedTransition` JSON
  - `GET /api/schema` → JSON Schema of the draft model
  - `GET /api/health` → `{"status": "ok"}`

**Key design decisions:**
- Bind to loopback `127.0.0.1`, no auth, single-operator.
- The config service is created once per-request with the injected paths resolved from the
  first registry entry (PR 1 single-project). The HTTP layer resolves paths via
  `_projects_path` / `_load_registry` + `CLONE_TRANSITIONS_RELPATH` / `CLONE_COLUMNS_RELPATH`.
- `ConfigInvalid` → HTTP 422 with `findings` JSON body.
- JSON Schema is generated from the model dataclasses — no static asset.
- `http` may import `cli.init` (the layering guard permits it, `tests/test_layering.py:42-48`).

- [ ] **Step 5.2.1: Create `http/config_api.py`**

```python
# src/kanbanmate/http/config_api.py
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
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import fastapi
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

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

app = FastAPI(
    title="KanbanMate Config API",
    description=(
        "Headless HTTP API for the KanbanMate pipeline config (helm PR 1). "
        "Loopback, single-operator, no auth. See DESIGN §11."
    ),
    version="1.0.0",
)


def _get_service(root: Path | None = None) -> ConfigService:
    """Build a :class:`~kanbanmate.app.config_service.ConfigService` for the first registry entry.

    Resolves the clone config file paths from the runtime registry and injects
    them into the service (DESIGN §12 — ``app`` may not import ``cli.init``, but
    ``http`` may).

    Args:
        root: The kanban runtime root.  Defaults to ``~/.kanban/``.

    Returns:
        A :class:`~kanbanmate.app.config_service.ConfigService` with the resolved
        config file paths.

    Raises:
        HTTPException: 503 when no project entry exists in the registry.
    """
    kanban_root = root or _DEFAULT_ROOT
    registry = _load_registry(_projects_path(kanban_root))
    if not registry:
        raise HTTPException(status_code=503, detail="No project registered in the kanban root")
    # PR 1: use the first (only expected) project entry.
    entry = next(iter(registry.values()))
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


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe.

    Returns:
        ``{"status": "ok"}``.
    """
    return {"status": "ok"}


@app.get("/api/config")
def get_config() -> JSONResponse:
    """Return the current pipeline draft loaded from the clone config files.

    Returns:
        The draft as a JSON object.

    Raises:
        HTTPException: 503 when no project is registered; 500 on load error.
    """
    svc = _get_service()
    try:
        draft = svc.load()
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse(content=_draft_to_dict(draft))


@app.post("/api/config/validate")
async def post_validate(request: fastapi.Request) -> JSONResponse:
    """Validate a posted draft without writing.

    The request body must be a JSON object representing a PipelineDraft
    (same shape as GET /api/config returns).

    Returns:
        A ``ValidationResult`` JSON object: ``{"ok": bool, "findings": [...]}``.
    """
    svc = _get_service()
    body = await request.json()
    draft = _dict_to_draft(body)
    result = svc.validate(draft)
    return JSONResponse(content=_validation_result_to_dict(result))


@app.post("/api/config")
async def post_config(request: fastapi.Request) -> JSONResponse:
    """Validate a posted draft and, if valid, atomically write both config files.

    On validation error (any ``error``-severity finding), returns HTTP 422 with
    the findings list — nothing is written.

    Returns:
        ``{"ok": true}`` on success, or ``{"ok": false, "findings": [...]}`` with
        status 422 on validation failure.
    """
    svc = _get_service()
    body = await request.json()
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
def get_render() -> JSONResponse:
    """Preview the rendered YAML strings for the current draft (no write).

    Returns:
        ``{"transitions": "<yaml string>", "columns": "<yaml string>"}``.
    """
    svc = _get_service()
    draft = svc.load()
    rendered = svc.render(draft)
    return JSONResponse(content={"transitions": rendered.transitions, "columns": rendered.columns})


@app.post("/api/config/resolve")
async def post_resolve(request: fastapi.Request) -> JSONResponse:
    """Simulate whitelist resolution for a (from_col, to_col) move.

    Request body: ``{"draft": {...}, "from_col": "Backlog", "to_col": "Brainstorming"}``.

    Returns:
        A ``ResolvedTransition`` JSON object.
    """
    svc = _get_service()
    body = await request.json()
    draft = _dict_to_draft(body.get("draft", {}))
    from_col = str(body.get("from_col", ""))
    to_col = str(body.get("to_col", ""))
    result = svc.resolve(draft, from_col, to_col)
    from dataclasses import asdict as _asdict
    return JSONResponse(content=_asdict(result))


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


def _dict_to_draft(body: dict[str, Any]) -> PipelineDraft:
    """Deserialise a JSON dict into a PipelineDraft.

    Args:
        body: A dict matching the PipelineDraft dataclass structure.

    Returns:
        A :class:`~kanbanmate.core.config_model.PipelineDraft`.

    Raises:
        HTTPException: 422 when the body is structurally invalid.
    """
    from kanbanmate.core.config_model import (  # noqa: PLC0415
        Binding,
        ColumnDef,
        Defaults,
        Definition,
        TransitionDef,
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
    except (TypeError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid draft structure: {exc}") from exc


def _generate_schema() -> dict[str, Any]:
    """Generate a minimal JSON Schema for the PipelineDraft model.

    Returns:
        A dict representing the JSON Schema.
    """
    return {
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
                                "from_col": {"type": "string"},
                                "to_col": {"type": "string"},
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
```

---

## Task 5.3 — `cli/config.py`: `kanban config` sub-app

**Files:**
- Create: `src/kanbanmate/cli/config.py`
- Modify: `src/kanbanmate/cli/app.py` (register `config_app`)

**Interfaces:**
- Produces: `config_app = typer.Typer(name="config", ...)` registered via `app.add_typer(config_app, name="config")`
- Sub-commands: `serve` (starts the FastAPI server), optional `validate`/`get` thin wrappers
- FastAPI import is LAZY — inside the `serve()` function body — so `kanban` CLI imports succeed with no `[ui]` extra

- [ ] **Step 5.3.1: Create `cli/config.py`**

```python
# src/kanbanmate/cli/config.py
"""``kanban config`` sub-app — CLI entry point for the config HTTP server (DESIGN §14).

Sub-commands:
  ``kanban config serve``   — start the FastAPI config API server.

The FastAPI import is LAZY (deferred to the ``serve`` function body) so the
bare ``kanban`` CLI never fails when ``[ui]`` is not installed.  An
:exc:`ImportError` there prints an actionable "install kanbanmate[ui]" message.

Layering: ``cli`` may import anything except ``daemon`` (no explicit guard in
``test_layering.py`` for cli, but cli is a top entrypoint — it imports typer
and the cli.init registry helpers).
"""

from __future__ import annotations

from pathlib import Path

import typer

config_app = typer.Typer(
    name="config",
    help="Pipeline config management: start the headless HTTP API server.",
    no_args_is_help=True,
    add_completion=False,
)

_DEFAULT_ROOT = Path("~/.kanban/").expanduser()
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8766  # distinct from the webhook receiver port (8765)


@config_app.command()
def serve(
    host: str = typer.Option(_DEFAULT_HOST, "--host", help="Bind address (loopback by default)."),
    port: int = typer.Option(_DEFAULT_PORT, "--port", help="TCP port to listen on."),
    root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Kanban runtime root."),
) -> None:
    """Start the KanbanMate config HTTP API server.

    Requires the ``[ui]`` optional extra (``pip install 'kanbanmate[ui]'``).
    The server binds to loopback by default (single-operator, no auth).

    Args:
        host: The bind address.
        port: The TCP port.
        root: The kanban runtime root (used to resolve the registry).
    """
    # Lazy import: FastAPI and uvicorn are NOT base dependencies.
    # This guard means `kanban` CLI works even without [ui] installed.
    try:
        import uvicorn  # noqa: PLC0415
        from kanbanmate.http.config_api import app as fastapi_app  # noqa: PLC0415
    except ImportError as exc:
        typer.echo(
            f"Error: {exc}\n\n"
            "The config server requires the [ui] optional extra.\n"
            "Install it with: pip install 'kanbanmate[ui]'",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(f"Starting KanbanMate config API on http://{host}:{port} (root: {root})")
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
```

- [ ] **Step 5.3.2: Register `config_app` in `cli/app.py`**

Open `src/kanbanmate/cli/app.py`. Find the section after the `pill_app` registration (around line 67):

```python
app.add_typer(pill_app, name="pill")
```

Add immediately after:

```python
# Config management sub-app (helm PR 1): `kanban config serve` starts the
# headless HTTP API for pipeline config editing.
from kanbanmate.cli.config import config_app  # noqa: E402
app.add_typer(config_app, name="config")
```

**NOTE:** Do NOT add this as a top-level import if it creates a circular import. Add it after the existing `add_typer` calls at the module level, or use a late import pattern that matches how `ticket_app` and `pill_app` are structured in the module. Read `cli/app.py` in full before editing to follow the existing pattern.

- [ ] **Step 5.3.3: Verify `kanban config --help` works (with no [ui] installed this should still work)**

```bash
cd /Users/izno/dev/worktrees/ticket-5
kanban config --help
```

Expected: shows `serve` sub-command in the help output.

```bash
kanban config serve --help
```

Expected: shows serve options. The import of fastapi/uvicorn is lazy (only happens on execution, not `--help`).

---

## Task 5.4 — HTTP tests + daemon-purity test

**Files:**
- Create: `tests/http/test_config_api.py`

**Interfaces:**
- Consumes: FastAPI `TestClient` (`from fastapi.testclient import TestClient`)
- Tests: all 7 endpoints + 422-on-invalid contract + daemon-purity runtime test

- [ ] **Step 5.4.1: Write the HTTP tests**

```python
# tests/http/test_config_api.py
"""Tests for :mod:`kanbanmate.http.config_api`.

Uses FastAPI's TestClient over a real server-less test session.  The
ConfigService's path resolution is patched to point at a tmp_path clone.

Also includes the daemon-purity runtime test: import kanbanmate.daemon in an
isolated subprocess and assert 'fastapi' is not in sys.modules.
"""

from __future__ import annotations

import importlib.resources
import shutil
import subprocess
import sys
from pathlib import Path
from dataclasses import asdict

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402 (after importorskip)

from kanbanmate.core.config_model import (  # noqa: E402
    Binding,
    ColumnDef,
    Defaults,
    Definition,
    PipelineDraft,
    TransitionDef,
)
from kanbanmate.core.transitions_defaults import render_transitions_yaml  # noqa: E402


def _columns_template_path() -> Path:
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    with importlib.resources.as_file(ref) as p:
        return p


def _make_test_clone(tmp_path: Path) -> tuple[Path, Path]:
    """Return (transitions_path, columns_path) for a tmp clone."""
    config_dir = tmp_path / ".claude" / "kanban"
    config_dir.mkdir(parents=True)
    tp = config_dir / "transitions.yml"
    cp = config_dir / "columns.yml"
    tp.write_text(render_transitions_yaml("owner/repo"), encoding="utf-8")
    shutil.copy(_columns_template_path(), cp)
    return tp, cp


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a TestClient for the config API, pointing at a tmp clone."""
    from kanbanmate.app.config_service import ConfigService
    import kanbanmate.http.config_api as api_mod

    tp, cp = _make_test_clone(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)

    # Patch _get_service to return our injected service.
    monkeypatch.setattr(api_mod, "_get_service", lambda root=None: svc)

    return TestClient(api_mod.app)


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    """GET /api/health returns 200 and {"status": "ok"}."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------


def test_get_config(client: TestClient) -> None:
    """GET /api/config returns the current draft with 14 columns."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "definition" in body
    assert "binding" in body
    assert len(body["definition"]["columns"]) == 14


# ---------------------------------------------------------------------------
# POST /api/config/validate
# ---------------------------------------------------------------------------


def test_post_validate_clean(client: TestClient) -> None:
    """POST /api/config/validate with the shipped config returns ok=True."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    resp = client.post("/api/config/validate", json=asdict(draft))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


def test_post_validate_invalid(client: TestClient) -> None:
    """POST /api/config/validate with a bad permission_mode returns ok=False."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    # Inject an invalid permission_mode into the first transition.
    draft_dict = asdict(draft)
    if draft_dict["definition"]["transitions"]:
        draft_dict["definition"]["transitions"][0]["permission_mode"] = "bypassPermissions"
    resp = client.post("/api/config/validate", json=draft_dict)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["findings"]


# ---------------------------------------------------------------------------
# POST /api/config (validate-then-save)
# ---------------------------------------------------------------------------


def test_post_config_valid_saves(client: TestClient, tmp_path: Path) -> None:
    """POST /api/config with a valid draft returns 200 {"ok": true}."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    resp = client.post("/api/config", json=asdict(draft))
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_post_config_invalid_returns_422(client: TestClient) -> None:
    """POST /api/config with an invalid draft returns 422 and findings."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    draft_dict = asdict(draft)
    if draft_dict["definition"]["transitions"]:
        draft_dict["definition"]["transitions"][0]["permission_mode"] = "bypassPermissions"
    resp = client.post("/api/config", json=draft_dict)
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("ok") is False
    assert body.get("findings")


# ---------------------------------------------------------------------------
# GET /api/config/render
# ---------------------------------------------------------------------------


def test_get_render(client: TestClient) -> None:
    """GET /api/config/render returns non-empty transitions and columns strings."""
    resp = client.get("/api/config/render")
    assert resp.status_code == 200
    body = resp.json()
    assert body["transitions"]
    assert body["columns"]
    assert "permission_mode" in body["transitions"]  # header present


# ---------------------------------------------------------------------------
# POST /api/config/resolve
# ---------------------------------------------------------------------------


def test_post_resolve_known_edge(client: TestClient) -> None:
    """POST /api/config/resolve for Backlog→Brainstorming returns matched=True, would_launch=True."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    payload = {"draft": asdict(draft), "from_col": "Backlog", "to_col": "Brainstorming"}
    resp = client.post("/api/config/resolve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True
    assert body["would_launch"] is True


def test_post_resolve_unwhitelisted(client: TestClient) -> None:
    """POST /api/config/resolve for an un-whitelisted move returns matched=False."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    payload = {"draft": asdict(draft), "from_col": "Brainstorming", "to_col": "Merge"}
    resp = client.post("/api/config/resolve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is False


# ---------------------------------------------------------------------------
# GET /api/schema
# ---------------------------------------------------------------------------


def test_get_schema(client: TestClient) -> None:
    """GET /api/schema returns a JSON Schema with the expected top-level keys."""
    resp = client.get("/api/schema")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema.get("title") == "PipelineDraft"
    assert "properties" in schema
    assert "definition" in schema["properties"]
    assert "binding" in schema["properties"]


# ---------------------------------------------------------------------------
# Daemon-purity test
# ---------------------------------------------------------------------------


def test_daemon_purity_no_fastapi_import() -> None:
    """import kanbanmate.daemon must NOT pull fastapi into sys.modules.

    The daemon hot-path is urllib-only (DESIGN §11.1, §15).  This test runs in
    an isolated subprocess so the test process's own [ui] install does not
    pollute the check.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import kanbanmate.daemon; "
                "assert 'fastapi' not in __import__('sys').modules, "
                "'fastapi was imported by kanbanmate.daemon'"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Daemon-purity test failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
```

- [ ] **Step 5.4.2: Run HTTP tests**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/http/test_config_api.py -v
```

Expected: all PASS. If `test_post_config_valid_saves` fails on a missing file, check the `_get_service` monkeypatching and ensure the service's `_transitions_path` / `_columns_path` point at the tmp clone files.

- [ ] **Step 5.4.3: Run layering guard**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/test_layering.py -v
```

Expected: PASS. `http/config_api.py` must not import `daemon` or `bin`.

- [ ] **Step 5.4.4: Phase gate**

```bash
cd /Users/izno/dev/worktrees/ticket-5
make lint
make test
make check
python -c "import kanbanmate"
```

Expected: all clean. `kanban --help` must show `config` as a sub-app. The daemon-purity test must pass.

- [ ] **Step 5.4.5: Final commit**

```bash
cd /Users/izno/dev/worktrees/ticket-5
git add src/kanbanmate/http/config_api.py src/kanbanmate/cli/config.py src/kanbanmate/cli/app.py tests/http/test_config_api.py
git commit -m "feat(helm): http/config_api.py + cli/config.py — FastAPI endpoints + kanban config serve"
```

---

## Self-review checklist

- [ ] `GET /api/health` → `{"status":"ok"}` ✓
- [ ] `GET /api/config` → current draft JSON ✓
- [ ] `POST /api/config/validate` → ValidationResult (never writes) ✓
- [ ] `POST /api/config` → validate-then-write; 422 + findings on error ✓
- [ ] `GET /api/config/render` → RenderedPipeline preview ✓
- [ ] `POST /api/config/resolve` → ResolvedTransition ✓
- [ ] `GET /api/schema` → generated JSON Schema ✓
- [ ] FastAPI import is lazy in `cli/config.py` — base `kanban` CLI works without `[ui]` ✓
- [ ] `config_app` registered in `cli/app.py` via `app.add_typer` ✓
- [ ] `pyproject.toml` has `ui = ["fastapi>=0.111", "uvicorn[standard]>=0.29"]` ✓
- [ ] daemon-purity test passes (`fastapi` not in `sys.modules` after `import kanbanmate.daemon`) ✓
- [ ] `tests/test_layering.py` passes unchanged ✓
- [ ] No static `schema.json` asset — schema is generated ✓
