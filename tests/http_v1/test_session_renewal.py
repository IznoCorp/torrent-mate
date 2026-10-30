"""A v1 session slides while it is used: renewed on the wire under a rotated cookie.

A request past :data:`SESSION_RENEWAL_INTERVAL_S` since the session's last renewal
answers with a new ``tm_v1_session`` — whatever its status — whose ``Max-Age`` is the
idle lifetime; the replaced value keeps signing in until the new one comes back, then for
:data:`SESSION_ROTATION_GRACE_S`. Idle for the lifetime, the session answers 401
``auth.required``. Signing out, a password change and an Admin's cut end what they ended.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from http.cookies import SimpleCookie

import httpx
import pytest
from fastapi.testclient import TestClient

from personalscraper.app.accounts.credentials import CredentialService
from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.passwords import hash_password
from personalscraper.app.accounts.sessions import (
    SESSION_RENEWAL_INTERVAL_S,
    SESSION_ROTATION_GRACE_S,
    SessionService,
    session_idle_s,
)
from personalscraper.app.services import AppServices
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.app import create_v1_app
from personalscraper.http_v1.session_cookie import SESSION_COOKIE

_PASSWORD = "correct horse battery staple"
_NEW_PASSWORD = "A brand-new passphrase 7"
_START = 1_000_000.0


class _Clock:
    """A settable clock.

    Attributes:
        now: The time it answers (epoch seconds).
    """

    def __init__(self) -> None:
        """Start the clock at :data:`_START`."""
        self.now = _START

    def __call__(self) -> float:
        """Answer the current time.

        Returns:
            :attr:`now`.
        """
        return self.now


@dataclasses.dataclass
class _Wire:
    """A client of the v1 sub-application over a clocked session service, signed in.

    Attributes:
        client: The test client; it sends the cookie :meth:`send` is given.
        services: The services behind it.
        clock: The sessions' clock.
        token: The session value it signed in with.
        account_id: The signed-in account.
    """

    client: TestClient
    services: AppServices
    clock: _Clock
    token: str
    account_id: str

    def send(self, method: str, path: str, token: str, **kwargs: object) -> httpx.Response:
        """Send one request carrying a given session value, and only it.

        Args:
            method: The HTTP method.
            path: The path.
            token: The ``tm_v1_session`` value.
            **kwargs: Passed to the client.

        Returns:
            The response.
        """
        self.client.cookies.clear()
        self.client.cookies.set(SESSION_COOKIE, token)
        return self.client.request(method, path, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def wire(test_config: Config, make_v1_services: Callable[[], AppServices]) -> _Wire:
    """A signed-in household account, its sessions on a settable clock.

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.
        make_v1_services: The services factory (its ``app.db`` is temporary).

    Returns:
        The wire.
    """
    built = make_v1_services()
    clock = _Clock()
    store = built.app_store
    sessions = SessionService(store, idle_days=test_config.web.session_idle_days, clock=clock)
    credentials = CredentialService(store, sessions)
    services = dataclasses.replace(built, sessions=sessions, credentials=credentials)
    store.accounts.insert_account(
        Account(
            id="account-sliding",
            name="Sliding",
            email="sliding@example.org",
            avatar="",
            role_id="household",
            password_hash=hash_password(_PASSWORD),
            created_at=1.0,
            updated_at=1.0,
        )
    )
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    client = TestClient(create_v1_app(test_config, settings, services), raise_server_exceptions=False)
    token = sessions.open("account-sliding", user_agent="pytest")
    return _Wire(client=client, services=services, clock=clock, token=token, account_id="account-sliding")


def _session_cookies(response: httpx.Response) -> list[SimpleCookie]:
    """The ``tm_v1_session`` cookies a response sets.

    Args:
        response: The response.

    Returns:
        Each ``Set-Cookie`` naming the session cookie, parsed.
    """
    found = []
    for header in response.headers.get_list("set-cookie"):
        cookie: SimpleCookie = SimpleCookie()
        cookie.load(header)
        if SESSION_COOKIE in cookie:
            found.append(cookie)
    return found


def _renewed(response: httpx.Response) -> str:
    """The session value a response hands, asserting it hands exactly one.

    Args:
        response: The response.

    Returns:
        The new value.
    """
    cookies = _session_cookies(response)
    assert len(cookies) == 1
    return cookies[0][SESSION_COOKIE].value


class TestRenewalOnTheWire:
    """A use past the interval answers with the rotated cookie."""

    def test_within_the_interval_no_cookie_is_set(self, wire: _Wire) -> None:
        """Requests within the interval of the sign-in set no cookie."""
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S - 1
        response = wire.send("GET", "/auth/me", wire.token)
        assert response.status_code == 200
        assert _session_cookies(response) == []

    def test_past_the_interval_the_cookie_is_rotated_with_its_attributes(
        self, wire: _Wire, test_config: Config
    ) -> None:
        """A new value: ``HttpOnly``, ``SameSite=Lax``, ``Path=/``, ``Secure`` per config, ``Max-Age`` = idle."""
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S
        response = wire.send("GET", "/auth/me", wire.token)
        assert response.status_code == 200
        cookie = _session_cookies(response)[0][SESSION_COOKIE]
        assert cookie.value not in ("", wire.token)
        assert cookie["httponly"] is True
        assert cookie["samesite"] == "lax"
        assert cookie["path"] == "/"
        assert cookie["max-age"] == str(session_idle_s(test_config.web.session_idle_days))
        assert bool(cookie["secure"]) is test_config.web.cookie_secure
        assert wire.send("GET", "/auth/me", cookie.value).status_code == 200

    def test_a_refused_request_still_hands_the_rotated_cookie(self, wire: _Wire) -> None:
        """A 403 that renewed the session carries the new value: the browser is never left with a dying one."""
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S
        response = wire.send("GET", "/accounts", wire.token)
        assert response.status_code == 403
        assert wire.send("GET", "/auth/me", _renewed(response)).status_code == 200

    def test_the_old_cookie_is_refused_after_the_grace(self, wire: _Wire) -> None:
        """The new value used, the old one signs in for the grace, then answers 401 ``auth.required``, no cookie set."""
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S
        new = _renewed(wire.send("GET", "/auth/me", wire.token))
        assert wire.send("GET", "/auth/me", new).status_code == 200
        in_flight = wire.send("GET", "/auth/me", wire.token)
        assert in_flight.status_code == 200
        assert _session_cookies(in_flight) == []
        wire.clock.now += SESSION_ROTATION_GRACE_S
        refused = wire.send("GET", "/auth/me", wire.token)
        assert refused.status_code == 401
        assert refused.json()["code"] == "auth.required"
        assert _session_cookies(refused) == []
        assert wire.send("GET", "/auth/me", new).status_code == 200

    def test_idle_past_the_lifetime_is_auth_required(self, wire: _Wire, test_config: Config) -> None:
        """Unused for the idle lifetime: 401 ``auth.required``, and no session cookie set."""
        wire.clock.now += session_idle_s(test_config.web.session_idle_days)
        refused = wire.send("GET", "/auth/me", wire.token)
        assert refused.status_code == 401
        assert refused.json()["code"] == "auth.required"
        assert _session_cookies(refused) == []

    def test_used_daily_the_session_outlives_its_lifetime(self, wire: _Wire, test_config: Config) -> None:
        """Used once a day for twice the idle lifetime, the browser keeping each cookie, it still signs in."""
        token = wire.token
        for _ in range(2 * test_config.web.session_idle_days):
            wire.clock.now += 86_400
            response = wire.send("GET", "/auth/me", token)
            assert response.status_code == 200
            token = _renewed(response)


class TestRevocationUnchanged:
    """Revocation ends what it ended; a revoked session never renews."""

    def test_sign_out_when_renewal_is_due_clears_the_cookie(self, wire: _Wire) -> None:
        """The answer only clears the cookie, and neither the value nor a successor signs in."""
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S
        response = wire.send("POST", "/auth/logout", wire.token)
        assert response.status_code == 200
        cookies = _session_cookies(response)
        assert len(cookies) == 1
        assert cookies[0][SESSION_COOKIE].value == ""
        assert cookies[0][SESSION_COOKIE]["max-age"] == "0"
        assert wire.send("GET", "/auth/me", wire.token).status_code == 401

    def test_a_revoked_session_never_renews(self, wire: _Wire) -> None:
        """Every session of the account revoked (an Admin's cut): 401, and no cookie handed."""
        wire.services.app_store.sessions.revoke_sessions_of(wire.account_id, except_id=None, now=wire.clock.now)
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S
        refused = wire.send("GET", "/auth/me", wire.token)
        assert refused.status_code == 401
        assert _session_cookies(refused) == []

    def test_a_password_change_when_renewal_is_due_keeps_this_session_and_ends_the_others(self, wire: _Wire) -> None:
        """The caller's session, renewed by the change's own request, stays; the other one ends."""
        elsewhere = wire.services.sessions.open(wire.account_id, user_agent="another browser")
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S
        response = wire.send(
            "PUT", "/auth/password", wire.token, json={"currentPassword": _PASSWORD, "newPassword": _NEW_PASSWORD}
        )
        assert response.status_code == 200
        assert wire.send("GET", "/auth/me", _renewed(response)).status_code == 200
        assert wire.send("GET", "/auth/me", elsewhere).status_code == 401

    def test_an_admin_cut_ends_the_old_value_in_its_grace(self, wire: _Wire) -> None:
        """Revoked after a renewal: neither the new value nor the replaced one signs in."""
        wire.clock.now += SESSION_RENEWAL_INTERVAL_S
        new = _renewed(wire.send("GET", "/auth/me", wire.token))
        wire.services.app_store.sessions.revoke_sessions_of(wire.account_id, except_id=None, now=wire.clock.now)
        assert wire.send("GET", "/auth/me", wire.token).status_code == 401
        assert wire.send("GET", "/auth/me", new).status_code == 401
