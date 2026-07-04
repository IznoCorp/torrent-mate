"""SPA static file serving with index.html fallback (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.7.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from personalscraper.logger import get_logger

logger = get_logger(__name__)


def mount_spa(app: FastAPI, static_dir: Path, dev_mode: bool) -> None:
    """Mount the SPA static files and index.html fallback route.

    When the built SPA is present (``static_dir / "index.html"`` exists):
        - Mounts ``/assets`` for hashed Vite output files.
        - Registers a catch-all GET fallback that returns ``index.html`` for
          any path NOT starting with ``/api`` or ``/ws``.

    When the SPA is missing and ``dev_mode`` is True:
        - Registers a catch-all that returns a 503 JSON response
          ``{"detail": "SPA not built (dev_mode)"}``.

    When the SPA is missing and ``dev_mode`` is False:
        - Registers the same 503 fallback. The CLI command (1.3) is responsible
          for refusing boot in this state — this is a safety net.

    Args:
        app: The FastAPI application instance.
        static_dir: Path to the ``static/`` directory containing the built SPA.
        dev_mode: If True, allow serving without a built SPA (503 instead of crash).
    """
    index_html = static_dir / "index.html"
    spa_present = index_html.exists()

    if spa_present:
        # Mount /assets for hashed Vite output (JS, CSS, fonts, images).
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa_assets")

        @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
        async def _spa_fallback(request: Request, full_path: str) -> FileResponse | Response:
            """Catch-all that returns index.html for non-API/non-WS paths."""
            if full_path.startswith("api/") or full_path.startswith("ws/"):
                return Response(status_code=404)
            return FileResponse(str(index_html))

        logger.info("spa_mounted", static_dir=str(static_dir))
    else:
        detail = "SPA not built (dev_mode)" if dev_mode else "SPA not built"

        @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
        async def _spa_missing_fallback(request: Request, full_path: str) -> JSONResponse | Response:
            """Catch-all that returns 503 when the SPA is not built."""
            if full_path.startswith("api/") or full_path.startswith("ws/"):
                return Response(status_code=404)
            return JSONResponse(status_code=503, content={"detail": detail})

        logger.info("spa_not_present", static_dir=str(static_dir), dev_mode=dev_mode)
