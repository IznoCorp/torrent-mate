"""``SignInNotifier``: a session a Plex sign-in opened is told to the account that holds it.

The operator's ruling Q4 A: a Plex sign-in can be phished — whoever has a person confirm a PIN
signs in as them — so every new Plex session reaches its holder twice:

- **in the application**: one notice for the account, a code and its parameters, which the
  interface words in the account's language;
- **by push**, when the account's ``account.sign_in`` switch is on (on until it turns it off,
  per account on all its devices — ruling FCM Q1 A): the same code, the ``language`` the
  account speaks, which the device's worker words it in (FG-2 A); the tap opens Profil, where
  the session can be ended.

The code names the device when its user agent does (``account.sign_in.device``, parameter
``device``), else ``account.sign_in.unknown_device``. A push that fails is logged and never
loses the notice; nothing here ever fails the sign-in — the bus isolates its subscribers too.

The notice is written in the request, before the sign-in answers; the push is not: each send can
wait on FCM for seconds per device, so it runs on a worker of its own, after the handler returns.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Final

from personalscraper.api.notify.fcm import PushMessage
from personalscraper.app.accounts.events import PlexSessionOpened
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.notice_repository import NoticeParam
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.logger import get_logger
from personalscraper.push.dispatch import PushChannel

log = get_logger("app.accounts.sign_in_notice")

#: The push type the account switches (the contract's ``NotificationType``).
SIGN_IN_NOTIFICATION_TYPE: Final = "account.sign_in"

#: The code of a sign-in whose device the user agent names; parameter ``device``.
SIGN_IN_DEVICE_CODE: Final = "account.sign_in.device"

#: The code of a sign-in whose user agent names no device; no parameter.
SIGN_IN_UNKNOWN_DEVICE_CODE: Final = "account.sign_in.unknown_device"

#: Where the push's tap lands: Profil, which lists the sessions and ends one.
_PROFILE_LINK: Final = "/account"


class SignInNotifier:
    """Tells an account of each session a Plex sign-in opened: an in-app notice, and a push under its switch."""

    def __init__(
        self,
        store: AppStore,
        push: PushChannel,
        *,
        clock: Callable[[], float] = time.time,
        defer: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        """Build the notifier; nothing is opened until the first event.

        Args:
            store: The environment's ``app.db``: the account, its switch, its notices.
            push: The push channel — the dispatcher, or :class:`UnconfiguredPush` without FCM.
            clock: The epoch clock.
            defer: Runs a send apart from the caller; by default a single worker thread of the
                notifier's own. A test passes a direct call to read the push at once.
        """
        self._store = store
        self._push = push
        self._clock = clock
        self._executor: ThreadPoolExecutor | None = None
        self._defer = defer if defer is not None else self._submit

    def _submit(self, send: Callable[[], None]) -> None:
        """Run a send on the notifier's worker, started on first use.

        Args:
            send: The send; it logs its own failure and never raises.
        """
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sign-in-push")
        self._executor.submit(send)

    def close(self) -> None:
        """Wait for the sends already asked, then release the worker; idempotent."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

    def subscribe(self, bus: EventBus) -> SubscriptionToken:
        """Listen for :class:`PlexSessionOpened` on a bus.

        Args:
            bus: The process's bus.

        Returns:
            The subscription's token.
        """
        return bus.subscribe(PlexSessionOpened, self.on_plex_session_opened)

    def on_plex_session_opened(self, event: PlexSessionOpened) -> None:
        """Write the account's notice, then push it when its switch allows.

        Args:
            event: The session opened.
        """
        store = self._store
        account = store.accounts.account(AccountId(event.account_id))
        if account is None:
            # Deleted between its sign-in and now: there is nobody left to tell.
            log.info("sign_in_notice.account_gone", account_id=event.account_id)
            return
        params: dict[str, NoticeParam] = {}
        if event.device:
            code = SIGN_IN_DEVICE_CODE
            params["device"] = event.device
        else:
            code = SIGN_IN_UNKNOWN_DEVICE_CODE
        store.notices.insert_notice(account.id, code, params, now=self._clock())
        if not store.preferences.enabled(account.id, SIGN_IN_NOTIFICATION_TYPE):
            log.info("sign_in_notice.push_switched_off", account_id=account.id)
            return
        account_id = account.id
        language = account.language.value

        def send() -> None:
            """Build the message and push it; whatever breaks is logged, the notice is already written."""
            try:
                message = PushMessage(code=code, params=params, link=_PROFILE_LINK, language=language)
                self._push.notify_account(account_id, message)
            except Exception as exc:
                log.warning(
                    "sign_in_notice.push_failed", account_id=account_id, error=type(exc).__name__, exc_info=True
                )

        self._defer(send)
