"""Unit tests for the password door of ``AccountService``: ``sign_in_with_password`` and ``set_password``.

Every unauthenticated failure is one indistinguishable refusal, ``auth.refused``: an unknown
e-mail, a wrong password, an account with no password, a Plex-linked account other than the
server's owner. Each runs scrypt once, so the time taken tells nothing either. The limiter
answers ``auth.rate_limited`` once a client key has failed too often, the right password
included. Every sign-in opens a new session.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import structlog

from personalscraper.app.accounts import service as service_module
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.passwords import hash_password, verify_password
from personalscraper.app.accounts.ratelimit import MAX_FAILED_ATTEMPTS, WINDOW_SECONDS, SlidingWindowRateLimiter
from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.service import AccountService, SignInResult
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.errors import AppNotFound, AppTooManyRequests, AppUnauthenticated, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus

_PASSWORD = "correct horse battery staple"
_WRONG = "not the password"
_KEY = "203.0.113.7"
_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)


class _Clock:
    """A settable monotonic clock for the limiter.

    Attributes:
        now: The time it answers (seconds).
    """

    def __init__(self) -> None:
        """Start the clock at zero."""
        self.now = 0.0

    def __call__(self) -> float:
        """Answer the current time.

        Returns:
            :attr:`now`.
        """
        return self.now


def _account(account_id: str, email: str, role_id: str, password: str | None) -> AccountRow:
    """An account row.

    Args:
        account_id: Its key.
        email: Its e-mail.
        role_id: Its role.
        password: Its password, hashed here; ``None`` for none.

    Returns:
        The row.
    """
    return AccountRow(
        id=account_id,
        name=account_id,
        email=email,
        avatar="",
        role_id=role_id,
        password_hash=hash_password(password) if password is not None else None,
        created_at=1.0,
        updated_at=1.0,
    )


def _link(account_id: str, plex_id: int, server_access: str) -> PlexLinkRow:
    """A Plex link.

    Args:
        account_id: The linked account.
        plex_id: Its plex.tv id.
        server_access: ``owner`` or ``shared``.

    Returns:
        The link.
    """
    return PlexLinkRow(
        account_id=account_id,
        plex_id=plex_id,
        plex_uuid=f"uuid-{plex_id}",
        plex_username=f"plex-{plex_id}",
        server_access=server_access,  # type: ignore[arg-type]
        token_ciphertext=None,
        token_stored_at=None,
        linked_at=1.0,
        last_sign_in_at=None,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` holding one account per way of signing in.

    ``admin@`` (Admin, local, password), ``local@`` (an ordinary seeded role, local,
    password), ``owner@`` (the server's owner, password kept as the fallback),
    ``shared@`` (Plex-linked, shared, a password hash left over), ``nopass@`` (local, no
    password).

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    repo = app_store.accounts
    repo.insert_account(_account("account-admin", "admin@example.org", "admin", _PASSWORD))
    repo.insert_account(_account("account-local", "Local@Example.org", "local-guest", _PASSWORD))
    repo.insert_account(_account("account-owner", "owner@example.org", "admin", _PASSWORD))
    repo.insert_account(_account("account-shared", "shared@example.org", "household", _PASSWORD))
    repo.insert_account(_account("account-nopass", "nopass@example.org", "local-guest", None))
    repo.upsert_plex_link(_link("account-owner", 1, "owner"))
    repo.upsert_plex_link(_link("account-shared", 2, "shared"))
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def limiter_clock() -> _Clock:
    """The limiter's clock.

    Returns:
        The clock.
    """
    return _Clock()


@pytest.fixture
def accounts(store: AppStore, limiter_clock: _Clock) -> AccountService:
    """The account service over the store, with its own limiter on a settable clock.

    Args:
        store: The store.
        limiter_clock: The limiter's clock.

    Returns:
        The service.
    """
    sessions = SessionService(lambda: store.accounts, ttl_hours=2, ceiling=lambda: _NO_CEILING)
    return AccountService(
        lambda: store.accounts,
        sessions,
        EventBus(),
        limiter=SlidingWindowRateLimiter(clock=limiter_clock),
    )


def _sign_in(accounts: AccountService, email: str, password: str, key: str = _KEY) -> SignInResult:
    """Sign in with a password from one client key.

    Args:
        accounts: The service.
        email: The e-mail typed.
        password: The password typed.
        key: The client key.

    Returns:
        The result.
    """
    return accounts.sign_in_with_password(email, password, client_key=key, user_agent="pytest")


def _refused(accounts: AccountService, email: str, password: str, key: str = _KEY) -> AppUnauthenticated:
    """Sign in and expect the one refusal.

    Args:
        accounts: The service.
        email: The e-mail typed.
        password: The password typed.
        key: The client key.

    Returns:
        The refusal raised.
    """
    with pytest.raises(AppUnauthenticated) as caught:
        _sign_in(accounts, email, password, key)
    assert caught.value.code == RefusalCode.AUTH_REFUSED
    return caught.value


class TestSignIn:
    """``sign_in_with_password`` — who passes the door."""

    def test_a_local_account_signs_in(self, accounts: AccountService) -> None:
        """The right password on a local account opens a session for it."""
        result = _sign_in(accounts, "local@example.org", _PASSWORD)
        assert result.account.id == "account-local"
        assert result.account.sign_in_kind == "local"
        actor = accounts._sessions.resolve(result.session_token)  # noqa: SLF001 — the session it opened
        assert actor is not None and actor.account_id == "account-local"

    def test_admin_signs_in(self, accounts: AccountService) -> None:
        """Admin holds every right: the door opens."""
        assert _sign_in(accounts, "admin@example.org", _PASSWORD).account.role.kind == "admin"

    def test_the_owner_signs_in_with_the_fallback_password(self, accounts: AccountService) -> None:
        """The Plex server's owner keeps the password door (O-K1-3)."""
        assert _sign_in(accounts, "owner@example.org", _PASSWORD).account.sign_in_kind == "owner"

    def test_the_email_is_matched_whatever_its_case(self, accounts: AccountService) -> None:
        """``LOCAL@EXAMPLE.ORG`` finds the account stored as ``Local@Example.org``."""
        assert _sign_in(accounts, "LOCAL@EXAMPLE.ORG", _PASSWORD).account.id == "account-local"

    def test_two_sign_ins_open_two_sessions(self, accounts: AccountService) -> None:
        """A new value every time; the first stays valid (no fixation, no adoption)."""
        first = _sign_in(accounts, "local@example.org", _PASSWORD)
        second = _sign_in(accounts, "local@example.org", _PASSWORD)
        assert first.session_token != second.session_token
        assert accounts._sessions.resolve(first.session_token) is not None  # noqa: SLF001
        assert accounts._sessions.resolve(second.session_token) is not None  # noqa: SLF001


