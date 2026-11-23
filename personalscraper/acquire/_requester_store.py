"""``acquisition_requester`` sub-store (K3 P2, migration 027).

Who asked for a follow: one row per (follow, account). The engine never learns of rights,
so an account is an opaque id and the rules over requesters (what is in force, who may
read, when the last one leaving removes the follow) belong to the acquisition model; this
store only holds and reads the rows. Nothing writes here yet: the follow service does.

Lives in its own module to keep ``store.py`` from growing — same pattern as
``_aired_store.py`` / ``_wanted_store.py``. Reads are lock-free (WAL); writes use
``BEGIN IMMEDIATE`` via the shared ``_write_tx`` context manager.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager

from personalscraper.acquire._store_rows import _row_to_requester
from personalscraper.acquire.domain import FollowRequester


class _RequesterSubStore:
    """Writer + reader for the ``acquisition_requester`` table."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        write_tx: Callable[[sqlite3.Connection], AbstractContextManager[None]],
    ) -> None:
        """Initialise with the shared connection and write-tx context manager.

        Args:
            conn: Shared :class:`sqlite3.Connection` to ``acquire.db``.
            write_tx: The ``_write_tx`` context manager from
                :mod:`personalscraper.acquire.store` (BEGIN IMMEDIATE
                serialisation), passed as a callable to avoid a circular
                import.
        """
        self._conn = conn
        self._write_tx = write_tx

    def list_for(self, followed_id: int) -> list[FollowRequester]:
        """Return the requesters of one follow, the oldest ask first.

        Args:
            followed_id: Rowid of the ``followed_series`` row.

        Returns:
            The follow's requesters ordered by ``since`` then account id; empty for a
            follow nobody asked for through the model (every follow written before
            migration 027: no backfill).
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT followed_id, account_id, via, floor, paused, since
            FROM acquisition_requester
            WHERE followed_id = ?
            ORDER BY since, account_id
            """,
            (followed_id,),
        ).fetchall()
        return [_row_to_requester(r) for r in rows]

    def upsert(self, requester: FollowRequester) -> None:
        """Insert a requester, or replace the row of its (follow, account).

        The row is replaced whole: the caller holds the model's state (``since`` kept
        from the first ask), the store does not guess which field changed.

        Args:
            requester: The requester to persist.

        Raises:
            sqlite3.IntegrityError: If the follow does not exist (the foreign key).
        """
        with self._write_tx(self._conn):
            self._conn.execute(
                """
                INSERT INTO acquisition_requester (followed_id, account_id, via, floor, paused, since)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(followed_id, account_id) DO UPDATE SET
                  via = excluded.via,
                  floor = excluded.floor,
                  paused = excluded.paused,
                  since = excluded.since
                """,
                (
                    requester.followed_id,
                    requester.account_id,
                    requester.via,
                    requester.floor,
                    1 if requester.paused else 0,
                    requester.since,
                ),
            )

    def delete(self, followed_id: int, account_id: str) -> bool:
        """Remove one account's ask for a follow.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            account_id: The account that no longer asks.

        Returns:
            ``True`` when a row was removed, ``False`` when the account did not ask.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                "DELETE FROM acquisition_requester WHERE followed_id = ? AND account_id = ?",
                (followed_id, account_id),
            )
        return cur.rowcount > 0

    def follows_of(self, account_ids: Iterable[str]) -> list[int]:
        """Return the follows any of the given accounts asked for.

        Args:
            account_ids: The accounts to look for.

        Returns:
            The distinct ``followed_series`` rowids, ascending; empty when no account is
            given or none asked.
        """
        accounts = list(dict.fromkeys(account_ids))
        if not accounts:
            return []
        placeholders = ", ".join("?" for _ in accounts)
        rows = self._conn.execute(
            "SELECT DISTINCT followed_id FROM acquisition_requester "  # noqa: S608 — placeholders only
            f"WHERE account_id IN ({placeholders}) ORDER BY followed_id",
            accounts,
        ).fetchall()
        return [int(r[0]) for r in rows]
