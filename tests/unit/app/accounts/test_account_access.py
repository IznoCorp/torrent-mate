"""Unit tests for an account's access: ``AccountService.set_account_access`` and the sign-in it gates.

An Admin, and only an Admin, cuts or gives back any account's access but the Plex server
owner's and its own. Cutting ends every session of the account in the same transaction;
giving it back opens none. A cut account's sign-in is refused ``auth.access_disabled``
only once its credentials are proven: every other failure stays the one ``auth.refused``,
after the same scrypt work. Nothing is published, and no password reaches a log line.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.app.accounts import service as service_module
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.passwords import hash_password, verify_password
from personalscraper.app.accounts.ratelimit import MAX_FAILED_ATTEMPTS, SlidingWindowRateLimiter
from personalscraper.app.accounts.repository import AccountRepository, AccountRow, PlexLinkRow, RoleRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.service import AccountService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.errors import AppForbidden, AppNotFound, AppUnauthenticated, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import Event, EventBus

_PASSWORD = "correct horse battery staple"
_WRONG = "not the password at all"
_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)


#: The logger the service writes its structlog events through.
_SERVICE_LOGGER = "app.accounts.service"


def _service_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    """The service's structlog events, read from the stdlib records they are rendered through.

    ``structlog.testing.capture_logs`` misses a logger cached before it (``cache_logger_on_first_use``,
    as after a CLI run in the same process); the stdlib records see every event.

    Args:
        caplog: pytest's log capture.

    Returns:
        The event dicts of ``app.accounts.service``, in order.
    """
    return [
        dict(record.msg) for record in caplog.records if record.name == _SERVICE_LOGGER and isinstance(record.msg, dict)
    ]


def _account(account_id: str, role_id: str) -> AccountRow:
    """An account row, its e-mail ``<key>@example.org``, its password :data:`_PASSWORD`.

    Args:
        account_id: Its key.
        role_id: Its role.

    Returns:
        The row.
    """
    return AccountRow(
        id=account_id,
        name=account_id,
        email=f"{account_id}@example.org",
        avatar="",
        role_id=role_id,
        password_hash=hash_password(_PASSWORD),
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
    """A fresh ``app.db``: an Admin, a manager who is not Admin, local accounts, the owner, a Plex-linked one.

    ``admin`` (Admin, local), ``manager`` (an ordinary role holding ``accounts.manage``),
    ``local`` and ``other`` (local guests), ``owner`` (the server's owner, on Admin),
    ``shared`` (Plex-linked, a password hash left over).

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
    for account_id, role_id in (
        ("admin", "admin"),
        ("manager", "manager"),
        ("local", "local-guest"),
        ("other", "local-guest"),
        ("owner", "admin"),
        ("shared", "household"),
    ):
        repo.insert_account(_account(account_id, role_id))
    repo.upsert_plex_link(_link("owner", 1, "owner"))
    repo.upsert_plex_link(_link("shared", 2, "shared"))
    try:
        yield app_store
    finally:
        app_store.close()


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
    return SessionService(lambda: store.accounts, ttl_hours=2, ceiling=lambda: _NO_CEILING)


@pytest.fixture
def limiter() -> SlidingWindowRateLimiter:
    """The password door's limiter.

    Returns:
        A fresh limiter.
    """
    return SlidingWindowRateLimiter()


@pytest.fixture
def accounts(
    store: AppStore, sessions: SessionService, bus: EventBus, limiter: SlidingWindowRateLimiter
) -> AccountService:
    """The account service.

    Args:
        store: The store.
        sessions: The session service.
        bus: The bus.
        limiter: The password door's limiter.

    Returns:
        The service.
    """
    return AccountService(lambda: store.accounts, sessions, bus, limiter=limiter)


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


def _row(store: AppStore, account_id: str) -> AccountRow:
    """An account's stored row.

    Args:
        store: The store.
        account_id: The account.

    Returns:
        The row.
    """
    row = store.accounts.account(account_id)
    assert row is not None
    return row


def _sign_in(accounts: AccountService, account_id: str, password: str = _PASSWORD) -> None:
    """Sign an account in through the password door.

    Args:
        accounts: The service.
        account_id: The account, its e-mail ``<key>@example.org``.
        password: The password typed.
    """
    accounts.sign_in_with_password(f"{account_id}@example.org", password, client_key="client", user_agent="pytest")


class TestSetAccountAccess:
    """``set_account_access`` — an Admin cuts or gives back an account's sign-in."""

    def test_cutting_ends_every_session_of_the_account_and_no_other(
        self, accounts: AccountService, sessions: SessionService, store: AppStore
    ) -> None:
        """The account is cut and its sessions all end at once; another account's keep running."""
        admin, admin_token = _signed_in(sessions, "admin")
        _, first = _signed_in(sessions, "local")
        _, second = _signed_in(sessions, "local")
        _, bystander = _signed_in(sessions, "other")
        summary = accounts.set_account_access(admin, "local", allowed=False)
        assert summary.id == "local" and summary.sign_in_allowed is False
        assert _row(store, "local").sign_in_allowed is False
        assert sessions.resolve(first) is None and sessions.resolve(second) is None
        assert sessions.resolve(bystander) is not None and sessions.resolve(admin_token) is not None

    def test_a_plex_linked_account_is_cut_too(
        self, accounts: AccountService, sessions: SessionService, store: AppStore
    ) -> None:
        """A Plex-linked account other than the owner is cut like any other."""
        admin, _ = _signed_in(sessions, "admin")
        _, running = _signed_in(sessions, "shared")
        summary = accounts.set_account_access(admin, "shared", allowed=False)
        assert summary.sign_in_allowed is False and summary.sign_in_kind.value == "plex"
        assert sessions.resolve(running) is None

    def test_giving_back_opens_no_session(
        self, accounts: AccountService, sessions: SessionService, store: AppStore
    ) -> None:
        """Given back, the account may sign in again; its ended sessions stay ended, none is opened."""
        admin, _ = _signed_in(sessions, "admin")
        _, running = _signed_in(sessions, "local")
        accounts.set_account_access(admin, "local", allowed=False)
        with patch.object(sessions, "open", wraps=sessions.open) as opened:
            summary = accounts.set_account_access(admin, "local", allowed=True)
        assert summary.sign_in_allowed is True and _row(store, "local").sign_in_allowed is True
        assert opened.call_count == 0
        assert sessions.resolve(running) is None

    @pytest.mark.parametrize("allowed", [True, False], ids=["allowed-again", "cut-again"])
    def test_the_value_already_held_changes_nothing(
        self, accounts: AccountService, sessions: SessionService, store: AppStore, allowed: bool
    ) -> None:
        """Setting the value the account holds answers it and writes nothing."""
        admin, _ = _signed_in(sessions, "admin")
        if not allowed:
            accounts.set_account_access(admin, "local", allowed=False)
        _, running = _signed_in(sessions, "local") if allowed else (None, None)
        before = _row(store, "local")
        summary = accounts.set_account_access(admin, "local", allowed=allowed)
        assert summary.sign_in_allowed is allowed
        assert _row(store, "local") == before
        if running is not None:
            assert sessions.resolve(running) is not None

    @pytest.mark.parametrize("account_id", ["local", "manager", "nobody"], ids=["other", "own", "unknown"])
    def test_a_manager_who_is_not_admin_is_refused_first(
        self, accounts: AccountService, sessions: SessionService, store: AppStore, account_id: str
    ) -> None:
        """403 ``account.access_admin_only`` whatever the account — its own, and one that does not exist."""
        manager, _ = _signed_in(sessions, "manager")
        before = store.accounts.account(account_id)
        with pytest.raises(AppForbidden) as caught:
            accounts.set_account_access(manager, account_id, allowed=False)
        assert caught.value.code == RefusalCode.ACCOUNT_ACCESS_ADMIN_ONLY
        assert store.accounts.account(account_id) == before

    def test_an_unknown_account_is_404(self, accounts: AccountService, sessions: SessionService) -> None:
        """For an Admin: 404 ``account.unknown``."""
        admin, _ = _signed_in(sessions, "admin")
        with pytest.raises(AppNotFound) as caught:
            accounts.set_account_access(admin, "nobody", allowed=False)
        assert caught.value.code == RefusalCode.ACCOUNT_UNKNOWN

    @pytest.mark.parametrize(
        ("actor_id", "account_id", "code"),
        [
            ("admin", "owner", RefusalCode.ACCOUNT_OWNER_ACCESS),
            ("owner", "owner", RefusalCode.ACCOUNT_OWNER_ACCESS),
            ("admin", "admin", RefusalCode.ACCOUNT_OWN_ACCESS),
        ],
        ids=["the-owner", "the-owner-itself", "its-own"],
    )
    def test_the_owner_and_its_own_account_are_refused(
        self,
        accounts: AccountService,
        sessions: SessionService,
        store: AppStore,
        actor_id: str,
        account_id: str,
        code: RefusalCode,
    ) -> None:
        """403 ``account.owner_access`` (checked before its own) and ``account.own_access``; nothing changed."""
        actor, running = _signed_in(sessions, actor_id)
        before = _row(store, account_id)
        with pytest.raises(AppForbidden) as caught:
            accounts.set_account_access(actor, account_id, allowed=False)
        assert caught.value.code == code
        assert _row(store, account_id) == before
        assert sessions.resolve(running) is not None

    def test_the_cut_and_the_revocation_are_one_transaction(
        self, accounts: AccountService, sessions: SessionService, store: AppStore
    ) -> None:
        """When the revocation fails, the account is not left cut: both commit or neither does."""
        admin, _ = _signed_in(sessions, "admin")
        _, running = _signed_in(sessions, "local")
        with (
            patch.object(AccountRepository, "revoke_sessions_of", side_effect=RuntimeError("disk")),
            pytest.raises(RuntimeError),
        ):
            accounts.set_account_access(admin, "local", allowed=False)
        assert _row(store, "local").sign_in_allowed is True
        assert sessions.resolve(running) is not None

    def test_publishes_nothing_and_logs_who_acted(
        self, accounts: AccountService, sessions: SessionService, bus: EventBus, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No event; one log line per change, naming the Admin; none for a no-op."""
        seen: list[object] = []
        bus.subscribe(Event, seen.append)
        admin, _ = _signed_in(sessions, "admin")
        _signed_in(sessions, "local")
        caplog.set_level(logging.DEBUG)
        accounts.set_account_access(admin, "local", allowed=False)
        accounts.set_account_access(admin, "local", allowed=False)
        accounts.set_account_access(admin, "local", allowed=True)
        assert seen == []
        changes = [line for line in _service_events(caplog) if line["event"].startswith("account_access_")]
        assert [(line["event"], line["account_id"], line["by"]) for line in changes] == [
            ("account_access_cut", "local", "admin"),
            ("account_access_given_back", "local", "admin"),
        ]
        assert changes[0]["sessions_revoked"] == 1


class TestCutSignIn:
    """The password door of a cut account."""

    def test_the_right_password_is_access_disabled_and_opens_nothing(
        self, accounts: AccountService, sessions: SessionService
    ) -> None:
        """Credentials proven: 403 ``auth.access_disabled``, after one scrypt run, no session opened."""
        admin, _ = _signed_in(sessions, "admin")
        accounts.set_account_access(admin, "local", allowed=False)
        with (
            patch.object(service_module, "verify_password", wraps=verify_password) as spy,
            patch.object(sessions, "open", wraps=sessions.open) as opened,
            pytest.raises(AppForbidden) as caught,
        ):
            _sign_in(accounts, "local")
        assert caught.value.code == RefusalCode.AUTH_ACCESS_DISABLED
        assert spy.call_count == 1
        assert opened.call_count == 0

    @pytest.mark.parametrize(
        ("account_id", "password"),
        [("local", _WRONG), ("shared", _PASSWORD)],
        ids=["wrong-password", "plex-linked"],
    )
    def test_unproven_credentials_stay_auth_refused(
        self, accounts: AccountService, sessions: SessionService, account_id: str, password: str
    ) -> None:
        """A cut account's wrong password, or a cut Plex-linked account's password: the one 401, one scrypt run."""
        admin, _ = _signed_in(sessions, "admin")
        accounts.set_account_access(admin, account_id, allowed=False)
        with (
            patch.object(service_module, "verify_password", wraps=verify_password) as spy,
            pytest.raises(AppUnauthenticated) as caught,
        ):
            _sign_in(accounts, account_id, password)
        assert caught.value.code == RefusalCode.AUTH_REFUSED
        assert spy.call_count == 1

    def test_a_refused_cut_sign_in_spends_no_failure(
        self, accounts: AccountService, sessions: SessionService, limiter: SlidingWindowRateLimiter
    ) -> None:
        """The credentials were right: the refusal is not a failed attempt, the client's budget is whole."""
        admin, _ = _signed_in(sessions, "admin")
        accounts.set_account_access(admin, "local", allowed=False)
        for _ in range(MAX_FAILED_ATTEMPTS + 1):
            with pytest.raises(AppForbidden):
                _sign_in(accounts, "local")
        assert limiter.allow("client")

    def test_given_back_the_account_signs_in(self, accounts: AccountService, sessions: SessionService) -> None:
        """Once given back, the right password opens a session again."""
        admin, _ = _signed_in(sessions, "admin")
        accounts.set_account_access(admin, "local", allowed=False)
        accounts.set_account_access(admin, "local", allowed=True)
        result = accounts.sign_in_with_password(
            "local@example.org", _PASSWORD, client_key="client", user_agent="pytest"
        )
        assert result.account.id == "local" and sessions.resolve(result.session_token) is not None

    def test_a_cut_landing_during_the_check_opens_no_session(
        self, accounts: AccountService, sessions: SessionService, store: AppStore
    ) -> None:
        """A cut committed while scrypt runs is read when the session would open: refused, nothing left live."""
        admin, _ = _signed_in(sessions, "admin")

        def cut_meanwhile(password: str, stored: str) -> bool:
            """Check the password, while an Admin cuts the account.

            Args:
                password: The password typed.
                stored: The stored hash.

            Returns:
                Whether it matches.
            """
            accounts.set_account_access(admin, "local", allowed=False)
            return verify_password(password, stored)

        with (
            patch.object(service_module, "verify_password", side_effect=cut_meanwhile),
            patch.object(sessions, "open", wraps=sessions.open) as opened,
            pytest.raises(AppForbidden) as caught,
        ):
            _sign_in(accounts, "local")
        assert caught.value.code == RefusalCode.AUTH_ACCESS_DISABLED
        assert opened.call_count == 0


def test_no_password_reaches_a_refusal_or_a_log(
    accounts: AccountService, sessions: SessionService, caplog: pytest.LogCaptureFixture
) -> None:
    """Neither the right nor a wrong password is in the access refusal or any log line."""
    admin, _ = _signed_in(sessions, "admin")
    caplog.set_level(logging.DEBUG)
    accounts.set_account_access(admin, "local", allowed=False)
    with pytest.raises(AppForbidden) as caught:
        _sign_in(accounts, "local")
    with pytest.raises(AppUnauthenticated):
        _sign_in(accounts, "local", _WRONG)
    logs = [record.msg for record in caplog.records]
    text = f"{logs} {caught.value} {caught.value.detail} {caught.value.params}"
    for secret in (_PASSWORD, _WRONG):
        assert secret not in text
