"""Repository for the ``disk`` and ``path`` tables.

Provides CRUD operations for disk identity rows and their associated path rows.
All write methods emit structlog events following the ``indexer.{component}.{action}``
convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import DiskRow, PathRow
from personalscraper.logger import get_logger

log = get_logger("indexer.disk")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_disk(row: sqlite3.Row) -> DiskRow:
    """Convert a ``sqlite3.Row`` from the ``disk`` table to a :class:`DiskRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`DiskRow` instance.
    """
    return DiskRow(
        id=row["id"],
        uuid=row["uuid"],
        label=row["label"],
        mount_path=row["mount_path"],
        last_seen_at=row["last_seen_at"],
        merkle_root=row["merkle_root"],
        is_mounted=row["is_mounted"],
        unreachable_strikes=row["unreachable_strikes"],
    )


def _row_to_path(row: sqlite3.Row) -> PathRow:
    """Convert a ``sqlite3.Row`` from the ``path`` table to a :class:`PathRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`PathRow` instance.
    """
    return PathRow(
        id=row["id"],
        disk_id=row["disk_id"],
        rel_path=row["rel_path"],
        dir_mtime_ns=row["dir_mtime_ns"],
        last_walked_at=row["last_walked_at"],
    )


# ---------------------------------------------------------------------------
# disk table operations
# ---------------------------------------------------------------------------


def insert(conn: sqlite3.Connection, row: DiskRow) -> int:
    """Insert a new disk row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`DiskRow` to insert.  The ``id`` field is ignored (auto-assigned).

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: If the ``uuid`` is not unique.
    """
    cursor = conn.execute(
        """
        INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.uuid,
            row.label,
            row.mount_path,
            row.last_seen_at,
            row.merkle_root,
            row.is_mounted,
            row.unreachable_strikes,
        ),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.disk.insert", uuid=row.uuid, label=row.label, rowid=rowid)
    return rowid


