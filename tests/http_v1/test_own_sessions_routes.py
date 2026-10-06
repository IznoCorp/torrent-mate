"""The account's own sessions: ``readOwnSessions`` lists them, ``revokeOwnSession`` ends one.

Only the caller's live sessions are listed, the one it calls with flagged ``current``; a
revoked one ends at once — its next request is 401 ``auth.required``. The current session is
never revoked by this route (``session.current``), and a session the caller does not hold —
another account's, an unknown one, one already ended — is 404 ``session.unknown``: the answer
never tells another account's session from one that does not exist.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from personalscraper.app.accounts.model import Account
from personalscraper.app.services import AppServices
from personalscraper.http_v1.session_cookie import SESSION_COOKIE

#: A desktop Firefox on macOS, as the browser sends it.
_FIREFOX_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:131.0) Gecko/20100101 Firefox/131.0"


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


def _caller_id(client: TestClient) -> str:
    """The account the client is signed in as.

    Args:
        client: A signed-in test client.

    Returns:
        Its account's key.
    """
    actor = _services(client).sessions.resolve(client.cookies.get(SESSION_COOKIE) or "")
    assert actor is not None
    return actor.account_id


def _session_id(client: TestClient, token: str) -> int:
    """The key of the live session a value names.

    Args:
        client: The test client.
        token: The session's value.

    Returns:
        Its key.
    """
    session_id = _services(client).sessions.live_session_id(token)
    assert session_id is not None
    return session_id


def _other_account(client: TestClient) -> str:
    """Create another account in the client's store.

    Args:
        client: The test client.

    Returns:
        The other account's key.
    """
    _services(client).app_store.accounts.insert_account(
        Account(
            id="account-other",
            name="Other",
            email="other@example.org",
            avatar="",
            role_id="household",
            password_hash=None,
            created_at=1.0,
            updated_at=1.0,
        )
    )
    return "account-other"


class TestReadOwnSessions:
    """``GET /auth/sessions`` — ``readOwnSessions``."""

    def test_lists_the_callers_live_sessions_the_current_one_flagged(
        self, v1_client: Callable[..., TestClient]
    ) -> None:
        """The caller's two sessions, its own flagged current, each with its device and its times."""
        client = v1_client(role="household")
        mine = client.cookies.get(SESSION_COOKIE) or ""
        sessions = _services(client).sessions
        elsewhere = sessions.open(_caller_id(client), user_agent=_FIREFOX_MAC)

        response = client.get("/auth/sessions")

        assert response.status_code == 200
        listed = {row["id"]: row for row in response.json()["sessions"]}
        assert set(listed) == {_session_id(client, mine), _session_id(client, elsewhere)}
        assert listed[_session_id(client, mine)]["current"] is True
        other = listed[_session_id(client, elsewhere)]
        assert other["current"] is False
        assert other["device"] == "Firefox · macOS"
        assert isinstance(other["createdAt"], float | int)
        assert isinstance(other["lastSeenAt"], float | int)

    def test_never_lists_another_accounts_session(self, v1_client: Callable[..., TestClient]) -> None:
        """A session of another account in the same store is not in the caller's list."""
        client = v1_client(role="household")
        theirs = _services(client).sessions.open(_other_account(client), user_agent=_FIREFOX_MAC)

        listed = [row["id"] for row in client.get("/auth/sessions").json()["sessions"]]

        assert _session_id(client, theirs) not in listed
        assert len(listed) == 1

    def test_a_revoked_session_is_not_listed(self, v1_client: Callable[..., TestClient]) -> None:
        """A signed-out session of the caller is gone from its list."""
        client = v1_client(role="household")
        sessions = _services(client).sessions
        ended = sessions.open(_caller_id(client), user_agent=_FIREFOX_MAC)
        ended_id = _session_id(client, ended)
        sessions.close(ended)

        listed = [row["id"] for row in client.get("/auth/sessions").json()["sessions"]]

        assert ended_id not in listed

    def test_an_unknown_browser_has_no_device(self, v1_client: Callable[..., TestClient]) -> None:
        """A session opened with no user agent answers ``device: null``."""
        client = v1_client(role="household")
        bare = _services(client).sessions.open(_caller_id(client), user_agent=None)

        listed = {row["id"]: row for row in client.get("/auth/sessions").json()["sessions"]}

        assert listed[_session_id(client, bare)]["device"] is None

    def test_without_a_session_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """401 ``auth.required``."""
        response = v1_client(role=None).get("/auth/sessions")
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_answers_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A read: the read-only instance answers it."""
        client = v1_client(role="household")
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        assert client.get("/auth/sessions").status_code == 200


class TestRevokeOwnSession:
    """``DELETE /auth/sessions/{sessionId}`` — ``revokeOwnSession``."""

    def test_revokes_it_and_its_next_request_is_401(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``{"ok": true}``; the revoked value is refused at once; the caller's session stays."""
        client = v1_client(role="household")
        mine = client.cookies.get(SESSION_COOKIE) or ""
        elsewhere = _services(client).sessions.open(_caller_id(client), user_agent=_FIREFOX_MAC)
        assert _services(client).sessions.resolve(elsewhere) is not None

        response = client.delete(f"/auth/sessions/{_session_id(client, elsewhere)}")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        client.cookies.set(SESSION_COOKIE, elsewhere)
        refused = client.get("/auth/me")
        assert refused.status_code == 401
        assert refused.json()["code"] == "auth.required"
        client.cookies.set(SESSION_COOKIE, mine)
        assert client.get("/auth/me").status_code == 200

    def test_the_current_session_is_refused(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``session.current``: signing out is ``signOut``'s; the session stays live."""
        client = v1_client(role="household")
        mine = client.cookies.get(SESSION_COOKIE) or ""

        response = client.delete(f"/auth/sessions/{_session_id(client, mine)}")

        assert response.status_code == 409
        assert response.json()["code"] == "session.current"
        assert client.get("/auth/me").status_code == 200

    def test_another_accounts_session_is_404_and_stays_live(self, v1_client: Callable[..., TestClient]) -> None:
        """404 ``session.unknown`` — never a 403 that would tell it exists; it keeps signing in."""
        client = v1_client(role="household")
        theirs = _services(client).sessions.open(_other_account(client), user_agent=_FIREFOX_MAC)

        response = client.delete(f"/auth/sessions/{_session_id(client, theirs)}")

        assert response.status_code == 404
        assert response.json()["code"] == "session.unknown"
        assert _services(client).sessions.resolve(theirs) is not None

    def test_an_unknown_id_is_404(self, v1_client: Callable[..., TestClient]) -> None:
        """404 ``session.unknown``, the same answer as another account's."""
        response = v1_client(role="household").delete("/auth/sessions/999999")
        assert response.status_code == 404
        assert response.json()["code"] == "session.unknown"

    def test_an_ended_session_is_404(self, v1_client: Callable[..., TestClient]) -> None:
        """A session already signed out is no live session: 404 ``session.unknown``."""
        client = v1_client(role="household")
        sessions = _services(client).sessions
        ended = sessions.open(_caller_id(client), user_agent=_FIREFOX_MAC)
        ended_id = _session_id(client, ended)
        sessions.close(ended)

        response = client.delete(f"/auth/sessions/{ended_id}")

        assert response.status_code == 404
        assert response.json()["code"] == "session.unknown"

    def test_without_a_session_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """401 ``auth.required``."""
        response = v1_client(role=None).delete("/auth/sessions/1")
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_refused_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write: 403 ``instance.read_only`` under ``WEB_ROLE=staging``; the session stays live."""
        client = v1_client(role="household")
        elsewhere = _services(client).sessions.open(_caller_id(client), user_agent=_FIREFOX_MAC)
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

        response = client.delete(f"/auth/sessions/{_session_id(client, elsewhere)}")

        assert response.status_code == 403
        assert response.json()["code"] == "instance.read_only"
        assert _services(client).sessions.resolve(elsewhere) is not None

    def test_a_cross_origin_delete_is_request_cross_origin(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``request.cross_origin``; the session stays live."""
        client = v1_client(role="household")
        elsewhere = _services(client).sessions.open(_caller_id(client), user_agent=_FIREFOX_MAC)

        response = client.delete(
            f"/auth/sessions/{_session_id(client, elsewhere)}", headers={"Origin": "https://evil.example"}
        )

        assert response.status_code == 403
        assert response.json()["code"] == "request.cross_origin"
        assert _services(client).sessions.resolve(elsewhere) is not None

    def test_a_non_numeric_id_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``request.invalid``."""
        response = v1_client(role="household").delete("/auth/sessions/abc")
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
