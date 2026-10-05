"""Unit tests for ``personalscraper.app.accounts.account_repository`` — accounts and Plex links ↔ dataclasses.

Every method round-trips its dataclass; the base's own refusals (a taken e-mail, one account per
plex id) surface as ``sqlite3.IntegrityError``; and no row's secret prints.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.account_repository import AccountRepository, AccountRow, PlexLinkRow
from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.pin_repository import PlexPinRow
from personalscraper.app.accounts.role_repository import RoleRow
from personalscraper.app.accounts.session_repository import SessionRow
from personalscraper.app.store.store import AppStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` on ``tmp_path``.

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


@pytest.fixture
def repo(store: AppStore) -> AccountRepository:
    """The store's account repository.

    Args:
        store: The fresh store.

    Returns:
        Its repository.
    """
    return store.accounts


def _account(
    account_id: str = "account-alice", email: str = "alice@example.org", role_id: str = "household"
) -> AccountRow:
    """Build an account row.

    Args:
        account_id: Its key.
        email: Its e-mail.
        role_id: Its role.

    Returns:
        The row.
    """
    return AccountRow(
        id=account_id,
        name="Alice",
        email=email,
        avatar="",
        role_id=role_id,
        password_hash=None,
        created_at=10.0,
        updated_at=10.0,
    )


def _link(account_id: str = "account-alice", plex_id: int = 42) -> PlexLinkRow:
    """Build a Plex link row.

    Args:
        account_id: The linked account.
        plex_id: plex.tv's id.

    Returns:
        The row.
    """
    return PlexLinkRow(
        account_id=account_id,
        plex_id=plex_id,
        plex_uuid="uuid-42",
        plex_username="alice",
        server_access="shared",
        token_ciphertext=None,
        token_stored_at=None,
        linked_at=20.0,
        last_sign_in_at=None,
    )


class TestAccounts:
    """Accounts."""

    def test_insert_account_round_trips(self, repo: AccountRepository) -> None:
        """Read back by id, by e-mail (any case) and in the list."""
        account = _account()
        repo.insert_account(account)
        assert repo.account("account-alice") == account
        assert repo.account_by_email("ALICE@example.ORG") == account
        assert repo.accounts() == [account]
        assert repo.account("account-missing") is None
        assert repo.account_by_email("nobody@example.org") is None

    def test_a_taken_email_is_refused_whatever_its_case(self, repo: AccountRepository) -> None:
        """``A@x`` then ``a@X`` → IntegrityError."""
        repo.insert_account(_account(email="A@x"))
        with pytest.raises(sqlite3.IntegrityError):
            repo.insert_account(_account(account_id="account-bob", email="a@X"))

    def test_set_role(self, repo: AccountRepository) -> None:
        """The account's role changes and ``updated_at`` with it."""
        repo.insert_account(_account())
        repo.set_role("account-alice", "requester", now=11.0)
        account = repo.account("account-alice")
        assert account is not None and (account.role_id, account.updated_at) == ("requester", 11.0)

    def test_set_password_hash_sets_and_clears(self, repo: AccountRepository) -> None:
        """A hash is stored, then cleared by ``None``."""
        repo.insert_account(_account())
        repo.set_password_hash("account-alice", "scrypt$1$2$3$s$h", now=12.0)
        account = repo.account("account-alice")
        assert account is not None and (account.password_hash, account.updated_at) == ("scrypt$1$2$3$s$h", 12.0)
        repo.set_password_hash("account-alice", None, now=13.0)
        account = repo.account("account-alice")
        assert account is not None and account.password_hash is None

    def test_set_sign_in_allowed_cuts_and_gives_back(self, repo: AccountRepository) -> None:
        """The access is stored as set, ``updated_at`` with it."""
        repo.insert_account(_account())
        repo.set_sign_in_allowed("account-alice", allowed=False, now=14.0)
        account = repo.account("account-alice")
        assert account is not None and (account.sign_in_allowed, account.updated_at) == (False, 14.0)
        repo.set_sign_in_allowed("account-alice", allowed=True, now=15.0)
        account = repo.account("account-alice")
        assert account is not None and (account.sign_in_allowed, account.updated_at) == (True, 15.0)

    def test_set_role_records_then_clears_the_demotion(self, repo: AccountRepository) -> None:
        """A Plex link's demotion keeps the role left; a later role given clears it."""
        repo.insert_account(_account(role_id="requester"))
        assert repo.account("account-alice").demoted_from is None  # type: ignore[union-attr]
        repo.set_role("account-alice", "household", now=11.0, demoted_from="requester")
        account = repo.account("account-alice")
        assert account is not None and (account.role_id, account.demoted_from) == ("household", "requester")
        repo.set_role("account-alice", "requester", now=12.0)
        account = repo.account("account-alice")
        assert account is not None and (account.role_id, account.demoted_from) == ("requester", None)

    def test_a_deleted_role_leaves_no_dangling_demotion(self, store: AppStore, repo: AccountRepository) -> None:
        """``demoted_from`` names a role by foreign key: deleting that role clears it."""
        store.roles.insert_role(
            RoleRow(id="role-gone", name="Gone", kind=RoleKind.ORDINARY, rights=frozenset()), now=1.0
        )
        repo.insert_account(_account())
        repo.set_role("account-alice", "household", now=11.0, demoted_from="role-gone")
        store.roles.delete_role("role-gone")
        account = repo.account("account-alice")
        assert account is not None and account.demoted_from is None

    def test_count_on_role_kind_and_accounts_on_role(self, repo: AccountRepository) -> None:
        """Counted by the role's kind; listed by the role."""
        repo.insert_account(_account(role_id="admin"))
        repo.insert_account(_account(account_id="account-bob", email="bob@x", role_id="household"))
        repo.insert_account(_account(account_id="account-carol", email="carol@x", role_id="household"))
        assert repo.count_on_role_kind(RoleKind.ADMIN) == 1
        assert repo.count_on_role_kind(RoleKind.ORDINARY) == 2
        assert repo.accounts_on_role("household") == ["account-bob", "account-carol"]
        assert repo.accounts_on_role("requester") == []


