"""Push subscriptions — one FCM registration token per browser per device, owned by one account.

The subscriptions live in the environment's ``app`` store (Q2, 2026-10-01: one file per
environment — ``app-dev.db``, ``app-staging.db``, ``app.db``); the table is created by the
``app`` store's baseline migration (``app/store/migrations/001_baseline.sql``), and this
module is an implementation over a connection it is GIVEN. Nothing here opens a file.
``account_id`` is a foreign key to the accounts table (``003_push_account_fk.sql``): deleting
an account deletes its subscriptions.

Rules the store keeps:

- **one browser, one owner** — a token is UNIQUE; presented by another account, it moves to
  that account (the browser was signed into another account) and is un-revoked;
- **the client re-sends its token at every start** (Firebase's monthly refresh, and iOS
  reading the permission as ``default`` after a reload): ``upsert`` refreshes ``refreshed_at``;
- **a revoked subscription is never sent to**; ``revoke_stale`` retires those not refreshed
  for 270 days (Firebase's expiry of an idle token);
- **timestamps are epoch ``time.time()``**, as ``pipeline_run``.

The token is a credential of the device: it is never logged, and :class:`PushSubscription`
keeps it out of its ``repr``.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Literal, Protocol, get_args

from personalscraper.api.notify.fcm import PushOutcome, PushResult
from personalscraper.core.sqlite import serialised

PushPlatform = Literal["android", "ios", "desktop", "unknown"]
RevokeReason = Literal["token_dead", "unregistered", "signed_out", "stale"]

#: Firebase expires a token idle for 270 days.
STALE_AFTER_SECONDS = 270 * 86_400

#: Outcomes that count as one more CONSECUTIVE failure of a subscription.
_FAILURES = frozenset({PushOutcome.REJECTED, PushOutcome.UNREACHABLE})


@dataclass(frozen=True)
class PushSubscription:
    """One subscription row.

    Attributes:
        id: Row id.
        account_id: Foreign key to ``account.id``; deleting the account deletes the row.
        token: The FCM registration token — kept out of ``repr``.
        platform: ``android`` / ``ios`` / ``desktop`` / ``unknown``.
        user_agent: The browser's user agent, as the client sent it.
        created_at: First upload (epoch seconds).
        refreshed_at: Last upload by the client.
        last_sent_at: Last send attempt.
        last_outcome: The last send's ``PushOutcome`` code.
        failure_count: Consecutive ``rejected`` / ``unreachable`` sends.
        revoked_at: When it stopped being sent to; None while live.
        revoked_reason: Why.
    """

    id: int
    account_id: str
    token: str = field(repr=False)
    platform: PushPlatform
    user_agent: str | None
    created_at: float
    refreshed_at: float
    last_sent_at: float | None
    last_outcome: str | None
    failure_count: int
    revoked_at: float | None
    revoked_reason: RevokeReason | None


class PushSubscriptionStore(Protocol):
    """Where an environment's push subscriptions are kept."""

    def upsert(
        self, *, account_id: str, token: str, platform: PushPlatform, user_agent: str | None, now: float
    ) -> PushSubscription:
        """Creates a subscription, or refreshes it, moving it to the presenting account and un-revoking it."""
        ...

    def live_for(self, account_id: str) -> list[PushSubscription]:
        """Returns the account's subscriptions that are not revoked."""
        ...

    def revoke(self, token: str, *, reason: RevokeReason, now: float) -> None:
        """Stops sending to a token (a no-op when unknown or already revoked)."""
        ...

    def record(self, token: str, result: PushResult, *, now: float) -> None:
        """Records one send's outcome on the token's subscription."""
        ...

    def revoke_stale(self, *, not_refreshed_since: float, now: float) -> int:
        """Revokes every live subscription not refreshed since a moment; returns how many."""
        ...


_COLUMNS = (
    "id, account_id, token, platform, user_agent, created_at, refreshed_at, last_sent_at, last_outcome, "
    "failure_count, revoked_at, revoked_reason"
)


