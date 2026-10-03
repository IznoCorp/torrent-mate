"""The v1 perimeter: one dependency on every route, closed by default (DESIGN C.5)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated, Any

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import Right
from personalscraper.http_v1.app import include_v1_router
from personalscraper.http_v1.deps import actor
from personalscraper.http_v1.perimeter import v1_perimeter

_ADMIN = Actor(
    account_id="a1",
    name="Alice",
    role_id="admin",
    role_kind=RoleKind.ADMIN,
    role_rights=frozenset(),
    ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
)
_READER = Actor(
    account_id="a2",
    name="Bob",
    role_id="r2",
    role_kind=RoleKind.ORDINARY,
    role_rights=frozenset({Right.LIBRARY_READ}),
    ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
)


class _StubResolver:
    """A resolver that signs every request in as one actor."""

    def __init__(self, signed_in: Actor) -> None:
        """Keep the actor.

        Args:
            signed_in: The actor every request resolves to.
        """
        self.signed_in = signed_in

    def resolve(self, request: Request) -> Actor | None:
        """Answer the actor.

        Args:
            request: The request (unused).

        Returns:
            The kept actor.
        """
        return self.signed_in


def _probe_router() -> APIRouter:
    """Build routes carrying real contract operationIds, and one the table does not name.

    Returns:
        The router.
    """
    router = APIRouter()

    @router.post("/auth/login", operation_id="signIn")
    def _public() -> dict[str, str]:
        """A public operation."""
        return {"ok": "yes"}

    # Its own path: the served ``GET /auth/me`` would otherwise answer first.
    @router.get("/probe/me", operation_id="readAccount")
    def _signed_in(who: Annotated[Actor, Depends(actor)]) -> dict[str, str]:
        """A signed-in operation answering who the perimeter resolved."""
        return {"accountId": who.account_id}

    @router.post("/library/items/delete", operation_id="deleteLibraryItems")
    def _right_gated() -> dict[str, str]:
        """A right-gated write."""
        return {"ok": "yes"}

    @router.get("/unlisted", operation_id="notAContractOperation")
    def _unlisted() -> dict[str, str]:
        """An operation the rights table does not name."""
        return {"ok": "yes"}

    return router


def _client(make_v1_app: Callable[..., FastAPI], signed_in: Actor | None = None) -> TestClient:
    """Build a client on the sub-application, the probe routes under the perimeter.

    Args:
        make_v1_app: The sub-application factory.
        signed_in: The actor every request resolves to; ``None`` keeps the default resolver.

    Returns:
        The test client.
    """
    app = make_v1_app(resolver=_StubResolver(signed_in) if signed_in is not None else None)
    include_v1_router(app, _probe_router())
    return TestClient(app, raise_server_exceptions=False)


def test_operation_absent_from_the_table_is_internal(make_v1_app: Callable[..., FastAPI]) -> None:
    """An operation the table does not name is never an open door: 500 ``internal``."""
    response = _client(make_v1_app, _ADMIN).get("/unlisted")

    assert response.status_code == 500
    assert response.json()["code"] == "internal"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "origin",
    [
        pytest.param("https://evil.example", id="other-host"),
        pytest.param("https://testserver", id="same-host-other-scheme"),
        pytest.param("null", id="opaque-origin"),
    ],
)
def test_cross_origin_write_is_refused(make_v1_app: Callable[..., FastAPI], method: str, origin: str) -> None:
    """An unsafe request from another origin is 403 ``request.cross_origin``, even toward a public operation.

    Args:
        make_v1_app: The sub-application factory.
        method: The unsafe method.
        origin: The ``Origin`` header; the request itself is ``http://testserver``.
    """
    app = make_v1_app()
    router = APIRouter()
    router.add_api_route("/probe", lambda: None, methods=[method], operation_id="signIn")
    include_v1_router(app, router)
    response = TestClient(app, raise_server_exceptions=False).request(method, "/probe", headers={"Origin": origin})

    assert response.status_code == 403
    assert response.json()["code"] == "request.cross_origin"


def test_https_origin_behind_the_proxy_headers_is_accepted(make_v1_app: Callable[..., FastAPI]) -> None:
    """Behind the reverse proxy (``X-Forwarded-Proto: https``) an ``https`` Origin is the request's own.

    The app runs under uvicorn's proxy-headers middleware, which rewrites the scope's
    scheme; it is applied here with every client trusted, the test client not being loopback.
    """
    app = make_v1_app()
    include_v1_router(app, _probe_router())
    proxied = ProxyHeadersMiddleware(app, trusted_hosts="*")

    response = TestClient(proxied, raise_server_exceptions=False).post(
        "/library/items/delete",
        headers={"Origin": "https://testserver", "X-Forwarded-Proto": "https"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


def test_same_origin_write_reaches_the_requirement(make_v1_app: Callable[..., FastAPI]) -> None:
    """A write from the request's own origin passes to the requirement."""
    response = _client(make_v1_app).post("/library/items/delete", headers={"Origin": "http://testserver"})

    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


