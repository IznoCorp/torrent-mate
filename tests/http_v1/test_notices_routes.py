"""``GET /notices`` — ``readNotices``: the signed-in account's in-app notices, its own only.

A notice is a code and its parameters, the interface words it in the account's language. The
services the application is built with listen for :class:`PlexSessionOpened` on their bus, so a
Plex sign-in reaches the account's notices without any other wiring.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from personalscraper.app.accounts.events import PlexSessionOpened
from personalscraper.app.accounts.model import Account
from personalscraper.app.services import AppServices
from personalscraper.http_v1.session_cookie import SESSION_COOKIE


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts on a production instance: no ceiling from the environment.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "prod")


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


class TestReadNotices:
    """``GET /notices`` — ``readNotices``."""

    def test_a_plex_session_opened_on_the_bus_is_the_callers_notice(self, v1_client: Callable[..., TestClient]) -> None:
        """The event on the services' bus becomes the account's notice: its code and its device."""
        client = v1_client(role="household")
        _services(client).event_bus.emit(PlexSessionOpened(account_id=_caller_id(client), device="Firefox · macOS"))

        response = client.get("/notices")

        assert response.status_code == 200
        (notice,) = response.json()["notices"]
        assert notice["code"] == "account.sign_in.device"
        assert notice["params"] == {"device": "Firefox · macOS"}
        assert isinstance(notice["id"], int)
        assert isinstance(notice["createdAt"], float | int)

    def test_the_newest_first(self, v1_client: Callable[..., TestClient]) -> None:
        """Two notices: the later one leads."""
        client = v1_client(role="household")
        notices = _services(client).app_store.notices
        caller = _caller_id(client)
        notices.insert_notice(caller, "account.sign_in.unknown_device", {}, now=10.0)
        notices.insert_notice(caller, "account.sign_in.device", {"device": "Safari · iOS"}, now=20.0)

        codes = [notice["code"] for notice in client.get("/notices").json()["notices"]]

        assert codes == ["account.sign_in.device", "account.sign_in.unknown_device"]

    def test_never_another_accounts_notice(self, v1_client: Callable[..., TestClient]) -> None:
        """A notice of another account in the same store is not the caller's."""
        client = v1_client(role="household")
        services = _services(client)
        services.app_store.accounts.insert_account(
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
        services.event_bus.emit(PlexSessionOpened(account_id="account-other", device=None))

        assert client.get("/notices").json() == {"notices": []}

    def test_a_notice_answers_its_read_state(self, v1_client: Callable[..., TestClient]) -> None:
        """A new notice is unread, a marked one carries the time it was read."""
        client = v1_client(role="household")
        notices = _services(client).app_store.notices
        caller = _caller_id(client)
        read = notices.insert_notice(caller, "account.sign_in.device", {}, now=10.0)
        notices.insert_notice(caller, "account.sign_in.unknown_device", {}, now=20.0)
        notices.mark_read_up_to(caller, read, now=30.0)

        by_code = {notice["code"]: notice for notice in client.get("/notices").json()["notices"]}

        assert by_code["account.sign_in.device"]["readAt"] == 30.0
        assert "readAt" not in by_code["account.sign_in.unknown_device"]

    def test_without_a_session_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """401 ``auth.required``."""
        response = v1_client(role=None).get("/notices")
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_answers_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A read: the read-only instance answers it."""
        client = v1_client(role="household")
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        assert client.get("/notices").status_code == 200


class TestMarkNoticesRead:
    """``POST /notices/read`` — ``markNoticesRead``: the caller's notices up to one, marked read."""

    def test_marks_the_callers_notices_up_to_the_given_one(self, v1_client: Callable[..., TestClient]) -> None:
        """The notices up to ``upTo`` are read; a later one stays unread."""
        client = v1_client(role="household")
        notices = _services(client).app_store.notices
        caller = _caller_id(client)
        seen = notices.insert_notice(caller, "account.sign_in.device", {}, now=10.0)
        later = notices.insert_notice(caller, "account.sign_in.device", {}, now=20.0)

        response = client.post("/notices/read", json={"upTo": seen})

        assert response.status_code == 200
        assert response.json() == {"marked": 1}
        read_at = {row.id: row.read_at for row in notices.notices_of(caller, limit=10)}
        assert read_at[seen] is not None
        assert read_at[later] is None

    def test_never_marks_another_accounts_notice(self, v1_client: Callable[..., TestClient]) -> None:
        """A notice of another account, named by its id, stays unread and nothing is marked."""
        client = v1_client(role="household")
        services = _services(client)
        services.app_store.accounts.insert_account(
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
        theirs = services.app_store.notices.insert_notice("account-other", "account.sign_in.device", {}, now=10.0)

        response = client.post("/notices/read", json={"upTo": theirs})

        assert response.status_code == 200
        assert response.json() == {"marked": 0}
        assert services.app_store.notices.notices_of("account-other", limit=10)[0].read_at is None

    def test_a_body_without_up_to_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``request.invalid``."""
        response = v1_client(role="household").post("/notices/read", json={})
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"

    def test_an_up_to_beyond_sqlite_integers_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``request.invalid`` — a notice id SQLite cannot hold never reaches the base."""
        response = v1_client(role="household").post("/notices/read", json={"upTo": 2**63})
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"

    def test_the_highest_sqlite_integer_is_accepted(self, v1_client: Callable[..., TestClient]) -> None:
        """The bound is inclusive: ``2**63 - 1`` marks what is there and answers 200."""
        response = v1_client(role="household").post("/notices/read", json={"upTo": 2**63 - 1})
        assert response.status_code == 200
        assert response.json() == {"marked": 0}

    def test_without_a_session_is_auth_required(self, v1_client: Callable[..., TestClient]) -> None:
        """401 ``auth.required``."""
        response = v1_client(role=None).post("/notices/read", json={"upTo": 1})
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"

    def test_refused_on_the_read_only_instance(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write: 403 ``instance.read_only`` under ``WEB_ROLE=staging``; the notice stays unread."""
        client = v1_client(role="household")
        notices = _services(client).app_store.notices
        caller = _caller_id(client)
        notice = notices.insert_notice(caller, "account.sign_in.device", {}, now=10.0)
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

        response = client.post("/notices/read", json={"upTo": notice})

        assert response.status_code == 403
        assert response.json()["code"] == "instance.read_only"
        assert notices.notices_of(caller, limit=10)[0].read_at is None

    def test_a_replayed_key_answers_the_first_answer_and_marks_nothing_more(
        self, v1_client: Callable[..., TestClient]
    ) -> None:
        """The same ``Idempotency-Key`` replays the first answer."""
        client = v1_client(role="household")
        notices = _services(client).app_store.notices
        caller = _caller_id(client)
        notice = notices.insert_notice(caller, "account.sign_in.device", {}, now=10.0)
        headers = {"Idempotency-Key": "mark-notices-0001"}

        first = client.post("/notices/read", json={"upTo": notice}, headers=headers)
        second = client.post("/notices/read", json={"upTo": notice}, headers=headers)

        assert first.json() == {"marked": 1}
        assert second.json() == {"marked": 1}
