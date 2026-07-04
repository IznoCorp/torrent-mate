"""FastAPI application factory for the TorrentMate web UI (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.1.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.logger import get_logger
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

    # Health and version routes are unauthenticated in S1. Phase 2 adds the
    # auth guard perimeter around everything except /api/health.
    app.include_router(health_router)
    app.include_router(version_router)

    # Mount the built SPA static files with index.html fallback.
    static_dir = Path(__file__).resolve().parent / "static"
    mount_spa(app, static_dir, config.web.dev_mode)

    logger.info("app_created", dev_mode=config.web.dev_mode)

    return app
