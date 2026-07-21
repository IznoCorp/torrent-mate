"""``cross_seed_history`` + ``cross_seed_quota`` sub-store.

Lives in its own module (not in ``store.py``) to keep the concrete store under
the module-size ceiling — same precedent as ``_wanted_store.py`` /
``_watch_store.py`` / ``_aired_store.py``. Reads are lock-free (WAL); writes use
``BEGIN IMMEDIATE`` via the shared ``_write_tx`` context manager injected by
:mod:`personalscraper.acquire.store`.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date

from personalscraper.logger import get_logger

log = get_logger("acquire.cross_seed_store")


class _CrossSeedSubStore:
    """Writer + reader for the ``cross_seed_history`` and ``cross_seed_quota`` tables.

    Records every cross-seed search attempt (upsert by source_hash+tracker)
    and enforces a daily quota to prevent runaway searches during back-catalog
    sweeps.  Reads are lock-free (WAL); writes use ``BEGIN IMMEDIATE``.
    """

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

    def record_search(self, source_hash: str, tracker: str) -> None:
        """Record a cross-seed search attempt (upsert).

        A re-search for the same source_hash+tracker pair updates
        ``searched_at`` in-place so that the most recent attempt is
        always the one checked by :meth:`was_searched_recently`.

        Args:
            source_hash: Torrent info-hash of the source (hex string).
            tracker: Tracker identifier string (e.g. ``"lacale"``).
        """
        now = time.time()
        with self._write_tx(self._conn):
            self._conn.execute(
                """
                INSERT INTO cross_seed_history (source_hash, tracker, searched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(source_hash, tracker) DO UPDATE SET
                    searched_at = excluded.searched_at
                """,
                (source_hash, tracker, now),
            )

    def was_searched_recently(self, source_hash: str, tracker: str, days: int) -> bool:
        """Return ``True`` if the pair was searched within *days*.

        Args:
            source_hash: Torrent info-hash of the source (hex string).
            tracker: Tracker identifier string.
            days: Look-back window in calendar days (86400 seconds each).

        Returns:
            ``True`` if a row exists with ``searched_at >= cutoff``.
        """
        cutoff = time.time() - (days * 86400)
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT 1 FROM cross_seed_history
            WHERE source_hash = ? AND tracker = ? AND searched_at >= ?
            LIMIT 1
            """,
            (source_hash, tracker, cutoff),
        ).fetchone()
        return row is not None

    def daily_searches_remaining(self, max_per_day: int) -> int:
        """Return the remaining quota for today.

        Reads the ``cross_seed_quota`` row for the current local date
        (``YYYY-MM-DD``).  Returns ``max_per_day - used``, clamped to
        ``>= 0``.

        Args:
            max_per_day: Maximum number of searches allowed per calendar day.

        Returns:
            Remaining quota, never negative.
        """
        today = date.today().isoformat()
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            "SELECT count FROM cross_seed_quota WHERE date = ?",
            (today,),
        ).fetchone()
        used = row["count"] if row is not None else 0
        return max(0, max_per_day - used)

    def increment_daily_count(self) -> None:
        """Increment today's search count (UPSERT).

        If today's row does not exist yet, inserts it with ``count=1``.
        Otherwise increments ``count`` by 1.  Self-contained — opens its
        own transaction via ``_write_tx``; call bare (no wrapping needed).
        """
        today = date.today().isoformat()
        with self._write_tx(self._conn):
            self._conn.execute(
                """
                INSERT INTO cross_seed_quota (date, count) VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET count = count + 1
                """,
                (today,),
            )
