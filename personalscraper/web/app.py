"""FastAPI application factory for the TorrentMate web UI (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.1.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing, suppress
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, FastAPI

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.indexer import migrations as _indexer_migrations
from personalscraper.indexer.db import apply_migrations
from personalscraper.logger import get_logger
from personalscraper.web.auth.routes import router as auth_router
from personalscraper.web.deps import is_staging_role, require_session
from personalscraper.web.registry_projection import RegistryHealthProjection
from personalscraper.web.routes.health import router as health_router
from personalscraper.web.routes.version import router as version_router
from personalscraper.web.static import mount_spa
from personalscraper.web.ws.relay import (
    ConnectionRegistry,
    _entry_to_message,
    init_redis_pool,
    read_stream_loop,
)
from personalscraper.web.ws.routes import router as ws_router

logger = get_logger(__name__)


def _apply_pending_indexer_migrations(config: Config) -> None:
    """Apply pending indexer schema migrations on web startup (prod only).

    The autodeploy poller ships new code + restarts but does **not** run
    indexer migrations, and the web app opens the DB read-only during
    requests — so a web wave that adds a migration serves ``500`` (``no such
    table``) on its new endpoints until an indexer scan next opens the DB
    (hit on S5: migration 013 / ``scrape_decision``).  Applying pending
    migrations here closes that gap on every prod boot.

    Skipped entirely on the **staging** clone: prod and staging share the same
    ``library.db`` (ENV-SEP), so the staging process must never write to the
    prod-owned DB.  Skipped when the DB file does not yet exist (the indexer
    creates + migrates it on first use).  Fail-soft: a migration error is
    logged but never aborts boot — health stays up and only the
    migration-dependent endpoints degrade, exactly as before this guard.

    Args:
        config: The parsed configuration (provides ``indexer.db_path``).
    """
    if is_staging_role():
        logger.info("web_boot_migrate_skipped", reason="staging role (read-only)")
        return
    db_path = config.indexer.db_path
    if db_path is None or not db_path.exists():
        logger.info("web_boot_migrate_skipped", reason="indexer db absent")
        return
    migrations_dir = Path(_indexer_migrations.__file__).resolve().parent
    try:
        with closing(sqlite3.connect(str(db_path), timeout=30)) as conn:
            apply_pragmas(conn)
            apply_migrations(conn, migrations_dir)
            conn.commit()
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        logger.info("web_boot_migrate_applied", db_version=version)
    except Exception:  # noqa: BLE001 — fail-soft: never abort boot on a migration error
        logger.error("web_boot_migrate_failed", db_path=str(db_path), exc_info=True)


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

    # Ensure the shared indexer DB is on the latest schema before serving —
    # the deploy path does not migrate, and web-wave migrations otherwise 500
    # until an indexer scan runs (prod-only; staging is read-only).
    _apply_pending_indexer_migrations(config)

    registry = ConnectionRegistry()
    app.state.ws_registry = registry

    redis_pool = None
    relay_task = None

    if config.web.enabled:
        redis_pool = await init_redis_pool(config.web)
        app.state.redis = redis_pool
        projection = app.state.registry_projection

        # Boot warm-up FIRST — replay the Redis stream tail through the
        # projection BEFORE starting the live relay, so the first REST hit
        # reflects history (S6 reg-health §3.4) and no replayed event can race
        # a live one (the reducer's event-time ordering guard is the primary
        # defence; this ordering makes the window vanish entirely).  Fail-soft:
        # Redis down or empty stream → projection stays at its neutral baseline.
        try:
            # redis-py's return type is loosely typed (bytes|str|None); cast to
            # the decoded shape the pool actually yields (decode_responses=True),
            # mirroring read_stream_loop's cast of xread.
            tail_entries = (
                cast(
                    "list[tuple[str, dict[str, str]]]",
                    await redis_pool.xrevrange(
                        config.web.stream_key,
                        max="+",
                        min="-",
                        count=1000,
                    ),
                )
                or []
            )
            # xrevrange returns newest-first; reverse for chronological order.
            for entry_id, fields in reversed(tail_entries):
                try:
                    msg = _entry_to_message(entry_id, fields)
                except (KeyError, ValueError, TypeError):
                    continue
                try:
                    projection.apply(msg["type"], msg["data"])
                except Exception:  # noqa: BLE001 — per-entry fail-soft
                    logger.warning(
                        "projection_warmup_entry_failed",
                        entry_id=entry_id,
                        event_type=msg.get("type"),
                    )
            logger.info(
                "projection_warmed_up",
                entries=len(tail_entries),
                providers=len(projection.snapshot()),
            )
        except Exception:  # noqa: BLE001 — fail-soft: Redis down → skip warm-up
            logger.warning("projection_warmup_failed", reason="redis unavailable")

        # Start the live relay AFTER the warm-up so history is applied first.
        relay_task = asyncio.create_task(
            read_stream_loop(redis_pool, registry, config.web.stream_key, projection=projection),
        )
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
    app.state.registry_projection = RegistryHealthProjection()

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
    from personalscraper.web.routes.config import capture_boot_hashes
    from personalscraper.web.routes.config import router as config_router

    guarded_api.include_router(config_router)
    from personalscraper.web.routes.decisions import router as decisions_router

    guarded_api.include_router(decisions_router)
    from personalscraper.web.routes.registry import router as registry_router

    guarded_api.include_router(registry_router)
    from personalscraper.web.routes.acquisition import router as acquisition_router

    guarded_api.include_router(acquisition_router)
    from personalscraper.web.routes.acquisition_triggers import router as acquisition_triggers_router

    guarded_api.include_router(acquisition_triggers_router)
    from personalscraper.web.routes.staging import router as staging_router

    guarded_api.include_router(staging_router)
    app.include_router(guarded_api)

    # Capture config file hashes at startup so /status detects
    # post-boot modifications without a lazy first-access race.
    capture_boot_hashes(app)

    # Mount the built SPA static files with index.html fallback.
    static_dir = Path(__file__).resolve().parent / "static"
    mount_spa(app, static_dir, config.web.dev_mode)

    logger.info("app_created", dev_mode=config.web.dev_mode)

    return app
