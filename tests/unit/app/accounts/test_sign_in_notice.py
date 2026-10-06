"""Unit tests for ``personalscraper.app.accounts.sign_in_notice`` — a new Plex session told to its holder.

Each :class:`PlexSessionOpened` writes one in-app notice for the account (a code and its
parameters, never a sentence) and, when the account's ``account.sign_in`` switch is on, pushes
the same code to its devices, worded by the worker in the ACCOUNT's language. A push channel that
fails, or is not configured, never loses the in-app notice.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.api.notify.fcm import PushMessage
from personalscraper.app.accounts.events import PlexSessionOpened
from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.sign_in_notice import (
    SIGN_IN_NOTIFICATION_TYPE,
    SignInNotifier,
)
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus
from personalscraper.i18n import Language
from personalscraper.push.dispatch import DispatchReport, UnconfiguredPush
from tests.conftest import LoggedEvents

_ACCOUNT = "account-alice"
_OTHER = "account-bob"
_NOW = 5_000.0


class _Push:
    """Records each fan-out it is asked for; raises when told to.

    Attributes:
        sent: ``(account_id, message)`` per call.
        fails: When True every call raises.
    """

    def __init__(self) -> None:
        """Start with nothing sent."""
        self.sent: list[tuple[str, PushMessage]] = []
        self.fails = False

    def notify_account(self, account_id: str, message: PushMessage) -> DispatchReport:
        """Record the fan-out.

        Args:
            account_id: The account.
            message: The message.

        Returns:
            An empty report.

        Raises:
            RuntimeError: When :attr:`fails`.
        """
        if self.fails:
            raise RuntimeError("the channel broke")
        self.sent.append((account_id, message))
        return DispatchReport()


def _account(account_id: str, language: Language) -> Account:
    """An account speaking one language.

    Args:
        account_id: Its key.
        language: Its language.

    Returns:
        The account.
    """
    return Account(
        id=account_id,
        name=account_id,
        email=f"{account_id}@example.org",
        avatar="",
        role_id="household",
        password_hash=None,
        created_at=1.0,
        updated_at=1.0,
        language=language,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` holding two accounts, one French, one English.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    app_store.accounts.insert_account(_account(_ACCOUNT, Language.FR))
    app_store.accounts.insert_account(_account(_OTHER, Language.EN))
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def push() -> _Push:
    """The push channel's fake.

    Returns:
        The fake.
    """
    return _Push()


@pytest.fixture
def notifier(store: AppStore, push: _Push) -> SignInNotifier:
    """The notifier over the store and the fake channel.

    Args:
        store: The store.
        push: The fake channel.

    Returns:
        The notifier.
    """
    return SignInNotifier(store, push, clock=lambda: _NOW)


class TestInAppNotice:
    """The in-app channel: one notice per session opened, the account's own."""

    def test_a_sign_in_writes_one_notice_naming_the_device(self, notifier: SignInNotifier, store: AppStore) -> None:
        """Code ``account.sign_in.device`` with the device; nothing for another account."""
        notifier.on_plex_session_opened(PlexSessionOpened(account_id=_ACCOUNT, device="Firefox · macOS"))

        notices = store.notices.notices_of(_ACCOUNT, limit=10)
        assert [(n.code, dict(n.params), n.created_at) for n in notices] == [
            ("account.sign_in.device", {"device": "Firefox · macOS"}, _NOW)
        ]
        assert store.notices.notices_of(_OTHER, limit=10) == []

    def test_an_unnamed_device_has_its_own_code_and_no_parameter(
        self, notifier: SignInNotifier, store: AppStore
    ) -> None:
        """A user agent that names nothing: ``account.sign_in.unknown_device``, no parameter."""
        notifier.on_plex_session_opened(PlexSessionOpened(account_id=_ACCOUNT, device=None))

        notices = store.notices.notices_of(_ACCOUNT, limit=10)
        assert [(n.code, dict(n.params)) for n in notices] == [("account.sign_in.unknown_device", {})]

    def test_a_failing_push_channel_keeps_the_notice(
        self, notifier: SignInNotifier, store: AppStore, push: _Push, logged_events: LoggedEvents
    ) -> None:
        """The push raises: the notice is written all the same, and the failure is logged."""
        push.fails = True

        with logged_events() as logs:
            notifier.on_plex_session_opened(PlexSessionOpened(account_id=_ACCOUNT, device="Firefox · macOS"))

        assert len(store.notices.notices_of(_ACCOUNT, limit=10)) == 1
        assert "sign_in_notice.push_failed" in [entry["event"] for entry in logs]


