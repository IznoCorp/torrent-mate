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

# Max accepted request body (1 MiB), mirroring the webhook receiver (``http/serve.py`` MAX_BODY_BYTES).
# A larger / absent Content-Length is rejected up front (413/411) so a single request can neither OOM
# the process nor pin a connection while a slow client streams an unbounded body. Connection-level
# slow-loris is additionally bounded by fronting with a reverse proxy in production (DESIGN §11).
_MAX_BODY_BYTES = 1 * 1024 * 1024

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
        root: The kanban runtime root.  When ``None`` (the endpoint call form),
            falls back to ``app.state.kanban_root`` (set by ``kanban config
            serve --root``), then to ``~/.kanban/``.

    Returns:
        A :class:`~kanbanmate.app.config_service.ConfigService` with the resolved
        config file paths.

    Raises:
        HTTPException: 503 when no project entry exists in the registry.
    """
    # The endpoints call _get_service() with no argument, so the CLI --root must
    # reach here via app.state (set in cli/config.py:serve before uvicorn.run);
    # otherwise a passed --root would be silently dropped and every request would
    # read the default ~/.kanban/ root.
    kanban_root = root or getattr(app.state, "kanban_root", None) or _DEFAULT_ROOT
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
    body = await _read_json_object(request)
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
def get_render() -> JSONResponse:
    """Preview the rendered YAML strings for the current draft (no write).

    Returns:
        ``{"transitions": "<yaml string>", "columns": "<yaml string>"}``.

    Raises:
        HTTPException: 500 on load/render error (consistent with GET /api/config).
    """
    svc = _get_service()
    try:
        draft = svc.load()
        rendered = svc.render(draft)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse(content={"transitions": rendered.transitions, "columns": rendered.columns})


@app.post("/api/config/resolve")
async def post_resolve(request: fastapi.Request) -> JSONResponse:
    """Simulate whitelist resolution for a (from_col, to_col) move.

    Request body: ``{"draft": {...}, "from_col": "Backlog", "to_col": "Brainstorming"}``.

    Returns:
        A ``ResolvedTransition`` JSON object.

    Raises:
        HTTPException: 422 when the posted draft is structurally invalid or the
            loader rejects it (resolve renders + loads the draft).
    """
    svc = _get_service()
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
