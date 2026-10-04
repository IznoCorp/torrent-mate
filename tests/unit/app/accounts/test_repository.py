"""Unit tests for ``personalscraper.app.accounts.repository`` — rows ↔ dataclasses over ``app.db``.

Every method round-trips its dataclass; the base's own refusals (a taken e-mail, a second
admin role, a second role for one start kind) surface as ``sqlite3.IntegrityError``; and
``immediate()`` is all-or-nothing.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.repository import (
    AccountRepository,
    AccountRow,
    PlexLinkRow,
    PlexPinRow,
    RoleRow,
    SessionRow,
)
from personalscraper.app.accounts.rights import Right
from personalscraper.app.store.store import AppStore

_OWN = frozenset(
    {
        Right.LIBRARY_READ,
        Right.ACQUISITION_REQUEST,
        Right.ACQUISITION_FOLLOW,
        Right.ACQUISITION_TODO_VIEW,
        Right.ACQUISITION_PILOT_OWN,
        Right.ACQUISITION_PAUSE_OWN,
    }
)


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


def _session(token_hash: str = "hash-1") -> SessionRow:
    """Build a session row (its id is assigned on insert).

    Args:
        token_hash: The cookie value's hash.

    Returns:
        The row.
    """
    return SessionRow(
        id=0,
        account_id="account-alice",
        token_hash=token_hash,
        created_at=30.0,
        expires_at=90.0,
        last_seen_at=30.0,
        revoked_at=None,
        user_agent="UA",
    )


class TestStore:
    """``AppStore.accounts``."""

    def test_is_one_repository_per_open_store(self, store: AppStore) -> None:
        """The same repository on every access."""
        assert store.accounts is store.accounts

    def test_close_drops_it(self, store: AppStore) -> None:
        """A closed store refuses to hand it out."""
        _ = store.accounts
        store.close()
        with pytest.raises(RuntimeError):
            _ = store.accounts


class TestRoles:
    """Roles, their rights and the start kinds."""

    def test_reads_the_five_seeds(self, repo: AccountRepository) -> None:
        """The seeds, in seed order, with their kinds, rights and starts; no seed has a name."""
        assert repo.roles() == [
            RoleRow(id="admin", name=None, kind=RoleKind.ADMIN, rights=frozenset(), default_for=frozenset()),
            RoleRow(
                id="household", name=None, kind=RoleKind.ORDINARY, rights=_OWN, default_for=frozenset({"plexHome"})
            ),
            RoleRow(
                id="plex-guest",
                name=None,
                kind=RoleKind.ORDINARY,
                rights=frozenset({Right.LIBRARY_READ}),
                default_for=frozenset({"plexGuest"}),
            ),
            RoleRow(id="requester", name=None, kind=RoleKind.ORDINARY, rights=_OWN, default_for=frozenset()),
            RoleRow(
                id="local-guest",
                name=None,
                kind=RoleKind.ORDINARY,
                rights=frozenset({Right.LIBRARY_READ}),
                default_for=frozenset({"local"}),
            ),
        ]

    def test_role_reads_one_or_none(self, repo: AccountRepository) -> None:
        """By id; an unknown id is None."""
        role = repo.role("admin")
        assert role is not None and role.kind is RoleKind.ADMIN
        assert repo.role("role-missing") is None

    def test_insert_role_round_trips(self, repo: AccountRepository) -> None:
        """A new role reads back as written, starts included."""
        role = RoleRow(
            id="role-1",
            name="Friends",
            kind=RoleKind.ORDINARY,
            rights=frozenset({Right.LIBRARY_READ, Right.SYSTEM_VIEW}),
        )
        repo.insert_role(role, now=5.0)
        assert repo.role("role-1") == role

    def test_insert_role_with_a_held_start_is_refused_whole(self, repo: AccountRepository) -> None:
        """A start kind already held: IntegrityError, and no half-written role."""
        role = RoleRow(
            id="role-1", name="X", kind=RoleKind.ORDINARY, rights=frozenset(), default_for=frozenset({"local"})
        )
        with pytest.raises(sqlite3.IntegrityError):
            repo.insert_role(role, now=5.0)
        assert repo.role("role-1") is None

    def test_a_second_admin_role_is_refused(self, repo: AccountRepository) -> None:
        """The base holds one admin role."""
        with pytest.raises(sqlite3.IntegrityError):
            repo.insert_role(RoleRow(id="role-1", name="X", kind=RoleKind.ADMIN, rights=frozenset()), now=5.0)

    def test_update_role_stores_a_name_and_replaces_the_rights(self, repo: AccountRepository) -> None:
        """A rename stores its text; the rights list is replaced whole."""
        repo.update_role("requester", name="Requesters", rights=frozenset({Right.LIBRARY_READ}), now=6.0)
        role = repo.role("requester")
        assert role is not None
        assert (role.name, role.rights) == ("Requesters", frozenset({Right.LIBRARY_READ}))

    def test_update_role_with_nothing_keeps_both(self, repo: AccountRepository) -> None:
        """``None`` leaves the field as it was."""
        repo.update_role("requester", name=None, rights=None, now=6.0)
        role = repo.role("requester")
        assert role is not None
        assert (role.name, role.rights) == (None, _OWN)

    def test_role_for_start(self, repo: AccountRepository) -> None:
        """The role a start kind begins on."""
        role = repo.role_for_start("plexGuest")
        assert role is not None and role.id == "plex-guest"

    def test_set_role_start_moves_the_start(self, repo: AccountRepository) -> None:
        """The start kind now names the other role; the old one loses it."""
        repo.set_role_start("local", "requester")
        role = repo.role_for_start("local")
        assert role is not None and role.id == "requester"
        starts = {r.id: r.default_for for r in repo.roles()}
        assert (starts["requester"], starts["local-guest"]) == (frozenset({"local"}), frozenset())


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


class TestSessions:
    """Sessions."""

    def test_insert_returns_the_id_and_round_trips(self, repo: AccountRepository) -> None:
        """The base assigns the id; the row reads back by its hash."""
        repo.insert_account(_account())
        session_id = repo.insert_session(_session())
        assert repo.session_by_hash("hash-1") == SessionRow(**{**_session().__dict__, "id": session_id})
        assert repo.session_by_hash("hash-missing") is None

    def test_touch_and_revoke(self, repo: AccountRepository) -> None:
        """``last_seen_at`` moves; ``revoked_at`` is set."""
        repo.insert_account(_account())
        session_id = repo.insert_session(_session())
        repo.touch_session(session_id, now=40.0)
        repo.revoke_session(session_id, now=50.0)
        row = repo.session_by_hash("hash-1")
        assert row is not None and (row.last_seen_at, row.revoked_at) == (40.0, 50.0)

    def test_revoke_sessions_of_with_no_exception_revokes_every_live_one(self, repo: AccountRepository) -> None:
        """``except_id=None`` revokes every live session of the account and no other account's."""
        repo.insert_account(_account())
        repo.insert_account(_account("account-bob", "bob@example.org"))
        for token_hash in ("hash-1", "hash-2", "hash-3"):
            repo.insert_session(_session(token_hash))
        already = repo.insert_session(_session("hash-old"))
        repo.revoke_session(already, now=35.0)
        repo.insert_session(replace(_session("hash-bob"), account_id="account-bob"))
        assert repo.revoke_sessions_of("account-alice", except_id=None, now=50.0) == 3
        for token_hash in ("hash-1", "hash-2", "hash-3"):
            row = repo.session_by_hash(token_hash)
            assert row is not None and row.revoked_at == 50.0
        old = repo.session_by_hash("hash-old")
        assert old is not None and old.revoked_at == 35.0
        bob = repo.session_by_hash("hash-bob")
        assert bob is not None and bob.revoked_at is None


