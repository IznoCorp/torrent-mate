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
from dataclasses import dataclass

from personalscraper.logger import get_logger

log = get_logger("acquire.watch_store")

_CANONICAL_KEY = "last_successful_run_at"

#: Keys of the published pending-run snapshot (§14.3 visibility). The watcher daemon and
#: the web server are SEPARATE processes: the debounce window lives in the daemon's
#: memory, so without publishing it the interface cannot say why nothing is happening —
#: the invisible wait NE-DOIT-PAS-2 forbids.
_PENDING_FIRES_AT = "pending_run_fires_at"
_PENDING_DOWNLOADS = "pending_run_active_downloads"
_PENDING_UPDATED_AT = "pending_run_updated_at"


@dataclass(frozen=True)
class PendingRun:
    """The watcher's current wait, as last published by the daemon.

    Attributes:
        fires_at: Epoch at which the grace counter expires and the pipeline runs, or
            None when no counter is running (something is still downloading, or there
            is no work at all).
        active_downloads: How many torrents are still downloading — the REASON a
            counter is not running, which is what DOIT-2 requires be displayed.
        updated_at: Epoch of the cycle that published this snapshot. A stale value
            means the daemon itself stopped; the reader decides what to make of it
            rather than being told a countdown that no longer ticks.
    """

    fires_at: float | None
    active_downloads: int
    updated_at: float


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

    def get_pending_run(self) -> PendingRun | None:
        """Return the watcher's last published wait, or ``None`` if it never published.

        Read-only — no lock taken (WAL). ``None`` means « the daemon has not said
        anything yet », which the caller must render as silence, not as « no wait ».

        Returns:
            The published :class:`PendingRun`, or None.
        """
        self._conn.row_factory = sqlite3.Row
        rows = {
            r["key"]: float(r["value"])
            for r in self._conn.execute(
                "SELECT key, value FROM watch_state WHERE key IN (?, ?, ?)",
                (_PENDING_FIRES_AT, _PENDING_DOWNLOADS, _PENDING_UPDATED_AT),
            )
        }
        if _PENDING_UPDATED_AT not in rows:
            return None
        return PendingRun(
            fires_at=rows.get(_PENDING_FIRES_AT),
            active_downloads=int(rows.get(_PENDING_DOWNLOADS, 0)),
            updated_at=rows[_PENDING_UPDATED_AT],
        )

    def set_pending_run(self, *, fires_at: float | None, active_downloads: int, now: float) -> None:
        """Publish this cycle's wait so the web process can show it (§8 / DOIT-2).

        A SNAPSHOT, not a journal: each cycle replaces the previous one. When no counter
        is running, ``fires_at`` is DELETED rather than zeroed — a stale deadline left
        behind would have the interface count down toward a moment that will never come.

        Args:
            fires_at: Epoch the grace counter expires, or None when none is running.
            active_downloads: Torrents still downloading (the reason a counter is held).
            now: Epoch of this cycle, published as the snapshot's freshness stamp.
        """
        with self._write_tx(self._conn):
            if fires_at is None:
                self._conn.execute("DELETE FROM watch_state WHERE key = ?", (_PENDING_FIRES_AT,))
            else:
                self._conn.execute(
                    "INSERT INTO watch_state (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (_PENDING_FIRES_AT, fires_at),
                )
            for key, value in ((_PENDING_DOWNLOADS, float(active_downloads)), (_PENDING_UPDATED_AT, now)):
                self._conn.execute(
                    "INSERT INTO watch_state (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )
