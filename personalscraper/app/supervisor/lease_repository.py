"""The supervisor's lease in ``app.db`` — the one ``run_lease`` row, or none.

Rows ↔ :class:`~personalscraper.app.supervisor.model.Lease`. The claim is one ``BEGIN IMMEDIATE``
transaction (read the row, ask the model whether it is claimable, write): the lease is data, not a
held SQLite lock, so the transaction is a brief leaf and the lock order is unchanged. The refusal of
a second holder is the model's rule (:meth:`~personalscraper.app.supervisor.model.Lease.claimable`);
the base only keeps the table to one row.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from personalscraper.app.supervisor.model import Lease
from personalscraper.core.sqlite import safe_rollback, serialised


class LeaseRepository:
    """The ``run_lease`` row over one ``app.db`` connection it is GIVEN; it opens nothing."""

    def __init__(self, conn: sqlite3.Connection, *, lock: threading.RLock | None = None) -> None:
        """Wrap an open, migrated ``app.db`` connection.

        Args:
            conn: The connection, in autocommit mode.
            lock: The lock every user of ``conn`` holds around it (the store's); a lock of
                its own when ``conn`` is this repository's alone.
        """
        self._conn = conn
        self._lock = lock if lock is not None else threading.RLock()

    @contextmanager
    def _writer(self) -> Iterator[None]:
        """Hold the writer lock for the read-decide-write of one claim.

        Joins the caller's transaction when there is one (``AppStore.immediate``); opens and ends
        its own otherwise.

        Yields:
            Nothing.

        Raises:
            BaseException: Whatever the block raised, after the rollback.
        """
        if self._conn.in_transaction:
            yield
            return
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            safe_rollback(self._conn)
            raise
        try:
            self._conn.execute("COMMIT")
        except BaseException:
            safe_rollback(self._conn)
            raise

    @staticmethod
    def _lease(row: tuple[object, ...]) -> Lease:
        """Build the lease from a ``run_lease`` row (without its ``id``).

        Args:
            row: ``holder_pid, holder_host, taken_at, renewed_at, expires_at``.

        Returns:
            The lease.
        """
        pid, host, taken_at, renewed_at, expires_at = row
        return Lease(
            holder_pid=int(pid),  # type: ignore[call-overload]
            holder_host=str(host),
            taken_at=float(taken_at),  # type: ignore[arg-type]
            renewed_at=float(renewed_at),  # type: ignore[arg-type]
            expires_at=float(expires_at),  # type: ignore[arg-type]
        )

    @serialised
    def read(self) -> Lease | None:
        """The lease as stored, live or not.

        Returns:
            The lease, or ``None`` when nobody holds one.
        """
        row = self._conn.execute(
            "SELECT holder_pid, holder_host, taken_at, renewed_at, expires_at FROM run_lease WHERE id = 1"
        ).fetchone()
        return None if row is None else self._lease(row)

    @serialised
    def claim(
        self, holder_pid: int, holder_host: str, now: float, ttl_s: float, pid_alive: Callable[[int], bool]
    ) -> Lease | None:
        """Take the lease if nobody holds it, or the one who does may be replaced.

        The claimer's ``holder_host`` is this machine: a dead holder is only taken over on the same host.

        Args:
            holder_pid: The claimer's process id.
            holder_host: The machine it runs on.
            now: The epoch of the claim.
            ttl_s: How long the lease lives, in seconds.
            pid_alive: Whether a process id names a live process of this machine.

        Returns:
            The new lease, or ``None`` when a live lease of a live holder stands.
        """
        with self._writer():
            held = self.read()
            if held is not None and not held.claimable(now, pid_alive, holder_host):
                return None
            lease = Lease(
                holder_pid=holder_pid, holder_host=holder_host, taken_at=now, renewed_at=now, expires_at=now + ttl_s
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO run_lease (id, holder_pid, holder_host, taken_at, renewed_at, expires_at)"
                " VALUES (1, ?, ?, ?, ?, ?)",
                (lease.holder_pid, lease.holder_host, lease.taken_at, lease.renewed_at, lease.expires_at),
            )
            return lease

    @serialised
    def renew(self, holder_pid: int, holder_host: str, now: float, ttl_s: float) -> bool:
        """Extend the lease, for its holder only (matched on process id AND host).

        Args:
            holder_pid: The process id that claims to hold it.
            holder_host: The machine it runs on.
            now: The epoch of the renewal.
            ttl_s: How long the lease lives from now, in seconds.

        Returns:
            ``True`` when the holder's lease was extended; ``False`` when it has none (it was
            released, or another took it over).
        """
        cursor = self._conn.execute(
            "UPDATE run_lease SET renewed_at = ?, expires_at = ? WHERE id = 1 AND holder_pid = ? AND holder_host = ?",
            (now, now + ttl_s, holder_pid, holder_host),
        )
        return cursor.rowcount == 1

    @serialised
    def release(self, holder_pid: int, holder_host: str) -> bool:
        """Delete the lease, for its holder only (a clean stop; matched on process id AND host).

        Args:
            holder_pid: The process id that claims to hold it.
            holder_host: The machine it runs on.

        Returns:
            ``True`` when the holder's lease was deleted.
        """
        cursor = self._conn.execute(
            "DELETE FROM run_lease WHERE id = 1 AND holder_pid = ? AND holder_host = ?", (holder_pid, holder_host)
        )
        return cursor.rowcount == 1
