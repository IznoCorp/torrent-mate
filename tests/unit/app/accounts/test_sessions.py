"""Unit tests for ``personalscraper.app.accounts.sessions`` — v1's sessions over ``app.db``.

The cookie value is never stored (only its sha256 hex); an expired, revoked or unknown
value resolves to nobody; the role and its rights are read on every resolution, so a
role change bites at the next call. A session ends after :data:`_IDLE_DAYS` unused: each
use renews it, at most every :data:`SESSION_RENEWAL_INTERVAL_S`, under a new value; the
replaced value keeps signing in until the new one is presented, then for
:data:`SESSION_ROTATION_GRACE_S`.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import json5
import pytest
from pydantic import ValidationError

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.service import AccountService
from personalscraper.app.accounts.sessions import (
    SESSION_RENEWAL_INTERVAL_S,
    SESSION_ROTATION_GRACE_S,
    SessionService,
)
from personalscraper.app.errors import AppUnauthenticated, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.conf.loader import load_config_dir
from personalscraper.conf.models.web import WebConfig
from personalscraper.core.event_bus import EventBus

_ACCOUNT_ID = "account-alice"
_IDLE_DAYS = 2
_IDLE_S = _IDLE_DAYS * 86_400
_EXAMPLE_DIR = Path(__file__).resolve().parents[4] / "config.example"
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
    return SessionService(lambda: store.accounts, idle_days=_IDLE_DAYS, ceiling=lambda: _NO_CEILING, clock=clock)


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


def _delete_the_role(store: AppStore, role_id: str) -> None:
    """Delete a role its accounts still stand on.

    The schema forbids it with ``foreign_keys=ON`` (``account.role_id`` references
    ``role``), and deleting the account instead cascades its sessions; a separate
    connection, which SQLite opens with foreign keys OFF, reaches the state.

    Args:
        store: The store.
        role_id: The role to delete.
    """
    conn = sqlite3.connect(store._db_path)  # noqa: SLF001 — the test writes the file itself
    try:
        conn.execute("DELETE FROM role WHERE id = ?", (role_id,))
        conn.commit()
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

    def test_expiry_is_the_idle_lifetime_from_now(
        self, sessions: SessionService, store: AppStore, clock: _Clock
    ) -> None:
        """``expires_at`` = creation + ``idle_days``."""
        sessions.open(_ACCOUNT_ID, user_agent=None)
        assert _rows(store)[0][1] == clock.now + _IDLE_S


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
        """At its ``expires_at`` the session no longer resolves."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += _IDLE_S
        assert sessions.resolve(token) is None

    def test_resolve_writes_nothing(self, sessions: SessionService, store: AppStore, clock: _Clock) -> None:
        """``resolve`` reads: past the renewal interval it still leaves the row as it was."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        before = _rows(store)
        clock.now += SESSION_RENEWAL_INTERVAL_S * 2
        assert sessions.resolve(token) is not None
        assert _rows(store) == before

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

    def test_a_session_whose_role_is_gone_is_nobody(self, sessions: SessionService, store: AppStore) -> None:
        """A live session whose account's role was deleted resolves to ``None``."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        _delete_the_role(store, "household")
        assert sessions.resolve(token) is None

    def test_read_account_refuses_once_the_role_is_gone(self, sessions: SessionService, store: AppStore) -> None:
        """An actor resolved before its role vanished is refused ``auth.required``."""
        accounts = AccountService(lambda: store.accounts, sessions, EventBus())
        actor = sessions.resolve(sessions.open(_ACCOUNT_ID, user_agent=None))
        assert actor is not None
        _delete_the_role(store, "household")
        with pytest.raises(AppUnauthenticated) as refused:
            accounts.read_account(actor)
        assert refused.value.code is RefusalCode.AUTH_REQUIRED

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
        service = SessionService(lambda: store.accounts, idle_days=_IDLE_DAYS, ceiling=lambda: ceilings[0], clock=clock)
        token = service.open(_ACCOUNT_ID, user_agent=None)
        ceilings.reverse()
        actor = service.resolve(token)
        assert actor is not None
        assert actor.ceiling.forbidden == frozenset({Right.LIBRARY_DELETE})


class TestIdleLifetime:
    """``web.session_idle_days``: v1's idle lifetime, 30 days unless configured."""

    def test_the_default_is_thirty_days(self) -> None:
        """The model's default."""
        assert WebConfig().session_idle_days == 30

    @pytest.mark.parametrize("days", [0, -1])
    def test_a_lifetime_not_positive_is_refused(self, days: int) -> None:
        """Zero or negative days would end every session as it opens: the model refuses them."""
        with pytest.raises(ValidationError, match="session_idle_days"):
            WebConfig(session_idle_days=days)

    def test_the_example_configuration_names_it(self) -> None:
        """``config.example/web.json5`` sets it, to the default — read raw, not through the model's default."""
        with (_EXAMPLE_DIR / "web.json5").open(encoding="utf-8") as fh:
            web = json5.load(fh)
        assert web["web"]["session_idle_days"] == 30
        assert load_config_dir(_EXAMPLE_DIR).web.session_idle_days == 30


