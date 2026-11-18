"""Unit tests for ``personalscraper.app.accounts.session_repository`` — sessions ↔ dataclasses over ``app.db``.

Every method round-trips its dataclass; a renewal is conditional on the row as it was read.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.session_repository import SessionRepository, SessionRow
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
def repo(store: AppStore) -> SessionRepository:
    """The store's session repository.

    Args:
        store: The fresh store.

    Returns:
        Its repository.
    """
    return store.sessions


def _account(
    account_id: str = "account-alice", email: str = "alice@example.org", role_id: str = "household"
) -> Account:
    """Build an account row.

    Args:
        account_id: Its key.
        email: Its e-mail.
        role_id: Its role.

    Returns:
        The row.
    """
    return Account(
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


class TestSessions:
    """Sessions."""

    def test_insert_returns_the_id_and_round_trips(self, store: AppStore, repo: SessionRepository) -> None:
        """The base assigns the id; the row reads back by its hash."""
        store.accounts.insert_account(_account())
        session_id = repo.insert_session(_session())
        assert repo.session_by_hash("hash-1") == SessionRow(**{**_session().__dict__, "id": session_id})
        assert repo.session_by_hash("hash-missing") is None

    def test_a_session_reads_back_by_its_key(self, store: AppStore, repo: SessionRepository) -> None:
        """``session`` finds the row by its id; an unknown id is ``None``."""
        store.accounts.insert_account(_account())
        session_id = repo.insert_session(_session())
        assert repo.session(session_id) == repo.session_by_hash("hash-1")
        assert repo.session(session_id + 1) is None

    def test_renew_replaces_the_hash_and_moves_the_expiry(self, store: AppStore, repo: SessionRepository) -> None:
        """A renewal from the ``last_seen_at`` read writes the new hash, expiry and use time."""
        store.accounts.insert_account(_account())
        session_id = repo.insert_session(_session())
        seen = repo.session(session_id)
        assert seen is not None
        assert repo.renew_session(
            session_id, seen_at=seen.last_seen_at, token_hash="hash-2", expires_at=900.0, now=40.0
        )
        row = repo.session(session_id)
        assert row is not None and (row.token_hash, row.expires_at, row.last_seen_at) == ("hash-2", 900.0, 40.0)
        assert repo.session_by_hash("hash-1") is None

    def test_renew_from_a_stale_read_or_a_revoked_row_writes_nothing(
        self, store: AppStore, repo: SessionRepository
    ) -> None:
        """Another renewal moved ``last_seen_at``, or the session is revoked: ``False``, nothing written."""
        store.accounts.insert_account(_account())
        session_id = repo.insert_session(_session())
        seen = repo.session(session_id)
        assert seen is not None
        assert repo.renew_session(
            session_id, seen_at=seen.last_seen_at, token_hash="hash-2", expires_at=900.0, now=40.0
        )
        stale = repo.renew_session(
            session_id, seen_at=seen.last_seen_at, token_hash="hash-3", expires_at=990.0, now=41.0
        )
        assert stale is False
        repo.revoke_session(session_id, now=50.0)
        revoked = repo.renew_session(session_id, seen_at=40.0, token_hash="hash-4", expires_at=999.0, now=60.0)
        assert revoked is False
        row = repo.session(session_id)
        assert row is not None and (row.token_hash, row.expires_at, row.revoked_at) == ("hash-2", 900.0, 50.0)

    def test_revoke_sessions_of_with_no_exception_revokes_every_live_one(
        self, store: AppStore, repo: SessionRepository
    ) -> None:
        """``except_id=None`` revokes every live session of the account and no other account's."""
        store.accounts.insert_account(_account())
        store.accounts.insert_account(_account("account-bob", "bob@example.org"))
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
