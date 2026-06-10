# personalscraper/core/sqlite/_pragmas.py
"""Canonical 8-PRAGMA set for WAL-mode SQLite connections (SSOT).

Event-free: no EventBus, no domain imports.
"""

from __future__ import annotations

import sqlite3

from personalscraper.logger import get_logger

log = get_logger("core.sqlite.pragmas")


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply the canonical 8-PRAGMA set to an open SQLite connection.

    Must be called immediately after sqlite3.connect() on every connection
    that should use WAL mode.

    Args:
        conn: An open sqlite3.Connection.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-65536")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
