"""Unit tests for ``personalscraper.app.accounts.sessions`` — v1's sessions over ``app.db``.

The cookie value is never stored (only its sha256 hex); an expired, revoked or unknown
value resolves to nobody; the role and its rights are read on every resolution, so a
role change bites at the next call; ``last_seen_at`` is written at most every
:data:`SESSION_TOUCH_INTERVAL_S`.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.sessions import SESSION_TOUCH_INTERVAL_S, SessionService
from personalscraper.app.store.store import AppStore

_ACCOUNT_ID = "account-alice"
_TTL_HOURS = 2
_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)


class _Clock:
    """A settable clock.

    Attributes:
        now: The time it answers (epoch seconds).
    """

    def __init__(self, now: float = 1_000.0) -> None:
        """Start the clock.

        Args:
            now: The initial time.
        """
        self.now = now

    def __call__(self) -> float:
        """Answer the current time.

        Returns:
            :attr:`now`.
        """
        return self.now


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` holding one account on the seeded ``household`` role.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    app_store.accounts.insert_account(
        AccountRow(
            id=_ACCOUNT_ID,
            name="Alice",
            email="alice@example.org",
            avatar="",
            role_id="household",
            password_hash=None,
            created_at=1.0,
            updated_at=1.0,
        )
    )
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def clock() -> _Clock:
    """A settable clock.

    Returns:
        The clock.
    """
    return _Clock()


@pytest.fixture
def sessions(store: AppStore, clock: _Clock) -> SessionService:
    """The session service over the store, the clock and no ceiling.

    Args:
        store: The store.
        clock: The clock.

    Returns:
        The service.
    """
    return SessionService(lambda: store.accounts, ttl_hours=_TTL_HOURS, ceiling=lambda: _NO_CEILING, clock=clock)


def _rows(store: AppStore) -> list[tuple[object, ...]]:
    """Every session row, read straight from the file.

    Args:
        store: The store.

    Returns:
        Each row's ``token_hash``, ``expires_at``, ``last_seen_at``, ``revoked_at``, ``user_agent``.
    """
    conn = sqlite3.connect(store._db_path)  # noqa: SLF001 — the test reads the file itself, as an attacker would
    try:
        return conn.execute(
            "SELECT token_hash, expires_at, last_seen_at, revoked_at, user_agent FROM session"
        ).fetchall()
    finally:
        conn.close()


class TestOpen:
    """``SessionService.open``."""

    def test_the_row_holds_the_hash_and_never_the_token(self, sessions: SessionService, store: AppStore) -> None:
        """Only the sha256 hex of the value reaches the file."""
        token = sessions.open(_ACCOUNT_ID, user_agent="UA")
        rows = _rows(store)
        assert len(rows) == 1
        assert rows[0][0] == hashlib.sha256(token.encode()).hexdigest()
        assert all(token not in str(cell) for cell in rows[0])
        assert rows[0][4] == "UA"

    def test_two_sessions_have_distinct_unguessable_values(self, sessions: SessionService) -> None:
        """Each value is a fresh 32-byte url-safe secret."""
        first = sessions.open(_ACCOUNT_ID, user_agent=None)
        second = sessions.open(_ACCOUNT_ID, user_agent=None)
        assert first != second
        assert len(first) >= 43

    def test_expiry_is_absolute_at_the_ttl(self, sessions: SessionService, store: AppStore, clock: _Clock) -> None:
        """``expires_at`` = creation + ``ttl_hours``."""
        sessions.open(_ACCOUNT_ID, user_agent=None)
        assert _rows(store)[0][1] == clock.now + _TTL_HOURS * 3600


class TestResolve:
    """``SessionService.resolve``."""

    def test_a_live_session_resolves_to_its_account_and_role(self, sessions: SessionService) -> None:
        """The actor carries the account, its role, the role's rights and the ceiling."""
        actor = sessions.resolve(sessions.open(_ACCOUNT_ID, user_agent=None))
        assert actor is not None
        assert actor.account_id == _ACCOUNT_ID
        assert actor.name == "Alice"
        assert actor.role_id == "household"
        assert actor.role_kind is RoleKind.ORDINARY
        assert Right.LIBRARY_READ in actor.role_rights
        assert actor.ceiling == _NO_CEILING

    def test_an_unknown_value_is_nobody(self, sessions: SessionService) -> None:
        """A value no session holds resolves to ``None``."""
        sessions.open(_ACCOUNT_ID, user_agent=None)
        assert sessions.resolve("not-a-session") is None

    def test_an_expired_session_is_nobody(self, sessions: SessionService, clock: _Clock) -> None:
        """At its ``expires_at`` the session no longer resolves, however recently used."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += _TTL_HOURS * 3600
        assert sessions.resolve(token) is None

    def test_a_revoked_session_is_nobody(self, sessions: SessionService) -> None:
        """``close`` ends the session."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        sessions.close(token)
        assert sessions.resolve(token) is None

    def test_a_role_change_bites_at_the_next_call(self, sessions: SessionService, store: AppStore) -> None:
        """The role and its rights are read on every call, never cached in the session."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        before = sessions.resolve(token)
        store.accounts.set_role(_ACCOUNT_ID, "local-guest", now=2.0)
        after = sessions.resolve(token)
        assert before is not None and after is not None
        assert after.role_id == "local-guest"
        assert after.role_rights == store.accounts.role("local-guest").rights  # type: ignore[union-attr]
        assert after.role_rights != before.role_rights

    def test_an_admin_role_carries_no_rights_list(self, sessions: SessionService, store: AppStore) -> None:
        """Admin is a kind, not a list."""
        store.accounts.set_role(_ACCOUNT_ID, "admin", now=2.0)
        actor = sessions.resolve(sessions.open(_ACCOUNT_ID, user_agent=None))
        assert actor is not None
        assert actor.role_kind is RoleKind.ADMIN
        assert actor.role_rights == frozenset()

    def test_the_ceiling_is_read_at_each_call(self, store: AppStore, clock: _Clock) -> None:
        """The instance ceiling is the one current at resolution."""
        ceilings = [_NO_CEILING, InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)]
        service = SessionService(lambda: store.accounts, ttl_hours=_TTL_HOURS, ceiling=lambda: ceilings[0], clock=clock)
        token = service.open(_ACCOUNT_ID, user_agent=None)
        ceilings.reverse()
        actor = service.resolve(token)
        assert actor is not None
        assert actor.ceiling.forbidden == frozenset({Right.LIBRARY_DELETE})


class TestTouch:
    """``last_seen_at`` is written at most every :data:`SESSION_TOUCH_INTERVAL_S`."""

    def test_the_interval_is_five_minutes(self) -> None:
        """300 s, as DESIGN § 3.4 sets it."""
        assert SESSION_TOUCH_INTERVAL_S == 300.0

    def test_unchanged_within_the_interval_then_updated(
        self, sessions: SessionService, store: AppStore, clock: _Clock
    ) -> None:
        """A use within 300 s of the last write leaves it; a use after rewrites it."""
        opened_at = clock.now
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now = opened_at + SESSION_TOUCH_INTERVAL_S - 1
        assert sessions.resolve(token) is not None
        assert _rows(store)[0][2] == opened_at
        clock.now = opened_at + SESSION_TOUCH_INTERVAL_S
        assert sessions.resolve(token) is not None
        assert _rows(store)[0][2] == clock.now


class TestClose:
    """``SessionService.close``."""

    def test_close_records_the_revocation_time(self, sessions: SessionService, store: AppStore, clock: _Clock) -> None:
        """``revoked_at`` = now."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += 10
        sessions.close(token)
        assert _rows(store)[0][3] == clock.now

    def test_close_is_idempotent(self, sessions: SessionService, store: AppStore, clock: _Clock) -> None:
        """A second close keeps the first revocation time; an unknown value is a no-op."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        sessions.close(token)
        first = _rows(store)[0][3]
        clock.now += 10
        sessions.close(token)
        sessions.close("not-a-session")
        assert _rows(store)[0][3] == first
