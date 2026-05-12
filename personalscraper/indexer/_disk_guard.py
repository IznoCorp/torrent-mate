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
from typing import TYPE_CHECKING

from personalscraper.indexer.db import IndexerDiskFullError
from personalscraper.indexer.events import DiskFullWarning
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus

log = get_logger("indexer.db")


def handle_disk_full(
    conn: sqlite3.Connection,
    exc: sqlite3.OperationalError,
    *,
    event_bus: EventBus,
) -> None:
    """Handle a mid-scan disk-full ``OperationalError``.

    If *exc* signals "disk I/O error" or "database or disk is full",
    this function runs ``PRAGMA wal_checkpoint(TRUNCATE)``, commits the
    connection, logs ``indexer.db.disk_full``, optionally emits
    :class:`DiskFullWarning` on the supplied bus, and raises
    :class:`IndexerDiskFullError`.

    For any other ``OperationalError`` the function returns ``None`` silently
    so callers can re-raise the original exception themselves.

    Args:
        conn: Open SQLite connection.
        exc: The ``OperationalError`` caught by the caller.
        event_bus: Optional :class:`EventBus`. When supplied, a
            :class:`DiskFullWarning` is emitted before the
            :class:`IndexerDiskFullError` is raised. The exact free /
            threshold byte counts are unavailable from the SQLite error
            payload, so both fields use the ``0`` sentinel; the disk path
            is derived from the connection's main DB file when possible.

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

    event_bus.emit(
        DiskFullWarning(
            source="indexer._disk_guard.handle_disk_full",
            disk_path=_db_path_from_conn(conn),
            free_bytes=0,
            threshold_bytes=0,
        ),
    )

    raise IndexerDiskFullError(Path("."), 0, 0) from exc


def _db_path_from_conn(conn: sqlite3.Connection) -> Path:
    """Best-effort lookup of the connection's main DB file path.

    Returns ``Path(".")`` when the connection is in-memory or the lookup
    fails for any reason — disk-full reporting must remain fail-soft so a
    secondary error here cannot mask the original disk-full condition.
    """
    try:
        for _seq, name, file_ in conn.execute("PRAGMA database_list").fetchall():
            if name == "main" and file_:
                return Path(file_)
    except sqlite3.Error:
        pass
    return Path(".")


__all__ = ["handle_disk_full"]