def test_write_with_no_origin_reaches_the_requirement(make_v1_app: Callable[..., FastAPI]) -> None:
    """A write with no Origin (a non-browser client) passes to the requirement."""
    response = _client(make_v1_app).post("/library/items/delete")

    assert response.status_code == 401


def test_public_operation_answers_with_nobody_signed_in(make_v1_app: Callable[..., FastAPI]) -> None:
    """A public operation answers under the default resolver."""
    response = _client(make_v1_app).post("/auth/login")

    assert response.status_code == 200
    assert response.json() == {"ok": "yes"}


def test_signed_in_operation_is_closed_by_default(make_v1_app: Callable[..., FastAPI]) -> None:
    """Nobody is signed in under the default resolver: 401."""
    response = _client(make_v1_app).get("/probe/me")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


def test_resolved_actor_reaches_the_route(make_v1_app: Callable[..., FastAPI]) -> None:
    """The actor the resolver answers is what ``deps.actor`` hands the route."""
    response = _client(make_v1_app, _READER).get("/probe/me")

    assert response.status_code == 200
    assert response.json() == {"accountId": "a2"}


def test_right_not_held_is_right_missing(make_v1_app: Callable[..., FastAPI]) -> None:
    """A signed-in account lacking the operation's right: 403 ``right.missing``."""
    response = _client(make_v1_app, _READER).post("/library/items/delete")

    assert response.status_code == 403
    assert response.json()["code"] == "right.missing"
    assert response.json()["params"] == {"rights": ["library.delete"]}


def test_right_held_passes(make_v1_app: Callable[..., FastAPI]) -> None:
    """Admin holds every right: the write passes."""
    response = _client(make_v1_app, _ADMIN).post("/library/items/delete")

    assert response.status_code == 200


def _api_dependants(routes: list[Any]) -> Iterator[tuple[str, Dependant]]:
    """Yield ``(path, dependant)`` for every API route, through FastAPI's included-router wrappers.

    Args:
        routes: A router's routes, ``_IncludedRouter`` wrappers or ``APIRoute`` instances.

    Yields:
        The route's path and its resolved dependency tree (an included router's
        dependencies are already part of it).
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route.path, route.dependant
        elif hasattr(route, "effective_candidates"):
            yield from _api_dependants(route.effective_candidates())
        elif hasattr(route, "dependant"):
            yield route.path, route.dependant


def _routes_without_perimeter(app: FastAPI) -> list[str]:
    """The paths of the sub-application's API routes that do not carry ``v1_perimeter``.

    Args:
        app: The v1 sub-application.

    Returns:
        The offending paths, sorted.
    """
    return sorted(
        path
        for path, dependant in _api_dependants(app.router.routes)
        if v1_perimeter not in {dependency.call for dependency in dependant.dependencies}
    )


def test_every_v1_route_carries_the_perimeter(make_v1_app: Callable[..., FastAPI]) -> None:
    """Every route of a sub-application built by ``create_v1_app`` and filled through ``include_v1_router`` has it."""
    app = make_v1_app()
    include_v1_router(app, _probe_router())

    assert list(_api_dependants(app.router.routes))
    assert _routes_without_perimeter(app) == []


@pytest.mark.parametrize("how", ["decorator", "add_api_route"])
def test_a_route_added_outside_include_v1_router_is_caught(make_v1_app: Callable[..., FastAPI], how: str) -> None:
    """Positive control: a route added by a bare ``@app.get`` / ``add_api_route`` is named as perimeter-less."""
    app = make_v1_app()
    include_v1_router(app, _probe_router())

    def _bare() -> dict[str, str]:
        """A route nobody guards."""
        return {"ok": "yes"}

    if how == "decorator":
        app.get("/bare", operation_id="bare")(_bare)
    else:
        app.add_api_route("/bare", _bare, methods=["GET"], operation_id="bare")

    assert _routes_without_perimeter(app) == ["/bare"]