class TestPlexLinks:
    """Plex links."""

    def test_upsert_round_trips_and_updates(self, repo: AccountRepository) -> None:
        """Inserted, then replaced on the same account."""
        repo.insert_account(_account())
        repo.upsert_plex_link(_link())
        assert repo.plex_link("account-alice") == _link()
        assert repo.plex_link_by_plex_id(42) == _link()
        updated = PlexLinkRow(**{**_link().__dict__, "server_access": "owner", "last_sign_in_at": 25.0})
        repo.upsert_plex_link(updated)
        assert repo.plex_link("account-alice") == updated
        assert repo.plex_link("account-missing") is None
        assert repo.plex_link_by_plex_id(7) is None

    def test_one_plex_id_links_one_account(self, repo: AccountRepository) -> None:
        """A plex id already linked to another account → IntegrityError."""
        repo.insert_account(_account())
        repo.insert_account(_account(account_id="account-bob", email="bob@x"))
        repo.upsert_plex_link(_link())
        with pytest.raises(sqlite3.IntegrityError):
            repo.upsert_plex_link(_link(account_id="account-bob"))

    def test_token_ciphertext_set_listed_and_cleared(self, repo: AccountRepository) -> None:
        """A kept token is listed; cleared, it is not."""
        repo.insert_account(_account())
        repo.upsert_plex_link(_link())
        assert repo.plex_links_with_token() == []
        repo.set_token_ciphertext("account-alice", b"cipher", now=21.0)
        link = repo.plex_link("account-alice")
        assert link is not None and (link.token_ciphertext, link.token_stored_at) == (b"cipher", 21.0)
        assert repo.plex_links_with_token() == [link]
        repo.set_token_ciphertext("account-alice", None, now=None)
        link = repo.plex_link("account-alice")
        assert link is not None and (link.token_ciphertext, link.token_stored_at) == (None, None)

    def test_an_upsert_without_a_token_keeps_the_sealed_one(self, repo: AccountRepository) -> None:
        """A link written with no ciphertext (no vault) keeps the token sealed before; a new one replaces it."""
        repo.insert_account(_account())
        repo.upsert_plex_link(
            PlexLinkRow(**{**_link().__dict__, "token_ciphertext": b"cipher", "token_stored_at": 21.0})
        )

        repo.upsert_plex_link(PlexLinkRow(**{**_link().__dict__, "last_sign_in_at": 30.0}))

        link = repo.plex_link("account-alice")
        assert link is not None
        assert (link.token_ciphertext, link.token_stored_at, link.last_sign_in_at) == (b"cipher", 21.0, 30.0)
        repo.upsert_plex_link(PlexLinkRow(**{**_link().__dict__, "token_ciphertext": b"new", "token_stored_at": 31.0}))
        link = repo.plex_link("account-alice")
        assert link is not None and (link.token_ciphertext, link.token_stored_at) == (b"new", 31.0)


class TestSecretsStayOutOfRepr:
    """A row's secret never prints through ``repr`` or ``str``."""

    def test_sentinels_do_not_print(self) -> None:
        """Hash, ciphertext, token hash, PIN code and nonce hash are absent from both renderings."""
        rows = [
            AccountRow("a", "n", "e@x.org", "", "r", "SENTINEL-PASSWORD-HASH", 1.0, 1.0),
            PlexLinkRow("a", 1, "u", "p", "owner", b"SENTINEL-CIPHERTEXT", 1.0, 1.0, None),
            SessionRow(1, "a", "SENTINEL-TOKEN-HASH", 1.0, 2.0, 1.0, None, None),
            PlexPinRow(1, "SENTINEL-PIN-CODE", "SENTINEL-NONCE-HASH", 1.0, None, None, None),
        ]
        for row in rows:
            for text in (repr(row), str(row)):
                assert "SENTINEL" not in text
