"""The v1 sub-application, mounted by v0's ``create_app`` under ``/api/v1`` where ``web.v1_enabled``.

A mounted sub-application rather than a router: the parent's ``openapi()``
leaves a mount out, so v0's committed ``frontend/openapi.json`` cannot move; the
sub-application carries its own exception handlers (``Problem``) and its own
OpenAPI document. Starlette never runs a mounted application's lifespan, so the
parent's lifespan enters :func:`v1_lifespan`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import APIRouter, Depends, FastAPI

from personalscraper import __version__
from personalscraper.app.services import AppServices
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.perimeter import NoSessionResolver, PrincipalResolver, v1_perimeter
from personalscraper.http_v1.problem import ProblemOnCrash, install_problem_handlers

#: Where v0's application mounts v1; a v1 route's path is the contract's without its ``/api``.
V1_PREFIX: Final = "/api/v1"


def include_v1_router(app: FastAPI, router: APIRouter) -> None:
    """Include one route module under the perimeter — the only way a v1 route is added.

    Args:
        app: The v1 sub-application.
        router: The route module's router.
    """
    app.include_router(router, dependencies=[Depends(v1_perimeter)])


def create_v1_app(
    config: Config,
    settings: Settings,
    services: AppServices,
    *,
    resolver: PrincipalResolver | None = None,
) -> FastAPI:
    """Build the v1 sub-application: its routes, its ``Problem`` handlers, its own OpenAPI document.

    No interactive documentation and no served OpenAPI route: every route it serves
    goes through the perimeter. Its document is read with ``.openapi()``.

    Args:
        config: The typed configuration.
        settings: The env-var settings.
        services: The application services every route calls.
        resolver: Resolves a request's session to a principal; ``None`` signs nobody
            in (:class:`NoSessionResolver`), so every non-public operation answers 401.

    Returns:
        The sub-application, ready to mount at :data:`V1_PREFIX`.
    """
    app = FastAPI(
        title="TorrentMate",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.config = config
    app.state.settings = settings
    app.state.services = services
    app.state.principal_resolver = resolver if resolver is not None else NoSessionResolver()
    install_problem_handlers(app)
    app.add_middleware(ProblemOnCrash)
    return app


@asynccontextmanager
async def v1_lifespan(v1_app: FastAPI | None) -> AsyncIterator[None]:
    """The v1 sub-application's lifespan, entered by the parent's (Starlette runs no mount's).

    Args:
        v1_app: The mounted sub-application, or ``None`` where v1 is not mounted.

    Yields:
        Nothing; on exit, the sub-application's services are closed.
    """
    if v1_app is None:
        yield
        return
    services: AppServices = v1_app.state.services
    try:
        yield
    finally:
        services.close()