class SqlitePushSubscriptionStore:
    """:class:`PushSubscriptionStore` over a ``sqlite3.Connection`` it is given."""

    def __init__(self, conn: sqlite3.Connection, *, lock: threading.RLock | None = None) -> None:
        """Wraps a connection; creates nothing.

        Args:
            conn: An open connection to the environment's ``app`` store (``:memory:`` in tests).
            lock: The lock every user of ``conn`` holds around it (the store's); a lock of
                its own when ``conn`` is this store's alone.
        """
        self._conn = conn
        self._lock = lock if lock is not None else threading.RLock()

    def _one(self, token: str) -> PushSubscription:
        """Reads one subscription by token.

        Args:
            token: The registration token.

        Returns:
            The subscription.

        Raises:
            LookupError: No such token (the message carries no token).
        """
        row = self._conn.execute(f"SELECT {_COLUMNS} FROM push_subscription WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise LookupError("no push subscription for that token")
        return PushSubscription(*row)

    @serialised
    def upsert(
        self, *, account_id: str, token: str, platform: PushPlatform, user_agent: str | None, now: float
    ) -> PushSubscription:
        """Creates a subscription, or refreshes it, moving it to the presenting account and un-revoking it.

        A subscription revoked or moved to another account starts its failure count afresh.

        Args:
            account_id: The account presenting the token.
            token: The registration token.
            platform: The device's platform.
            user_agent: The browser's user agent.
            now: Epoch seconds.

        Returns:
            The subscription as stored.

        Raises:
            ValueError: An unknown platform.
        """
        if platform not in get_args(PushPlatform):
            raise ValueError(f"unknown push platform {platform!r}")
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO push_subscription (account_id, token, platform, user_agent, created_at, refreshed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    failure_count = CASE
                        WHEN push_subscription.revoked_at IS NOT NULL
                          OR push_subscription.account_id != excluded.account_id THEN 0
                        ELSE push_subscription.failure_count END,
                    account_id = excluded.account_id,
                    platform = excluded.platform,
                    user_agent = excluded.user_agent,
                    refreshed_at = excluded.refreshed_at,
                    revoked_at = NULL,
                    revoked_reason = NULL
                """,
                (account_id, token, platform, user_agent, now, now),
            )
        return self._one(token)

    @serialised
    def live_for(self, account_id: str) -> list[PushSubscription]:
        """Returns the account's subscriptions that are not revoked, oldest first.

        Args:
            account_id: The account.

        Returns:
            The live subscriptions.
        """
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM push_subscription WHERE account_id = ? AND revoked_at IS NULL ORDER BY id",
            (account_id,),
        ).fetchall()
        return [PushSubscription(*row) for row in rows]

    @serialised
    def revoke(self, token: str, *, reason: RevokeReason, now: float) -> None:
        """Stops sending to a token; a no-op when unknown or already revoked (the first reason stays).

        Args:
            token: The registration token.
            reason: Why.
            now: Epoch seconds.
        """
        with self._conn:
            self._conn.execute(
                "UPDATE push_subscription SET revoked_at = ?, revoked_reason = ? "
                "WHERE token = ? AND revoked_at IS NULL",
                (now, reason, token),
            )

    @serialised
    def record(self, token: str, result: PushResult, *, now: float) -> None:
        """Records one send's outcome.

        ``rejected`` and ``unreachable`` add one to the consecutive failure count; a
        delivery resets it; the other outcomes (a deferral, our misconfiguration, a dead
        token, revoked separately) leave it as it is — they say nothing about this device.

        Args:
            token: The registration token.
            result: The send's result.
            now: Epoch seconds.
        """
        if result.outcome in _FAILURES:
            count = "failure_count + 1"
        elif result.outcome is PushOutcome.DELIVERED:
            count = "0"
        else:
            count = "failure_count"
        with self._conn:
            self._conn.execute(
                f"UPDATE push_subscription SET last_sent_at = ?, last_outcome = ?, failure_count = {count} "
                "WHERE token = ?",
                (now, result.outcome.value, token),
            )

    @serialised
    def revoke_stale(self, *, not_refreshed_since: float, now: float) -> int:
        """Revokes every live subscription not refreshed since a moment, as ``stale``.

        Args:
            not_refreshed_since: The cut-off (``now - STALE_AFTER_SECONDS`` in practice).
            now: Epoch seconds.

        Returns:
            How many were revoked.
        """
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE push_subscription SET revoked_at = ?, revoked_reason = 'stale' "
                "WHERE revoked_at IS NULL AND refreshed_at < ?",
                (now, not_refreshed_since),
            )
        return cursor.rowcount


__all__ = [
    "STALE_AFTER_SECONDS",
    "PushPlatform",
    "PushSubscription",
    "PushSubscriptionStore",
    "RevokeReason",
    "SqlitePushSubscriptionStore",
]
