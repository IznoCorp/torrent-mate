"""Per-op apply functions for outbox row handlers: move, nfo_write, artwork_write, trailer_download."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from personalscraper.indexer.outbox._disk import _ensure_path_id, _resolve_path_id
from personalscraper.indexer.outbox._types import OutboxPayloadError
from personalscraper.indexer.schema import ItemAttributeRow
from personalscraper.logger import get_logger

log = get_logger("indexer.outbox")

# ---------------------------------------------------------------------------
# Artwork kind whitelist (DESIGN §9.6 defensive depth)
# ---------------------------------------------------------------------------

#: Allowed values for ``payload["kind"]`` in ``artwork_write`` outbox rows.
#: Cross-checked against :class:`personalscraper.indexer.schema.ArtworkInventory` field names.
_ALLOWED_ARTWORK_KINDS: frozenset[str] = frozenset(
    {"poster", "fanart", "landscape", "banner", "clearlogo", "clearart", "discart", "characterart"}
)


# ---------------------------------------------------------------------------
# Per-op apply functions (DESIGN §9.3 idempotence contracts)
# ---------------------------------------------------------------------------


def _apply_move(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    """Apply a ``move`` outbox row: UPSERT ``media_file`` keyed by ``(path_id, filename)``.

    Idempotent: replaying with the same payload produces the same row.

    ``size_bytes`` and ``mtime_ns`` are best-effort: if either is absent/None,
    the media_file UPSERT is skipped and the caller still marks the row
    ``'done'``.  The next scan reconciles the missing file row via the
    dir-mtime walk (DESIGN §17.1).

    Args:
        conn: Open SQLite connection.
        payload: Parsed JSON payload with keys:
            ``disk_id``, ``dst_rel_path``, ``filename``, ``size_bytes``, ``mtime_ns``.
            ``size_bytes`` and ``mtime_ns`` may be ``None`` (best-effort).
    """
    disk_id_raw = payload.get("disk_id")
    dst_rel_path_raw = payload.get("dst_rel_path")
    filename_raw = payload.get("filename")
    size_bytes_raw = payload.get("size_bytes")
    mtime_ns_raw = payload.get("mtime_ns")

    # disk_id, dst_rel_path, filename are required for any meaningful update.
    if disk_id_raw is None or dst_rel_path_raw is None or filename_raw is None:
        log.warning(
            "indexer.outbox.move.fields_missing",
            disk_id=disk_id_raw,
            dst_rel_path=dst_rel_path_raw,
            filename=filename_raw,
        )
        return

    # size_bytes / mtime_ns are best-effort; if missing, defer file-row
    # materialisation to the next scan (DESIGN §17.1: silent miss reconciled
    # by walk).  The row is still marked 'done' by the caller.
    if size_bytes_raw is None or mtime_ns_raw is None:
        log.info(
            "indexer.outbox.move.fields_missing",
            disk_id=disk_id_raw,
            dst_rel_path=dst_rel_path_raw,
            filename=filename_raw,
            reason="size_bytes_or_mtime_ns_none",
        )
        return

    disk_id: int = int(disk_id_raw)
    dst_rel_path: str = str(dst_rel_path_raw)
    filename: str = str(filename_raw)
    size_bytes: int = int(size_bytes_raw)
    mtime_ns: int = int(mtime_ns_raw)

    path_id = _ensure_path_id(conn, disk_id, dst_rel_path)
    now = int(time.time())

    conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (NULL, ?, ?, ?, ?, NULL, NULL, NULL, NULL, 0, ?, NULL, 0, NULL)
        ON CONFLICT(path_id, filename) DO UPDATE SET
            size_bytes = excluded.size_bytes,
            mtime_ns   = excluded.mtime_ns,
            last_verified_at = excluded.last_verified_at,
            deleted_at = NULL,
            miss_strikes = 0
        """,
        (path_id, filename, size_bytes, mtime_ns, now),
    )
    log.info("indexer.outbox.applied.move", disk_id=disk_id, dst_rel_path=dst_rel_path, filename=filename)


