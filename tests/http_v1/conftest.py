"""Shared builders for the v1 sub-application's tests."""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow, RoleRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.service import AccountService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.composition import build_app_services
from personalscraper.app.services import AppServices
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.app import create_v1_app
from personalscraper.http_v1.perimeter import ActorResolver
from personalscraper.http_v1.session_cookie import SESSION_COOKIE

#: The role an ordinary role with listed rights is created as, in ``v1_client``.
LISTED_ROLE_ID = "role-listed"


@pytest.fixture(autouse=True)
def _no_plex_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave the composed Plex door without a server, so no v1 test can reach plex.tv.

    ``tests/conftest.py`` loads the repository's ``.env``: its ``PLEX_TOKEN`` would give the
    door built by ``build_app_services`` a real server and a real plex.tv client. Emptied, the
    door refuses ``plex.server_unreachable`` before asking plex.tv; a test of the door swaps in
    one over fakes.

    Args:
        monkeypatch: pytest's monkeypatch.
    """
    monkeypatch.setenv("PLEX_TOKEN", "")


@pytest.fixture
def make_v1_services(test_config: Config) -> Iterator[Callable[[], AppServices]]:
    """Return a factory building the process's services over the synthetic config, closed at teardown.

    Their ``app.db`` lives under the config's temporary ``data_dir``.

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.

    Yields:
        A callable returning ``build_app_services``'s services.
    """
    built: list[AppServices] = []

    def _make() -> AppServices:
        """Build the services.

        Returns:
            The services, inert until first use.
        """
        services = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]
        built.append(services)
        return services

    yield _make
    for services in built:
        services.close()


@pytest.fixture
def make_v1_app(test_config: Config, make_v1_services: Callable[[], AppServices]) -> Callable[..., FastAPI]:
    """Return a factory building the v1 sub-application over the synthetic config.

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.
        make_v1_services: The services factory.

    Returns:
        A callable ``make(resolver=None)`` returning ``create_v1_app``'s application.
    """

    def _make(resolver: ActorResolver | None = None) -> FastAPI:
        """Build the sub-application over the synthetic config and fresh services.

        Args:
            resolver: The actor resolver; ``None`` keeps the default (the session cookie).

        Returns:
            The v1 sub-application.
        """
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        return create_v1_app(test_config, settings, make_v1_services(), resolver=resolver)

    return _make


def _with_ceiling(services: AppServices, ceiling: InstanceCeiling, idle_days: int) -> AppServices:
    """Rebuild the session and account services under a fixed ceiling.

    Args:
        services: The services to derive from.
        ceiling: The ceiling every resolution reads.
        idle_days: The sessions' idle lifetime.

    Returns:
        The same services, but for ``sessions`` and ``accounts``.
    """
    store = services.app_store
    sessions = SessionService(lambda: store.accounts, idle_days=idle_days, ceiling=lambda: ceiling)
    accounts = AccountService(lambda: store.accounts, sessions, services.event_bus)
    return dataclasses.replace(services, sessions=sessions, accounts=accounts)


@pytest.fixture
def v1_client(test_config: Config, make_v1_services: Callable[[], AppServices]) -> Callable[..., TestClient]:
    """Return a factory: a client of the v1 sub-application, signed in through a real session (DESIGN C.10).

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.
        make_v1_services: The services factory (its ``app.db`` is temporary).

    Returns:
        A callable ``make(role="household", rights=None, ceiling=None, server_access=None)``:
        ``role`` names a seeded role, or ``None`` for a client with no session; ``rights``,
        when given, signs in on a new ordinary role carrying exactly them; ``ceiling``, when
        given, replaces the environment's; ``server_access`` links the account to Plex.
        The client carries the session in ``tm_v1_session``.
    """
    numbers = itertools.count(1)

    def _make(
        role: str | None = "household",
        rights: frozenset[Right] | None = None,
        ceiling: InstanceCeiling | None = None,
        server_access: str | None = None,
    ) -> TestClient:
        """Build the client, and the account and session it signs in with.

        Args:
            role: The seeded role's id, or ``None`` for no session.
            rights: The rights of a new ordinary role to sign in on instead.
            ceiling: A fixed instance ceiling, or ``None`` for the environment's.
            server_access: ``owner`` or ``shared`` to link the account to Plex.

        Returns:
            The test client.
        """
        services = make_v1_services()
        if ceiling is not None:
            services = _with_ceiling(services, ceiling, test_config.web.session_idle_days)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        client = TestClient(create_v1_app(test_config, settings, services), raise_server_exceptions=False)
        if role is None:
            return client
        repo = services.app_store.accounts
        role_id = role
        if rights is not None:
            role_id = LISTED_ROLE_ID
            repo.insert_role(RoleRow(id=role_id, name="Listed", kind=RoleKind.ORDINARY, rights=rights), now=1.0)
        number = next(numbers)
        account_id = f"account-{number}"
        repo.insert_account(
            AccountRow(
                id=account_id,
                name=f"Account {number}",
                email=f"account-{number}@example.org",
                avatar="",
                role_id=role_id,
                password_hash=None,
                created_at=1.0,
                updated_at=1.0,
            )
        )
        if server_access is not None:
            repo.upsert_plex_link(
                PlexLinkRow(
                    account_id=account_id,
                    plex_id=number,
                    plex_uuid=f"uuid-{number}",
                    plex_username=f"plex-{number}",
                    server_access=server_access,  # type: ignore[arg-type]
                    token_ciphertext=None,
                    token_stored_at=None,
                    linked_at=1.0,
                    last_sign_in_at=None,
                )
            )
        client.cookies.set(SESSION_COOKIE, services.sessions.open(account_id, user_agent="pytest"))
        return client

    return _make
