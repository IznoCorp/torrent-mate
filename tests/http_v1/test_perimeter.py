"""The v1 perimeter: one dependency on every route, closed by default (DESIGN C.5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.testclient import TestClient

from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.principal import Principal, RoleKind
from personalscraper.app.accounts.rights import Right
from personalscraper.http_v1.app import include_v1_router
from personalscraper.http_v1.deps import principal

_ADMIN = Principal(
    account_id="a1",
    name="Alice",
    role_id="admin",
    role_kind=RoleKind.ADMIN,
    role_rights=frozenset(),
    ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
)
_READER = Principal(
    account_id="a2",
    name="Bob",
    role_id="r2",
    role_kind=RoleKind.ORDINARY,
    role_rights=frozenset({Right.LIBRARY_READ}),
    ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
)


class _StubResolver:
    """A resolver that signs every request in as one principal."""

    def __init__(self, signed_in: Principal) -> None:
        """Keep the principal.

        Args:
            signed_in: The principal every request resolves to.
        """
        self.signed_in = signed_in

    def resolve(self, request: Request) -> Principal | None:
        """Answer the principal.

        Args:
            request: The request (unused).

        Returns:
            The kept principal.
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

    @router.get("/auth/me", operation_id="readAccount")
    def _signed_in(who: Annotated[Principal, Depends(principal)]) -> dict[str, str]:
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


def _client(make_v1_app: Callable[..., FastAPI], signed_in: Principal | None = None) -> TestClient:
    """Build a client on the sub-application, the probe routes under the perimeter.

    Args:
        make_v1_app: The sub-application factory.
        signed_in: The principal every request resolves to; ``None`` keeps the default resolver.

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


def test_cross_origin_write_is_refused(make_v1_app: Callable[..., FastAPI]) -> None:
    """A write from another origin is 403 ``request.cross_origin``, even on a public operation."""
    response = _client(make_v1_app).post("/auth/login", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["code"] == "request.cross_origin"


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
    response = _client(make_v1_app).get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


def test_resolved_principal_reaches_the_route(make_v1_app: Callable[..., FastAPI]) -> None:
    """The principal the resolver answers is what ``deps.principal`` hands the route."""
    response = _client(make_v1_app, _READER).get("/auth/me")

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
