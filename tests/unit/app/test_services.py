"""Unit tests for ``personalscraper.app.services`` and its builder in ``app.composition``."""

from __future__ import annotations

import hashlib

import pytest

from personalscraper.api.plex import PlexClient
from personalscraper.app.accounts.plex_sign_in import PRODUCTS
from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.composition import build_app_services
from personalscraper.app.library.service import LibraryService
from personalscraper.app.services import AppServices
from personalscraper.conf.environment import Environment
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus


def test_build_app_services_is_inert(test_config: Config) -> None:
    """The builder opens nothing: a fresh bus, and ``close`` is safe to call."""
    services = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]

    assert isinstance(services, AppServices)
    assert isinstance(services.event_bus, EventBus)
    services.close()


def test_each_build_has_its_own_bus(test_config: Config) -> None:
    """Two builds share no bus (one per process, never a module global)."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert (
        build_app_services(test_config, settings).event_bus is not build_app_services(test_config, settings).event_bus
    )


def test_the_library_service_is_built_inert(test_config: Config) -> None:
    """The library service is built over the configured stores without opening them; no key, no client."""
    services = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]

    assert isinstance(services.library, LibraryService)
    assert test_config.acquire.db_path is not None
    assert not test_config.acquire.db_path.exists()
    services.close()


def test_the_configured_idle_lifetime_reaches_the_sessions(test_config: Config) -> None:
    """``web.session_idle_days`` = 5: a session the built service opens expires five days after it opens."""
    config = test_config.model_copy(update={"web": test_config.web.model_copy(update={"session_idle_days": 5})})
    services = build_app_services(config, Settings(_env_file=None))  # type: ignore[call-arg]
    try:
        repo = services.app_store.accounts
        repo.insert_account(
            AccountRow(
                id="account-alice",
                name="Alice",
                email="alice@example.org",
                avatar="",
                role_id="household",
                password_hash=None,
                created_at=1.0,
                updated_at=1.0,
            )
        )
        token = services.sessions.open("account-alice", user_agent=None)
        row = repo.session_by_hash(hashlib.sha256(token.encode()).hexdigest())
        assert row is not None
        assert row.expires_at - row.created_at == 5 * 86_400
    finally:
        services.close()


def test_the_plex_door_is_composed_from_the_configuration_and_the_settings(
    test_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The door's forward address is ``web.plex_forward_url``, its server the one ``PLEX_URL`` and ``PLEX_TOKEN`` name.

    The server's own token is the one the owner is cross-checked against, and the environment
    names the product on plex.tv.
    """
    monkeypatch.setattr("personalscraper.conf.environment.current_environment", lambda: Environment.STAGING)
    config = test_config.model_copy(
        update={"web": test_config.web.model_copy(update={"plex_forward_url": "https://tm.example.org/"})}
    )
    settings = Settings(_env_file=None, plex_url="http://plex.example.invalid:32400", plex_token="planted-server-token")  # type: ignore[call-arg]
    services = build_app_services(config, settings)
    try:
        door = services.plex_sign_in
        assert door._forward_url == "https://tm.example.org/"
        assert door._server_token == "planted-server-token"
        assert isinstance(door._server, PlexClient)
        assert door._server.base_url == "http://plex.example.invalid:32400"
        assert door._server._token == "planted-server-token"
        assert door._environment is Environment.STAGING
        assert PRODUCTS[door._environment] == "TorrentMate (staging)"
    finally:
        services.close()


def test_the_plex_door_has_no_server_without_a_token(test_config: Config) -> None:
    """No ``PLEX_TOKEN``: no server client is built, and the door admits nobody."""
    settings = Settings(_env_file=None, plex_url="http://plex.example.invalid:32400", plex_token="")  # type: ignore[call-arg]
    services = build_app_services(test_config, settings)
    try:
        assert services.plex_sign_in._server is None
        assert services.plex_sign_in._server_token == ""
        assert services.plex_sign_in._forward_url is None
    finally:
        services.close()


@pytest.mark.parametrize(("keys", "malformed"), [("", False), ("not-a-fernet-key", True)])
def test_malformed_token_keys_leave_the_door_without_a_vault_and_say_so(
    test_config: Config, keys: str, malformed: bool
) -> None:
    """A malformed ``PLEX_TOKEN_KEYS`` does not stop the build: no vault, and the door knows the keys were bad."""
    settings = Settings(_env_file=None, plex_token_keys=keys)  # type: ignore[call-arg]
    services = build_app_services(test_config, settings)
    try:
        assert services.plex_sign_in._vault is None
        assert services.plex_sign_in._vault_keys_malformed is malformed
    finally:
        services.close()


def test_every_suite_runs_with_no_plex_server_configured() -> None:
    """Whatever the shell or ``.env`` holds, a test's settings name no Plex token, no vault key, the default address.

    The root ``conftest.py`` empties them for every suite, so no composed door outside
    ``tests/http_v1`` can build a real server or plex.tv client.
    """
    settings = Settings()

    assert settings.plex_token == ""
    assert settings.plex_token_keys == ""
    assert settings.plex_url == Settings.model_fields["plex_url"].default
