"""The idempotency records' rows in ``app.db``.

Rows ↔ dataclasses, and nothing more: when a record is replayed, refused, taken over or
swept is the service's rule (:mod:`personalscraper.app.idempotency.service`).

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, and the service wraps a claim's several statements in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass

from personalscraper.core.sqlite import serialised


@dataclass(frozen=True)
class IdempotencyRow:
    """One record.

    Attributes:
        fingerprint: The digest of the request that claimed the key.
        claim_id: The run that claimed it.
        created_at: When it was claimed (epoch seconds).
        status: The stored answer's status; ``None`` while the run has not answered.
        body: The stored answer's body.
        content_type: The stored answer's ``Content-Type``, if it had one.
    """

    fingerprint: str
    claim_id: str
    created_at: float
    status: int | None
    body: bytes | None
    content_type: str | None


class IdempotencyRepository:
    """The idempotency records over one ``app.db`` connection it is GIVEN; it opens nothing."""

    def __init__(self, conn: sqlite3.Connection, *, lock: threading.RLock | None = None) -> None:
        """Wrap an open, migrated ``app.db`` connection.

        Args:
            conn: The connection, in autocommit mode.
            lock: The lock every user of ``conn`` holds around it (the store's); a lock of
                its own when ``conn`` is this repository's alone.
        """
        self._conn = conn
        self._lock = lock if lock is not None else threading.RLock()

    @serialised
    def find(self, account_id: str, key: str, operation: str) -> IdempotencyRow | None:
        """Read one record.

        Args:
            account_id: The account the key belongs to.
            key: The ``Idempotency-Key``.
            operation: The method and path, ``"POST /accounts"``.

        Returns:
            The record, or ``None``.
        """
        row = self._conn.execute(
            "SELECT fingerprint, claim_id, created_at, status, body, content_type FROM idempotency_record"
            " WHERE account_id = ? AND idempotency_key = ? AND operation = ?",
            (account_id, key, operation),
        ).fetchone()
        if row is None:
            return None
        return IdempotencyRow(
            fingerprint=row[0],
            claim_id=row[1],
            created_at=row[2],
            status=row[3],
            body=None if row[4] is None else bytes(row[4]),
            content_type=row[5],
        )

    @serialised
    def claim(
        self, account_id: str, key: str, operation: str, fingerprint: str, claim_id: str, created_at: float
    ) -> None:
        """Write a running claim, replacing a record of the same identity.

        Args:
            account_id: The account the key belongs to.
            key: The ``Idempotency-Key``.
            operation: The method and path.
            fingerprint: The digest of the claiming request.
            claim_id: The run claiming it.
            created_at: Now (epoch seconds).
        """
        self._conn.execute(
            "INSERT OR REPLACE INTO idempotency_record"
            " (account_id, idempotency_key, operation, fingerprint, claim_id, created_at, status, body, content_type)"
            " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
            (account_id, key, operation, fingerprint, claim_id, created_at),
        )

    @serialised
    def complete(self, claim_id: str, status: int, body: bytes, content_type: str | None) -> bool:
        """Store the answer of the run that still holds its claim.

        Args:
            claim_id: The run answering.
            status: The answer's status.
            body: The answer's body.
            content_type: The answer's ``Content-Type``, if any.

        Returns:
            True when the claim was still the run's; False when it was taken over or swept.
        """
        cursor = self._conn.execute(
            "UPDATE idempotency_record SET status = ?, body = ?, content_type = ?"
            " WHERE claim_id = ? AND status IS NULL",
            (status, body, content_type, claim_id),
        )
        return cursor.rowcount == 1

    @serialised
    def release(self, claim_id: str) -> None:
        """Delete the running claim of a run, leaving nothing stored.

        Args:
            claim_id: The run whose claim goes.
        """
        self._conn.execute("DELETE FROM idempotency_record WHERE claim_id = ? AND status IS NULL", (claim_id,))

    @serialised
    def sweep(self, before: float) -> int:
        """Delete every record claimed before an instant.

        Args:
            before: The oldest ``created_at`` kept (epoch seconds).

        Returns:
            How many records went.
        """
        return self._conn.execute("DELETE FROM idempotency_record WHERE created_at < ?", (before,)).rowcount

    @serialised
    def count(self) -> int:
        """Count the records.

        Returns:
            How many records the table holds.
        """
        return int(self._conn.execute("SELECT COUNT(*) FROM idempotency_record").fetchone()[0])
