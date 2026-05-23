"""Disk-mount helpers for the outbox drainer: path resolution and disk lookups."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.db import _apply_pragmas
from personalscraper.logger import get_logger

log = get_logger("indexer.outbox")


def _disk_is_mounted(conn: sqlite3.Connection, disk_id: int) -> bool:
    """Return ``True`` if the disk row has ``is_mounted=1``.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the ``disk`` table row.

    Returns:
        ``True`` when the disk is considered mounted, ``False`` otherwise or if
        the disk row does not exist.
    """
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT is_mounted FROM disk WHERE id = ?", (disk_id,)).fetchone()
    if row is None:
        return False
    result: bool = bool(row["is_mounted"])
    return result


def _resolve_path_id(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> int | None:
    """Look up (or create) the ``path`` row for ``(disk_id, rel_path)``.

    The path row must already exist for the drain to apply the row; if it does
    not exist, the caller should treat the row as unresolvable.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the disk.
        rel_path: Relative path string (directory portion only, no filename).

    Returns:
        The ``path.id`` if the row exists, ``None`` otherwise.
    """
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id FROM path WHERE disk_id = ? AND rel_path = ?",
        (disk_id, rel_path),
    ).fetchone()
    if row is None:
        return None
    result: int = row["id"]
    return result


def _ensure_path_id(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> int:
    """Look up the ``path`` row, inserting it if absent, and return its id.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the disk.
        rel_path: Relative path string.

    Returns:
        The ``path.id`` (existing or newly inserted).
    """
    existing = _resolve_path_id(conn, disk_id, rel_path)
    if existing is not None:
        return existing
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (?, ?, NULL, ?)",
        (disk_id, rel_path, now),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    return rowid


def disk_id_for_path(path: Path, db_path: Path) -> tuple[int, str] | None:
    """Resolve (disk_id, rel_path) for *path* via the disk table (best-effort).

    Opens a short independent connection to *db_path*, queries mounted disks,
    and returns the longest mount_path prefix match.  Never raises — same
    best-effort contract as :func:`publish_event`.

    Args:
        path: Absolute filesystem path on a mounted disk.
        db_path: Absolute path to the indexer SQLite database.  Must be the
            resolved ``Config.indexer.db_path`` so lookups target the
            user-configured DB (DESIGN §9.4).

    Returns:
        ``(disk_id, rel_path)`` where ``rel_path`` is *path* relative to
        the matched disk's ``mount_path``. ``None`` when no mounted disk
        matches or on any error.
    """
    # Guard against non-Path inputs: tests sometimes pass a bare ``MagicMock``
    # config whose ``.indexer.db_path`` resolves to a Mock attribute. See the
    # equivalent guard in :func:`publish_event` for rationale.
    if not isinstance(db_path, Path):
        log.debug(
            "indexer.db.disk_lookup_skipped_invalid_db_path",
            path=str(path),
            db_path_type=type(db_path).__name__,
        )
        return None

    try:
        conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        _apply_pragmas(conn)
        try:
            cursor = conn.execute("SELECT id, mount_path FROM disk WHERE is_mounted=1")
            rows = cursor.fetchall()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "indexer.db.disk_lookup_failed",
            path=str(path),
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,
        )
        return None

    path_str = str(path)
    best: tuple[int, str] | None = None
    best_len = -1
    for disk_id, mount_path in rows:
        if mount_path is None:
            continue
        if path_str == mount_path or path_str.startswith(mount_path.rstrip("/") + "/"):
            mlen = len(mount_path.rstrip("/"))
            if mlen > best_len:
                rel = path_str[mlen:].lstrip("/")
                best = (disk_id, rel)
                best_len = mlen
    return best