class TestRefused:
    """Every failure is ``auth.refused``, and runs scrypt once."""

    @pytest.mark.parametrize(
        ("email", "password"),
        [
            ("nobody@example.org", _PASSWORD),
            ("local@example.org", _WRONG),
            ("nopass@example.org", _PASSWORD),
            ("shared@example.org", _PASSWORD),
            ("shared@example.org", _WRONG),
        ],
        ids=["unknown-email", "wrong-password", "no-password", "plex-linked", "plex-linked-wrong"],
    )
    def test_one_refusal_one_scrypt(self, accounts: AccountService, email: str, password: str) -> None:
        """Unknown e-mail, wrong password, no password, Plex-linked: one code, scrypt run once."""
        with patch.object(service_module, "verify_password", wraps=verify_password) as spy:
            refusal = _refused(accounts, email, password)
        assert spy.call_count == 1
        assert refusal.status == 401
        assert refusal.params == {}

    def test_the_refusal_carries_no_credential(self, accounts: AccountService) -> None:
        """Neither the e-mail nor the password is in the refusal or any log line."""
        with structlog.testing.capture_logs() as logs:
            refusal = _refused(accounts, "local@example.org", _WRONG)
            _refused(accounts, "nobody@example.org", _WRONG)
            _sign_in(accounts, "local@example.org", _PASSWORD)
        text = f"{refusal.detail} {refusal.params} {refusal} {logs}".lower()
        for secret in ("local@example.org", "nobody@example.org", _WRONG, _PASSWORD):
            assert secret.lower() not in text


