"""The roster and credential services authorise its actor before it touches a store.

An in-process caller is refused what the v1 perimeter refuses an HTTP one, before any
row is read or written and before the password limiter is consulted; an ``AnyOf``
requirement still opens on any one of its rights.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.account_repository import AccountRow
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.credentials import CredentialService
from personalscraper.app.accounts.passwords import hash_password
from personalscraper.app.accounts.ratelimit import SlidingWindowRateLimiter
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.accounts.roster import RosterService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.errors import AppForbidden, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
#: The read-only clone's ceiling: every write refused, the session's own included.
_READ_ONLY = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)
_PASSWORD = "correct horse battery staple"
_PROVISIONAL = "A provisional one 1!"


class _RecordingLimiter(SlidingWindowRateLimiter):
    """A password limiter recording every key it is asked about.

    Attributes:
        asked: The keys passed to :meth:`allow` or :meth:`record_failure`, in order.
    """

    def __init__(self) -> None:
        """Start with nothing asked."""
        super().__init__()
        self.asked: list[str] = []

    def allow(self, key: str) -> bool:
        """Record the key, then answer as the real limiter.

        Args:
            key: The limited key.

        Returns:
            The real limiter's answer.
        """
        self.asked.append(key)
        return super().allow(key)

    def record_failure(self, key: str) -> None:
        """Record the key, then count the failure as the real limiter.

        Args:
            key: The limited key.
        """
        self.asked.append(key)
        super().record_failure(key)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` with one household member holding a password.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    app_store.accounts.insert_account(
        AccountRow(
            id="account-household",
            name="Household",
            email="household@example.org",
            avatar="",
            role_id="household",
            password_hash=hash_password(_PASSWORD),
            created_at=1.0,
            updated_at=1.0,
        )
    )
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def limiter() -> _RecordingLimiter:
    """The password-change limiter, recording what it is asked.

    Returns:
        The limiter.
    """
    return _RecordingLimiter()


@pytest.fixture
def accounts(store: AppStore) -> RosterService:
    """The roster service over the store.

    Args:
        store: The store.

    Returns:
        The service.
    """
    return RosterService(store, EventBus())


@pytest.fixture
def credentials(store: AppStore, limiter: _RecordingLimiter) -> CredentialService:
    """The credential service over the store.

    Args:
        store: The store.
        limiter: The password-change limiter.

    Returns:
        The service.
    """
    sessions = SessionService(store, idle_days=1, ceiling=lambda: _NO_CEILING)
    return CredentialService(store, sessions, password_limiter=limiter)


def _household(store: AppStore, ceiling: InstanceCeiling = _NO_CEILING) -> Actor:
    """The household member's actor, its role read from the base.

    Args:
        store: The store.
        ceiling: The instance's ceiling.

    Returns:
        The actor: an ordinary role without ``accounts.manage``.
    """
    role = store.roles.role("household")
    assert role is not None
    assert Right.ACCOUNTS_MANAGE not in role.rights
    return Actor(
        account_id="account-household",
        name="Household",
        role_id=role.id,
        role_kind=role.kind,
        role_rights=role.rights,
        ceiling=ceiling,
    )


def test_an_actor_without_accounts_manage_creates_no_account(store: AppStore, accounts: RosterService) -> None:
    """``right.missing`` on a role within the actor's rights: no row is written."""
    before = [account.id for account in store.accounts.accounts()]

    with pytest.raises(AppForbidden) as refused:
        accounts.create_account(
            _household(store), name="Guest", email="guest@example.org", role_id="local-guest", password=_PROVISIONAL
        )

    assert refused.value.code is RefusalCode.RIGHT_MISSING
    assert refused.value.params == {"rights": [Right.ACCOUNTS_MANAGE.value]}
    assert [account.id for account in store.accounts.accounts()] == before


def test_a_read_only_instance_refuses_the_own_password_before_it_is_checked(
    store: AppStore, credentials: CredentialService, limiter: _RecordingLimiter
) -> None:
    """``instance.read_only`` before the current password is checked: the limiter is never consulted."""
    stored = store.accounts.account("account-household")
    assert stored is not None

    with pytest.raises(AppForbidden) as refused:
        credentials.change_own_password(
            _household(store, _READ_ONLY), "token", current_password="not the password", new_password="A new one 7!"
        )

    assert refused.value.code is RefusalCode.INSTANCE_READ_ONLY
    assert limiter.asked == []
    after = store.accounts.account("account-household")
    assert after is not None
    assert after.password_hash == stored.password_hash


def test_a_reassigner_reads_the_roster(accounts: RosterService) -> None:
    """``readAccounts`` is any of two rights: ``acquisition.reassign`` alone opens it."""
    reassigner = Actor(
        account_id="account-reassigner",
        name="Reassigner",
        role_id="reassigner",
        role_kind=RoleKind.ORDINARY,
        role_rights=frozenset({Right.ACQUISITION_REASSIGN}),
        ceiling=_NO_CEILING,
    )

    roster = accounts.read_roster(reassigner)

    assert [account.id for account in roster.accounts] == ["account-household"]
