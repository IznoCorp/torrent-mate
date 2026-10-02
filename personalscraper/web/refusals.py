"""v0's answer to an application-layer refusal.

The application layer raises :class:`~personalscraper.app.errors.AppRefusal`
subclasses and knows no HTTP framework; v0 answers them as ``{"detail": ...}``
with the refusal's status, byte-for-byte what Starlette's ``HTTPException``
handler answered for the raises they replaced.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from personalscraper.app.errors import AppRefusal


def install_refusal_handler(app: FastAPI) -> None:
    """Register the one handler that answers an :class:`AppRefusal` on *app*.

    Args:
        app: The FastAPI application (``create_app``'s, or a test harness's).
    """

    @app.exception_handler(AppRefusal)
    async def _app_refusal(_: Request, exc: AppRefusal) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)
