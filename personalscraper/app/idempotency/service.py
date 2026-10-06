"""A write's first answer, kept so that a replay with the same ``Idempotency-Key`` applies nothing.

A key is scoped to (account, key, operation): one account's answer is never handed to
another, and the same key on another method and path is another record. The first request
with a key CLAIMS it; its answer is then COMPLETED into the record, or the claim RELEASED
when the request failed on the server's side (a 5xx: nothing it did is known to have
held, so a retry must apply). A later claim reads the record:

- the same request (same fingerprint), answered → :class:`Replay`, nothing applied;
- the same request, still running → refused ``request.in_progress``: a concurrent
  duplicate is never applied twice, and the client retries it later;
- another request → refused ``request.key_reused``.

A claim left running past ``pending_s`` (its process died mid-request) is taken over; the
abandoned run can then no longer complete. Every record is swept ``retention_s`` after its
claim, at the next claim.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from personalscraper.app.errors import AppConflict, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.logger import get_logger

log = get_logger("app.idempotency")

#: How long a record is kept: a day covers an offline outbox replaying after a night away.
DEFAULT_RETENTION_S: Final = 24 * 3600.0

#: How long a claim may run before it is treated as abandoned. No v1 write runs this long:
#: a long act (a run, a rescrape) is enqueued and answered at once.
DEFAULT_PENDING_S: Final = 300.0


@dataclass(frozen=True)
class Claimed:
    """The key is this request's: apply it, then complete or release the claim.

    Attributes:
        claim_id: The run holding the claim.
    """

    claim_id: str


@dataclass(frozen=True)
class Replay:
    """The key's first answer, to answer again without applying anything.

    Attributes:
        status: Its status.
        body: Its body.
        content_type: Its ``Content-Type``, if it had one.
    """

    status: int
    body: bytes
    content_type: str | None


class IdempotencyService:
    """Claims, completes and releases idempotency keys over ``app.db``."""

    def __init__(
        self,
        store: AppStore,
        *,
        retention_s: float = DEFAULT_RETENTION_S,
        pending_s: float = DEFAULT_PENDING_S,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            retention_s: How long a record is kept after its claim.
            pending_s: How long a claim may run before it is taken over.
            clock: The epoch clock.
        """
        self._store = store
        self._retention_s = retention_s
        self._pending_s = pending_s
        self._clock = clock

    def claim(self, account_id: str, key: str, operation: str, fingerprint: str) -> Claimed | Replay:
        """Claim a key for one request, or read back its first answer.

        Args:
            account_id: The signed-in account.
            key: The request's ``Idempotency-Key``.
            operation: Its method and path, ``"POST /accounts"``.
            fingerprint: The digest of the request (method, path, query, body).

        Returns:
            :class:`Claimed` when the request is to be applied; :class:`Replay` when its
            first answer is stored.

        Raises:
            AppConflict: ``request.key_reused`` — the key was claimed by another request;
                ``request.in_progress`` — the same request is still running.
        """
        store = self._store
        now = self._clock()
        with store.immediate():
            store.idempotency.sweep(now - self._retention_s)
            row = store.idempotency.find(account_id, key, operation)
            if row is not None:
                if row.fingerprint != fingerprint:
                    raise AppConflict(
                        "The idempotency key was used for another request.", code=RefusalCode.REQUEST_KEY_REUSED
                    )
                if row.status is not None:
                    return Replay(status=row.status, body=row.body or b"", content_type=row.content_type)
                if now - row.created_at <= self._pending_s:
                    raise AppConflict(
                        "The request with this idempotency key is still running.",
                        code=RefusalCode.REQUEST_IN_PROGRESS,
                    )
                log.warning("idempotency_claim_taken_over", operation=operation, claimed_at=row.created_at)
            claim_id = uuid.uuid4().hex
            store.idempotency.claim(account_id, key, operation, fingerprint, claim_id, now)
        return Claimed(claim_id=claim_id)

    def complete(self, claim: Claimed, status: int, body: bytes, content_type: str | None) -> None:
        """Store a claimed request's answer, for its replays.

        Args:
            claim: The claim the request held.
            status: The answer's status.
            body: The answer's body.
            content_type: The answer's ``Content-Type``, if any.
        """
        if not self._store.idempotency.complete(claim.claim_id, status, body, content_type):
            log.warning("idempotency_claim_lost", status=status)

    def release(self, claim: Claimed) -> None:
        """Drop a claimed request's claim, storing nothing: its retry applies.

        Args:
            claim: The claim the request held.
        """
        self._store.idempotency.release(claim.claim_id)
