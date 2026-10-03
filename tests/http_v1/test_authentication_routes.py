"""The ``authentication`` tag's routes served so far: ``readAccount``, ``signOut`` and ``signIn``.

The session is v1's own (``tm_v1_session``); v0's ``tm_session`` never signs a v1 request
in. ``readAccount`` answers the contract's ``Account``, its ``forbiddenWrites`` being the
instance's ceiling; ``signOut`` revokes the session and clears its cookie; ``signIn`` opens
a new session from an e-mail and a password, refusing every failure as ``auth.refused``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
import structlog
from fastapi import Response
from fastapi.testclient import TestClient

from personalscraper.app.accounts.passwords import hash_password
from personalscraper.app.accounts.ratelimit import MAX_FAILED_ATTEMPTS
from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.services import AppServices
from personalscraper.app.store.store import AppStore
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.web import WebConfig
from personalscraper.http_v1.session_cookie import SESSION_COOKIE, clear_session_cookie, set_session_cookie

#: The password the seeded local account holds.
_PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts on a production instance: no ceiling from the environment.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)


def _services(client: TestClient) -> AppServices:
    """The services the client's application was built with.

    Args:
        client: The test client.

    Returns:
        Its services.
    """
    services: AppServices = client.app.state.services  # type: ignore[attr-defined]
    return services


def _cookie(header: str) -> SimpleCookie:
    """Parse one ``Set-Cookie`` header.

    Args:
        header: The header's value.

    Returns:
        The parsed cookie.
    """
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(header)
    return cookie


class TestReadAccount:
    """``GET /auth/me`` — ``readAccount``."""

    def test_without_a_cookie_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """No session: 401 ``auth.required``, as a Problem."""
        response = v1_client(role=None).get("/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_v0s_cookie_never_signs_v1_in(self, v1_client: Callable[..., TestClient]) -> None:
        """A request carrying only v0's ``tm_session`` — even holding a live v1 value — is 401."""
        client = v1_client()
        token = client.cookies.get(SESSION_COOKIE)
        client.cookies.clear()
        client.cookies.set("tm_session", token)
        response = client.get("/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_an_unknown_value_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """A cookie no session holds: 401."""
        client = v1_client(role=None)
        client.cookies.set(SESSION_COOKIE, "forged")
        assert client.get("/auth/me").status_code == 401

    def test_answers_the_signed_in_account(self, v1_client: Callable[..., TestClient]) -> None:
        """The account, its seeded role (no name, its start kinds), signs in locally, no avatar."""
        client = v1_client(role="household")
        role = _services(client).app_store.accounts.role("household")
        assert role is not None

        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json() == {
            "id": "account-1",
            "name": "Account 1",
            "email": "account-1@example.org",
            "role": {
                "id": "household",
                "kind": "ordinary",
                "rights": sorted(right.value for right in role.rights),
                "defaultFor": ["plexHome"],
            },
            "signInKind": "local",
            "forbiddenWrites": [],
        }

    def test_a_session_whose_role_is_gone_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """The account's role was deleted: 401 ``auth.required``.

        ``foreign_keys=ON`` forbids the state through the store; a separate connection
        (foreign keys OFF) reaches it.
        """
        client = v1_client()
        db_path = _services(client).app_store._db_path  # noqa: SLF001 — the test writes the file itself
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DELETE FROM role WHERE id = 'household'")
            conn.commit()
        finally:
            conn.close()
        response = client.get("/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_the_session_value_is_never_echoed(self, v1_client: Callable[..., TestClient]) -> None:
        """Neither the body nor any header of the answer carries the cookie value."""
        client = v1_client()
        token = client.cookies.get(SESSION_COOKIE)
        assert token
        response = client.get("/auth/me")
        assert token not in response.text
        assert all(token not in value for value in response.headers.values())

    def test_admin_carries_no_rights_list(self, v1_client: Callable[..., TestClient]) -> None:
        """Admin: kind ``admin``, rights ``[]``, no ``defaultFor``."""
        role = v1_client(role="admin").get("/auth/me").json()["role"]
        assert role == {"id": "admin", "kind": "admin", "rights": []}

    def test_a_renamed_role_carries_its_name(self, v1_client: Callable[..., TestClient]) -> None:
        """A role an Admin named is answered with its name."""
        client = v1_client(rights=frozenset({Right.LIBRARY_READ}))
        role = client.get("/auth/me").json()["role"]
        assert role["name"] == "Listed"
        assert role["rights"] == ["library.read"]
        assert "defaultFor" not in role

    @pytest.mark.parametrize(("server_access", "kind"), [("owner", "owner"), ("shared", "plex")])
    def test_sign_in_kind_follows_the_plex_link(
        self, v1_client: Callable[..., TestClient], server_access: str, kind: str
    ) -> None:
        """The server's owner signs in as ``owner``; any other linked account as ``plex``."""
        response = v1_client(server_access=server_access).get("/auth/me")
        assert response.json()["signInKind"] == kind

    def test_the_avatar_is_answered_when_present(self, v1_client: Callable[..., TestClient]) -> None:
        """An account with a picture carries its address."""
        client = v1_client()
        conn = _services(client).app_store.accounts._conn  # noqa: SLF001 — no repository method sets an avatar yet
        conn.execute("UPDATE account SET avatar = 'https://plex.tv/users/1/avatar'")
        assert client.get("/auth/me").json()["avatar"] == "https://plex.tv/users/1/avatar"

    def test_forbidden_writes_on_the_preprod(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``PERSONALSCRAPER_ENV=staging`` forbids ``library.delete`` alone."""
        client = v1_client()
        monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
        assert client.get("/auth/me").json()["forbiddenWrites"] == ["library.delete"]

    def test_forbidden_writes_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``PERSONALSCRAPER_WEB_ROLE=staging`` forbids every write right, Admin included."""
        client = v1_client(role="admin")
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        assert client.get("/auth/me").json()["forbiddenWrites"] == sorted(right.value for right in WRITE_RIGHTS)


class TestSignOut:
    """``POST /auth/logout`` — ``signOut``."""

    def test_without_a_cookie_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """No session to close: 401."""
        response = v1_client(role=None).post("/auth/logout")
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_revokes_and_clears_the_cookie(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``{"ok": true}``; the cookie is cleared; the old value no longer signs in."""
        client = v1_client()
        token = client.cookies.get(SESSION_COOKIE)

        response = client.post("/auth/logout")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        cleared = _cookie(response.headers["set-cookie"])[SESSION_COOKIE]
        assert cleared.value == ""
        assert cleared["max-age"] == "0"
        assert cleared["path"] == "/"
        client.cookies.clear()
        client.cookies.set(SESSION_COOKIE, token)
        after = client.get("/auth/me")
        assert after.status_code == 401
        assert after.json()["code"] == "auth.required"

    def test_signs_out_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Closing one's own session is a session act, not a write: allowed under ``WEB_ROLE=staging``."""
        client = v1_client()
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        response = client.post("/auth/logout")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


def _seed_password_account(client: TestClient, email: str = "local@example.org") -> str:
    """Add a local account holding :data:`_PASSWORD` to the client's ``app.db``.

    Args:
        client: The test client.
        email: The account's e-mail.

    Returns:
        The account's key.
    """
    account_id = f"account-{email.split('@')[0]}"
    _services(client).app_store.accounts.insert_account(
        AccountRow(
            id=account_id,
            name="Local",
            email=email,
            avatar="",
            role_id="local-guest",
            password_hash=hash_password(_PASSWORD),
            created_at=1.0,
            updated_at=1.0,
        )
    )
    return account_id


class TestSignIn:
    """``POST /auth/login`` — ``signIn``, the password door."""

    def test_opens_a_session_and_answers_the_account(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``Account``; ``Set-Cookie`` hands, with v1's attributes, a session that signs the account in."""
        client = v1_client(role=None)
        account_id = _seed_password_account(client)

        response = client.post("/auth/login", json={"email": "LOCAL@example.org", "password": _PASSWORD})

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == account_id
        assert body["signInKind"] == "local"
        cookie = _cookie(response.headers["set-cookie"])[SESSION_COOKIE]
        assert cookie["httponly"] is True
        assert cookie["samesite"] == "strict"
        assert cookie["path"] == "/"
        assert bool(cookie["secure"]) is client.app.state.config.web.cookie_secure  # type: ignore[attr-defined]
        assert cookie.value not in response.text
        signed_in = _services(client).sessions.resolve(cookie.value)
        assert signed_in is not None and signed_in.account_id == account_id

    def test_a_preset_cookie_is_never_adopted(self, v1_client: Callable[..., TestClient]) -> None:
        """A value planted before the sign-in is replaced, and signs nobody in after it (no fixation)."""
        client = v1_client(role=None)
        _seed_password_account(client)
        client.cookies.set(SESSION_COOKIE, "planted-by-an-attacker")

        response = client.post("/auth/login", json={"email": "local@example.org", "password": _PASSWORD})

        issued = _cookie(response.headers["set-cookie"])[SESSION_COOKIE].value
        assert issued != "planted-by-an-attacker"
        assert _services(client).sessions.resolve("planted-by-an-attacker") is None

    def test_two_sign_ins_two_sessions(self, v1_client: Callable[..., TestClient]) -> None:
        """Each sign-in hands a new value; the first still signs in."""
        client = v1_client(role=None)
        _seed_password_account(client)
        body = {"email": "local@example.org", "password": _PASSWORD}

        first = _cookie(client.post("/auth/login", json=body).headers["set-cookie"])[SESSION_COOKIE].value
        second = _cookie(client.post("/auth/login", json=body).headers["set-cookie"])[SESSION_COOKIE].value

        assert first != second
        assert _services(client).sessions.resolve(first) is not None

    @pytest.mark.parametrize(
        ("email", "password"),
        [("nobody@example.org", _PASSWORD), ("local@example.org", "wrong password")],
        ids=["unknown-email", "wrong-password"],
    )
    def test_a_failure_is_auth_refused(self, v1_client: Callable[..., TestClient], email: str, password: str) -> None:
        """401 ``auth.refused``, no cookie, and neither credential anywhere in the answer or the log."""
        client = v1_client(role=None)
        _seed_password_account(client)

        with structlog.testing.capture_logs() as logs:
            response = client.post("/auth/login", json={"email": email, "password": password})

        assert response.status_code == 401
        assert response.json()["code"] == "auth.refused"
        assert "set-cookie" not in response.headers
        for secret in (email, password):
            assert secret not in response.text
            assert secret not in str(logs)

    def test_a_plex_linked_account_is_auth_refused(self, v1_client: Callable[..., TestClient]) -> None:
        """A shared Plex account signs in by Plex only: the same 401 ``auth.refused``, even with its password."""
        client = v1_client(role=None)
        account_id = _seed_password_account(client)
        _services(client).app_store.accounts.upsert_plex_link(
            PlexLinkRow(
                account_id=account_id,
                plex_id=7,
                plex_uuid="uuid-7",
                plex_username="plex-7",
                server_access="shared",
                token_ciphertext=None,
                token_stored_at=None,
                linked_at=1.0,
                last_sign_in_at=None,
            )
        )

        response = client.post("/auth/login", json={"email": "local@example.org", "password": _PASSWORD})

        assert response.status_code == 401
        assert response.json()["code"] == "auth.refused"

    def test_a_missing_field_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """The contract's body is ``{email, password}``: v0's ``username`` alone is refused 400."""
        response = v1_client(role=None).post("/auth/login", json={"username": "x", "password": _PASSWORD})
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"

    def test_the_sixth_failure_is_rate_limited(self, v1_client: Callable[..., TestClient]) -> None:
        """Past ``MAX_FAILED_ATTEMPTS`` failures in the window: 429 ``auth.rate_limited``, right password included."""
        client = v1_client(role=None)
        _seed_password_account(client)
        for _ in range(MAX_FAILED_ATTEMPTS):
            assert client.post("/auth/login", json={"email": "local@example.org", "password": "no"}).status_code == 401

        response = client.post("/auth/login", json={"email": "local@example.org", "password": _PASSWORD})

        assert response.status_code == 429
        assert response.json()["code"] == "auth.rate_limited"

    def test_behind_the_proxy_the_key_is_the_rightmost_forwarded_address(
        self, v1_client: Callable[..., TestClient]
    ) -> None:
        """From loopback, the rightmost ``X-Forwarded-For`` keys the limit; a spoofed leftmost one changes nothing."""
        app = v1_client(role=None).app
        client = TestClient(app, client=("127.0.0.1", 50000), raise_server_exceptions=False)
        _seed_password_account(client)
        wrong = {"email": "local@example.org", "password": "no"}
        right = {"email": "local@example.org", "password": _PASSWORD}
        for number in range(MAX_FAILED_ATTEMPTS):
            client.post("/auth/login", json=wrong, headers={"x-forwarded-for": f"10.0.0.{number}, 198.51.100.9"})

        spoofed = client.post("/auth/login", json=right, headers={"x-forwarded-for": "10.9.9.9, 198.51.100.9"})
        other = client.post("/auth/login", json=right, headers={"x-forwarded-for": "198.51.100.10"})

        assert spoofed.status_code == 429
        assert other.status_code == 200

    def test_signs_in_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Opening one's own session is a session act: allowed under ``WEB_ROLE=staging``."""
        client = v1_client(role=None)
        _seed_password_account(client)
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        response = client.post("/auth/login", json={"email": "local@example.org", "password": _PASSWORD})
        assert response.status_code == 200


class TestCookie:
    """The ``tm_v1_session`` cookie's attributes."""

    @pytest.mark.parametrize("secure", [True, False])
    def test_set_carries_the_attributes(self, secure: bool) -> None:
        """``HttpOnly``, ``SameSite=Strict``, ``Path=/``, ``Max-Age`` = the TTL, ``Secure`` per ``cookie_secure``."""
        web = WebConfig(cookie_secure=secure, session_ttl_hours=3)
        response = Response()
        set_session_cookie(response, "value", web)
        header = response.headers["set-cookie"]
        cookie = _cookie(header)[SESSION_COOKIE]
        assert cookie.value == "value"
        assert cookie["httponly"] is True
        assert cookie["samesite"] == "strict"
        assert cookie["path"] == "/"
        assert cookie["max-age"] == str(3 * 3600)
        assert bool(cookie["secure"]) is secure

    def test_max_age_is_the_sessions_lifetime(self, test_config: Config, tmp_path: Path) -> None:
        """For one configured ``session_ttl_hours``, ``Max-Age`` == the session's ``expires_at - created_at``."""
        web = test_config.web.model_copy(update={"session_ttl_hours": 5})
        store = AppStore(tmp_path / "app.db")
        try:
            store.accounts.insert_account(
                AccountRow(
                    id="account-ttl",
                    name="TTL",
                    email="ttl@example.org",
                    avatar="",
                    role_id="household",
                    password_hash=None,
                    created_at=1.0,
                    updated_at=1.0,
                )
            )
            sessions = SessionService(lambda: store.accounts, ttl_hours=web.session_ttl_hours, clock=lambda: 1_000.0)
            sessions.open("account-ttl", user_agent=None)
            conn = sqlite3.connect(tmp_path / "app.db")
            try:
                created_at, expires_at = conn.execute("SELECT created_at, expires_at FROM session").fetchone()
            finally:
                conn.close()
        finally:
            store.close()

        response = Response()
        set_session_cookie(response, "value", web)
        cookie = _cookie(response.headers["set-cookie"])[SESSION_COOKIE]

        assert int(cookie["max-age"]) == expires_at - created_at

    @pytest.mark.parametrize("secure", [True, False])
    def test_clear_carries_the_same_attributes(self, secure: bool) -> None:
        """The clearing cookie names the same cookie, with an empty value and ``Max-Age=0``."""
        response = Response()
        clear_session_cookie(response, WebConfig(cookie_secure=secure))
        cookie = _cookie(response.headers["set-cookie"])[SESSION_COOKIE]
        assert cookie.value == ""
        assert cookie["max-age"] == "0"
        assert cookie["httponly"] is True
        assert cookie["samesite"] == "strict"
        assert cookie["path"] == "/"
        assert bool(cookie["secure"]) is secure

    def test_the_name_is_v1s_own(self) -> None:
        """Never v0's ``tm_session``."""
        assert SESSION_COOKIE == "tm_v1_session"
