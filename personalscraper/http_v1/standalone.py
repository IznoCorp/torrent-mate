"""The standalone v1 server: the v1 sub-application in a process of its own, behind a reverse proxy.

The dev interface talks to this process for the operations v1 serves. It mounts
:func:`~personalscraper.http_v1.app.create_v1_app` at :data:`~personalscraper.http_v1.app.V1_PREFIX`
(its routes are prefix-less) and nothing else: no v0 route, no SPA, no indexer migration,
no ``library.db`` access. Starlette runs no mounted application's lifespan, so the parent's
enters :func:`~personalscraper.http_v1.app.v1_lifespan`.

The reverse proxy terminates TLS and keeps ``Host``; its ``X-Forwarded-Proto`` is trusted
from the given proxy addresses only, so the perimeter's cross-origin check compares an
``https`` Origin with the scheme the proxy received, and a forged header from anywhere
else changes nothing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from personalscraper.app.composition import build_app_services
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.http_v1.app import V1_PREFIX, create_v1_app, v1_lifespan
from personalscraper.http_v1.security_headers import SecurityHeaders

#: The reverse proxy runs on the same machine: only loopback is trusted by default.
DEFAULT_TRUSTED_PROXIES: Final = "127.0.0.1"


def build_standalone_v1_app(
    config: Config,
    settings: Settings,
    *,
    trusted_proxies: str = DEFAULT_TRUSTED_PROXIES,
) -> FastAPI:
    """Build the standalone v1 application: v1 mounted at ``/api/v1``, behind the trusted proxy.

    Args:
        config: The typed configuration; its ``data_dir`` and ``PERSONALSCRAPER_ENV`` name
            the ``app`` store the services open on first use.
        settings: The env-var settings.
        trusted_proxies: The addresses whose ``X-Forwarded-*`` headers are believed, in
            uvicorn's ``trusted_hosts`` form (comma-separated).

    Returns:
        The parent application; its lifespan closes the v1 services on exit.
    """
    v1_app = create_v1_app(config, settings, build_app_services(config, settings, event_bus=EventBus()))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Enter the mounted v1 application's lifespan.

        Args:
            _app: The parent application.

        Yields:
            Nothing; on exit, the v1 services are closed.
        """
        async with v1_lifespan(v1_app):
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount(V1_PREFIX, v1_app)
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted_proxies)
    # Outside the mount: a path v1 does not own (the parent's 404) carries them too.
    app.add_middleware(SecurityHeaders)
    return app
