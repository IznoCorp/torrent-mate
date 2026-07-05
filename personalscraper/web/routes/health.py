"""Health-check route for the TorrentMate web UI (tm-shell feature).

**Unauthenticated** — phase 2 adds the auth guard perimeter around everything
except this health endpoint (DESIGN §4.4: health stays public).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from personalscraper.logger import get_logger

router = APIRouter(prefix="/api", tags=["health"])
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    """Response model for the health-check endpoint.

    Attributes:
        status: Always ``"ok"`` if the handler is reachable.
        redis: ``True`` if the configured Redis instance responds to PING.
        db: ``True`` if ``library.db`` exists at the configured data_dir path.
    """

    status: str
    redis: bool
    db: bool


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Health-check endpoint — reachable, Redis, and DB presence.

    Both probes are **fail-soft**: they never raise and never block boot.
    A down Redis or missing DB returns ``false`` for that key, not a 5xx.

    Returns:
        A dict with:
        - **status**: Always ``"ok"`` if this handler is reachable.
        - **redis**: ``True`` if the configured Redis instance responds to PING.
        - **db**: ``True`` if ``library.db`` exists at the configured data_dir path.
    """
    config = request.app.state.config
    web_config = config.web

    # Redis probe — short-lived sync connection, fail-soft.
    redis_ok = False
    try:
        import redis

        r = redis.Redis.from_url(
            web_config.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        redis_ok = r.ping()
    except Exception:
        logger.warning("redis_health_check_failed", redis_url=web_config.redis_url)

    # DB probe — simple existence check, fail-soft.
    db_ok = False
    try:
        db_ok = (config.paths.data_dir / "library.db").exists()
    except Exception:
        logger.warning("db_health_check_failed", data_dir=str(config.paths.data_dir))

    return HealthResponse(status="ok", redis=redis_ok, db=db_ok)
