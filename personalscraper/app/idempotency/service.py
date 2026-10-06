"""A write's first answer, kept so that a replay with the same ``Idempotency-Key`` applies nothing.

A key is scoped to (account, key, operation): one account's answer is never handed to
another, and the same key on another method and path is another record. The first request
with a key CLAIMS it; its answer is then COMPLETED into the record when it will not change
however often the request is sent (a success, or a refusal in :data:`FINAL_REFUSALS`), or
the claim RELEASED when it may (a 401, 403, 408, 423 or 429 says nothing of the write; a 5xx
is taken as rolled back), so the retry applies. A later claim reads the record:

- the same request (same fingerprint), answered → :class:`Replay`, nothing applied;
- the same request, still running → refused ``request.in_progress``: a concurrent
  duplicate is never applied twice, and the client retries it later;
- another request → refused ``request.key_reused``.

A claim left running past ``pending_s`` (its process died mid-request) is taken over; the
abandoned run can then no longer complete. Every record is swept ``retention_s`` after its
claim, at the next claim.

Two residuals are known and accepted, each pinned by a test so a change is seen:

- a 5xx raised AFTER the write committed releases the claim like any 5xx, and the retry
  applies the write a second time;
- a request still running past ``pending_s`` cannot be told from a dead one: the retry takes
  its claim over and applies the write while the original may still commit it.

A request's fingerprint is an HMAC-SHA256 keyed by a 32-byte secret kept in a file of its
own beside ``app.db`` (mode 0600, made on first use), never in ``app.db``: a stolen
``app.db`` holds no digest a guessed password in a body can be tested against.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.errors import AppConflict, RefusalCode
from personalscraper.app.idempotency.ids import ClaimId
from personalscraper.app.store.store import AppStore
from personalscraper.logger import get_logger

log = get_logger("app.idempotency")

#: How long a record is kept: a day covers an offline outbox replaying after a night away.
DEFAULT_RETENTION_S: Final = 24 * 3600.0

#: How long a claim may run before it is treated as abandoned. No v1 write runs this long:
#: a long act (a run, a rescrape) is enqueued and answered at once.
DEFAULT_PENDING_S: Final = 300.0

#: The refusals kept and replayed: those that say something about the REQUEST, so sending it
#: again gives them again. The client's outbox drops exactly these as final
#: (``FINAL_STATUSES`` in ``webui/design/src/lib/query-client.ts``) and re-sends anything
#: else with the same key, which must then apply.
FINAL_REFUSALS: Final = frozenset({400, 404, 405, 409, 410, 415, 422})

#: The length of the fingerprint key, in bytes.
FINGERPRINT_KEY_BYTES: Final = 32


def is_kept(status: int) -> bool:
    """Whether an answer is kept for the replays, or its claim released for the retry.

    Args:
        status: The answer's status.

    Returns:
        True for a success (2xx) or a final refusal (:data:`FINAL_REFUSALS`).
    """
    return 200 <= status < 300 or status in FINAL_REFUSALS


def fingerprint_key_path(app_db: Path) -> Path:
    """Where an environment's fingerprint key file lives: beside its ``app.db``, never in it.

    Args:
        app_db: The environment's ``app`` store file.

    Returns:
        ``<data_dir>/<app store stem>.idempotency.key``.
    """
    return app_db.with_name(f"{app_db.stem}.idempotency.key")


class FingerprintKeyError(RuntimeError):
    """The fingerprint key file holds something other than a key: a server defect."""


def _load_or_make_key(path: Path) -> bytes:
    """Read the fingerprint key file, making it first when there is none.

    Made whole or not at all: the key is written to a private temporary file, then linked
    to ``path``, which fails when another process linked its own first — whose key is then
    read, so every process of the environment holds the same key.

    Args:
        path: The key file.

    Returns:
        The key.

    Raises:
        FingerprintKeyError: The file does not hold a key of :data:`FINGERPRINT_KEY_BYTES`.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        draft = path.with_name(f".{path.name}.{uuid.uuid4().hex}")
        descriptor = os.open(draft, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(secrets.token_bytes(FINGERPRINT_KEY_BYTES))
            try:
                os.link(draft, path)
            except FileExistsError:
                pass
        finally:
            draft.unlink(missing_ok=True)
    key = path.read_bytes()
    if len(key) != FINGERPRINT_KEY_BYTES:
        raise FingerprintKeyError(f"{path} holds {len(key)} bytes, not a {FINGERPRINT_KEY_BYTES} bytes key.")
    return key


@dataclass(frozen=True)
class Claimed:
    """The key is this request's: apply it, then complete or release the claim.

    Attributes:
        claim_id: The run holding the claim.
    """

    claim_id: ClaimId


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
        key_path: Path,
        retention_s: float = DEFAULT_RETENTION_S,
        pending_s: float = DEFAULT_PENDING_S,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            key_path: The fingerprint key file, read (or made) on the first fingerprint.
            retention_s: How long a record is kept after its claim.
            pending_s: How long a claim may run before it is taken over.
            clock: The epoch clock.
        """
        self._store = store
        self._retention_s = retention_s
        self._pending_s = pending_s
        self._clock = clock
        self._key_path = key_path
        self._key: bytes | None = None
        self._key_lock = threading.Lock()

    def fingerprint(self, method: str, path: str, query: str, body: bytes) -> str:
        """Digest what makes two requests the same request, under the server's key.

        Args:
            method: The method, upper case.
            path: The path.
            query: The raw query string.
            body: The raw body.

        Returns:
            The HMAC-SHA256 hex of the four, each length-prefixed so no two splits collide.
        """
        digest = hmac.new(self._fingerprint_key(), digestmod=hashlib.sha256)
        for part in (method.encode(), path.encode(), query.encode(), body):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
        return digest.hexdigest()

    def _fingerprint_key(self) -> bytes:
        """The fingerprint key, read once per process.

        Returns:
            The key.
        """
        with self._key_lock:
            if self._key is None:
                self._key = _load_or_make_key(self._key_path)
            return self._key

    def claim(self, account_id: AccountId, key: str, operation: str, fingerprint: str) -> Claimed | Replay:
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
            claim_id = ClaimId(uuid.uuid4().hex)
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
