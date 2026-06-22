"""Read-only jobs HTTP surface (bosun §11.4).

Registered on the shared config-API ``app`` via side-effect import. Auth-gated by the existing
``_auth_guard`` middleware (these paths are NOT in ``_AUTH_OPEN_PATHS``). There is NO generic job
creation here — jobs are created only by the privileged endpoints (phases 2-5), so every argv is
server-constructed (DESIGN §11.4).
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kanbanmate.app import ops
from kanbanmate.http.config_api import _kanban_root, app


@app.get("/api/ops")
async def list_ops(type: str | None = None, limit: int = 50) -> JSONResponse:
    """Return job records newest-first (optionally filtered by ``type``)."""
    return JSONResponse(content={"jobs": ops.list_jobs(_kanban_root(), type=type, limit=limit)})


@app.get("/api/ops/{job_id}")
async def get_op(job_id: str) -> JSONResponse:
    """Return one job record; 404 when unknown."""
    try:
        return JSONResponse(content=ops.read_job(_kanban_root(), job_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_id}'") from exc
