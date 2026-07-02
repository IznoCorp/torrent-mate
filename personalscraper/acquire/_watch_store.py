"""Watcher daemon KV sub-store over the ``watch_state`` table.

Persists ``last_successful_run_at`` across daemon restarts so the safety-net
check survives a PM2 restart or machine reboot.  The table is a simple
key-value store (key TEXT PRIMARY KEY, value REAL NOT NULL) with a single
canonical key ``"last_successful_run_at"``.

Reads are lock-free (WAL).  Writes use ``BEGIN IMMEDIATE`` via the shared
``_write_tx`` context manager from :mod:`personalscraper.acquire.store`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager

from personalscraper.logger import get_logger

log = get_logger("acquire.watch_store")

_CANONICAL_KEY = "last_successful_run_at"


class _WatchSubStore:
    """Writer + reader for the ``watch_state`` key-value table.

    Lives in its own module (not in ``store.py``) to keep the concrete
    store under the 1000-line module-size hard ceiling.  Instances are
    bound to the shared ``acquire.db`` connection.
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
                :mod:`personalscraper.acquire.store` for BEGIN IMMEDIATE
                serialisation.  Passed as a callable object to avoid a
                circular import (``_watch_store`` is imported by ``store``,
                so ``store`` cannot be the source of the symbol).
        """
        self._conn = conn
        self._write_tx = write_tx

    def get_last_successful_run_at(self) -> float | None:
        """Return the persisted ``last_successful_run_at`` timestamp, or ``None``.

        Read-only — no lock taken (WAL).

        Returns:
            The wall-clock timestamp (``time.time()``) of the most recent
            successful pipeline run, or ``None`` if never recorded.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            "SELECT value FROM watch_state WHERE key = ?",
            (_CANONICAL_KEY,),
        ).fetchone()
        if row is None:
            return None
        return float(row["value"])

    def set_last_successful_run_at(self, ts: float) -> None:
        """Persist the ``last_successful_run_at`` timestamp (upsert).

        Uses INSERT … ON CONFLICT … DO UPDATE SET so the first write and
        subsequent updates go through the same single SQL statement.
        Serialised via ``_write_tx`` (BEGIN IMMEDIATE).

        Args:
            ts: Wall-clock timestamp (``time.time()``) of the successful
                pipeline run to record.
        """
        with self._write_tx(self._conn):
            self._conn.execute(
                """
                INSERT INTO watch_state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (_CANONICAL_KEY, ts),
            )
        log.debug("watch_state_persisted", key=_CANONICAL_KEY, value=ts)
