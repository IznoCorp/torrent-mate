"""Disk-full guard for the indexer SQLite database.

Extracted from :mod:`personalscraper.indexer.db` in Sub-phase 4.2a as a
pure mechanical move (zero behavior change). Sub-phase 4.2b extends
:func:`handle_disk_full` with an optional :class:`EventBus` parameter so
the disk-full path emits :class:`DiskFullWarning` for cross-component
reactions (Telegram alerts, future Web UI).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.indexer.db import IndexerDiskFullError
from personalscraper.logger import get_logger

log = get_logger("indexer.db")


def handle_disk_full(conn: sqlite3.Connection, exc: sqlite3.OperationalError) -> None:
    """Handle a mid-scan disk-full ``OperationalError``.

    If *exc* signals "disk I/O error" or "database or disk is full",
    this function runs ``PRAGMA wal_checkpoint(TRUNCATE)``, commits the
    connection, logs ``indexer.db.disk_full``, and raises
    :class:`IndexerDiskFullError`.

    For any other ``OperationalError`` the function returns ``None`` silently
    so callers can re-raise the original exception themselves.

    Args:
        conn: Open SQLite connection.
        exc: The ``OperationalError`` caught by the caller.

    Raises:
        IndexerDiskFullError: When the error is disk-related.
    """
    msg = exc.args[0] if exc.args else ""
    disk_full_signals = ("disk i/o error", "database or disk is full")
    if not any(signal in msg.lower() for signal in disk_full_signals):
        return None

    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    except Exception:  # noqa: BLE001 — best-effort; ignore secondary errors
        pass

    log.warning(
        "indexer.db.disk_full",
        error=str(exc),
        error_type=type(exc).__name__,
        exc_info=True,
    )
    raise IndexerDiskFullError(Path("."), 0, 0) from exc


__all__ = ["handle_disk_full"]
