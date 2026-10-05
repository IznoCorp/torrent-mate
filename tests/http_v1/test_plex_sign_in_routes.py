"""The Plex door's routes: ``POST /auth/plex/start`` (``startPlexSignIn``), ``POST /auth/plex`` (``signInWithPlex``).

The service behind them is the real ``PlexSignInService`` over the client's ``app.db``, with
plex.tv and the Plex server faked from the operator's captures (the unit suite's fakes). What
these pin is the wire: the pin cookie's attributes, the nonce it carries and nothing else, the
202 while the PIN is unclaimed, the session cookie on success with the pin cookie cleared, every
refusal as a contract ``Problem`` — and the sign-in page's ``forwardUrl`` taken from the
configuration, whatever ``Host`` the request carries.
"""

from __future__ import annotations

import dataclasses
import io
import json
import logging
from collections.abc import Callable
from http.cookies import SimpleCookie
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.api.plex_account import PlexAccountClient
from personalscraper.app.accounts.plex_sign_in import PlexSignInService
from personalscraper.app.services import AppServices
from personalscraper.conf.environment import Environment
from personalscraper.http_v1.session_cookie import PLEX_PIN_COOKIE, SESSION_COOKIE
from tests.conftest import LoggedEvents
from tests.unit.app.accounts.test_plex_sign_in import (
    CODE,
    EMAIL,
    SERVER_TOKEN,
    SHARED_MACHINE,
    USER_TOKEN,
    _Clock,
    _local,
    _PlexTv,
    _Response,
    _Server,
    _user,
)


def _services(client: TestClient) -> AppServices:
    """The services the client's application was built with.

    Args:
        client: The test client.

    Returns:
        Its services.
    """
    services: AppServices = client.app.state.services  # type: ignore[attr-defined]
    return services


def _cookies(response: object) -> SimpleCookie:
    """Every ``Set-Cookie`` of an answer, parsed.

    Args:
        response: The answer.

    Returns:
        The cookies.
    """
    cookie: SimpleCookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):  # type: ignore[attr-defined]
        cookie.load(header)
    return cookie


def _door(
    client: TestClient,
    *,
    server: _Server | None = None,
    forward_url: str | None = None,
) -> tuple[_PlexTv, _Clock]:
    """Swap the client's Plex door for one over the fakes.

    Args:
        client: A client of the v1 sub-application.
        server: The Plex server; the captured one when ``None``.
        forward_url: The configured forward address.

    Returns:
        plex.tv and the door's clock.
    """
    services = _services(client)
    plextv, clock = _PlexTv(), _Clock()
    door = PlexSignInService(
        lambda: services.app_store.accounts,
        services.credentials,
        vault=None,
        client_factory=lambda product, client_id: PlexAccountClient(
            product=product,
            client_identifier=client_id,
            session=plextv,  # type: ignore[arg-type]
        ),
        server=server if server is not None else _Server(),
        server_token=SERVER_TOKEN,
        environment=Environment.DEV,
        forward_url=forward_url,
        bus=services.event_bus,
        clock=clock,
    )
    client.app.state.services = dataclasses.replace(services, plex_sign_in=door)  # type: ignore[attr-defined]
    return plextv, clock


def _start(client: TestClient) -> tuple[int, str]:
    """Start a sign-in and carry its pin cookie as the browser would on ``/api/v1/auth/plex``.

    The test client speaks to the sub-application at its root, so the cookie's path
    (``/api/v1/auth/plex``) would not match: it is set on the client by hand.

    Args:
        client: The client.

    Returns:
        The PIN's id and the nonce.
    """
    response = client.post("/auth/plex/start")
    assert response.status_code == 200
    nonce = _cookies(response)[PLEX_PIN_COOKIE].value
    client.cookies.set(PLEX_PIN_COOKIE, nonce)
    return response.json()["pinId"], nonce