def get_by_uuid(conn: sqlite3.Connection, uuid: str) -> DiskRow | None:
    """Fetch a disk row by its volume UUID.

    Args:
        conn: Open SQLite connection.
        uuid: Volume UUID string to look up.

    Returns:
        :class:`DiskRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM disk WHERE uuid = ?", (uuid,)).fetchone()
    if row is None:
        return None
    return _row_to_disk(row)


def get_by_id(conn: sqlite3.Connection, id: int) -> DiskRow | None:
    """Fetch a disk row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`DiskRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM disk WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_disk(row)


def update_mount_path(conn: sqlite3.Connection, id: int, mount_path: str | None) -> bool:
    """Update the ``mount_path`` column for a disk row.

    Also updates ``is_mounted`` based on whether ``mount_path`` is ``None``.

    Args:
        conn: Open SQLite connection.
        id: PK of the disk row to update.
        mount_path: New mount path, or ``None`` to mark unmounted.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    is_mounted = 0 if mount_path is None else 1
    cursor = conn.execute(
        "UPDATE disk SET mount_path = ?, is_mounted = ? WHERE id = ?",
        (mount_path, is_mounted, id),
    )
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.disk.update_mount_path", id=id, mount_path=mount_path, is_mounted=is_mounted)
    return updated


def update_is_mounted(conn: sqlite3.Connection, id: int, is_mounted: int) -> bool:
    """Update the ``is_mounted`` flag for a disk row.

    When *is_mounted* is set to ``0`` (unmounted), ``mount_path`` is
    automatically cleared to ``NULL`` in the same statement.  This keeps the
    CHECK constraint ``(is_mounted = 0 AND mount_path IS NULL) OR
    (is_mounted = 1 AND mount_path IS NOT NULL)`` satisfied without requiring
    callers to perform two operations.

    Note: setting *is_mounted* to ``1`` without also updating ``mount_path``
    via :func:`update_mount_path` will violate the CHECK constraint, because
    ``mount_path`` must be non-``NULL`` when the disk is mounted.  Prefer
    :func:`update_mount_path` when a concrete path is available.

    Args:
        conn: Open SQLite connection.
        id: PK of the disk row to update.
        is_mounted: New value: 0 (unmounted — also clears ``mount_path``) or 1.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    if is_mounted == 0:
        # Auto-clear mount_path when marking unmounted so the CHECK constraint
        # (is_mounted=0 AND mount_path IS NULL) is satisfied atomically.
        cursor = conn.execute(
            "UPDATE disk SET is_mounted = ?, mount_path = NULL WHERE id = ?",
            (is_mounted, id),
        )
    else:
        cursor = conn.execute("UPDATE disk SET is_mounted = ? WHERE id = ?", (is_mounted, id))
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.disk.update_is_mounted", id=id, is_mounted=is_mounted)
    return updated


def update_unreachable_strikes(conn: sqlite3.Connection, id: int, strikes: int) -> bool:
    """Update the ``unreachable_strikes`` column for a disk row.

    Called by the scanner when a disk produces an I/O error during a walk,
    to track how many consecutive scans have failed for this disk.

    Args:
        conn: Open SQLite connection.
        id: PK of the disk row to update.
        strikes: New ``unreachable_strikes`` value.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute(
        "UPDATE disk SET unreachable_strikes = ? WHERE id = ?",
        (strikes, id),
    )
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.disk.update_unreachable_strikes", id=id, strikes=strikes)
    return updated


def update_merkle_root(conn: sqlite3.Connection, id: int, merkle_root: str | None) -> bool:
    """Update the ``merkle_root`` column for a disk row.

    Args:
        conn: Open SQLite connection.
        id: PK of the disk row to update.
        merkle_root: New 16-char hex merkle root, or ``None`` to clear it.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute("UPDATE disk SET merkle_root = ? WHERE id = ?", (merkle_root, id))
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.disk.update_merkle_root", id=id, merkle_root=merkle_root)
    return updated


def update_last_seen_at(conn: sqlite3.Connection, id: int, last_seen_at: int) -> bool:
    """Update the ``last_seen_at`` column for a disk row.

    Called whenever a scan visits the disk successfully so observers can tell
    "when was this disk last touched by the indexer". Distinct from
    ``update_is_mounted`` (state) and ``update_merkle_root`` (content
    fingerprint).

    Args:
        conn: Open SQLite connection.
        id: PK of the disk row to update.
        last_seen_at: Unix epoch seconds (typically ``int(time.time())``).

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute("UPDATE disk SET last_seen_at = ? WHERE id = ?", (last_seen_at, id))
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.disk.update_last_seen_at", id=id, last_seen_at=last_seen_at)
    return updated


# ---------------------------------------------------------------------------
# path table operations
# ---------------------------------------------------------------------------


def insert_path(conn: sqlite3.Connection, row: PathRow) -> int:
    """Insert a new path row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`PathRow` to insert.  The ``id`` field is ignored (auto-assigned).

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: If the ``(disk_id, rel_path)`` pair is not unique.
    """
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (?, ?, ?, ?)",
        (row.disk_id, row.rel_path, row.dir_mtime_ns, row.last_walked_at),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.disk.insert_path", disk_id=row.disk_id, rel_path=row.rel_path, rowid=rowid)
    return rowid


def upsert_path(conn: sqlite3.Connection, row: PathRow) -> int:
    """Upsert a path row, updating ``dir_mtime_ns`` and ``last_walked_at`` on conflict.

    Uses ``RETURNING id`` instead of ``cursor.lastrowid`` because SQLite's
    ``last_insert_rowid()`` is unreliable for ``ON CONFLICT DO UPDATE`` upserts —
    it may return the rowid of the last *successfully inserted* row in the table
    rather than the rowid of the row that was updated.

    Args:
        conn: Open SQLite connection.
        row: :class:`PathRow` to upsert.

    Returns:
        The ``rowid`` (= ``id``) of the upserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(disk_id, rel_path) DO UPDATE SET
          dir_mtime_ns = excluded.dir_mtime_ns,
          last_walked_at = excluded.last_walked_at
        RETURNING id
        """,
        (row.disk_id, row.rel_path, row.dir_mtime_ns, row.last_walked_at),
    )
    returned = cursor.fetchone()
    rowid: int = returned[0]
    # Per-path upserts fire once per file visit on a full scan, which produces
    # tens of thousands of identical-rowid log lines under INFO and drowns
    # out everything else.  Demoted to debug — the walker emits one
    # ``indexer.scan.disk_done`` summary at INFO per disk, which is the right
    # granularity for an operator skim.
    log.debug("indexer.disk.upsert_path", disk_id=row.disk_id, rel_path=row.rel_path, rowid=rowid)
    return rowid


def get_path_by_id(conn: sqlite3.Connection, id: int) -> PathRow | None:
    """Fetch a path row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`PathRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM path WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_path(row)


def get_path_by_disk_and_relpath(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> PathRow | None:
    """Fetch a path row by its ``(disk_id, rel_path)`` unique key.

    Used by the quick-mode scanner to look up an existing ``path`` row and
    compare its stored ``dir_mtime_ns`` against the current filesystem value
    without performing a full subtree walk.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the owning disk row.
        rel_path: Relative directory path as stored in the ``path`` table.

    Returns:
        :class:`PathRow` if found, ``None`` if no row matches ``(disk_id, rel_path)``.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT * FROM path WHERE disk_id = ? AND rel_path = ?",
        (disk_id, rel_path),
    ).fetchone()
    if row is None:
        return None
    return _row_to_path(row)
