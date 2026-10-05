"""Unit tests for ``personalscraper.app.store.store`` — the repositories it hands out and its transaction.

Each repository is one per open store; ``immediate()`` is all-or-nothing across them.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.account_repository import AccountRow
from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.rights import Right
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


class TestImmediate:
    """``immediate()`` — BEGIN IMMEDIATE … COMMIT / ROLLBACK."""

    def test_commits(self, store: AppStore) -> None:
        """Every write inside lands."""
        with store.immediate():
            store.accounts.insert_account(_account())
            store.settings.set_setting("k", "v")
        assert store.accounts.account("account-alice") is not None and store.settings.setting("k") == "v"

    def test_rolls_back_on_an_exception(self, store: AppStore) -> None:
        """An exception inside undoes every write, multi-statement ones included, and propagates."""
        with pytest.raises(RuntimeError), store.immediate():
            store.accounts.insert_account(_account())
            store.roles.insert_role(
                RoleRow(id="role-1", name="X", kind=RoleKind.ORDINARY, rights=frozenset({Right.LIBRARY_READ})), now=1.0
            )
            raise RuntimeError("boom")
        assert store.accounts.account("account-alice") is None
        assert store.roles.role("role-1") is None

    def test_original_error_survives_a_transaction_ended_by_sqlite(self, store: AppStore) -> None:
        """When SQLite already ended the transaction, the block's own error still propagates."""
        with pytest.raises(RuntimeError, match="boom"), store.immediate():
            store._conn.execute("ROLLBACK")  # what SQLITE_FULL / SQLITE_IOERR do on their own
            raise RuntimeError("boom")
        assert not store._conn.in_transaction

    def test_failed_commit_releases_the_writer_lock(self, store: AppStore) -> None:
        """A COMMIT refused (deferred foreign key) propagates and leaves no open transaction."""
        with pytest.raises(sqlite3.IntegrityError), store.immediate():
            store._conn.execute("PRAGMA defer_foreign_keys = ON")
            store.accounts.insert_account(_account(role_id="role-that-does-not-exist"))
        assert not store._conn.in_transaction
        assert store.accounts.account("account-alice") is None

    def test_writes_across_repositories_are_one_transaction(self, store: AppStore) -> None:
        """Accounts and sessions written in one ``immediate()`` that raises midway leave no row."""
        with pytest.raises(RuntimeError), store.immediate():
            store.accounts.insert_account(_account())
            session_id = store.sessions.insert_session(_session())
            store.accounts.set_sign_in_allowed("account-alice", allowed=False, now=11.0)
            raise RuntimeError("boom")
        assert store.accounts.account("account-alice") is None
        assert store.sessions.session(session_id) is None