class TestStartPlexSignIn:
    """``POST /auth/plex/start``."""

    def test_answers_the_pin_and_sets_the_pin_cookie(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``{pinId, signInUrl}``; the pin cookie HttpOnly, SameSite=Strict, scoped to the Plex door."""
        client = v1_client(role=None)
        _door(client)

        response = client.post("/auth/plex/start")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"pinId", "signInUrl"}
        assert body["signInUrl"].startswith("https://app.plex.tv/auth#?")
        cookie = _cookies(response)[PLEX_PIN_COOKIE]
        assert cookie["httponly"] is True
        assert cookie["samesite"] == "strict"
        assert cookie["path"] == "/api/v1/auth/plex"
        assert int(cookie["max-age"]) == 1800
        assert bool(cookie["secure"]) is client.app.state.config.web.cookie_secure  # type: ignore[attr-defined]
        assert cookie.value not in response.text
        row = _services(client).app_store.accounts.pin(body["pinId"])
        assert row is not None and cookie.value not in row.nonce_hash

    def test_a_forged_host_never_moves_the_forward_address(self, v1_client: Callable[..., TestClient]) -> None:
        """``forwardUrl`` is the configured one; the request's ``Host`` has no say."""
        client = v1_client(role=None)
        _door(client, forward_url="https://tm.example.org/")

        response = client.post("/auth/plex/start", headers={"host": "evil.example.net"})

        url = response.json()["signInUrl"]
        assert "forwardUrl=https%3A%2F%2Ftm.example.org%2F" in url
        assert "evil" not in url

    def test_the_composed_door_without_a_server_token_asks_nobody(self, v1_client: Callable[..., TestClient]) -> None:
        """``build_app_services``'s door with no ``PLEX_TOKEN``: 503 ``plex.server_unreachable``, no pin cookie."""
        client = v1_client(role=None)

        response = client.post("/auth/plex/start")

        assert response.status_code == 503
        assert response.json()["code"] == "plex.server_unreachable"
        assert PLEX_PIN_COOKIE not in _cookies(response)

    def test_plex_tv_down_is_a_503_problem(self, v1_client: Callable[..., TestClient]) -> None:
        """503 ``plex.unreachable``, no pin cookie."""
        client = v1_client(role=None)
        plextv, _ = _door(client)
        plextv.down = True

        response = client.post("/auth/plex/start")

        assert response.status_code == 503
        assert response.json()["code"] == "plex.unreachable"
        assert PLEX_PIN_COOKIE not in _cookies(response)


class TestSignInWithPlex:
    """``POST /auth/plex``."""

    def test_pending_is_202_and_signs_nobody_in(self, v1_client: Callable[..., TestClient]) -> None:
        """202 ``{"pending": true}``; no session cookie."""
        client = v1_client(role=None)
        plextv, clock = _door(client)
        plextv.pending_then_claimed()
        pin_id, _ = _start(client)
        clock.now += 2.0

        response = client.post("/auth/plex", json={"pinId": pin_id})

        assert response.status_code == 202
        assert response.json() == {"pending": True}
        assert SESSION_COOKIE not in _cookies(response)

    def test_claimed_opens_a_session_and_clears_the_pin_cookie(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``Account`` (the owner on Admin); the session cookie set, the pin cookie cleared on its path."""
        client = v1_client(role=None)
        _, clock = _door(client)
        pin_id, _ = _start(client)
        clock.now += 2.0

        response = client.post("/auth/plex", json={"pinId": pin_id}, headers={"user-agent": "pytest-browser"})

        assert response.status_code == 200
        body = response.json()
        assert (body["role"]["id"], body["signInKind"], body["email"]) == ("admin", "owner", EMAIL)
        cookies = _cookies(response)
        signed_in = _services(client).sessions.resolve(cookies[SESSION_COOKIE].value)
        assert signed_in is not None and signed_in.account_id == body["id"]
        cleared = cookies[PLEX_PIN_COOKIE]
        assert cleared.value == "" and cleared["path"] == "/api/v1/auth/plex"
        for secret in (USER_TOKEN, SERVER_TOKEN, CODE):
            assert secret not in response.text

    def test_a_link_ends_the_session_the_dropped_password_opened(self, v1_client: Callable[..., TestClient]) -> None:
        """A shared user's local account linked by e-mail: its old cookie answers 401, the new one 200."""
        client = v1_client(role=None)
        _, clock = _door(client, server=_Server(SHARED_MACHINE))
        services = _services(client)
        services.app_store.accounts.insert_account(_local("account-local", EMAIL, "requester"))
        running = services.sessions.open("account-local", user_agent="old browser")
        old = TestClient(client.app, raise_server_exceptions=False)
        old.cookies.set(SESSION_COOKIE, running)
        assert old.get("/auth/me").status_code == 200
        pin_id, _ = _start(client)
        clock.now += 2.0

        response = client.post("/auth/plex", json={"pinId": pin_id})

        assert response.status_code == 200
        assert old.get("/auth/me").status_code == 401
        fresh = TestClient(client.app, raise_server_exceptions=False)
        fresh.cookies.set(SESSION_COOKIE, _cookies(response)[SESSION_COOKIE].value)
        assert fresh.get("/auth/me").status_code == 200

    def test_without_the_pin_cookie_is_pin_unknown(self, v1_client: Callable[..., TestClient]) -> None:
        """Another browser's PIN: 400 ``plex.pin_unknown``; plex.tv not asked."""
        client = v1_client(role=None)
        plextv, clock = _door(client)
        pin_id, _ = _start(client)
        client.cookies.delete(PLEX_PIN_COOKIE)
        clock.now += 2.0

        response = client.post("/auth/plex", json={"pinId": pin_id})

        assert response.status_code == 400
        assert response.json()["code"] == "plex.pin_unknown"
        assert plextv.count("/api/v2/pins/") == 0

    def test_no_access_is_the_one_refusal(self, v1_client: Callable[..., TestClient]) -> None:
        """No access to the server: 401 ``auth.refused``, the e-mail absent from the Problem."""
        client = v1_client(role=None)
        _, clock = _door(client, server=_Server("REDACTED-machine-9"))
        pin_id, _ = _start(client)
        clock.now += 2.0

        response = client.post("/auth/plex", json={"pinId": pin_id})

        assert response.status_code == 401
        assert response.json()["code"] == "auth.refused"
        assert EMAIL not in response.text
        assert SESSION_COOKIE not in _cookies(response)

    @pytest.mark.parametrize("body", [{}, {"pinId": "abc"}, {"pinId": 1, "extra": True}])
    def test_a_malformed_body_is_request_invalid(
        self, v1_client: Callable[..., TestClient], body: dict[str, object]
    ) -> None:
        """400 ``request.invalid``."""
        client = v1_client(role=None)
        _door(client)
        response = client.post("/auth/plex", json=body)
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"


#: A nonce no browser was given: a forged pin cookie.
FOREIGN_NONCE = "PLANTED-foreign-nonce-77c1"


def _no_access(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """The identity reaches another server only.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    server.identifier = "REDACTED-machine-9"


def _owner_mismatch(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """The resource is owned, the server's token is another account's.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    plextv.users[SERVER_TOKEN] = _user(plex_id=900099)


def _unconfirmed(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """A local account holds the e-mail, which plex.tv has not confirmed.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    _services(client).app_store.accounts.insert_account(_local("account-local", EMAIL, "requester"))
    plextv.users[USER_TOKEN] = _user(confirmed=False)


def _token_refused(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """plex.tv refuses the token the PIN yielded.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    del plextv.users[USER_TOKEN]


def _server_token_refused(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """plex.tv refuses the server's own token.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    del plextv.users[SERVER_TOKEN]


def _foreign_nonce(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """The pin cookie carries a nonce this PIN was not bound to.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    client.cookies.set(PLEX_PIN_COOKIE, FOREIGN_NONCE)


def _no_cookie(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """The browser sends no pin cookie.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    client.cookies.delete(PLEX_PIN_COOKIE)


def _expired(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """The PIN is past its expiry.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    clock.now += 3600.0


def _forgotten(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """plex.tv answers 404 to the PIN check.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    plextv.pin = [_Response(404, None)]


def _pending(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """The PIN is not claimed yet.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    plextv.pending_then_claimed()


def _plex_tv_down(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """plex.tv fails at the transport, with the token in its error.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    plextv.down = True


def _server_down(client: TestClient, plextv: _PlexTv, clock: _Clock, server: _Server) -> None:
    """The Plex server does not answer its identifier.

    Args:
        client: The client.
        plextv: plex.tv.
        clock: The door's clock.
        server: The door's server.
    """
    server.identifier = None


class TestNoLeak:
    """No planted secret — a token, the PIN code, the e-mail, a nonce — reaches a log or a Problem."""

    @pytest.mark.parametrize(
        ("arrange", "status", "code"),
        [
            (_no_access, 401, "auth.refused"),
            (_owner_mismatch, 401, "auth.refused"),
            (_unconfirmed, 401, "auth.refused"),
            (_token_refused, 401, "plex.token_refused"),
            (_server_token_refused, 503, "plex.server_unreachable"),
            (_foreign_nonce, 400, "plex.pin_unknown"),
            (_no_cookie, 400, "plex.pin_unknown"),
            (_expired, 409, "plex.pin_expired"),
            (_forgotten, 409, "plex.pin_expired"),
            (_pending, 202, None),
            (_plex_tv_down, 503, "plex.unreachable"),
            (_server_down, 503, "plex.server_unreachable"),
        ],
        ids=[
            "no-access",
            "owner-mismatch",
            "unconfirmed",
            "token-refused",
            "server-token-refused",
            "foreign-nonce",
            "no-cookie",
            "expired",
            "forgotten",
            "pending",
            "plex-tv-down",
            "server-down",
        ],
    )
    def test_no_secret_reaches_a_log_or_an_answer(
        self,
        v1_client: Callable[..., TestClient],
        arrange: Any,
        status: int,
        code: str | None,
        logged_events: LoggedEvents,
    ) -> None:
        """Start, arrange the path, poll: every answer body and every log record is free of the planted values."""
        client = v1_client(role=None)
        server = _Server()
        plextv, clock = _door(client, server=server)
        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        logging.getLogger().addHandler(handler)
        try:
            with logged_events() as logs:
                started = client.post("/auth/plex/start")
                nonce = _cookies(started)[PLEX_PIN_COOKIE].value
                client.cookies.set(PLEX_PIN_COOKIE, nonce)
                clock.now += 2.0
                arrange(client, plextv, clock, server)
                response = client.post("/auth/plex", json={"pinId": started.json()["pinId"]})
        finally:
            logging.getLogger().removeHandler(handler)

        assert response.status_code == status
        if code is not None:
            assert response.json()["code"] == code
        # The start's sign-in page carries the PIN code by design: it is read for everything else.
        start_body = started.text.lower()
        for secret in (USER_TOKEN, SERVER_TOKEN, EMAIL, nonce):
            assert secret.lower() not in start_body, secret
        everything = "\n".join([response.text, captured.getvalue(), json.dumps(logs, default=str)]).lower()
        for secret in (USER_TOKEN, SERVER_TOKEN, CODE, EMAIL, nonce, FOREIGN_NONCE):
            assert secret.lower() not in everything, secret

    def test_plex_tv_down_at_the_start_leaks_nothing(
        self, v1_client: Callable[..., TestClient], logged_events: LoggedEvents
    ) -> None:
        """plex.tv fails at the start with the token in its error: the 503 and the logs carry no planted value."""
        client = v1_client(role=None)
        plextv, _ = _door(client)
        plextv.down = True
        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        logging.getLogger().addHandler(handler)
        try:
            with logged_events() as logs:
                response = client.post("/auth/plex/start")
        finally:
            logging.getLogger().removeHandler(handler)

        assert response.status_code == 503
        everything = "\n".join([response.text, captured.getvalue(), json.dumps(logs, default=str)]).lower()
        for secret in (USER_TOKEN, SERVER_TOKEN, CODE, EMAIL):
            assert secret.lower() not in everything, secret
