"""The v1 sub-application, mounted by v0's ``create_app`` under ``/api/v1`` where ``web.v1_enabled``.

A mounted sub-application rather than a router: the parent's ``openapi()``
leaves a mount out, so v0's committed ``frontend/openapi.json`` cannot move; the
sub-application carries its own exception handlers (``Problem``) and its own
OpenAPI document. Starlette never runs a mounted application's lifespan, so the
parent's lifespan enters :func:`v1_lifespan`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Final

from fastapi import APIRouter, Depends, FastAPI

from personalscraper.app.services import AppServices
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.perimeter import ActorResolver, v1_perimeter
from personalscraper.http_v1.problem import ProblemOnCrash, install_problem_handlers
from personalscraper.http_v1.routes import authentication, system
from personalscraper.http_v1.session_cookie import SessionActorResolver

#: Where v0's application mounts v1; a v1 route's path is the contract's without its ``/api``.
V1_PREFIX: Final = "/api/v1"

#: The OpenAPI document's ``info.version``, fixed as v0's is: the package version would
#: move the committed ``frontend/openapi-v1.json`` with every release. ``readVersion``
#: serves the running version.
_DOCUMENT_VERSION: Final = "0.1.0"

#: The schemas FastAPI adds for the 422 it declares on every operation with a body or a parameter.
_VALIDATION_SCHEMAS: Final = ("HTTPValidationError", "ValidationError")


def _without_validation_answers(build: Callable[[], dict[str, Any]]) -> Callable[[], dict[str, Any]]:
    """Wrap an application's ``openapi`` so its document declares no 422.

    FastAPI declares a 422 ``HTTPValidationError`` on every operation with a body or a
    parameter; v1 answers an invalid request 400 ``request.invalid`` (``problem.py``), so
    that 422 would be a status v1 never answers, against the contract (DESIGN C.4).

    Args:
        build: FastAPI's own ``openapi``, which builds the document once and caches it.

    Returns:
        The replacement, removing the 422 answers and their then orphan schemas.
    """

    def openapi() -> dict[str, Any]:
        """Build (or read back) the document, without FastAPI's 422.

        Returns:
            The document.
        """
        document = build()
        for item in document.get("paths", {}).values():
            for operation in item.values():
                if isinstance(operation, dict):
                    operation.get("responses", {}).pop("422", None)
        schemas = document.get("components", {}).get("schemas", {})
        for name in _VALIDATION_SCHEMAS:
            schemas.pop(name, None)
        return document

    return openapi


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
    resolver: ActorResolver | None = None,
) -> FastAPI:
    """Build the v1 sub-application: its routes, its ``Problem`` handlers, its own OpenAPI document.

    No interactive documentation and no served OpenAPI route: every route it serves
    goes through the perimeter. Its document is read with ``.openapi()``.

    Args:
        config: The typed configuration.
        settings: The env-var settings.
        services: The application services every route calls.
        resolver: Resolves a request's session to an actor; ``None`` reads the
            ``tm_v1_session`` cookie through ``services.sessions``
            (:class:`SessionActorResolver`).

    Returns:
        The sub-application, ready to mount at :data:`V1_PREFIX`.
    """
    app = FastAPI(
        title="TorrentMate",
        version=_DOCUMENT_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.config = config
    app.state.settings = settings
    app.state.services = services
    app.state.actor_resolver = resolver if resolver is not None else SessionActorResolver(services.sessions)
    app.openapi = _without_validation_answers(app.openapi)  # type: ignore[method-assign]
    install_problem_handlers(app)
    app.add_middleware(ProblemOnCrash)
    include_v1_router(app, authentication.router)
    include_v1_router(app, system.router)
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