class TestRenewal:
    """``SessionService.use``: a request's use renews the session, at most once per interval, under a new value."""

    def test_the_interval_is_one_hour(self) -> None:
        """A burst of requests writes once an hour at most; the grace is one minute."""
        assert SESSION_RENEWAL_INTERVAL_S == 3600.0
        assert SESSION_ROTATION_GRACE_S == 60.0

    def test_no_write_within_the_interval(self, sessions: SessionService, store: AppStore, clock: _Clock) -> None:
        """A use within the interval of the last renewal resolves, renews nothing and writes nothing."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        before = _rows(store)
        for _ in range(5):
            clock.now += (SESSION_RENEWAL_INTERVAL_S - 1) / 5
            use = sessions.use(token)
            assert use is not None and use.renewed_token is None
        assert _rows(store) == before

    def test_renewal_moves_the_expiry_and_rotates_the_value(
        self, sessions: SessionService, store: AppStore, clock: _Clock
    ) -> None:
        """Past the interval: ``expires_at`` = now + the idle lifetime, under a new value's hash."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        use = sessions.use(token)
        assert use is not None and use.actor.account_id == _ACCOUNT_ID
        assert use.renewed_token is not None and use.renewed_token != token
        token_hash, expires_at, last_seen_at, revoked_at, _ = _rows(store)[0]
        assert token_hash == hashlib.sha256(use.renewed_token.encode()).hexdigest()
        assert (expires_at, last_seen_at, revoked_at) == (clock.now + _IDLE_S, clock.now, None)

    def test_a_session_used_never_expires(self, sessions: SessionService, clock: _Clock) -> None:
        """Used every day for a year, a session with a two-day idle lifetime still signs in."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        for _ in range(365):
            clock.now += 86_400
            use = sessions.use(token)
            assert use is not None
            if use.renewed_token is not None:
                token = use.renewed_token
        assert sessions.use(token) is not None

    def test_idle_past_the_lifetime_ends_the_session(self, sessions: SessionService, clock: _Clock) -> None:
        """Renewed once, then unused for the idle lifetime: nobody."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        use = sessions.use(token)
        assert use is not None and use.renewed_token is not None
        clock.now += _IDLE_S
        assert sessions.use(use.renewed_token) is None

    def test_the_old_value_is_refused_after_the_grace_once_the_new_one_is_used(
        self, sessions: SessionService, clock: _Clock
    ) -> None:
        """The new value presented, the old one signs in for the grace, then never again."""
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        use = sessions.use(old)
        assert use is not None and use.renewed_token is not None
        assert sessions.use(use.renewed_token) is not None
        clock.now += SESSION_ROTATION_GRACE_S - 1
        assert sessions.use(old) is not None
        clock.now += 1
        assert sessions.use(old) is None
        assert sessions.resolve(old) is None
        assert sessions.use(use.renewed_token) is not None

    def test_a_request_in_flight_with_the_old_value_still_signs_in(
        self, sessions: SessionService, clock: _Clock
    ) -> None:
        """Two concurrent requests carry the same value: the second, after the first renewed, signs in unrenewed."""
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        first = sessions.use(old)
        assert first is not None and first.renewed_token is not None
        assert sessions.use(first.renewed_token) is not None
        second = sessions.use(old)
        assert second is not None and second.renewed_token is None

    def test_a_lost_renewal_keeps_the_old_value(self, sessions: SessionService, store: AppStore, clock: _Clock) -> None:
        """A new value the browser never received: the old one signs in and renews again, the lost one kept."""
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        lost = sessions.use(old)
        assert lost is not None and lost.renewed_token is not None
        clock.now += SESSION_RENEWAL_INTERVAL_S - 1
        assert sessions.use(old) is not None
        clock.now += 1
        again = sessions.use(old)
        assert again is not None and again.renewed_token is not None
        assert sessions.use(lost.renewed_token) is not None
        assert sessions.use(again.renewed_token) is not None
        assert len(_rows(store)) == 1

    def test_one_renewal_for_two_simultaneous_uses(
        self, sessions: SessionService, store: AppStore, clock: _Clock
    ) -> None:
        """A second use whose row was read before the first renewed loses the race: one rotation."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        stale = store.accounts.session_by_hash(hashlib.sha256(token.encode()).hexdigest())
        first = sessions.use(token)
        assert first is not None and first.renewed_token is not None
        assert stale is not None
        assert sessions._renew(store.accounts, stale, clock.now) is None  # noqa: SLF001 — the race's loser
        assert _rows(store)[0][0] == hashlib.sha256(first.renewed_token.encode()).hexdigest()

    def test_a_revoked_session_never_renews(self, sessions: SessionService, store: AppStore, clock: _Clock) -> None:
        """Closed, then used past the interval: nobody, and the row keeps its value and expiry."""
        token = sessions.open(_ACCOUNT_ID, user_agent=None)
        sessions.close(token)
        before = _rows(store)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        assert sessions.use(token) is None
        assert _rows(store) == before

    def test_revocation_ends_the_old_value_in_its_grace(
        self, sessions: SessionService, store: AppStore, clock: _Clock
    ) -> None:
        """Every session of the account revoked: neither the new value nor the replaced one signs in."""
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        use = sessions.use(old)
        assert use is not None and use.renewed_token is not None
        store.accounts.revoke_sessions_of(_ACCOUNT_ID, except_id=None, now=clock.now)
        assert sessions.use(old) is None
        assert sessions.use(use.renewed_token) is None

    def test_a_value_in_its_grace_never_takes_the_session_over(
        self, sessions: SessionService, store: AppStore, clock: _Clock
    ) -> None:
        """A replaced value presented in its grace, the session due: it signs in, renews nothing, writes nothing.

        A renews to B at t0; B is presented at t0 + 3570 (not due), starting A's grace;
        A is presented at t0 + 3601, in its grace and due: B keeps the session, A dies
        with its grace.
        """
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        renewal = sessions.use(old)
        assert renewal is not None and renewal.renewed_token is not None
        new = renewal.renewed_token
        renewed_at = clock.now
        clock.now = renewed_at + SESSION_RENEWAL_INTERVAL_S - 30
        assert sessions.use(new) is not None
        clock.now = renewed_at + SESSION_RENEWAL_INTERVAL_S + 1
        before = _rows(store)
        late = sessions.use(old)
        assert late is not None and late.renewed_token is None
        assert _rows(store) == before
        assert sessions.resolve(new) is not None
        clock.now = renewed_at + SESSION_RENEWAL_INTERVAL_S + SESSION_ROTATION_GRACE_S
        assert sessions.use(old) is None
        assert sessions.use(new) is not None

    def test_a_renewal_from_a_value_awaiting_its_successor_keeps_the_newest_holder(
        self, sessions: SessionService, store: AppStore, clock: _Clock
    ) -> None:
        """A renews to B, B never presented, A presented ten hours later: C is issued and B is not orphaned.

        The value the renewal overwrites (B) is the one recorded as replaced; once C is
        presented, A and B both have the grace left, then only C signs in.
        """
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        lost = sessions.use(old)
        assert lost is not None and lost.renewed_token is not None
        clock.now += 10 * SESSION_RENEWAL_INTERVAL_S
        again = sessions.use(old)
        assert again is not None and again.renewed_token is not None
        newest = again.renewed_token
        assert sessions.use(lost.renewed_token) is not None
        assert sessions.use(newest) is not None
        clock.now += SESSION_ROTATION_GRACE_S
        assert sessions.use(old) is None
        assert sessions.use(lost.renewed_token) is None
        assert sessions.use(newest) is not None
        assert _rows(store)[0][0] == hashlib.sha256(newest.encode()).hexdigest()

    def test_the_old_value_names_the_same_session(self, sessions: SessionService, clock: _Clock) -> None:
        """In its grace the replaced value names the renewed session: its key, and closing it closes both."""
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        key = sessions.live_session_id(old)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        use = sessions.use(old)
        assert use is not None and use.renewed_token is not None
        assert sessions.live_session_id(old) == key == sessions.live_session_id(use.renewed_token)
        sessions.close(old)
        assert sessions.use(use.renewed_token) is None


class TestEviction:
    """``SessionService._forget_stale``: the replaced values held in memory are dropped once they cannot sign in."""

    def test_a_value_past_its_grace_is_forgotten_at_the_next_renewal(
        self, sessions: SessionService, clock: _Clock
    ) -> None:
        """Renewed, the new value presented, the grace passed, renewed again: the first value's entry is gone."""
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        first = sessions.use(old)
        assert first is not None and first.renewed_token is not None
        assert sessions.use(first.renewed_token) is not None
        old_hash = hashlib.sha256(old.encode()).hexdigest()
        assert old_hash in sessions._replaced  # noqa: SLF001 — the memory bound is the subject
        clock.now += SESSION_RENEWAL_INTERVAL_S
        second = sessions.use(first.renewed_token)
        assert second is not None and second.renewed_token is not None
        assert old_hash not in sessions._replaced  # noqa: SLF001 — the memory bound is the subject

    def test_a_value_awaiting_for_an_idle_lifetime_is_forgotten(self, sessions: SessionService, clock: _Clock) -> None:
        """Renewed, the new value never presented, an idle lifetime passed: another session's renewal evicts it."""
        old = sessions.open(_ACCOUNT_ID, user_agent=None)
        key = sessions.live_session_id(old)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        lost = sessions.use(old)
        assert lost is not None and lost.renewed_token is not None
        old_hash = hashlib.sha256(old.encode()).hexdigest()
        assert sessions._awaiting == {key: [old_hash]}  # noqa: SLF001 — the memory bound is the subject
        clock.now += _IDLE_S
        other = sessions.open(_ACCOUNT_ID, user_agent=None)
        clock.now += SESSION_RENEWAL_INTERVAL_S
        renewal = sessions.use(other)
        assert renewal is not None and renewal.renewed_token is not None
        assert old_hash not in sessions._replaced  # noqa: SLF001 — the memory bound is the subject
        assert key not in sessions._awaiting  # noqa: SLF001 — the memory bound is the subject


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
