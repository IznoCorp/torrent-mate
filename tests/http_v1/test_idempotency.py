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
import re
import sqlite3
from collections.abc import Callable, Iterator
from typing import Any, Final

import pytest
from _repo_paths import DESIGN_SRC
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.ratelimit import SlidingWindowRateLimiter
from personalscraper.app.accounts.requirements import OPERATION_RIGHTS
from personalscraper.app.accounts.rights import Public
from personalscraper.app.idempotency.ids import ClaimId
from personalscraper.app.idempotency.service import FINAL_REFUSALS, Claimed
from personalscraper.app.services import AppServices
from personalscraper.http_v1.idempotency import (
    IDEMPOTENCY_HEADER,
    IdempotencyRecorder,
    idempotency_guard,
)
from personalscraper.http_v1.session_cookie import SESSION_COOKIE
from tests.conftest import LoggedEvents
from tests.http_v1.test_authentication_routes import _PASSWORD, _with_password

_UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: The client's ``FINAL_STATUSES`` set literal, its members one per line.
_FINAL_STATUSES = re.compile(r"const FINAL_STATUSES = new Set\(\[(.*?)\]\);", re.DOTALL)


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

    def test_a_final_refusal_is_answered_from_the_store(self, v1_client: Callable[..., TestClient]) -> None:
        """The world changed since the refusal: the replay still answers it, the write is not applied again."""
        client = v1_client(role="admin")
        taken_id = _create_role(client, None).json()["id"]
        first = _create_role(client, "key-taken")
        assert first.json()["code"] == "role.name_taken"
        assert client.delete(f"/roles/{taken_id}").status_code == 200
        second = _create_role(client, "key-taken")
        assert (second.status_code, second.json()) == (409, first.json())
        assert "Friends" not in _role_names(client)

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

    def test_the_key_with_another_query_is_refused(self, v1_client: Callable[..., TestClient]) -> None:
        """The same body under another query string is another request: 409 ``request.key_reused``."""
        client = v1_client(role="admin")
        assert _create_role(client, "key-query").status_code == 201
        response = client.post(
            "/roles?origin=outbox",
            json={"name": "Friends", "rights": ["library.read"]},
            headers={IDEMPOTENCY_HEADER: "key-query"},
        )
        assert response.status_code == 409
        assert response.json()["code"] == "request.key_reused"
        assert _role_names(client).count("Friends") == 1

    def test_a_duplicate_of_a_running_write_is_refused(self, v1_client: Callable[..., TestClient]) -> None:
        """While the first send still runs, the duplicate is refused ``request.in_progress`` and applies nothing."""
        client = v1_client(role="admin")
        body = json.dumps({"name": "Friends", "rights": ["library.read"]}).encode()
        account_id = _services(client).sessions.use(client.cookies[SESSION_COOKIE]).actor.account_id  # type: ignore[union-attr]
        idempotency = _services(client).idempotency
        idempotency.claim(account_id, "key-run", "POST /roles", idempotency.fingerprint("POST", "/roles", "", body))
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

    def test_residual_a_failure_after_the_commit_is_applied_again(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RESIDUAL, pinned as it is: a 5xx raised after the write committed releases the key too.

        Most 5xx roll back, so the claim is released on every one; a write that committed
        before its 5xx is applied again by the retry. Here the second apply is refused on its
        content (the name is taken); a write with no such guard would apply twice.
        """
        client = v1_client(role="admin")
        roles = _services(client).roles
        create_role = roles.create_role
        applied: list[object] = []

        def commit_then_fail(*args: Any, **kwargs: Any) -> Any:
            """Create the role, then fail the first time only.

            Args:
                *args: The service call's positional arguments.
                **kwargs: Its keyword arguments.

            Returns:
                The created role, from the second call on.

            Raises:
                RuntimeError: On the first call, after the role was created.
            """
            created = create_role(*args, **kwargs)
            applied.append(created)
            if len(applied) == 1:
                raise RuntimeError("failed after the commit")
            return created

        monkeypatch.setattr(roles, "create_role", commit_then_fail)
        assert _create_role(client, "key-late").status_code == 500
        retried = _create_role(client, "key-late")
        assert retried.json()["code"] == "role.name_taken"
        assert _role_names(client).count("Friends") == 1


class TestWhatIsKept:
    """Only an answer that will not change is kept: a success or a final refusal."""

    def test_the_kept_refusals_are_the_clients_final_statuses(self) -> None:
        """The server keeps exactly the refusals the client's outbox drops as final (``query-client.ts``)."""
        source = (DESIGN_SRC / "lib" / "query-client.ts").read_text(encoding="utf-8")
        found = _FINAL_STATUSES.search(source)
        assert found is not None, "FINAL_STATUSES not found in query-client.ts"
        client_final = {int(status) for status in re.findall(r"^\s*(\d{3}),", found.group(1), re.MULTILINE)}
        assert client_final
        assert set(FINAL_REFUSALS) == client_final

    def test_a_too_many_requests_is_not_kept(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 429 says nothing of the write: once the window has passed, the same key applies it."""
        client = v1_client(role="local-guest")
        _with_password(client)
        change = {"currentPassword": _PASSWORD, "newPassword": "A brand-new passphrase 7"}
        services = _services(client)
        monkeypatch.setattr(
            services.credentials, "_password_limiter", SlidingWindowRateLimiter(max_attempts=0, window_seconds=60.0)
        )
        limited = client.put("/auth/password", json=change, headers={IDEMPOTENCY_HEADER: "key-limited"})
        assert limited.status_code == 429
        monkeypatch.setattr(services.credentials, "_password_limiter", SlidingWindowRateLimiter())
        retried = client.put("/auth/password", json=change, headers={IDEMPOTENCY_HEADER: "key-limited"})
        assert (retried.status_code, retried.json()) == (200, {"ok": True})


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

    def __init__(self, events: list[str], *, failing: str | None = None) -> None:
        """Share the event log.

        Args:
            events: Where each settlement and each sent message is logged.
            failing: ``"complete"`` or ``"release"``: that call raises, as a store down would.
        """
        self.events = events
        self._failing = failing

    def complete(self, claim: Claimed, status: int, body: bytes, content_type: str | None) -> None:
        """Log a completion.

        Args:
            claim: The claim.
            status: The stored status.
            body: The stored body.
            content_type: The stored type.

        Raises:
            sqlite3.OperationalError: When completions fail.
        """
        if self._failing == "complete":
            raise sqlite3.OperationalError("database is locked")
        self.events.append(f"complete {status} {body!r} {content_type}")

    def release(self, claim: Claimed) -> None:
        """Log a release.

        Args:
            claim: The claim.

        Raises:
            sqlite3.OperationalError: When releases fail.
        """
        if self._failing == "release":
            raise sqlite3.OperationalError("database is locked")
        self.events.append("release")


def _run_recorder(inner: Callable[..., Any], *, failing: str | None = None) -> list[str]:
    """Run an inner ASGI application under :class:`IdempotencyRecorder`, logging what leaves.

    Args:
        inner: ``async (scope, receive, send)``; the claim is already in the request's state.
        failing: The service call that raises (``"complete"`` or ``"release"``), if any.

    Returns:
        The settlements and the sent message types, in the order they happened.
    """
    events: list[str] = []
    recorder = IdempotencyRecorder(inner, service=_RecordingService(events, failing=failing))  # type: ignore[arg-type]

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

    scope = {"type": "http", "state": {"idempotency_claim": Claimed(claim_id=ClaimId("c1"))}}
    with contextlib.suppress(RuntimeError, asyncio.CancelledError):
        asyncio.run(recorder(scope, receive, send))  # type: ignore[arg-type]
    return events


def _answering(status: int) -> Callable[..., Any]:
    """An inner application answering one status with a JSON body.

    Args:
        status: The status answered.

    Returns:
        ``async (scope, receive, send)``.
    """

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        """Answer the status.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        headers = [(b"content-type", b"application/json")]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": b"{}"})

    return inner


_SENT: Final = ["sent http.response.start", "sent http.response.body"]


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

    def test_an_answer_that_never_completes_keeps_the_claim(self) -> None:
        """The application fails mid-answer, after the route ran: the claim stays for the take-over to arbitrate."""

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

        assert _run_recorder(inner) == []

    def test_a_cancel_after_the_route_keeps_the_claim(self) -> None:
        """A shutdown cancels the request once its write committed: nothing releases the key to a second apply."""

        async def inner(scope: Any, receive: Any, send: Any) -> None:
            """Start an answer, then be cancelled.

            Args:
                scope: The ASGI scope.
                receive: The ASGI receive channel.
                send: The ASGI send channel.

            Raises:
                asyncio.CancelledError: Always, mid-answer.
            """
            await send({"type": "http.response.start", "status": 201, "headers": []})
            raise asyncio.CancelledError

        assert _run_recorder(inner) == []

    def test_a_failed_store_still_answers_and_keeps_the_claim(self, logged_events: LoggedEvents) -> None:
        """The answer cannot be stored: the client still gets it, the claim stays running, an error is logged."""
        with logged_events() as logs:
            events = _run_recorder(_answering(201), failing="complete")
        assert events == _SENT
        assert [log["log_level"] for log in logs if log["event"] == "idempotency_store_failed"] == ["error"]

    @pytest.mark.parametrize("status", [401, 403, 408, 423, 429, 500, 503])
    def test_an_answer_that_may_change_releases_the_claim(self, status: int) -> None:
        """Neither a success nor a final refusal: nothing is kept, the retry with the same key applies."""
        assert _run_recorder(_answering(status)) == ["release", *_SENT]

    @pytest.mark.parametrize("status", [200, 201, 204, 400, 404, 405, 409, 410, 415, 422])
    def test_a_success_or_a_final_refusal_is_kept(self, status: int) -> None:
        """The answers the client will not send again differently are kept for the replays."""
        assert _run_recorder(_answering(status)) == [f"complete {status} b'{{}}' application/json", *_SENT]

    def test_a_failed_release_still_answers(self, logged_events: LoggedEvents) -> None:
        """The claim cannot be released: the client still gets the answer, an error is logged."""
        with logged_events() as logs:
            events = _run_recorder(_answering(503), failing="release")
        assert events == _SENT
        assert [log["log_level"] for log in logs if log["event"] == "idempotency_store_failed"] == ["error"]