class TestRateLimit:
    """The limiter: ``MAX_FAILED_ATTEMPTS`` failures per key inside ``WINDOW_SECONDS``."""

    def _exhaust(self, accounts: AccountService, key: str = _KEY) -> None:
        """Fail as many times as the limiter tolerates.

        Args:
            accounts: The service.
            key: The client key.
        """
        for _ in range(MAX_FAILED_ATTEMPTS):
            _refused(accounts, "local@example.org", _WRONG, key)

    def test_the_next_attempt_is_rate_limited_even_with_the_right_password(self, accounts: AccountService) -> None:
        """The sixth attempt inside the window: 429 ``auth.rate_limited``, the correct password included."""
        self._exhaust(accounts)
        with pytest.raises(AppTooManyRequests) as caught:
            _sign_in(accounts, "local@example.org", _PASSWORD)
        assert caught.value.code == RefusalCode.AUTH_RATE_LIMITED

    def test_another_key_is_not_limited(self, accounts: AccountService) -> None:
        """The limit is per client key."""
        self._exhaust(accounts)
        assert _sign_in(accounts, "local@example.org", _PASSWORD, key="198.51.100.1").account.id == "account-local"

    def test_the_window_slides(self, accounts: AccountService, limiter_clock: _Clock) -> None:
        """Past the window, the key may try again."""
        self._exhaust(accounts)
        limiter_clock.now += WINDOW_SECONDS + 1
        assert _sign_in(accounts, "local@example.org", _PASSWORD).account.id == "account-local"

    def test_a_success_does_not_give_the_budget_back(self, accounts: AccountService) -> None:
        """A client holding another valid account cannot walk the limiter round.

        Four wrong tries on the admin's e-mail, a sign-in to its own account, one more
        failure: the key has used its five, and the next attempt is refused whatever the
        password. Failures expire with the window alone.
        """
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            _refused(accounts, "admin@example.org", _WRONG)
        _sign_in(accounts, "local@example.org", _PASSWORD)
        _refused(accounts, "admin@example.org", _WRONG)
        with pytest.raises(AppTooManyRequests) as caught:
            _sign_in(accounts, "admin@example.org", _PASSWORD)
        assert caught.value.code == RefusalCode.AUTH_RATE_LIMITED

    @pytest.mark.parametrize(
        "email",
        ["nobody@example.org", "nopass@example.org", "local@example.org", "shared@example.org"],
        ids=["unknown-email", "no-password", "wrong-password", "plex-linked"],
    )
    def test_every_refusal_kind_counts_against_the_limiter(self, accounts: AccountService, email: str) -> None:
        """Whatever the refusal, the sixth attempt is ``auth.rate_limited``.

        A kind that did not count would make the 429 an oracle on which e-mails exist.
        """
        for _ in range(MAX_FAILED_ATTEMPTS):
            _refused(accounts, email, _WRONG if email == "local@example.org" else _PASSWORD)
        with pytest.raises(AppTooManyRequests) as caught:
            _sign_in(accounts, "local@example.org", _PASSWORD)
        assert caught.value.code == RefusalCode.AUTH_RATE_LIMITED

    def test_unknown_and_known_emails_share_one_budget(self, accounts: AccountService) -> None:
        """Failures on an unknown e-mail and on a known one from one key add up."""
        for _ in range(MAX_FAILED_ATTEMPTS - 2):
            _refused(accounts, "nobody@example.org", _WRONG)
        for _ in range(2):
            _refused(accounts, "local@example.org", _WRONG)
        with pytest.raises(AppTooManyRequests) as caught:
            _sign_in(accounts, "local@example.org", _PASSWORD)
        assert caught.value.code == RefusalCode.AUTH_RATE_LIMITED

    def test_each_service_has_its_own_limiter(self, store: AppStore) -> None:
        """Without an injected limiter, each service builds its own (v0's is never shared)."""
        sessions = SessionService(lambda: store.accounts, ttl_hours=2)
        first = AccountService(lambda: store.accounts, sessions, EventBus())
        second = AccountService(lambda: store.accounts, sessions, EventBus())
        self._exhaust(first)
        assert _sign_in(second, "local@example.org", _PASSWORD).account.id == "account-local"


class TestSetPassword:
    """``set_password`` — the CLI's door of last resort."""

    def test_sets_a_password_that_signs_in(self, accounts: AccountService, store: AppStore) -> None:
        """The account without a password gets one; the door opens with it; only a hash is kept."""
        accounts.set_password("NOPASS@example.org", "a new password")
        row = store.accounts.account("account-nopass")
        assert row is not None and row.password_hash is not None
        assert "a new password" not in row.password_hash
        assert _sign_in(accounts, "nopass@example.org", "a new password").account.id == "account-nopass"

    def test_replaces_the_previous_password(self, accounts: AccountService) -> None:
        """The old password no longer opens the door."""
        accounts.set_password("local@example.org", "the replacement")
        _refused(accounts, "local@example.org", _PASSWORD)
        assert _sign_in(accounts, "local@example.org", "the replacement").account.id == "account-local"

    def test_an_unknown_email_is_account_unknown(self, accounts: AccountService) -> None:
        """No account: ``account.unknown``, with neither the e-mail nor the password in the refusal."""
        with pytest.raises(AppNotFound) as caught:
            accounts.set_password("nobody@example.org", "whatever secret")
        assert caught.value.code == RefusalCode.ACCOUNT_UNKNOWN
        assert "nobody@example.org" not in str(caught.value)
        assert "whatever secret" not in str(caught.value)
