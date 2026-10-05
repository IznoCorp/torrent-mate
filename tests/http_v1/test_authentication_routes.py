"""The ``authentication`` tag's session routes: ``readAccount``, ``signOut``, ``signIn``, ``changeOwnPassword``, ``setOwnLanguage``.

The session is v1's own (``tm_v1_session``); v0's ``tm_session`` never signs a v1 request
in. ``readAccount`` answers the contract's ``Account``, its ``forbiddenWrites`` being the
instance's ceiling; ``signOut`` revokes the session and clears its cookie; ``signIn`` opens
a new session from an e-mail and a password, refusing every failure as ``auth.refused``;
``changeOwnPassword`` replaces a local account's password and ends its other sessions;
``setOwnLanguage`` sets the signed-in account's own language, and no other's.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from personalscraper.app.accounts.avatar import GRAVATAR_SIZE
from personalscraper.app.accounts.passwords import PASSWORD_MINIMUM, hash_password
from personalscraper.app.accounts.ratelimit import MAX_FAILED_ATTEMPTS
from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.services import AppServices
from personalscraper.app.store.store import AppStore
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.web import WebConfig
from personalscraper.i18n import Language
from personalscraper.http_v1.models.accounts import ResetAccountPasswordBody
from personalscraper.http_v1.models.authentication import ChangeOwnPasswordBody
from personalscraper.http_v1.session_cookie import SESSION_COOKIE, clear_session_cookie, set_session_cookie
from tests.conftest import LoggedEvents

#: The Gravatar key of the seeded account's e-mail, ``account-1@example.org``.
_GRAVATAR_DIGEST = hashlib.sha256(b"account-1@example.org").hexdigest()

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
        """The account, its seeded role (no name, its start kinds), signs in locally, its Gravatar."""
        client = v1_client(role="household")
        role = _services(client).app_store.accounts.role("household")
        assert role is not None

        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json() == {
            "id": "account-1",
            "name": "Account 1",
            "email": "account-1@example.org",
            "avatar": f"https://www.gravatar.com/avatar/{_GRAVATAR_DIGEST}?d=404&s={GRAVATAR_SIZE}",
            "role": {
                "id": "household",
                "kind": "ordinary",
                "rights": sorted(right.value for right in role.rights),
                "defaultFor": ["plexHome"],
            },
            "signInKind": "local",
            "forbiddenWrites": [],
            "language": "en",
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

    @pytest.mark.parametrize("server_access", ["owner", "shared"])
    def test_a_plex_linked_account_shows_its_plex_picture(
        self, v1_client: Callable[..., TestClient], server_access: str
    ) -> None:
        """B-695: a linked account is shown its plex.tv picture, over its Gravatar, with no token kept."""
        response = v1_client(server_access=server_access).get("/auth/me")
        assert response.json()["avatar"] == "https://plex.tv/users/uuid-1/avatar"

    def test_an_account_with_no_email_and_no_link_has_no_avatar(self, v1_client: Callable[..., TestClient]) -> None:
        """Neither source: the property is absent, and the interface draws the initial."""
        client = v1_client()
        conn = _services(client).app_store.accounts._conn  # noqa: SLF001 — no repository method blanks an e-mail
        conn.execute("UPDATE account SET email = ''")
        assert "avatar" not in client.get("/auth/me").json()

    def test_the_stored_avatar_column_is_not_the_source(self, v1_client: Callable[..., TestClient]) -> None:
        """One place decides: a value left in ``account.avatar`` never outranks the resolution."""
        client = v1_client(server_access="owner")
        conn = _services(client).app_store.accounts._conn  # noqa: SLF001 — no repository method sets an avatar
        conn.execute("UPDATE account SET avatar = 'https://example.invalid/stale.png'")
        assert client.get("/auth/me").json()["avatar"] == "https://plex.tv/users/uuid-1/avatar"

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
        assert cookie["samesite"] == "lax"
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
    def test_a_failure_is_auth_refused(
        self, v1_client: Callable[..., TestClient], email: str, password: str, logged_events: LoggedEvents
    ) -> None:
        """401 ``auth.refused``, no cookie, and neither credential anywhere in the answer or the log."""
        client = v1_client(role=None)
        _seed_password_account(client)

        with logged_events() as logs:
            response = client.post("/auth/login", json={"email": email, "password": password})

        assert response.status_code == 401
        assert response.json()["code"] == "auth.refused"
        assert "set-cookie" not in response.headers
        for secret in (email, password):
            assert secret not in response.text
            assert secret not in str(logs)

    def test_a_cut_account_is_access_disabled_once_its_password_is_proven(
        self, v1_client: Callable[..., TestClient]
    ) -> None:
        """The right password: 403 ``auth.access_disabled``, no cookie; a wrong one stays 401 ``auth.refused``."""
        client = v1_client(role=None)
        account_id = _seed_password_account(client)
        _services(client).app_store.accounts.set_sign_in_allowed(account_id, allowed=False, now=2.0)

        cut = client.post("/auth/login", json={"email": "local@example.org", "password": _PASSWORD})
        wrong = client.post("/auth/login", json={"email": "local@example.org", "password": "wrong password"})

        assert cut.status_code == 403
        assert cut.json()["code"] == "auth.access_disabled"
        assert "set-cookie" not in cut.headers
        assert wrong.status_code == 401
        assert wrong.json()["code"] == "auth.refused"

    def test_a_cross_origin_post_is_request_cross_origin(self, v1_client: Callable[..., TestClient]) -> None:
        """A cross-origin POST is 403 ``request.cross_origin`` even with right credentials, and opens no session."""
        client = v1_client(role=None)
        email = "local@example.org"
        _seed_password_account(client, email)

        response = client.post(
            "/auth/login", json={"email": email, "password": _PASSWORD}, headers={"Origin": "https://evil.example"}
        )

        assert response.status_code == 403
        assert response.json()["code"] == "request.cross_origin"
        assert "set-cookie" not in response.headers

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

    def test_a_success_on_another_account_does_not_reset_the_budget(self, v1_client: Callable[..., TestClient]) -> None:
        """Four failures on one account, a sign-in to another, one more failure: 429 ``auth.rate_limited``."""
        client = v1_client(role=None)
        _seed_password_account(client)
        _seed_password_account(client, "guest@example.org")
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            assert client.post("/auth/login", json={"email": "local@example.org", "password": "no"}).status_code == 401
        assert client.post("/auth/login", json={"email": "guest@example.org", "password": _PASSWORD}).status_code == 200
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


def _with_password(client: TestClient) -> str:
    """Give the client's signed-in account :data:`_PASSWORD`.

    Args:
        client: A signed-in test client.

    Returns:
        The account's key.
    """
    services = _services(client)
    actor = services.sessions.resolve(client.cookies.get(SESSION_COOKIE) or "")
    assert actor is not None
    services.app_store.accounts.set_password_hash(actor.account_id, hash_password(_PASSWORD), now=1.0)
    return actor.account_id


class TestChangeOwnPassword:
    """``PUT /auth/password`` — ``changeOwnPassword``, a local account's own password."""

    _NEW = "A brand-new passphrase 7"

    def test_changes_it_and_ends_the_other_sessions(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``{"ok": true}``; the new password signs in, the old does not; the caller's session stays, others end."""
        client = v1_client(role="local-guest")
        account_id = _with_password(client)
        elsewhere = _services(client).sessions.open(account_id, user_agent="another browser")

        response = client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": self._NEW})

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert client.get("/auth/me").status_code == 200
        assert _services(client).sessions.resolve(elsewhere) is None
        email = f"{account_id}@example.org"
        login = client.post("/auth/login", json={"email": email, "password": self._NEW})
        assert login.status_code == 200
        old = client.post("/auth/login", json={"email": email, "password": _PASSWORD})
        assert old.status_code == 401

    def test_the_other_session_is_refused_on_the_wire(self, v1_client: Callable[..., TestClient]) -> None:
        """A request carrying the other session's value is 401 ``auth.required`` after the change."""
        client = v1_client(role="local-guest")
        account_id = _with_password(client)
        mine = client.cookies.get(SESSION_COOKIE)
        elsewhere = _services(client).sessions.open(account_id, user_agent="another browser")

        client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": self._NEW})

        client.cookies.set(SESSION_COOKIE, elsewhere)
        refused = client.get("/auth/me")
        assert refused.status_code == 401
        assert refused.json()["code"] == "auth.required"
        client.cookies.set(SESSION_COOKIE, mine)
        assert client.get("/auth/me").status_code == 200

    @pytest.mark.parametrize(
        ("server_access", "code"),
        [("owner", "password.held_by_cli"), ("shared", "auth.plex_only")],
        ids=["owner", "plex-linked"],
    )
    def test_a_password_held_elsewhere_is_403(
        self, v1_client: Callable[..., TestClient], server_access: str, code: str
    ) -> None:
        """The owner's fallback is the CLI's; a Plex-linked account holds none."""
        client = v1_client(role="household", server_access=server_access)
        _with_password(client)
        response = client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": self._NEW})
        assert response.status_code == 403
        assert response.json()["code"] == code

    def test_a_wrong_current_password_is_400(
        self, v1_client: Callable[..., TestClient], logged_events: LoggedEvents
    ) -> None:
        """400 ``password.current_wrong``; no password in the answer or the log."""
        client = v1_client(role="local-guest")
        _with_password(client)
        with logged_events() as logs:
            response = client.put("/auth/password", json={"currentPassword": "wrong one", "newPassword": self._NEW})
        assert response.status_code == 400
        assert response.json()["code"] == "password.current_wrong"
        for secret in ("wrong one", self._NEW, _PASSWORD):
            assert secret not in response.text
            assert secret not in str(logs)

    def test_a_short_new_password_names_the_minimum(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``password.too_short`` with ``params.minimum``."""
        client = v1_client(role="local-guest")
        _with_password(client)
        short = "x" * (PASSWORD_MINIMUM - 1)
        response = client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": short})
        assert response.status_code == 400
        assert response.json()["code"] == "password.too_short"
        assert response.json()["params"] == {"minimum": PASSWORD_MINIMUM}

    def test_a_weak_new_password_is_too_weak(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``password.too_weak`` with ``params.minimum``; the weak password not echoed."""
        client = v1_client(role="local-guest")
        _with_password(client)
        weak = "a brand-new passphrase"
        response = client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": weak})
        assert response.status_code == 400
        assert response.json()["code"] == "password.too_weak"
        assert response.json()["params"] == {"minimum": PASSWORD_MINIMUM}
        assert weak not in response.text

    def test_the_sixth_wrong_current_password_is_rate_limited(self, v1_client: Callable[..., TestClient]) -> None:
        """Five wrong current passwords: the sixth attempt is 429 ``auth.rate_limited``, the right one included."""
        client = v1_client(role="local-guest")
        _with_password(client)
        for _ in range(MAX_FAILED_ATTEMPTS):
            client.put("/auth/password", json={"currentPassword": "wrong one", "newPassword": self._NEW})
        response = client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": self._NEW})
        assert response.status_code == 429
        assert response.json()["code"] == "auth.rate_limited"

    def test_without_a_session_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """401 ``auth.required``."""
        response = v1_client(role=None).put(
            "/auth/password", json={"currentPassword": _PASSWORD, "newPassword": self._NEW}
        )
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_refused_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write on one's own account: 403 ``instance.read_only`` under ``WEB_ROLE=staging``."""
        client = v1_client(role="local-guest")
        _with_password(client)
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        response = client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": self._NEW})
        assert response.status_code == 403
        assert response.json()["code"] == "instance.read_only"

    def test_a_cross_origin_put_is_request_cross_origin(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``request.cross_origin``; the password is not changed."""
        client = v1_client(role="local-guest")
        _with_password(client)
        response = client.put(
            "/auth/password",
            json={"currentPassword": _PASSWORD, "newPassword": self._NEW},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "request.cross_origin"
        again = client.put("/auth/password", json={"currentPassword": _PASSWORD, "newPassword": self._NEW})
        assert again.status_code == 200

    def test_the_bodies_never_show_a_password(self) -> None:
        """Neither password body's ``repr`` nor ``str`` holds the passwords it carries."""
        change = ChangeOwnPasswordBody(current_password=_PASSWORD, new_password=self._NEW)
        reset = ResetAccountPasswordBody(password=self._NEW)
        for text in (repr(change), str(change), repr(reset), str(reset)):
            assert _PASSWORD not in text
            assert self._NEW not in text

    def test_a_missing_field_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``request.invalid``, the password typed not echoed."""
        response = v1_client(role="local-guest").put("/auth/password", json={"newPassword": self._NEW})
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert self._NEW not in response.text


class TestSetOwnLanguage:
    """``PUT /auth/language`` — ``setOwnLanguage``, the signed-in account's own language (FG-1 B)."""

    def test_sets_it_and_reads_it_back(self, v1_client: Callable[..., TestClient]) -> None:
        """200 with the ``Account`` as now held; ``readAccount`` answers the language chosen."""
        client = v1_client(role="household")

        response = client.put("/auth/language", json={"language": "fr"})

        assert response.status_code == 200
        assert response.json()["language"] == "fr"
        assert response.json()["id"] == "account-1"
        assert client.get("/auth/me").json()["language"] == "fr"

    def test_another_account_keeps_its_own(self, v1_client: Callable[..., TestClient]) -> None:
        """Only the caller's row moves: another account of the same store keeps its language."""
        client = v1_client(role="household")
        repo = _services(client).app_store.accounts
        repo.insert_account(
            AccountRow(
                id="account-other",
                name="Other",
                email="other@example.org",
                avatar="",
                role_id="household",
                password_hash=None,
                created_at=1.0,
                updated_at=1.0,
                language=Language.EN,
            )
        )

        assert client.put("/auth/language", json={"language": "fr"}).status_code == 200

        other = repo.account("account-other")
        assert other is not None and other.language is Language.EN

    @pytest.mark.parametrize("language", ["de", "", "EN", None])
    def test_a_value_outside_language_is_request_invalid(
        self, v1_client: Callable[..., TestClient], language: str | None
    ) -> None:
        """400 ``request.invalid``; the language held unchanged."""
        client = v1_client(role="household")
        response = client.put("/auth/language", json={"language": language})
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert client.get("/auth/me").json()["language"] == "en"

    def test_without_a_session_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """401 ``auth.required``."""
        response = v1_client(role=None).put("/auth/language", json={"language": "fr"})
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_refused_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write on one's own account: 403 ``instance.read_only`` under ``WEB_ROLE=staging``, nothing written."""
        client = v1_client(role="household")
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        response = client.put("/auth/language", json={"language": "fr"})
        assert response.status_code == 403
        assert response.json()["code"] == "instance.read_only"
        assert client.get("/auth/me").json()["language"] == "en"

    def test_a_cross_origin_put_is_request_cross_origin(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``request.cross_origin``; the language is not changed."""
        client = v1_client(role="household")
        response = client.put("/auth/language", json={"language": "fr"}, headers={"Origin": "https://evil.example"})
        assert response.status_code == 403
        assert response.json()["code"] == "request.cross_origin"
        assert client.get("/auth/me").json()["language"] == "en"


class TestCookie:
    """The ``tm_v1_session`` cookie's attributes."""

    @pytest.mark.parametrize("secure", [True, False])
    def test_set_carries_the_attributes(self, secure: bool) -> None:
        """``HttpOnly``, ``SameSite=Lax``, ``Path=/``, ``Max-Age`` = idle lifetime, ``Secure`` per ``cookie_secure``."""
        web = WebConfig(cookie_secure=secure, session_idle_days=3)
        response = Response()
        set_session_cookie(response, "value", web)
        header = response.headers["set-cookie"]
        cookie = _cookie(header)[SESSION_COOKIE]
        assert cookie.value == "value"
        assert cookie["httponly"] is True
        assert cookie["samesite"] == "lax"
        assert cookie["path"] == "/"
        assert cookie["max-age"] == str(3 * 86_400)
        assert bool(cookie["secure"]) is secure

    def test_max_age_is_the_sessions_lifetime(self, test_config: Config, tmp_path: Path) -> None:
        """For one configured ``session_idle_days``, ``Max-Age`` == the session's ``expires_at - created_at``."""
        web = test_config.web.model_copy(update={"session_idle_days": 5})
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
            sessions = SessionService(lambda: store.accounts, idle_days=web.session_idle_days, clock=lambda: 1_000.0)
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
        assert cookie["samesite"] == "lax"
        assert cookie["path"] == "/"
        assert bool(cookie["secure"]) is secure

    @pytest.mark.parametrize("origin", ["https://evil.example", "null"], ids=["other-site", "opaque"])
    def test_lax_keeps_the_origin_check_as_the_csrf_guard(
        self, v1_client: Callable[..., TestClient], origin: str
    ) -> None:
        """Under ``SameSite=Lax`` a write carrying the session from another origin is still 403, nothing written."""
        client = v1_client(role="admin")
        roles_before = client.get("/accounts").json()["roles"]

        created = client.post("/roles", json={"name": "Forged", "rights": []}, headers={"Origin": origin})
        deleted = client.delete("/roles/requester", headers={"Origin": origin})

        for response in (created, deleted):
            assert response.status_code == 403
            assert response.json()["code"] == "request.cross_origin"
        assert client.get("/accounts").json()["roles"] == roles_before

    def test_the_name_is_v1s_own(self) -> None:
        """Never v0's ``tm_session``."""
        assert SESSION_COOKIE == "tm_v1_session"
