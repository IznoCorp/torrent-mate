"""The ``authentication`` tag's routes served so far: ``readAccount`` and ``signOut``.

The session is v1's own (``tm_v1_session``); v0's ``tm_session`` never signs a v1 request
in. ``readAccount`` answers the contract's ``Account``, its ``forbiddenWrites`` being the
instance's ceiling; ``signOut`` revokes the session and clears its cookie.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.services import AppServices
from personalscraper.app.store.store import AppStore
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.web import WebConfig
from personalscraper.http_v1.session_cookie import SESSION_COOKIE, clear_session_cookie, set_session_cookie


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
