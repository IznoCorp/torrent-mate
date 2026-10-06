"""Unit tests for ``personalscraper.app.services`` and its builder in ``app.composition``."""

from __future__ import annotations

import hashlib
import logging

import pytest

from personalscraper.acquire.delete_authority import StrictDeletePermit
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.api.plex import PlexClient
from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.plex_sign_in import PRODUCTS
from personalscraper.app.composition import ONE_ATTEMPT, LazyProviders, build_app_services, build_provider_registry
from personalscraper.app.library.reads import LibraryReads
from personalscraper.app.services import AppServices
from personalscraper.conf.environment import Environment
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus


def test_build_app_services_is_inert(test_config: Config) -> None:
    """The builder opens nothing: the services hold the bus they are handed, and ``close`` is safe to call."""
    services = build_app_services(test_config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]

    assert isinstance(services, AppServices)
    assert isinstance(services.event_bus, EventBus)
    services.close()


def test_the_library_service_is_built_inert(test_config: Config) -> None:
    """The library service is built over the configured stores without opening them; no key, no client."""
    services = build_app_services(test_config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]

    assert isinstance(services.library, LibraryReads)
    assert test_config.acquire.db_path is not None
    assert not test_config.acquire.db_path.exists()
    services.close()


def test_the_configured_idle_lifetime_reaches_the_sessions(test_config: Config) -> None:
    """``web.session_idle_days`` = 5: a session the built service opens expires five days after it opens."""
    config = test_config.model_copy(update={"web": test_config.web.model_copy(update={"session_idle_days": 5})})
    services = build_app_services(config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]
    try:
        repo = services.app_store.accounts
        repo.insert_account(
            Account(
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
        row = services.app_store.sessions.session_by_hash(hashlib.sha256(token.encode()).hexdigest())
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
    services = build_app_services(config, settings, event_bus=EventBus())
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
    services = build_app_services(test_config, settings, event_bus=EventBus())
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
    services = build_app_services(test_config, settings, event_bus=EventBus())
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


def test_the_library_deletes_through_the_strict_permit_over_the_configured_acquire_db(
    test_config: Config,
) -> None:
    """The library's permit reads ``acquire.db`` read-only and refuses what it cannot read (R1); nothing created."""
    services = build_app_services(test_config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]
    try:
        permit = services.deletion._delete_permit
        assert isinstance(permit, StrictDeletePermit)
        assert permit._db_path == test_config.acquire.db_path
        assert test_config.acquire.db_path is not None
        assert not test_config.acquire.db_path.exists()
        assert services.deletion._config is test_config
    finally:
        services.close()


def test_the_library_tells_the_plex_server_the_settings_name(test_config: Config) -> None:
    """``PLEX_URL`` and ``PLEX_TOKEN`` set: the library's deletion tells that server."""
    settings = Settings(_env_file=None, plex_url="http://plex.example.invalid:32400", plex_token="planted-server-token")  # type: ignore[call-arg]
    services = build_app_services(test_config, settings, event_bus=EventBus())
    try:
        plex = services.deletion._plex
        assert isinstance(plex, PlexClient)
        assert plex.base_url == "http://plex.example.invalid:32400"
        assert plex._token == "planted-server-token"
    finally:
        services.close()


def test_the_library_has_no_plex_server_without_a_token(test_config: Config) -> None:
    """No ``PLEX_TOKEN``: the library holds no Plex client, and a deletion reports Plex not configured."""
    services = build_app_services(test_config, Settings(_env_file=None, plex_token=""), event_bus=EventBus())  # type: ignore[call-arg]
    try:
        assert services.deletion._plex is None
    finally:
        services.close()


def test_a_given_bus_is_the_services_bus(test_config: Config) -> None:
    """A process that already holds a bus hands it over: the services publish on that one, not a second."""
    bus = EventBus()
    services = build_app_services(test_config, Settings(_env_file=None), event_bus=bus)  # type: ignore[call-arg]
    try:
        assert services.event_bus is bus
    finally:
        services.close()


def test_the_registry_speaks_the_configured_language(test_config: Config) -> None:
    """``scraper.language`` = ``en-US``: the registry's TMDB and TVDB clients ask in ``en-US``."""
    config = test_config.model_copy(update={"scraper": test_config.scraper.model_copy(update={"language": "en-US"})})
    registry = build_provider_registry(config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]
    try:
        assert registry.get("tmdb")._language == "en-US"  # type: ignore[attr-defined]
        assert registry.get("tvdb")._language == "en-US"  # type: ignore[attr-defined]
    finally:
        registry.close()


def test_a_given_registry_serves_the_library_and_stays_its_owners(test_config: Config) -> None:
    """The library asks the handed-over registry's clients; closing the services leaves that registry to its owner."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    registry = build_provider_registry(test_config, settings, event_bus=EventBus(), retry=ONE_ATTEMPT)
    closed: list[bool] = []
    original_close = registry.close
    registry.close = lambda: closed.append(True)  # type: ignore[method-assign]
    services = build_app_services(test_config, settings, providers=registry, event_bus=EventBus())
    try:
        assert services.sheets._providers.get("tmdb") is registry.get("tmdb")
        assert services.sheets._providers.get("tvdb") is registry.get("tvdb")
    finally:
        services.close()
        assert closed == []
        original_close()


def test_without_a_registry_the_services_build_their_own_lazily(test_config: Config) -> None:
    """No registry handed over: the services build one on the first provider call, with one attempt."""
    services = build_app_services(test_config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]
    providers = services.sheets._providers
    assert isinstance(providers, LazyProviders)
    assert providers._registry is None
    tmdb = providers.get("tmdb")
    assert tmdb is not None
    assert tmdb._transport._policy.retry == ONE_ATTEMPT  # type: ignore[attr-defined]
    registry = providers._registry
    assert registry is not None
    closed: list[bool] = []
    original_close = registry.close
    registry.close = lambda: closed.append(True)  # type: ignore[method-assign]
    services.close()
    assert closed == [True]
    original_close()


def test_the_lazy_registry_and_the_plex_door_are_on_the_process_bus(test_config: Config) -> None:
    """The registry the services build and the Plex door publish on the bus handed in, not another."""
    bus = EventBus()
    settings = Settings(_env_file=None, plex_url="http://plex.example.invalid:32400", plex_token="planted-server-token")  # type: ignore[call-arg]
    services = build_app_services(test_config, settings, event_bus=bus)
    try:
        tmdb = services.sheets._providers.get("tmdb")
        assert tmdb is not None
        assert tmdb._transport._event_bus is bus  # type: ignore[attr-defined]
        assert services.plex_sign_in._bus is bus
    finally:
        services.close()


def test_a_missing_tvdb_key_leaves_tmdb_served(test_config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only ``TMDB_API_KEY`` set, OMDb listed without its key: the library still gets TMDB, and no TVDB."""
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    providers_config = test_config.providers.model_copy(update={"RatingProvider": {"imdb": 1}})
    config = test_config.model_copy(update={"providers": providers_config})
    services = build_app_services(config, Settings(_env_file=None, tvdb_api_key=""), event_bus=EventBus())  # type: ignore[call-arg]
    try:
        assert services.sheets._providers.get("tmdb") is not None
        assert services.sheets._providers.get("tvdb") is None
    finally:
        services.close()


def test_with_neither_key_no_provider_is_served_and_it_is_said_once(
    test_config: Config, caplog: pytest.LogCaptureFixture
) -> None:
    """Neither ``TMDB_API_KEY`` nor ``TVDB_API_KEY``: no client, and ``app.providers.unavailable`` once."""
    caplog.set_level(logging.DEBUG)
    services = build_app_services(
        test_config,
        Settings(_env_file=None, tmdb_api_key="", tvdb_api_key=""),  # type: ignore[call-arg]
        event_bus=EventBus(),
    )
    try:
        assert services.sheets._providers.get("tmdb") is None
        assert services.sheets._providers.get("tvdb") is None
    finally:
        services.close()
    said = [record.msg for record in caplog.records if _unavailable(record)]
    assert len(said) == 1
    assert said[0]["issues"] == ["missing_credentials"]


def test_a_build_that_raises_is_attempted_once_and_said_once(caplog: pytest.LogCaptureFixture) -> None:
    """A builder raising ``RuntimeError``: one attempt over three calls, no client, said once with its type."""
    attempts: list[bool] = []

    def build() -> ProviderRegistry:
        attempts.append(True)
        raise RuntimeError("planted")

    caplog.set_level(logging.DEBUG)
    providers = LazyProviders(build)

    assert [providers.get("tmdb") for _ in range(3)] == [None, None, None]
    assert attempts == [True]
    said = [record.msg for record in caplog.records if _unavailable(record)]
    assert len(said) == 1
    assert said[0]["error"] == "RuntimeError"


def test_a_closed_lookup_builds_nothing(test_config: Config) -> None:
    """``close`` before any call: a later ``get`` builds no registry and answers ``None``."""
    attempts: list[bool] = []

    def build() -> ProviderRegistry:
        attempts.append(True)
        return build_provider_registry(test_config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]

    providers = LazyProviders(build)
    providers.close()

    assert providers.get("tmdb") is None
    assert attempts == []


def _unavailable(record: logging.LogRecord) -> bool:
    """Whether ``record`` is the composition's ``app.providers.unavailable`` event.

    Args:
        record: A captured log record.

    Returns:
        True for that event.
    """
    return (
        record.name == "app.composition"
        and isinstance(record.msg, dict)
        and record.msg["event"] == "app.providers.unavailable"
    )


def test_one_plex_client_serves_the_door_and_the_library(test_config: Config) -> None:
    """``PLEX_TOKEN`` set: the door's server and the library's deletion follow-up are the same client."""
    settings = Settings(_env_file=None, plex_url="http://plex.example.invalid:32400", plex_token="planted-server-token")  # type: ignore[call-arg]
    services = build_app_services(test_config, settings, event_bus=EventBus())
    try:
        assert isinstance(services.deletion._plex, PlexClient)
        assert services.plex_sign_in._server is services.deletion._plex
    finally:
        services.close()


def test_the_rescrape_and_the_services_share_one_run_service(test_config: Config) -> None:
    """A rescrape ask lands in the queue ``services.runs`` reads: both hold the SAME ``RunService``.

    The rescrape service's run service is private, so identity is read there: a second instance would
    queue rescrapes the web never sees nor the supervisor starts.
    """
    services = build_app_services(test_config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]
    try:
        assert services.rescrape._runs is services.runs  # noqa: SLF001
    finally:
        services.close()
