"""FastAPI application factory for the TorrentMate web UI (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.1.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.web.auth.routes import router as auth_router
from personalscraper.web.deps import require_session
from personalscraper.web.routes.health import router as health_router
from personalscraper.web.routes.version import router as version_router
from personalscraper.web.static import mount_spa
from personalscraper.web.ws.relay import (
    ConnectionRegistry,
    init_redis_pool,
    read_stream_loop,
)
from personalscraper.web.ws.routes import router as ws_router

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — manages the Redis event relay lifecycle.

    Startup:
        - Creates the :class:`ConnectionRegistry` and stores it on app state.
        - If ``web.enabled``, creates an async Redis pool and launches the
          ``read_stream_loop`` background task.  Redis unavailability at boot
          is **not fatal** — the loop handles transient failures internally.

    Shutdown:
        - Cancels the relay task and awaits graceful termination.
        - Closes the Redis connection pool.
    """
    config = app.state.config
    registry = ConnectionRegistry()
    app.state.ws_registry = registry

    redis_pool = None
    relay_task = None

    if config.web.enabled:
        redis_pool = await init_redis_pool(config.web)
        app.state.redis = redis_pool
        relay_task = asyncio.create_task(read_stream_loop(redis_pool, registry, config.web.stream_key))
        logger.info("relay_started", stream_key=config.web.stream_key)
    else:
        app.state.redis = None
        logger.info("relay_disabled", reason="web.enabled is False")

    try:
        yield
    finally:
        if relay_task is not None:
            relay_task.cancel()
            with suppress(asyncio.CancelledError):
                await relay_task
        if redis_pool is not None:
            await redis_pool.aclose()
            logger.info("relay_stopped")


def create_app(config: Config, settings: Settings) -> FastAPI:
    """Create and configure the FastAPI application.

    Stores ``config`` and ``settings`` on ``app.state`` so that route handlers
    and dependencies can access them via ``request.app.state``.

    Args:
        config: The parsed configuration object (config.json5).
        settings: The application settings (secrets from .env).

    Returns:
        A fully configured FastAPI application instance.
    """
    app = FastAPI(title="TorrentMate", version="0.1.0", lifespan=_lifespan)

    # Store config + settings on app.state for dependency access.
    app.state.config = config
    app.state.settings = settings

    # Set defaults for state that the lifespan would otherwise populate.
    # This ensures TestClient (which may not trigger lifespan) can still
    # access ws_registry and redis — the lifespan will overwrite these
    # when it runs.
    app.state.ws_registry = ConnectionRegistry()
    app.state.redis = None

    # ── Public routes (no authentication required) ────────────────────
    # Health is the liveness probe — must stay public.
    app.include_router(health_router)
    # Auth router: login is public; logout + /me guard themselves
    # individually via Depends(require_session).
    app.include_router(auth_router)

    # ── WebSocket event relay ─────────────────────────────────────────
    # WS auth mirrors the REST guard but closes 4401 instead of HTTP 401.
    # Mounted outside the guarded API block because it has its own
    # handshake-level auth (DESIGN §4.5).
    app.include_router(ws_router)

    # ── Guard perimeter — S2–S7 convention mount point ────────────────
    # Every /api/* router added below inherits Depends(require_session).
    # Health + auth.login are the ONLY exceptions, mounted above before
    # the guard.  All future waves mount their routers here.
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    guarded_api.include_router(version_router)
    from personalscraper.web.routes.pipeline import router as pipeline_router

    guarded_api.include_router(pipeline_router)
    from personalscraper.web.routes.maintenance import router as maintenance_router

    guarded_api.include_router(maintenance_router)
    app.include_router(guarded_api)

    # Mount the built SPA static files with index.html fallback.
    static_dir = Path(__file__).resolve().parent / "static"
    mount_spa(app, static_dir, config.web.dev_mode)

    logger.info("app_created", dev_mode=config.web.dev_mode)

    return app
