"""Who asked for a follow, read for the supervisor's ask: the one question ``ask_acquisition`` puts to ``acquire.db``.

The web process never creates nor migrates ``acquire.db``, so the read goes through a read-only open
of the file as it finds it. A file, a table or a row that is not there reads as « nobody asked »: the
ask is then refused to an account holding only ``acquisition.pilot.own`` (it fails closed), and stays
open to ``acquisition.pilot.any``, which needs no requester.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from contextlib import closing
from pathlib import Path

from personalscraper.core.sqlite import connect_read_only
from personalscraper.logger import get_logger

log = get_logger("app.supervisor.requesters")


class AcquireRequesters:
    """The requesters of a follow, read from ``acquire.db`` on each call."""

    def __init__(self, db_path: Path) -> None:
        """Remember the file; nothing is opened yet.

        Args:
            db_path: ``acquire.db``.
        """
        self._db_path = db_path

    def requesters_of(self, followed_id: int) -> Collection[str]:
        """The accounts that asked for a follow.

        Args:
            followed_id: The ``followed_series`` row.

        Returns:
            Their account ids; empty for a follow nobody asked for through the model, and when the
            store cannot be read (logged).
        """
        try:
            with closing(connect_read_only(self._db_path)) as conn:
                rows = conn.execute(
                    "SELECT account_id FROM acquisition_requester WHERE followed_id = ?", (followed_id,)
                ).fetchall()
        except sqlite3.Error:
            log.warning("supervisor.requesters_unreadable", followed_id=followed_id, exc_info=True)
            return ()
        return tuple(str(row[0]) for row in rows)
