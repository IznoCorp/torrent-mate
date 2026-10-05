"""Unit tests for the password writes: ``change_own_password`` (credentials) and ``reset_account_password`` (roster).

A local account changes its own password from its current one; the change ends the
account's other sessions and keeps the caller's. The Plex server owner's fallback is the
CLI's (``password.held_by_cli``) and a Plex-linked account holds none (``auth.plex_only``).
Wrong current passwords are limited per account. An Admin, and only an Admin, resets a
local account's password to a provisional one; the reset ends no session. Neither write
publishes an event, and no password reaches a refusal, a log line or a ``repr``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.app.accounts import credentials as credentials_module
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.credentials import CredentialService
from personalscraper.app.accounts.passwords import PASSWORD_MINIMUM, hash_password, verify_password
from personalscraper.app.accounts.ratelimit import MAX_FAILED_ATTEMPTS, WINDOW_SECONDS, SlidingWindowRateLimiter
from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow, RoleRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.roster import RosterService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.errors import (
    AppBadRequest,
    AppForbidden,
    AppNotFound,
    AppTooManyRequests,
    AppUnauthenticated,
    RefusalCode,
)
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import Event, EventBus
from tests.conftest import LoggedEvents

_PASSWORD = "correct horse battery staple"
_NEW = "A brand-new passphrase 7"
_WRONG = "not the password at all"
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


def _account(account_id: str, role_id: str, password: str | None) -> AccountRow:
    """An account row, its e-mail ``<key>@example.org``.

    Args:
        account_id: Its key.
        role_id: Its role.
        password: Its password, hashed here; ``None`` for none.

    Returns:
        The row.
    """
    return AccountRow(
        id=account_id,
        name=account_id,
        email=f"{account_id}@example.org",
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
    """A fresh ``app.db``: every way of holding a password, an Admin and a manager who is not Admin.

    ``admin`` (Admin, local, password), ``manager`` (an ordinary role holding
    ``accounts.manage``, local, password), ``local`` and ``other`` (local guests,
    password), ``owner`` (the server's owner, the fallback password), ``shared``
    (Plex-linked, a password hash left over), ``nopass`` (local, no password).

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    repo = app_store.accounts
    repo.insert_role(
        RoleRow(id="manager", name="Manager", kind=RoleKind.ORDINARY, rights=frozenset({Right.ACCOUNTS_MANAGE})),
        now=1.0,
    )
    repo.insert_account(_account("admin", "admin", _PASSWORD))
    repo.insert_account(_account("manager", "manager", _PASSWORD))
    repo.insert_account(_account("local", "local-guest", _PASSWORD))
    repo.insert_account(_account("other", "local-guest", _PASSWORD))
    repo.insert_account(_account("owner", "admin", _PASSWORD))
    repo.insert_account(_account("shared", "household", _PASSWORD))
    repo.insert_account(_account("nopass", "local-guest", None))
    repo.upsert_plex_link(_link("owner", 1, "owner"))
    repo.upsert_plex_link(_link("shared", 2, "shared"))
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def limiter_clock() -> _Clock:
    """The password-change limiter's clock.

    Returns:
        The clock.
    """
    return _Clock()


@pytest.fixture
def bus() -> EventBus:
    """The bus the service publishes on.

    Returns:
        A fresh bus.
    """
    return EventBus()


@pytest.fixture
def sessions(store: AppStore) -> SessionService:
    """The session service over the store, with no ceiling.

    Args:
        store: The store.

    Returns:
        The service.
    """
    return SessionService(lambda: store.accounts, idle_days=1, ceiling=lambda: _NO_CEILING)


@pytest.fixture
def accounts(store: AppStore, sessions: SessionService, limiter_clock: _Clock) -> CredentialService:
    """The credential service, its password-change limiter on a settable clock.

    Args:
        store: The store.
        sessions: The session service.
        limiter_clock: The limiter's clock.

    Returns:
        The service.
    """
    return CredentialService(
        lambda: store.accounts,
        sessions,
        password_limiter=SlidingWindowRateLimiter(clock=limiter_clock),
    )


@pytest.fixture
def roster(store: AppStore, bus: EventBus) -> RosterService:
    """The roster service.

    Args:
        store: The store.
        bus: The bus.

    Returns:
        The service.
    """
    return RosterService(lambda: store.accounts, bus)


def _signed_in(sessions: SessionService, account_id: str) -> tuple[Actor, str]:
    """Open a session for an account and resolve its actor.

    Args:
        sessions: The session service.
        account_id: The account.

    Returns:
        The actor and the session's value.
    """
    token = sessions.open(account_id, user_agent="pytest")
    actor = sessions.resolve(token)
    assert actor is not None
    return actor, token


def _change(
    accounts: CredentialService, sessions: SessionService, account_id: str, current: str, new: str = _NEW
) -> str:
    """Sign an account in and change its password.

    Args:
        accounts: The service.
        sessions: The session service.
        account_id: The account.
        current: The current password typed.
        new: The new password typed.

    Returns:
        The caller's session value.
    """
    actor, token = _signed_in(sessions, account_id)
    accounts.change_own_password(actor, token, current_password=current, new_password=new)
    return token


def _stored_hash(store: AppStore, account_id: str) -> str | None:
    """An account's stored password hash.

    Args:
        store: The store.
        account_id: The account.

    Returns:
        The hash, or ``None``.
    """
    row = store.accounts.account(account_id)
    assert row is not None
    return row.password_hash


class TestChangeOwnPassword:
    """``change_own_password`` — a local account replaces its own password."""

    def test_the_new_password_replaces_the_old(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore
    ) -> None:
        """The new password is kept as a scrypt hash; the old one no longer matches."""
        _change(accounts, sessions, "local", _PASSWORD)
        stored = _stored_hash(store, "local")
        assert stored is not None and stored.startswith("scrypt$")
        assert _NEW not in stored
        assert verify_password(_NEW, stored)
        assert not verify_password(_PASSWORD, stored)

    def test_the_other_sessions_end_and_the_callers_stays(
        self, accounts: CredentialService, sessions: SessionService
    ) -> None:
        """Every other session of the account is revoked; the caller's and another account's are not."""
        _, elsewhere = _signed_in(sessions, "local")
        _, someone_else = _signed_in(sessions, "other")
        kept = _change(accounts, sessions, "local", _PASSWORD)
        assert sessions.resolve(kept) is not None
        assert sessions.resolve(elsewhere) is None
        assert sessions.resolve(someone_else) is not None

    def test_the_owner_is_held_by_cli(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore
    ) -> None:
        """The server owner's fallback is replaced on the server only: 403 ``password.held_by_cli``."""
        before = _stored_hash(store, "owner")
        with pytest.raises(AppForbidden) as caught:
            _change(accounts, sessions, "owner", _PASSWORD)
        assert caught.value.code == RefusalCode.PASSWORD_HELD_BY_CLI
        assert _stored_hash(store, "owner") == before

    def test_a_plex_linked_account_is_plex_only(self, accounts: CredentialService, sessions: SessionService) -> None:
        """A Plex-linked account holds no password here: 403 ``auth.plex_only``."""
        with pytest.raises(AppForbidden) as caught:
            _change(accounts, sessions, "shared", _PASSWORD)
        assert caught.value.code == RefusalCode.AUTH_PLEX_ONLY

    @pytest.mark.parametrize("account_id", ["local", "nopass"], ids=["wrong-current", "no-password-held"])
    def test_a_wrong_current_password_runs_scrypt_once(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore, account_id: str
    ) -> None:
        """400 ``password.current_wrong``, scrypt run once even when no hash is held, nothing changed."""
        before = _stored_hash(store, account_id)
        actor, token = _signed_in(sessions, account_id)
        with patch.object(credentials_module, "verify_password", wraps=verify_password) as spy:
            with pytest.raises(AppBadRequest) as caught:
                accounts.change_own_password(actor, token, current_password=_WRONG, new_password=_NEW)
        assert caught.value.code == RefusalCode.PASSWORD_CURRENT_WRONG
        assert spy.call_count == 1
        assert _stored_hash(store, account_id) == before

    @pytest.mark.parametrize("new", ["x" * (PASSWORD_MINIMUM - 1), ""], ids=["one-short", "empty"])
    def test_a_short_new_password_names_the_minimum(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore, new: str
    ) -> None:
        """400 ``password.too_short`` with ``minimum``; the stored password and the sessions untouched."""
        before = _stored_hash(store, "local")
        _, elsewhere = _signed_in(sessions, "local")
        with pytest.raises(AppBadRequest) as caught:
            _change(accounts, sessions, "local", _PASSWORD, new)
        assert caught.value.code == RefusalCode.PASSWORD_TOO_SHORT
        assert caught.value.params == {"minimum": PASSWORD_MINIMUM}
        assert _stored_hash(store, "local") == before
        assert sessions.resolve(elsewhere) is not None

    @pytest.mark.parametrize(
        "new",
        ["a brand-new passphrase 7", "A brand-new passphrase", "Abrandnewpassphrase7"],
        ids=["no-uppercase", "no-digit", "no-special"],
    )
    def test_a_weak_new_password_is_refused_by_the_policy(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore, new: str
    ) -> None:
        """400 ``password.too_weak`` with ``minimum``; the stored password and the sessions untouched."""
        before = _stored_hash(store, "local")
        _, elsewhere = _signed_in(sessions, "local")
        with pytest.raises(AppBadRequest) as caught:
            _change(accounts, sessions, "local", _PASSWORD, new)
        assert caught.value.code == RefusalCode.PASSWORD_TOO_WEAK
        assert caught.value.params == {"minimum": PASSWORD_MINIMUM}
        assert _stored_hash(store, "local") == before
        assert sessions.resolve(elsewhere) is not None

    def test_a_deleted_account_is_auth_required(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore
    ) -> None:
        """The account vanished after the perimeter resolved it: 401 ``auth.required``."""
        actor, token = _signed_in(sessions, "local")
        store.accounts._conn.execute("DELETE FROM session WHERE account_id = 'local'")  # noqa: SLF001
        store.accounts._conn.execute("DELETE FROM account WHERE id = 'local'")  # noqa: SLF001
        with pytest.raises(AppUnauthenticated) as caught:
            accounts.change_own_password(actor, token, current_password=_PASSWORD, new_password=_NEW)
        assert caught.value.code == RefusalCode.AUTH_REQUIRED

    def test_a_concurrent_change_is_current_wrong(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore
    ) -> None:
        """The hash moved between the check and the write: the typed password is no longer current."""
        actor, token = _signed_in(sessions, "local")
        replaced = hash_password("set meanwhile elsewhere")
        real_hash = credentials_module.hash_password

        def _hash_then_race(password: str) -> str:
            """Hash the new password, while another writer replaces the stored one.

            Args:
                password: The password to hash.

            Returns:
                Its hash.
            """
            store.accounts.set_password_hash("local", replaced, now=2.0)
            return real_hash(password)

        with patch.object(credentials_module, "hash_password", side_effect=_hash_then_race):
            with pytest.raises(AppBadRequest) as caught:
                accounts.change_own_password(actor, token, current_password=_PASSWORD, new_password=_NEW)
        assert caught.value.code == RefusalCode.PASSWORD_CURRENT_WRONG
        assert _stored_hash(store, "local") == replaced

    def test_publishes_nothing(self, accounts: CredentialService, sessions: SessionService, bus: EventBus) -> None:
        """No event: a password change moves no right."""
        seen: list[object] = []
        bus.subscribe(Event, seen.append)
        _change(accounts, sessions, "local", _PASSWORD)
        assert seen == []


class TestChangeRateLimit:
    """Wrong current passwords: ``MAX_FAILED_ATTEMPTS`` per account inside ``WINDOW_SECONDS``."""

    def _exhaust(self, accounts: CredentialService, sessions: SessionService, account_id: str = "local") -> None:
        """Type a wrong current password as many times as the limiter tolerates.

        Args:
            accounts: The service.
            sessions: The session service.
            account_id: The account.
        """
        for _ in range(MAX_FAILED_ATTEMPTS):
            with pytest.raises(AppBadRequest):
                _change(accounts, sessions, account_id, _WRONG)

    def test_the_next_attempt_is_rate_limited_even_with_the_right_password(
        self, accounts: CredentialService, sessions: SessionService, store: AppStore
    ) -> None:
        """The sixth attempt: 429 ``auth.rate_limited``, the right current password included; nothing changed."""
        before = _stored_hash(store, "local")
        self._exhaust(accounts, sessions)
        with pytest.raises(AppTooManyRequests) as caught:
            _change(accounts, sessions, "local", _PASSWORD)
        assert caught.value.code == RefusalCode.AUTH_RATE_LIMITED
        assert _stored_hash(store, "local") == before

    def test_another_account_is_not_limited(self, accounts: CredentialService, sessions: SessionService) -> None:
        """The limit is per account."""
        self._exhaust(accounts, sessions)
        _change(accounts, sessions, "other", _PASSWORD)

    def test_the_window_slides(
        self, accounts: CredentialService, sessions: SessionService, limiter_clock: _Clock
    ) -> None:
        """Past the window, the account may try again."""
        self._exhaust(accounts, sessions)
        limiter_clock.now += WINDOW_SECONDS + 1
        _change(accounts, sessions, "local", _PASSWORD)

    def test_a_success_does_not_give_the_budget_back(
        self, accounts: CredentialService, sessions: SessionService
    ) -> None:
        """Four failures, a success, one more failure: the account has used its five."""
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            with pytest.raises(AppBadRequest):
                _change(accounts, sessions, "local", _WRONG)
        _change(accounts, sessions, "local", _PASSWORD)
        with pytest.raises(AppBadRequest):
            _change(accounts, sessions, "local", _WRONG)
        with pytest.raises(AppTooManyRequests):
            _change(accounts, sessions, "local", _NEW)

    def test_the_sign_in_limiter_is_another(self, store: AppStore, sessions: SessionService) -> None:
        """Wrong current passwords never spend the sign-in door's budget, nor the reverse."""
        accounts = CredentialService(lambda: store.accounts, sessions)
        self._exhaust(accounts, sessions)
        result = accounts.sign_in_with_password("local@example.org", _PASSWORD, client_key="local", user_agent="pytest")
        assert result.account.id == "local"


class TestResetAccountPassword:
    """``reset_account_password`` — an Admin gives a local account a provisional password."""

    def test_an_admin_resets_and_the_sessions_stay(
        self, roster: RosterService, sessions: SessionService, store: AppStore
    ) -> None:
        """The provisional password is kept as a hash; the account's sessions keep running."""
        admin, _ = _signed_in(sessions, "admin")
        _, running = _signed_in(sessions, "local")
        roster.reset_account_password(admin, "local", password=_NEW)
        stored = _stored_hash(store, "local")
        assert stored is not None and verify_password(_NEW, stored)
        assert sessions.resolve(running) is not None

    def test_an_account_without_a_password_gets_one(
        self, roster: RosterService, sessions: SessionService, store: AppStore
    ) -> None:
        """A local account holding none is given one."""
        admin, _ = _signed_in(sessions, "admin")
        roster.reset_account_password(admin, "nopass", password=_NEW)
        stored = _stored_hash(store, "nopass")
        assert stored is not None and verify_password(_NEW, stored)

    @pytest.mark.parametrize("account_id", ["local", "manager", "nobody"], ids=["other", "own", "unknown"])
    def test_a_manager_who_is_not_admin_is_refused_first(
        self, roster: RosterService, sessions: SessionService, store: AppStore, account_id: str
    ) -> None:
        """403 ``password.reset_admin_only`` whatever the account — its own, and one that does not exist."""
        manager, _ = _signed_in(sessions, "manager")
        before = store.accounts.account(account_id)
        with pytest.raises(AppForbidden) as caught:
            roster.reset_account_password(manager, account_id, password=_NEW)
        assert caught.value.code == RefusalCode.PASSWORD_RESET_ADMIN_ONLY
        assert store.accounts.account(account_id) == before

    def test_an_admin_never_resets_its_own_password(
        self, roster: RosterService, sessions: SessionService, store: AppStore
    ) -> None:
        """403 ``password.reset_own``: an Admin changes its own password in Profil, the current one required."""
        admin, _ = _signed_in(sessions, "admin")
        before = _stored_hash(store, "admin")
        with pytest.raises(AppForbidden) as caught:
            roster.reset_account_password(admin, "admin", password=_NEW)
        assert caught.value.code == RefusalCode.PASSWORD_RESET_OWN
        assert _stored_hash(store, "admin") == before

    def test_the_admin_check_comes_before_the_own_account_check(
        self, roster: RosterService, sessions: SessionService
    ) -> None:
        """A manager who is not Admin resetting its own password still reads ``password.reset_admin_only``."""
        manager, _ = _signed_in(sessions, "manager")
        with pytest.raises(AppForbidden) as caught:
            roster.reset_account_password(manager, "manager", password=_NEW)
        assert caught.value.code == RefusalCode.PASSWORD_RESET_ADMIN_ONLY

    def test_an_unknown_account_is_404(self, roster: RosterService, sessions: SessionService) -> None:
        """For an Admin: 404 ``account.unknown``."""
        admin, _ = _signed_in(sessions, "admin")
        with pytest.raises(AppNotFound) as caught:
            roster.reset_account_password(admin, "nobody", password=_NEW)
        assert caught.value.code == RefusalCode.ACCOUNT_UNKNOWN

    @pytest.mark.parametrize(
        ("account_id", "code"),
        [("owner", RefusalCode.PASSWORD_HELD_BY_CLI), ("shared", RefusalCode.AUTH_PLEX_ONLY)],
        ids=["owner", "plex-linked"],
    )
    def test_a_password_held_elsewhere_is_refused(
        self, roster: RosterService, sessions: SessionService, store: AppStore, account_id: str, code: RefusalCode
    ) -> None:
        """The owner's fallback is the CLI's; a Plex-linked account holds none: 403, nothing changed."""
        admin, _ = _signed_in(sessions, "admin")
        before = _stored_hash(store, account_id)
        with pytest.raises(AppForbidden) as caught:
            roster.reset_account_password(admin, account_id, password=_NEW)
        assert caught.value.code == code
        assert _stored_hash(store, account_id) == before

    @pytest.mark.parametrize(
        ("password", "code", "params"),
        [
            ("", RefusalCode.PASSWORD_REQUIRED, {}),
            ("x" * (PASSWORD_MINIMUM - 1), RefusalCode.PASSWORD_TOO_SHORT, {"minimum": PASSWORD_MINIMUM}),
            ("x" * PASSWORD_MINIMUM, RefusalCode.PASSWORD_TOO_WEAK, {"minimum": PASSWORD_MINIMUM}),
        ],
        ids=["empty", "one-short", "too-weak"],
    )
    def test_a_refused_password(
        self,
        roster: RosterService,
        sessions: SessionService,
        store: AppStore,
        password: str,
        code: RefusalCode,
        params: dict[str, int],
    ) -> None:
        """400 ``password.required`` / ``password.too_short`` / ``password.too_weak`` (``minimum``); nothing changed."""
        admin, _ = _signed_in(sessions, "admin")
        before = _stored_hash(store, "local")
        with pytest.raises(AppBadRequest) as caught:
            roster.reset_account_password(admin, "local", password=password)
        assert caught.value.code == code
        assert caught.value.params == params
        assert _stored_hash(store, "local") == before

    def test_publishes_nothing(self, roster: RosterService, sessions: SessionService, bus: EventBus) -> None:
        """No event: a reset moves no right."""
        seen: list[object] = []
        bus.subscribe(Event, seen.append)
        admin, _ = _signed_in(sessions, "admin")
        roster.reset_account_password(admin, "local", password=_NEW)
        assert seen == []


def test_no_password_reaches_a_refusal_or_a_log(
    accounts: CredentialService, roster: RosterService, sessions: SessionService, logged_events: LoggedEvents
) -> None:
    """Neither the current, the new nor the provisional password is in any refusal or log line."""
    admin, _ = _signed_in(sessions, "admin")
    refusals: list[Exception] = []
    with logged_events() as logs:
        _change(accounts, sessions, "local", _PASSWORD)
        for current, new in ((_WRONG, _NEW + "!"), (_NEW, "tiny-secret")):
            actor, token = _signed_in(sessions, "local")
            with pytest.raises(AppBadRequest) as caught:
                accounts.change_own_password(actor, token, current_password=current, new_password=new)
            refusals.append(caught.value)
        roster.reset_account_password(admin, "other", password=_NEW + "?")
        with pytest.raises(AppForbidden) as forbidden:
            roster.reset_account_password(admin, "owner", password=_NEW + "#")
        refusals.append(forbidden.value)
    text = f"{logs} " + " ".join(f"{refusal} {refusal.detail} {refusal.params}" for refusal in refusals)  # type: ignore[attr-defined]
    for secret in (_PASSWORD, _NEW, _WRONG, "tiny-secret"):
        assert secret not in text
