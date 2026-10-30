"""Unit tests for ``CredentialService.system_actor``: who an unattended act is attributed to.

The Plex server's owner, else the first Admin; with neither, the reserved ``system`` account,
logged; an owner that cannot be named (several links, or a link whose account is gone) is logged
and never stops the runs. The instance ceiling binds the actor.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.actor import SYSTEM_ROLE_ID, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.credentials import CredentialService
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.model import Account, PlexLink
from personalscraper.app.accounts.rights import WRITE_RIGHTS
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.store.store import AppStore
from tests.conftest import LoggedEvents

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
_READ_ONLY = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)


def _account(account_id: str, name: str, role_id: str, created_at: float) -> Account:
    """An account row.

    Args:
        account_id: Its key.
        name: Its display name.
        role_id: Its role.
        created_at: Its creation epoch (the order of "first").

    Returns:
        The row.
    """
    return Account(
        id=account_id,
        name=name,
        email=f"{account_id}@example.org",
        avatar="",
        role_id=role_id,
        password_hash=None,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` with no account.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    try:
        yield app_store
    finally:
        app_store.close()


def _owner_link(account_id: str, plex_id: int) -> PlexLink:
    """An owner link of an account.

    Args:
        account_id: The account holding it (it need not exist).
        plex_id: The plex.tv identity, unique per link.

    Returns:
        The link.
    """
    return PlexLink(
        account_id=account_id,
        plex_id=plex_id,
        plex_uuid=f"uuid-{plex_id}",
        plex_username=f"plex-{plex_id}",
        server_access="owner",
        token_ciphertext=None,
        token_stored_at=None,
        linked_at=float(plex_id),
        last_sign_in_at=None,
    )


def _service(store: AppStore, ceiling: InstanceCeiling = _NO_CEILING) -> CredentialService:
    """The credential service over a store, under a ceiling.

    Args:
        store: The store.
        ceiling: The instance's ceiling.

    Returns:
        The service.
    """
    return CredentialService(store, SessionService(store, idle_days=30), ceiling=lambda: ceiling)


def test_the_owner_is_the_system_actor(store: AppStore) -> None:
    """The owner wins over an older Admin, and carries the Admin role."""
    store.accounts.insert_account(_account("account-first", "First", "admin", 1.0))
    store.accounts.insert_account(_account("account-owner", "Owner", "admin", 2.0))
    store.accounts.upsert_plex_link(
        PlexLink(
            account_id="account-owner",
            plex_id=1,
            plex_uuid="uuid-1",
            plex_username="plex-1",
            server_access="owner",
            token_ciphertext=None,
            token_stored_at=None,
            linked_at=1.0,
            last_sign_in_at=None,
        )
    )

    actor = _service(store).system_actor()

    assert (actor.account_id, actor.name) == (AccountId("account-owner"), "Owner")
    assert (actor.role_id, actor.role_kind) == (SYSTEM_ROLE_ID, RoleKind.ADMIN)


def test_without_an_owner_the_first_admin_is_the_system_actor(store: AppStore) -> None:
    """No owner link: the oldest Admin account; an ordinary account is never picked."""
    store.accounts.insert_account(_account("account-local", "Local", "local-guest", 1.0))
    store.accounts.insert_account(_account("account-first", "First", "admin", 2.0))
    store.accounts.insert_account(_account("account-second", "Second", "admin", 3.0))

    actor = _service(store).system_actor()

    assert (actor.account_id, actor.name) == (AccountId("account-first"), "First")


def test_with_neither_the_reserved_system_account_is_used_and_logged(
    store: AppStore, logged_events: LoggedEvents
) -> None:
    """No owner, no Admin: ``system``, and ``app.system_actor_unattributed`` says so."""
    with logged_events() as events:
        actor = _service(store).system_actor()

    assert (actor.account_id, actor.name) == (AccountId("system"), "system")
    assert actor.role_kind is RoleKind.ADMIN
    assert [event["event"] for event in events].count("app.system_actor_unattributed") == 1


def test_an_attributed_actor_logs_nothing(store: AppStore, logged_events: LoggedEvents) -> None:
    """The unattributed warning is for the fallback alone."""
    store.accounts.insert_account(_account("account-first", "First", "admin", 1.0))

    with logged_events() as events:
        _service(store).system_actor()

    assert "app.system_actor_unattributed" not in [event["event"] for event in events]


def test_the_instance_ceiling_binds_the_system_actor(store: AppStore) -> None:
    """A read-only instance gives the system actor its ceiling, in every attribution."""
    assert _service(store, _READ_ONLY).system_actor().ceiling == _READ_ONLY
    store.accounts.insert_account(_account("account-first", "First", "admin", 1.0))
    assert _service(store, _READ_ONLY).system_actor().ceiling == _READ_ONLY


def test_several_owner_links_log_an_error_and_fall_back_to_the_first_admin(
    store: AppStore, logged_events: LoggedEvents
) -> None:
    """A stale second owner link never raises: ERROR logged, the first Admin is attributed."""
    store.accounts.insert_account(_account("account-first", "First", "admin", 1.0))
    store.accounts.insert_account(_account("account-owner-a", "Owner A", "admin", 2.0))
    store.accounts.insert_account(_account("account-owner-b", "Owner B", "admin", 3.0))
    store.accounts.upsert_plex_link(_owner_link("account-owner-a", 1))
    store.accounts.upsert_plex_link(_owner_link("account-owner-b", 2))

    with logged_events() as events:
        actor = _service(store).system_actor()

    assert (actor.account_id, actor.role_kind) == (AccountId("account-first"), RoleKind.ADMIN)
    assert [event["event"] for event in events].count("app.system_actor_ambiguous_owner") == 1
    assert next(e for e in events if e["event"] == "app.system_actor_ambiguous_owner")["log_level"] == "error"


def test_several_owner_links_with_no_admin_fall_back_to_the_system_account(store: AppStore) -> None:
    """Ambiguous owner and no Admin account: the reserved ``system`` account."""
    store.accounts.insert_account(_account("account-owner-a", "Owner A", "local-guest", 2.0))
    store.accounts.insert_account(_account("account-owner-b", "Owner B", "local-guest", 3.0))
    store.accounts.upsert_plex_link(_owner_link("account-owner-a", 1))
    store.accounts.upsert_plex_link(_owner_link("account-owner-b", 2))

    assert _service(store).system_actor().account_id == AccountId("system")


def test_an_owner_link_whose_account_is_gone_is_logged_and_falls_back(
    store: AppStore, tmp_path: Path, logged_events: LoggedEvents
) -> None:
    """The owner's account row is missing: logged, and the first Admin is attributed."""
    store.accounts.insert_account(_account("account-first", "First", "admin", 1.0))
    store.accounts.insert_account(_account("account-gone", "Gone", "admin", 2.0))
    store.accounts.upsert_plex_link(_owner_link("account-gone", 1))
    # A raw connection enforces no foreign key: the account goes, its link stays (a damaged file).
    raw = sqlite3.connect(tmp_path / "app.db")
    try:
        raw.execute("DELETE FROM account WHERE id = 'account-gone'")
        raw.commit()
    finally:
        raw.close()

    with logged_events() as events:
        actor = _service(store).system_actor()

    assert actor.account_id == AccountId("account-first")
    assert [event["event"] for event in events].count("app.system_actor_owner_account_missing") == 1
