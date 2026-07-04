"""FastAPI application factory for the TorrentMate web UI (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.1.
"""

from __future__ import annotations

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

logger = get_logger(__name__)


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
    app = FastAPI(title="TorrentMate", version="0.1.0")

    # Store config + settings on app.state for dependency access.
    app.state.config = config
    app.state.settings = settings

    # ── Public routes (no authentication required) ────────────────────
    # Health is the liveness probe — must stay public.
    app.include_router(health_router)
    # Auth router: login is public; logout + /me guard themselves
    # individually via Depends(require_session).
    app.include_router(auth_router)

    # ── Guard perimeter — S2–S7 convention mount point ────────────────
    # Every /api/* router added below inherits Depends(require_session).
    # Health + auth.login are the ONLY exceptions, mounted above before
    # the guard.  All future waves mount their routers here.
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    guarded_api.include_router(version_router)
    app.include_router(guarded_api)

    # Mount the built SPA static files with index.html fallback.
    static_dir = Path(__file__).resolve().parent / "static"
    mount_spa(app, static_dir, config.web.dev_mode)

    logger.info("app_created", dev_mode=config.web.dev_mode)

    return app
