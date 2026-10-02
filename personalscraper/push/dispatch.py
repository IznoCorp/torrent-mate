"""Fan one push message out to every live device of one account.

``PushDispatcher.notify_account`` sends the message to each live subscription of the
account, revokes a token FCM declares dead, records every outcome on its subscription,
and reports the counts. It decides nothing else: no trigger, no recipient policy, no
words (K5), and **no retry loop** (NE-DOIT-PAS-8) — a deferral is reported with its
back-off, and the re-send is the caller's.

Two answers stop the fan-out, because they concern the whole channel, not one device:

- ``misconfigured`` — our credentials or project are wrong; every other device would
  answer the same, and Système must say the CHANNEL is broken (``misconfigured=True``);
- ``quota_exceeded`` — the project's quota (any 429, decided once by ``classify``; the
  dispatcher reads the outcome, never an error string); the devices not yet tried are
  counted as deferred, behind the same back-off.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from personalscraper.api.notify.fcm import PushMessage, PushOutcome, PushResult
from personalscraper.logger import get_logger
from personalscraper.push.store import PushSubscriptionStore

log = get_logger("push.dispatch")


class PushSender(Protocol):
    """What the dispatcher needs of a sender — ``FcmSender`` satisfies it."""

    def send(self, token: str, message: PushMessage, *, validate_only: bool = False) -> PushResult:
        """Sends one message to one token; never raises on delivery."""
        ...


@dataclass(frozen=True)
class DispatchReport:
    """What one fan-out did.

    Attributes:
        delivered: Devices FCM accepted the message for.
        revoked: Dead tokens revoked.
        deferred: ``retry_later`` and ``quota_exceeded`` answers, plus the devices a quota stop left untried.
        failed: ``rejected``, ``unreachable`` and ``misconfigured`` answers.
        misconfigured: True ⇒ the channel is broken (credentials / project), not a device.
        retry_after_seconds: The longest back-off a deferral asked for, if any.
    """

    delivered: int = 0
    revoked: int = 0
    deferred: int = 0
    failed: int = 0
    misconfigured: bool = False
    retry_after_seconds: float | None = None


class PushDispatcher:
    """Sends one message to every live device of an account."""

    def __init__(
        self, sender: PushSender, store: PushSubscriptionStore, clock: Callable[[], float] = time.time
    ) -> None:
        """Builds the dispatcher.

        Args:
            sender: The FCM sender.
            store: The environment's subscription store.
            clock: Epoch seconds (``time.time``, as ``pipeline_run``).
        """
        self._sender = sender
        self._store = store
        self._clock = clock

    def notify_account(self, account_id: str, message: PushMessage) -> DispatchReport:
        """Every live subscription of the account, one send each; ``token_dead`` ⇒ revoke; every result recorded.

        Args:
            account_id: K1's account key.
            message: What to say, as facts.

        Returns:
            The counts; never raises on a delivery failure.
        """
        subscriptions = self._store.live_for(account_id)
        delivered = revoked = deferred = failed = 0
        misconfigured = False
        retry_after: float | None = None
        for index, subscription in enumerate(subscriptions):
            result = self._sender.send(subscription.token, message)
            now = self._clock()
            self._store.record(subscription.token, result, now=now)
            outcome = result.outcome
            if outcome is PushOutcome.DELIVERED:
                delivered += 1
            elif outcome is PushOutcome.TOKEN_DEAD:
                self._store.revoke(subscription.token, reason="token_dead", now=now)
                revoked += 1
            elif outcome in (PushOutcome.RETRY_LATER, PushOutcome.QUOTA_EXCEEDED):
                deferred += 1
                if result.retry_after_seconds is not None:
                    retry_after = max(retry_after or 0.0, result.retry_after_seconds)
                # The project's quota: every other send would meet it — they are deferred untried.
                if outcome is PushOutcome.QUOTA_EXCEEDED:
                    deferred += len(subscriptions) - index - 1
                    break
            else:
                failed += 1
                if outcome is PushOutcome.MISCONFIGURED:
                    misconfigured = True
                    break
        report = DispatchReport(delivered, revoked, deferred, failed, misconfigured, retry_after)
        log.info(
            "push.dispatched",
            account_id=account_id,
            code=message.code,
            devices=len(subscriptions),
            delivered=delivered,
            revoked=revoked,
            deferred=deferred,
            failed=failed,
            misconfigured=misconfigured,
        )
        return report


__all__ = ["DispatchReport", "PushDispatcher", "PushSender"]