class TestPush:
    """The push channel: the same code, the account's language, under its switch."""

    def test_pushes_the_code_in_the_accounts_language_to_profil(self, notifier: SignInNotifier, push: _Push) -> None:
        """One fan-out to the account: its code, the device, ``language`` = the account's, the tap on Profil."""
        notifier.on_plex_session_opened(PlexSessionOpened(account_id=_OTHER, device="Safari · iOS"))

        assert len(push.sent) == 1
        account_id, message = push.sent[0]
        assert account_id == _OTHER
        assert message.code == "account.sign_in.device"
        assert dict(message.params) == {"device": "Safari · iOS"}
        assert message.language == "en"
        assert message.link == "/account"

    def test_a_french_account_is_pushed_in_french(self, notifier: SignInNotifier, push: _Push) -> None:
        """The language follows the recipient account, not the server's."""
        notifier.on_plex_session_opened(PlexSessionOpened(account_id=_ACCOUNT, device=None))

        assert [message.language for _, message in push.sent] == ["fr"]

    def test_a_switch_turned_off_pushes_nothing_but_keeps_the_notice(
        self, notifier: SignInNotifier, store: AppStore, push: _Push
    ) -> None:
        """``account.sign_in`` off for the account: no push; the in-app notice is still written."""
        store.preferences.set_enabled(_ACCOUNT, SIGN_IN_NOTIFICATION_TYPE, enabled=False, now=1.0)

        notifier.on_plex_session_opened(PlexSessionOpened(account_id=_ACCOUNT, device="Firefox · macOS"))

        assert push.sent == []
        assert len(store.notices.notices_of(_ACCOUNT, limit=10)) == 1

    def test_a_switch_turned_back_on_pushes(self, notifier: SignInNotifier, store: AppStore, push: _Push) -> None:
        """Off then on again: pushed."""
        store.preferences.set_enabled(_ACCOUNT, SIGN_IN_NOTIFICATION_TYPE, enabled=False, now=1.0)
        store.preferences.set_enabled(_ACCOUNT, SIGN_IN_NOTIFICATION_TYPE, enabled=True, now=2.0)

        notifier.on_plex_session_opened(PlexSessionOpened(account_id=_ACCOUNT, device=None))

        assert len(push.sent) == 1

    def test_another_accounts_switch_does_not_count(
        self, notifier: SignInNotifier, store: AppStore, push: _Push
    ) -> None:
        """The switch is per account: Bob's off leaves Alice pushed."""
        store.preferences.set_enabled(_OTHER, SIGN_IN_NOTIFICATION_TYPE, enabled=False, now=1.0)

        notifier.on_plex_session_opened(PlexSessionOpened(account_id=_ACCOUNT, device=None))

        assert [account_id for account_id, _ in push.sent] == [_ACCOUNT]

    def test_an_account_gone_meanwhile_is_told_nothing(self, notifier: SignInNotifier, push: _Push) -> None:
        """An event naming no account writes nothing and pushes nothing."""
        notifier.on_plex_session_opened(PlexSessionOpened(account_id="account-gone", device=None))

        assert push.sent == []


class TestWiring:
    """The notifier listens on the bus it is subscribed to."""

    def test_subscribed_it_answers_the_event(self, notifier: SignInNotifier, store: AppStore) -> None:
        """``subscribe`` then an emit: the notice is written."""
        bus = EventBus()
        notifier.subscribe(bus)

        bus.emit(PlexSessionOpened(account_id=_ACCOUNT, device=None))

        assert len(store.notices.notices_of(_ACCOUNT, limit=10)) == 1


class TestUnconfiguredPush:
    """No FCM sender configured: the push channel says so, and sends nothing."""

    def test_logs_not_configured_and_reports_nothing_delivered(self, logged_events: LoggedEvents) -> None:
        """``push.not_configured`` with the account and the code; an empty report."""
        with logged_events() as logs:
            report = UnconfiguredPush().notify_account(_ACCOUNT, PushMessage(code="account.sign_in.unknown_device"))

        assert report == DispatchReport()
        events = [entry for entry in logs if entry["event"] == "push.not_configured"]
        assert [(entry["account_id"], entry["code"]) for entry in events] == [
            (_ACCOUNT, "account.sign_in.unknown_device")
        ]