def _apply_nfo_write(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    """Apply an ``nfo_write`` outbox row: UPDATE ``media_item.nfo_status`` and IDs.

    Resolved by ``(disk_id, rel_dir)`` → nearest ``media_item`` via ``path`` table.
    ``rel_path`` in the payload is the .nfo FILE path; ``path`` table stores
    directories, so we resolve via the parent directory.
    Idempotent when current values equal payload.

    Args:
        conn: Open SQLite connection.
        payload: Parsed JSON payload with keys:
            ``disk_id``, ``rel_path``, ``item_kind``, ``tmdb_id``, ``imdb_id``.
    """
    disk_id: int = int(payload["disk_id"])
    rel_path: str = str(payload["rel_path"])
    tmdb_id: int | None = payload.get("tmdb_id")
    imdb_id: str | None = payload.get("imdb_id")

    # rel_path points at the .nfo file; resolve via its parent directory
    # because the path table stores directories, not individual files.
    rel_dir = str(Path(rel_path).parent) if "/" in rel_path else ""
    if rel_dir == ".":
        rel_dir = ""  # disk-root edge case

    path_id = _resolve_path_id(conn, disk_id, rel_dir)
    if path_id is None:
        log.warning(
            "indexer.outbox.nfo_write.path_not_found",
            disk_id=disk_id,
            rel_path=rel_path,
            rel_dir=rel_dir,
        )
        return

    now = int(time.time())
    # Primary path: resolve item via media_file → media_release.  Fallback
    # path: resolve via item_attribute(key='dispatch_path') so files still
    # in Stage A (release_id=NULL because enrich / release_linker has not
    # run yet) are not silently dropped.  The fallback matches the
    # absolute on-disk media directory: mount_path + parent(rel_path).
    cursor = conn.execute(
        """
        UPDATE media_item SET
            nfo_status = 'valid',
            tmdb_id = COALESCE(?, tmdb_id),
            imdb_id = COALESCE(?, imdb_id),
            date_modified = ?
        WHERE id IN (
            SELECT DISTINCT mr.item_id
              FROM media_file mf
              JOIN media_release mr ON mr.id = mf.release_id
             WHERE mf.path_id = ?
            UNION
            SELECT mi.id
              FROM media_item mi
              JOIN item_attribute ia ON ia.item_id = mi.id AND ia.key = 'dispatch_path'
              JOIN path p ON p.id = ?
              JOIN disk d ON d.id = p.disk_id
             WHERE ia.value = d.mount_path || CASE WHEN p.rel_path = '' THEN '' ELSE '/' || p.rel_path END
        )
        """,
        (tmdb_id, imdb_id, now, path_id, path_id),
    )
    if cursor.rowcount == 0:
        log.warning(
            "indexer.outbox.nfo_write.no_item_matched",
            disk_id=disk_id,
            rel_path=rel_path,
            path_id=path_id,
        )
    log.info(
        "indexer.outbox.applied.nfo_write",
        disk_id=disk_id,
        rel_path=rel_path,
        rows_updated=cursor.rowcount,
    )


def _apply_artwork_write(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    """Apply an ``artwork_write`` outbox row: flip boolean in ``media_item.artwork_json``.

    Uses SQLite JSON1 ``json_set`` to toggle the ``kind`` key to ``true``.
    Idempotent: replaying when the bit is already set is a no-op.

    ``rel_path`` in the payload is the artwork FILE path; ``path`` table stores
    directories, so we resolve via the parent directory.

    Args:
        conn: Open SQLite connection.
        payload: Parsed JSON payload with keys:
            ``disk_id``, ``rel_path``, ``kind``.

    Raises:
        OutboxPayloadError: If ``kind`` is not in :data:`_ALLOWED_ARTWORK_KINDS`.
    """
    disk_id: int = int(payload["disk_id"])
    rel_path: str = str(payload["rel_path"])
    kind: str = str(payload["kind"])

    # Whitelist kind before it is interpolated into the JSON path expression.
    # The internal trust boundary is narrow, but defensive depth is cheap.
    if kind not in _ALLOWED_ARTWORK_KINDS:
        raise OutboxPayloadError(f"unknown artwork kind: {kind!r}")

    # rel_path points at the artwork file; resolve via its parent directory
    # because the path table stores directories, not individual files.
    rel_dir = str(Path(rel_path).parent) if "/" in rel_path else ""
    if rel_dir == ".":
        rel_dir = ""  # disk-root edge case

    path_id = _resolve_path_id(conn, disk_id, rel_dir)
    if path_id is None:
        log.warning(
            "indexer.outbox.artwork_write.path_not_found",
            disk_id=disk_id,
            rel_path=rel_path,
            rel_dir=rel_dir,
        )
        return

    now = int(time.time())
    # Use json_set on the artwork_json column; initialise to '{}' if NULL.
    # Same fallback semantics as _apply_nfo_write — Stage A files have
    # release_id=NULL so we resolve via dispatch_path attribute too.
    cursor = conn.execute(
        f"""
        UPDATE media_item SET
            artwork_json = json_set(COALESCE(artwork_json, '{{}}'), '$.{kind}', json('true')),
            date_modified = ?
        WHERE id IN (
            SELECT DISTINCT mr.item_id
              FROM media_file mf
              JOIN media_release mr ON mr.id = mf.release_id
             WHERE mf.path_id = ?
            UNION
            SELECT mi.id
              FROM media_item mi
              JOIN item_attribute ia ON ia.item_id = mi.id AND ia.key = 'dispatch_path'
              JOIN path p ON p.id = ?
              JOIN disk d ON d.id = p.disk_id
             WHERE ia.value = d.mount_path || CASE WHEN p.rel_path = '' THEN '' ELSE '/' || p.rel_path END
        )
        """,
        (now, path_id, path_id),
    )
    if cursor.rowcount == 0:
        log.warning(
            "indexer.outbox.artwork_write.no_item_matched",
            disk_id=disk_id,
            rel_path=rel_path,
            kind=kind,
            path_id=path_id,
        )
    log.info(
        "indexer.outbox.applied.artwork_write",
        disk_id=disk_id,
        rel_path=rel_path,
        kind=kind,
        rows_updated=cursor.rowcount,
    )


def _apply_trailer_download(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    """Apply a ``trailer_download`` outbox row: UPSERT ``item_attribute(key='trailer_found')``.

    Idempotent: replaying with the same ``trailer_path`` is a no-op.

    ``rel_path`` in the payload is the trailer FILE path; ``path`` table stores
    directories, so we resolve via the parent directory.

    Args:
        conn: Open SQLite connection.
        payload: Parsed JSON payload with keys:
            ``disk_id``, ``rel_path``, ``trailer_path``.
    """
    disk_id: int = int(payload["disk_id"])
    rel_path: str = str(payload["rel_path"])
    trailer_path: str = str(payload["trailer_path"])

    # rel_path points at the trailer file; resolve via its parent directory
    # because the path table stores directories, not individual files.
    rel_dir = str(Path(rel_path).parent) if "/" in rel_path else ""
    if rel_dir == ".":
        rel_dir = ""  # disk-root edge case

    path_id = _resolve_path_id(conn, disk_id, rel_dir)
    if path_id is None:
        log.warning(
            "indexer.outbox.trailer_download.path_not_found",
            disk_id=disk_id,
            rel_path=rel_path,
            rel_dir=rel_dir,
        )
        return

    # Find item_id via path → media_file → media_release → media_item,
    # with the same dispatch_path fallback used by nfo_write / artwork_write
    # so Stage A files (release_id NULL) still resolve to their owning item.
    conn.row_factory = sqlite3.Row
    item_row = conn.execute(
        """
        SELECT DISTINCT mr.item_id AS item_id
          FROM media_file mf
          JOIN media_release mr ON mr.id = mf.release_id
         WHERE mf.path_id = ?
        UNION
        SELECT mi.id AS item_id
          FROM media_item mi
          JOIN item_attribute ia ON ia.item_id = mi.id AND ia.key = 'dispatch_path'
          JOIN path p ON p.id = ?
          JOIN disk d ON d.id = p.disk_id
         WHERE ia.value = d.mount_path || CASE WHEN p.rel_path = '' THEN '' ELSE '/' || p.rel_path END
        LIMIT 1
        """,
        (path_id, path_id),
    ).fetchone()

    if item_row is None:
        log.warning("indexer.outbox.trailer_download.item_not_found", disk_id=disk_id, rel_path=rel_path)
        return

    item_id: int = item_row["item_id"]
    attr = ItemAttributeRow(item_id=item_id, key="trailer_found", value=trailer_path)
    conn.execute(
        """
        INSERT INTO item_attribute (item_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(item_id, key) DO UPDATE SET value = excluded.value
        """,
        (attr.item_id, attr.key, attr.value),
    )
    log.info(
        "indexer.outbox.applied.trailer_download",
        disk_id=disk_id,
        rel_path=rel_path,
        trailer_path=trailer_path,
    )


# Map op → apply function.
_OP_HANDLERS = {
    "move": _apply_move,
    "nfo_write": _apply_nfo_write,
    "artwork_write": _apply_artwork_write,
    "trailer_download": _apply_trailer_download,
}
