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
