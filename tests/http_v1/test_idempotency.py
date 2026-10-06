"""v1's ``Idempotency-Key``: a replayed write answers its first answer and applies nothing.

Through the real sub-application and a real session: a write sent twice with one key is
applied once and answered twice alike; the key reused on another request is refused; a key
is one account's; a server failure leaves the key free for the retry; a duplicate of a
running write is refused. Every mutating operation that signs an account in carries the
guard and declares the header; the public doors carry neither.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.requirements import OPERATION_RIGHTS
from personalscraper.app.accounts.rights import Public
from personalscraper.app.idempotency.service import Claimed
from personalscraper.app.services import AppServices
from personalscraper.http_v1.idempotency import (
    IDEMPOTENCY_HEADER,
    IdempotencyRecorder,
    idempotency_guard,
    request_fingerprint,
)
from personalscraper.http_v1.session_cookie import SESSION_COOKIE

_UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _services(client: TestClient) -> AppServices:
    """The services behind a client's application.

    Args:
        client: A ``v1_client`` client.

    Returns:
        Its application's services.
    """
    app: FastAPI = client.app  # type: ignore[assignment]
    services: AppServices = app.state.services
    return services


def _role_names(client: TestClient) -> list[str | None]:
    """The names of the roles the client's ``app.db`` holds.

    Args:
        client: A ``v1_client`` client.

    Returns:
        Every role's name.
    """
    return [role.name for role in _services(client).app_store.roles.roles()]


def _create_role(client: TestClient, key: str | None, name: str = "Friends") -> Any:
    """Create a role, with a key or without.

    Args:
        client: The signed-in client.
        key: The ``Idempotency-Key``, or ``None`` for none.
        name: The role's name.

    Returns:
        The response.
    """
    headers = {} if key is None else {IDEMPOTENCY_HEADER: key}
    return client.post("/roles", json={"name": name, "rights": ["library.read"]}, headers=headers)


class TestReplay:
    """The same write, sent again with its key."""

    def test_a_replayed_creation_answers_its_first_answer_and_creates_once(
        self, v1_client: Callable[..., TestClient]
    ) -> None:
        """The second send answers the same 201 and the same new id; one role exists."""
        client = v1_client(role="admin")
        first = _create_role(client, "key-1")
        second = _create_role(client, "key-1")
        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json() == first.json()
        assert second.headers["content-type"] == first.headers["content-type"]
        assert _role_names(client).count("Friends") == 1

    def test_a_replayed_deletion_answers_its_first_answer(self, v1_client: Callable[..., TestClient]) -> None:
        """A deletion sent again answers its first 200, not the 404 of a role already gone."""
        client = v1_client(role="admin")
        role_id = _create_role(client, None).json()["id"]
        first = client.delete(f"/roles/{role_id}", headers={IDEMPOTENCY_HEADER: "key-del"})
        second = client.delete(f"/roles/{role_id}", headers={IDEMPOTENCY_HEADER: "key-del"})
        assert first.status_code == 200
        assert (second.status_code, second.json()) == (200, first.json())

    def test_a_refusal_is_replayed_as_answered(self, v1_client: Callable[..., TestClient]) -> None:
        """A write refused on its content answers the same refusal when sent again."""
        client = v1_client(role="admin")
        assert _create_role(client, None).status_code == 201
        first = _create_role(client, "key-taken")
        second = _create_role(client, "key-taken")
        assert first.status_code == 409
        assert first.json()["code"] == "role.name_taken"
        assert (second.status_code, second.json()) == (409, first.json())

    def test_without_a_key_every_send_applies(self, v1_client: Callable[..., TestClient]) -> None:
        """No key, no deduplication: a write sent twice is applied twice."""
        client = v1_client(role="admin")
        assert _create_role(client, None).status_code == 201
        assert _create_role(client, None).json()["code"] == "role.name_taken"


class TestRefusals:
    """A key that cannot be honoured."""

    def test_the_key_on_another_request_is_refused(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``request.key_reused``, and nothing of the second request is applied."""
        client = v1_client(role="admin")
        assert _create_role(client, "key-1", name="Friends").status_code == 201
        response = _create_role(client, "key-1", name="Neighbours")
        assert response.status_code == 409
        assert response.json()["code"] == "request.key_reused"
        assert "Neighbours" not in _role_names(client)

    def test_a_duplicate_of_a_running_write_is_refused(self, v1_client: Callable[..., TestClient]) -> None:
        """While the first send still runs, the duplicate is refused ``request.in_progress`` and applies nothing."""
        client = v1_client(role="admin")
        body = json.dumps({"name": "Friends", "rights": ["library.read"]}).encode()
        account_id = _services(client).sessions.use(client.cookies[SESSION_COOKIE]).actor.account_id  # type: ignore[union-attr]
        _services(client).idempotency.claim(
            account_id, "key-run", "POST /roles", request_fingerprint("POST", "/roles", "", body)
        )
        response = client.post(
            "/roles", content=body, headers={IDEMPOTENCY_HEADER: "key-run", "content-type": "application/json"}
        )
        assert response.status_code == 409
        assert response.json()["code"] == "request.in_progress"
        assert "Friends" not in _role_names(client)

    @pytest.mark.parametrize("key", ["", "with space", "x" * 256], ids=["empty", "space", "too-long"])
    def test_a_malformed_key_is_request_invalid(self, v1_client: Callable[..., TestClient], key: str) -> None:
        """400 ``request.invalid`` naming the header, and nothing is applied."""
        client = v1_client(role="admin")
        response = _create_role(client, key)
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert "Friends" not in _role_names(client)


