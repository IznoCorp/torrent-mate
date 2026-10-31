"""The application settings' rows in ``app.db`` — one value per key.

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, and a service that needs several calls to be one act wraps them in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading

from personalscraper.core.sqlite import serialised


class SettingRepository:
    """The application settings over one ``app.db`` connection it is GIVEN; it opens nothing."""

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
    def setting(self, key: str) -> str | None:
        """One application setting.

        Args:
            key: Its key.

        Returns:
            Its value, or ``None``.
        """
        row = self._conn.execute("SELECT value FROM app_setting WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    @serialised
    def set_setting(self, key: str, value: str) -> None:
        """Store an application setting, replacing its value.

        Args:
            key: Its key.
            value: Its value.
        """
        self._conn.execute(
            "INSERT INTO app_setting (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