class TestPinsAndSettings:
    """Plex PINs and the application's settings."""

    def test_pin_round_trips_checked_and_consumed(self, repo: AccountRepository) -> None:
        """Inserted, checked, consumed."""
        pin = PlexPinRow(
            pin_id=9,
            code="ABCD",
            nonce_hash="n",
            created_at=1.0,
            expires_at=2.0,
            last_checked_at=None,
            consumed_at=None,
        )
        repo.insert_pin(pin)
        assert repo.pin(9) == pin
        repo.mark_pin_checked(9, now=1.5)
        repo.consume_pin(9, now=1.7)
        assert repo.pin(9) == PlexPinRow(**{**pin.__dict__, "last_checked_at": 1.5, "consumed_at": 1.7})
        assert repo.pin(10) is None

    def test_setting_set_read_and_replaced(self, repo: AccountRepository) -> None:
        """Absent, set, replaced."""
        assert repo.setting("plex.client_identifier") is None
        repo.set_setting("plex.client_identifier", "one")
        repo.set_setting("plex.client_identifier", "two")
        assert repo.setting("plex.client_identifier") == "two"


class TestImmediate:
    """``immediate()`` — BEGIN IMMEDIATE … COMMIT / ROLLBACK."""

    def test_commits(self, repo: AccountRepository) -> None:
        """Every write inside lands."""
        with repo.immediate():
            repo.insert_account(_account())
            repo.set_setting("k", "v")
        assert repo.account("account-alice") is not None and repo.setting("k") == "v"

    def test_rolls_back_on_an_exception(self, repo: AccountRepository) -> None:
        """An exception inside undoes every write, multi-statement ones included, and propagates."""
        with pytest.raises(RuntimeError), repo.immediate():
            repo.insert_account(_account())
            repo.insert_role(
                RoleRow(id="role-1", name="X", kind=RoleKind.ORDINARY, rights=frozenset({Right.LIBRARY_READ})), now=1.0
            )
            raise RuntimeError("boom")
        assert repo.account("account-alice") is None
        assert repo.role("role-1") is None

    def test_original_error_survives_a_transaction_ended_by_sqlite(self, repo: AccountRepository) -> None:
        """When SQLite already ended the transaction, the block's own error still propagates."""
        with pytest.raises(RuntimeError, match="boom"), repo.immediate():
            repo._conn.execute("ROLLBACK")  # what SQLITE_FULL / SQLITE_IOERR do on their own
            raise RuntimeError("boom")
        assert not repo._conn.in_transaction

    def test_failed_commit_releases_the_writer_lock(self, repo: AccountRepository) -> None:
        """A COMMIT refused (deferred foreign key) propagates and leaves no open transaction."""
        with pytest.raises(sqlite3.IntegrityError), repo.immediate():
            repo._conn.execute("PRAGMA defer_foreign_keys = ON")
            repo.insert_account(_account(role_id="role-that-does-not-exist"))
        assert not repo._conn.in_transaction
        assert repo.account("account-alice") is None


class TestSecretsStayOutOfRepr:
    """A row's secret never prints through ``repr`` or ``str``."""

    def test_sentinels_do_not_print(self) -> None:
        """Hash, ciphertext, token hash and nonce hash are absent from both renderings."""
        rows = [
            AccountRow("a", "n", "e@x.org", "", "r", "SENTINEL-PASSWORD-HASH", 1.0, 1.0),
            PlexLinkRow("a", 1, "u", "p", "owner", b"SENTINEL-CIPHERTEXT", 1.0, 1.0, None),
            SessionRow(1, "a", "SENTINEL-TOKEN-HASH", 1.0, 2.0, 1.0, None, None),
            PlexPinRow(1, "c", "SENTINEL-NONCE-HASH", 1.0, None, None, None),
        ]
        for row in rows:
            for text in (repr(row), str(row)):
                assert "SENTINEL" not in text