class TestScope:
    """A key is one account's."""

    def test_another_account_with_the_same_key_is_applied_for_itself(
        self, v1_client: Callable[..., TestClient]
    ) -> None:
        """The second account's write is its own, never the first account's answer."""
        client = v1_client(role="admin")
        first = _create_role(client, "shared-key", name="Friends")
        services = _services(client)
        services.app_store.accounts.insert_account(
            Account(
                id=AccountId("account-other"),
                name="Other",
                email="other@example.org",
                avatar="",
                role_id=RoleId("admin"),
                password_hash=None,
                created_at=1.0,
                updated_at=1.0,
            )
        )
        client.cookies.set(SESSION_COOKIE, services.sessions.open(AccountId("account-other"), user_agent="pytest"))
        second = _create_role(client, "shared-key", name="Neighbours")
        assert second.status_code == 201
        assert second.json()["id"] != first.json()["id"]
        assert second.json()["name"] == "Neighbours"


class TestServerFailure:
    """A write the server failed."""

    def test_a_server_failure_leaves_the_key_to_the_retry(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 500 stores nothing: the retry with the same key applies."""
        client = v1_client(role="admin")
        roles = _services(client).roles
        create_role = roles.create_role
        calls = iter([True])

        def fail_once(*args: Any, **kwargs: Any) -> Any:
            """Fail the first call, then create.

            Args:
                *args: The service call's positional arguments.
                **kwargs: Its keyword arguments.

            Returns:
                The created role, from the second call on.

            Raises:
                RuntimeError: On the first call.
            """
            if next(calls, False):
                raise RuntimeError("store down")
            return create_role(*args, **kwargs)

        monkeypatch.setattr(roles, "create_role", fail_once)
        assert _create_role(client, "key-retry").status_code == 500
        retried = _create_role(client, "key-retry")
        assert retried.status_code == 201
        assert _role_names(client).count("Friends") == 1


#: A served route: an ``APIRoute``, or FastAPI's included-router context of one — both carry
#: ``methods``, ``operation_id`` and ``dependant``.
_Route = Any


def _served_routes(routes: list[Any]) -> Iterator[_Route]:
    """Yield every API route an application serves, through FastAPI's included-router wrappers.

    Args:
        routes: A router's routes, ``_IncludedRouter`` wrappers or ``APIRoute`` instances.

    Yields:
        Each route, its included router's dependencies part of its dependant.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_candidates"):
            yield from _served_routes(route.effective_candidates())
        elif getattr(route, "dependant", None) is not None:
            yield route


def _writes(app: FastAPI) -> list[_Route]:
    """The application's routes that take a mutating method.

    Args:
        app: The v1 sub-application.

    Returns:
        Them, in serving order.
    """
    return [route for route in _served_routes(app.router.routes) if route.methods & _UNSAFE]


def _is_public(route: _Route) -> bool:
    """Whether a route's operation is a public door.

    Args:
        route: A served route.

    Returns:
        True when ``OPERATION_RIGHTS`` names it ``Public``.
    """
    return isinstance(OPERATION_RIGHTS[str(route.operation_id)], Public)


def _guarded(route: _Route) -> bool:
    """Whether a route's dependencies, at any depth, include the idempotency guard.

    Args:
        route: A served route.

    Returns:
        True when :func:`idempotency_guard` is among them.
    """
    pending = list(route.dependant.dependencies)
    while pending:
        dependant = pending.pop()
        if dependant.call is idempotency_guard:
            return True
        pending.extend(dependant.dependencies)
    return False


class TestCoverage:
    """Every mutating operation that signs an account in is guarded; no other is."""

    def test_every_signed_in_write_carries_the_guard(self, make_v1_app: Callable[..., FastAPI]) -> None:
        """The routes are read from the application: a new write without the guard fails here."""
        writes = _writes(make_v1_app())
        assert writes, "no mutating route found"
        assert any(_is_public(route) for route in writes), "no public door found"
        unguarded = [route.operation_id for route in writes if not _is_public(route) and not _guarded(route)]
        assert unguarded == []

    def test_no_read_and_no_public_door_carries_the_guard(self, make_v1_app: Callable[..., FastAPI]) -> None:
        """A read changes nothing to deduplicate; a door signs no account in to scope a key to."""
        served = list(_served_routes(make_v1_app().router.routes))
        assert any(not route.methods & _UNSAFE for route in served), "no read found"
        wrongly = [
            route.operation_id
            for route in served
            if _guarded(route) and (not route.methods & _UNSAFE or _is_public(route))
        ]
        assert wrongly == []

    def test_the_document_declares_the_header_on_exactly_the_guarded_writes(
        self, make_v1_app: Callable[..., FastAPI]
    ) -> None:
        """The served document names ``Idempotency-Key`` on each guarded write, optional, and on nothing else."""
        app = make_v1_app()
        guarded = {route.operation_id for route in _served_routes(app.router.routes) if _guarded(route)}
        declared: dict[str, bool] = {}
        for item in app.openapi()["paths"].values():
            for operation in item.values():
                for parameter in operation.get("parameters", []):
                    if parameter["in"] == "header" and parameter["name"] == IDEMPOTENCY_HEADER:
                        declared[operation["operationId"]] = parameter.get("required", False)
        assert set(declared) == guarded
        assert not any(declared.values())


class _RecordingService:
    """Stands in for the idempotency service: records what the recorder settles, in order."""

    def __init__(self, events: list[str]) -> None:
        """Share the event log.

        Args:
            events: Where each settlement and each sent message is logged.
        """
        self.events = events

    def complete(self, claim: Claimed, status: int, body: bytes, content_type: str | None) -> None:
        """Log a completion.

        Args:
            claim: The claim.
            status: The stored status.
            body: The stored body.
            content_type: The stored type.
        """
        self.events.append(f"complete {status} {body!r} {content_type}")

    def release(self, claim: Claimed) -> None:
        """Log a release.

        Args:
            claim: The claim.
        """
        self.events.append("release")


def _run_recorder(inner: Callable[..., Any]) -> list[str]:
    """Run an inner ASGI application under :class:`IdempotencyRecorder`, logging what leaves.

    Args:
        inner: ``async (scope, receive, send)``; the claim is already in the request's state.

    Returns:
        The settlements and the sent message types, in the order they happened.
    """
    events: list[str] = []
    recorder = IdempotencyRecorder(inner, service=_RecordingService(events))  # type: ignore[arg-type]

    async def receive() -> dict[str, Any]:
        """Answer an empty request body.

        Returns:
            The one body message.
        """
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        """Log a message leaving.

        Args:
            message: The ASGI message.
        """
        events.append(f"sent {message['type']}")

    scope = {"type": "http", "state": {"idempotency_claim": Claimed(claim_id="c1")}}
    with contextlib.suppress(RuntimeError):
        asyncio.run(recorder(scope, receive, send))  # type: ignore[arg-type]
    return events


class TestRecorder:
    """The answer of a claimed request is kept before the client reads it."""

    def test_the_answer_is_stored_before_it_leaves(self) -> None:
        """A crash once the client has the answer can no longer leave the claim to be applied again."""

        async def inner(scope: Any, receive: Any, send: Any) -> None:
            """Answer 201 in two body chunks.

            Args:
                scope: The ASGI scope.
                receive: The ASGI receive channel.
                send: The ASGI send channel.
            """
            headers = [(b"content-type", b"application/json")]
            await send({"type": "http.response.start", "status": 201, "headers": headers})
            await send({"type": "http.response.body", "body": b'{"id":', "more_body": True})
            await send({"type": "http.response.body", "body": b'"x"}'})

        assert _run_recorder(inner) == [
            'complete 201 b\'{"id":"x"}\' application/json',
            "sent http.response.start",
            "sent http.response.body",
            "sent http.response.body",
        ]

    def test_an_answer_that_never_completes_releases_the_claim(self) -> None:
        """The application fails mid-answer: nothing is stored, nothing half-sent, the retry applies."""

        async def inner(scope: Any, receive: Any, send: Any) -> None:
            """Start an answer, then fail.

            Args:
                scope: The ASGI scope.
                receive: The ASGI receive channel.
                send: The ASGI send channel.

            Raises:
                RuntimeError: Always, mid-answer.
            """
            await send({"type": "http.response.start", "status": 200, "headers": []})
            raise RuntimeError("mid-answer")

        assert _run_recorder(inner) == ["release"]
