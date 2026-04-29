"""Outbox drainer and publish_event helper for the media indexer sub-system.

Implements the best-effort write-through change log described in DESIGN §9.1–§9.4.
The drainer processes pending rows from ``index_outbox`` in FIFO order,
deduplicates rows that target the same ``(disk_id, rel_path, filename)`` tuple,
retries on SQLite lock errors, and defers rows whose target disk is unreachable
to ``pending_op`` for replay on remount.

Public API:
- :func:`drain` — full drainer; returns :class:`DrainStats`.
- :func:`drain_if_present` — convenience wrapper (replaces the Phase 2 stub).
- :func:`publish_event` — best-effort outbox insert from pipeline mutation points.
- :class:`OutboxPayloadError` — raised on invalid payload values (e.g. unknown artwork kind).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from personalscraper.indexer.config import IndexerConfig
from personalscraper.indexer.repos import outbox_repo
from personalscraper.indexer.schema import IndexOutboxRow, ItemAttributeRow
from personalscraper.logger import get_logger

log = get_logger("indexer.outbox")

# ---------------------------------------------------------------------------
# Retry policy (DESIGN §9.2 / §17.1)
# ---------------------------------------------------------------------------

#: Backoff delays (seconds) between successive lock-retry attempts.
_RETRY_DELAYS: tuple[float, ...] = (0.05, 0.20, 1.0)

#: Maximum number of retries on ``OperationalError: database is locked``.
_MAX_RETRIES: int = len(_RETRY_DELAYS)


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class OutboxPayloadError(ValueError):
    """Raised when an outbox payload contains an invalid or unexpected value.

    Used to signal defensive validation failures before any DB write is attempted,
    e.g. an unknown ``kind`` in an ``artwork_write`` payload.
    """


# ---------------------------------------------------------------------------
# Artwork kind whitelist (DESIGN §9.6 defensive depth)
# ---------------------------------------------------------------------------

#: Allowed values for ``payload["kind"]`` in ``artwork_write`` outbox rows.
#: Cross-checked against :class:`personalscraper.indexer.schema.ArtworkInventory` field names.
_ALLOWED_ARTWORK_KINDS: frozenset[str] = frozenset(
    {"poster", "fanart", "landscape", "banner", "clearlogo", "clearart", "discart", "characterart"}
)


# ---------------------------------------------------------------------------
# DrainStats — summary returned by drain()
# ---------------------------------------------------------------------------


@dataclass
class DrainStats:
    """Summary statistics produced by a single drainer run.

    Args:
        applied: Number of rows applied to the indexer tables.
        deduped: Number of rows skipped as stale duplicates (marked done without applying).
        deferred: Number of rows moved to ``pending_op`` because their disk was unreachable.
        failed: Number of rows that exhausted retries and were marked failed.
        replayed: Number of ``pending_op`` rows replayed on remount.
    """

    applied: int = field(default=0)
    deduped: int = field(default=0)
    deferred: int = field(default=0)
    failed: int = field(default=0)
    replayed: int = field(default=0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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
    conn.execute(
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
        )
        """,
        (tmdb_id, imdb_id, now, path_id),
    )
    log.info("indexer.outbox.applied.nfo_write", disk_id=disk_id, rel_path=rel_path)


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
    conn.execute(
        f"""
        UPDATE media_item SET
            artwork_json = json_set(COALESCE(artwork_json, '{{}}'), '$.{kind}', json('true')),
            date_modified = ?
        WHERE id IN (
            SELECT DISTINCT mr.item_id
            FROM media_file mf
            JOIN media_release mr ON mr.id = mf.release_id
            WHERE mf.path_id = ?
        )
        """,
        (now, path_id),
    )
    log.info("indexer.outbox.applied.artwork_write", disk_id=disk_id, rel_path=rel_path, kind=kind)


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

    # Find item_id via path → media_file → media_release → media_item.
    conn.row_factory = sqlite3.Row
    item_row = conn.execute(
        """
        SELECT DISTINCT mr.item_id
        FROM media_file mf
        JOIN media_release mr ON mr.id = mf.release_id
        WHERE mf.path_id = ?
        LIMIT 1
        """,
        (path_id,),
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


# ---------------------------------------------------------------------------
# Deduplication key extraction
# ---------------------------------------------------------------------------


def _dedup_key(row: IndexOutboxRow) -> tuple[int, str, str] | None:
    """Extract ``(disk_id, rel_path, filename)`` dedup key from an outbox row.

    Rows that do not carry all three fields are not deduplicated (key is ``None``).

    Args:
        row: Outbox row to inspect.

    Returns:
        A ``(disk_id, rel_path, filename)`` tuple, or ``None`` if fields are missing.
    """
    try:
        payload: dict[str, Any] = json.loads(row.payload_json)
    except (json.JSONDecodeError, ValueError):
        return None

    disk_id = payload.get("disk_id")
    filename = payload.get("filename")

    # Determine the rel_path field name per op.
    if row.op == "move":
        rel_path = payload.get("dst_rel_path")
    else:
        rel_path = payload.get("rel_path")

    if disk_id is None or rel_path is None or filename is None:
        return None

    return (int(disk_id), str(rel_path), str(filename))


# ---------------------------------------------------------------------------
# Single-row apply with retry
# ---------------------------------------------------------------------------


def _apply_row_with_retry(conn: sqlite3.Connection, row: IndexOutboxRow) -> str:
    """Attempt to apply a single outbox row with lock-retry semantics.

    Processes the row in its own short transaction.  On
    ``OperationalError: database is locked``, retries up to :data:`_MAX_RETRIES`
    times with backoff.  After exhaustion, the row is left to the caller to
    mark as ``'failed'``.

    Args:
        conn: Open SQLite connection (WAL mode, ``isolation_level=None``).
        row: The outbox row to apply.

    Returns:
        ``'done'`` on success, ``'failed'`` after retry exhaustion,
        ``'skip'`` if the op is unknown or the payload is malformed.
    """
    try:
        payload: dict[str, Any] = json.loads(row.payload_json)
    except (json.JSONDecodeError, ValueError):
        log.warning("indexer.outbox.bad_payload", row_id=row.id, op=row.op)
        return "skip"

    handler = _OP_HANDLERS.get(row.op)
    if handler is None:
        log.warning("indexer.outbox.unknown_op", row_id=row.id, op=row.op)
        return "skip"

    for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                handler(conn, payload)
                outbox_repo.mark_done(conn, row.id)
                conn.execute("COMMIT")
                return "done"
            except Exception:
                conn.execute("ROLLBACK")
                raise
        except sqlite3.OperationalError as exc:
            if "database is locked" in str(exc).lower():
                if delay is not None:
                    log.warning(
                        "indexer.outbox.lock_retry",
                        row_id=row.id,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)
                    continue
                # Exhausted all retries.
                log.error("indexer.outbox.row_failed", row_id=row.id, op=row.op, error=str(exc))
                return "failed"
            # Non-lock OperationalError: give up immediately.
            log.error("indexer.outbox.row_failed", row_id=row.id, op=row.op, error=str(exc))
            return "failed"
        except Exception as exc:  # noqa: BLE001
            log.error("indexer.outbox.row_failed", row_id=row.id, op=row.op, error=str(exc))
            return "failed"

    # Unreachable, but satisfies type checker.
    return "failed"  # pragma: no cover


# ---------------------------------------------------------------------------
# Pending-op replay
# ---------------------------------------------------------------------------


def _replay_pending_ops(conn: sqlite3.Connection, disk_id: int, stats: DrainStats) -> None:
    """Replay all ``pending_op`` rows for a newly-mounted disk.

    Fetches rows for ``disk_id`` in FIFO order, re-applies each one via the
    same drainer logic, then sets ``replayed_at``.  Logs
    ``indexer.pending_op.replayed`` per row.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the mounted disk whose pending ops should be replayed.
        stats: Mutable stats accumulator; ``replayed`` count is updated in place.
    """
    pending_ops = outbox_repo.fetch_for_disk(conn, disk_id)
    for op_row in pending_ops:
        if op_row.replayed_at is not None:
            # Already replayed in a previous run; skip.
            continue

        # Synthesise a temporary IndexOutboxRow to reuse _apply_row_with_retry.
        synthetic = IndexOutboxRow(
            id=op_row.id,
            source="pending_op",
            op=op_row.op,
            payload_json=op_row.payload_json,
            created_at=op_row.created_at,
            processed_at=None,
            status="pending",
        )

        # Apply with retry, ignoring the resulting mark_done on index_outbox
        # (the synthetic id does not exist there).
        try:
            payload: dict[str, Any] = json.loads(op_row.payload_json)
        except (json.JSONDecodeError, ValueError):
            log.warning("indexer.pending_op.bad_payload", row_id=op_row.id, op=op_row.op)
            continue

        handler = _OP_HANDLERS.get(op_row.op)
        if handler is None:
            log.warning("indexer.pending_op.unknown_op", row_id=op_row.id, op=op_row.op)
            continue

        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    handler(conn, payload)
                    outbox_repo.mark_replayed(conn, op_row.id)
                    conn.execute("COMMIT")
                    log.info("indexer.pending_op.replayed", row_id=op_row.id, disk_id=disk_id)
                    stats.replayed += 1
                    break
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and delay is not None:
                    log.warning(
                        "indexer.pending_op.lock_retry",
                        row_id=op_row.id,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)
                    continue
                log.error("indexer.pending_op.replay_failed", row_id=op_row.id, error=str(exc))
                break
            except Exception as exc:  # noqa: BLE001
                log.error("indexer.pending_op.replay_failed", row_id=op_row.id, error=str(exc))
                break

        # Suppress unused variable warning for synthetic (it is used for typing context).
        _ = synthetic


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def drain(conn: sqlite3.Connection, config: IndexerConfig) -> DrainStats:
    """Drain all pending outbox rows and return statistics.

    Implements DESIGN §9.2 drainer behaviour:

    - Rows are processed in ``id ASC`` order (FIFO).
    - For multiple rows targeting the same ``(disk_id, rel_path, filename)``
      tuple, only the **latest** row (highest ``id``) is applied; older rows
      are marked ``'done'`` without applying (deduplication).
    - Each row is processed in its own short ``BEGIN IMMEDIATE`` transaction.
    - On ``OperationalError: database is locked``, retries up to 3× with
      backoff (50 ms, 200 ms, 1 s).  After exhaustion the row is marked
      ``'failed'`` and ``indexer.outbox.row_failed`` is logged.
    - When the target disk is unreachable (``is_mounted=0``), the row is moved
      to ``pending_op`` with ``status='deferred'`` and
      ``indexer.outbox.deferred`` is logged.
    - At the start of drain, for every disk that has ``pending_op`` rows whose
      ``replayed_at IS NULL`` and whose ``is_mounted=1``, those rows are
      replayed first.
    - TTL purge of ``pending_op`` rows older than 30 days is run at the end.

    Args:
        conn: Open SQLite connection to ``library.db``.
        config: Indexer configuration (used for future policy knobs;
            currently not accessed beyond type contract).

    Returns:
        :class:`DrainStats` with counts of applied, deduped, deferred,
        failed, and replayed rows.
    """
    stats = DrainStats()

    # --- Replay pending_op for newly-mounted disks ---
    conn.row_factory = sqlite3.Row
    mounted_disk_ids: list[int] = [
        r["disk_id"]
        for r in conn.execute("SELECT DISTINCT disk_id FROM pending_op WHERE replayed_at IS NULL").fetchall()
    ]
    for disk_id in mounted_disk_ids:
        if _disk_is_mounted(conn, disk_id):
            _replay_pending_ops(conn, disk_id, stats)

    # --- Fetch pending outbox rows (in batches of 100 to bound memory) ---
    while True:
        rows = outbox_repo.fetch_pending(conn, limit=100)
        if not rows:
            break

        # Build dedup map: key → id of the latest (highest id) row.
        # Older rows for the same key are stale and should be marked done
        # without applying.
        latest_id_for_key: dict[tuple[int, str, str], int] = {}
        for row in rows:
            key = _dedup_key(row)
            if key is not None:
                if key not in latest_id_for_key or row.id > latest_id_for_key[key]:
                    latest_id_for_key[key] = row.id

        for row in rows:
            key = _dedup_key(row)

            # Deduplication: mark older rows done without applying.
            if key is not None and latest_id_for_key.get(key, row.id) != row.id:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    outbox_repo.mark_done(conn, row.id)
                    conn.execute("COMMIT")
                except Exception:  # noqa: BLE001
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:  # noqa: BLE001
                        pass
                stats.deduped += 1
                continue

            # Disk-reachability check: defer if the disk is unreachable.
            try:
                payload: dict[str, Any] = json.loads(row.payload_json)
            except (json.JSONDecodeError, ValueError):
                payload = {}

            raw_disk_id: Any = payload.get("disk_id")
            if raw_disk_id is not None and not _disk_is_mounted(conn, int(raw_disk_id)):
                deferred_ok = False
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    outbox_repo.insert_pending_op_row(
                        conn,
                        disk_id=int(raw_disk_id),
                        op=row.op,
                        payload_json=row.payload_json,
                    )
                    outbox_repo.mark_deferred(conn, row.id)
                    conn.execute("COMMIT")
                    deferred_ok = True
                except Exception as exc:  # noqa: BLE001
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:  # noqa: BLE001
                        pass
                    log.warning(
                        "indexer.outbox.defer_failed",
                        row_id=row.id,
                        disk_id=raw_disk_id,
                        error=str(exc),
                    )
                if deferred_ok:
                    log.info("indexer.outbox.deferred", row_id=row.id, disk_id=raw_disk_id)
                    stats.deferred += 1
                else:
                    # Defer failed — row cannot be replayed; mark it failed so
                    # the outer fetch_pending loop terminates (without this, the
                    # same row would be re-fetched forever — Bug 1).
                    try:
                        conn.execute("BEGIN IMMEDIATE")
                        outbox_repo.mark_failed(conn, row.id)
                        conn.execute("COMMIT")
                    except Exception:  # noqa: BLE001
                        try:
                            conn.execute("ROLLBACK")
                        except Exception:  # noqa: BLE001
                            pass
                    stats.failed += 1
                continue

            # Apply the row with retry.
            outcome = _apply_row_with_retry(conn, row)
            if outcome == "done":
                stats.applied += 1
            elif outcome == "failed":
                # Mark failed outside of the aborted transaction.
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    outbox_repo.mark_failed(conn, row.id)
                    conn.execute("COMMIT")
                except Exception:  # noqa: BLE001
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:  # noqa: BLE001
                        pass
                stats.failed += 1
            # outcome == 'skip': unknown op or bad payload — leave pending for
            # operator investigation; do not increment any counter.

    # --- TTL purge of stale pending_op rows ---
    outbox_repo.purge_expired(conn, ttl_days=30)

    log.info(
        "indexer.outbox.drain_complete",
        applied=stats.applied,
        deduped=stats.deduped,
        deferred=stats.deferred,
        failed=stats.failed,
        replayed=stats.replayed,
    )
    return stats


def drain_if_present(conn: sqlite3.Connection, config: IndexerConfig | None = None) -> int:
    """Drain the outbox if any pending rows exist; return the count applied.

    This is the public convenience wrapper used by pipeline steps and
    :func:`~personalscraper.indexer.cli.library_index_command`.  It replaces the
    Phase 2 no-op stub with real drain logic.

    If *config* is ``None``, a default :class:`IndexerConfig` is instantiated.
    This allows existing call sites (e.g. the CLI) that pass only ``conn`` to
    continue working without a signature change.

    Args:
        conn: Open SQLite connection to ``library.db``.
        config: Indexer configuration.  When ``None``, a default instance is
            used.

    Returns:
        Number of outbox rows successfully applied (``DrainStats.applied``).
    """
    if config is None:
        config = IndexerConfig()
    stats = drain(conn, config)
    return stats.applied


def publish_event(
    disk_id: int,
    op: str,
    payload: dict[str, Any],
    db_path: Path,
    source: str = "dispatch",
) -> None:
    """Insert a pending outbox row for a pipeline mutation event (best-effort).

    Opens a **short, independent** connection to ``library.db`` at *db_path*,
    inserts one row in ``index_outbox``, then closes.  Does NOT acquire
    ``indexer_lock`` — publishers must write while a scan holds the lock
    (DESIGN §6.4 / §5.3).

    On any exception (DB locked, disk full, path error): logs
    ``indexer.db.outbox_lost`` with the payload and returns silently.
    The FS operation that triggered the event has already succeeded;
    next scan reconciles the missed entry as ordinary external drift.

    Args:
        disk_id: PK of the ``disk`` row for the mutation target.
        op: Operation type: ``'move'``, ``'nfo_write'``, ``'artwork_write'``,
            or ``'trailer_download'``.
        payload: Dict of op-specific fields (per DESIGN §9.3).  ``disk_id`` is
            injected automatically.
        db_path: Absolute path to the indexer SQLite database.  Must be the
            resolved ``Config.indexer.db_path`` so events land in the
            user-configured DB (DESIGN §9.4).
        source: Originating subsystem: ``'dispatch'``, ``'scraper'``,
            ``'trailers'``, or ``'scanner'``.  Defaults to ``'dispatch'``.
    """
    # Guard against non-Path inputs: tests sometimes pass a bare ``MagicMock``
    # config whose ``.indexer.db_path`` resolves to a Mock attribute. Without
    # this guard, ``sqlite3.connect(str(<MagicMock ...>))`` would create a
    # garbage file at the stringified mock repr in the cwd. Best-effort: skip
    # silently when ``db_path`` is not a real ``pathlib.Path``.
    if not isinstance(db_path, Path):
        log.debug(
            "indexer.db.outbox_skipped_invalid_db_path",
            op=op,
            disk_id=disk_id,
            db_path_type=type(db_path).__name__,
        )
        return

    # Merge disk_id into the payload so the drainer can resolve it.
    full_payload: dict[str, Any] = {"disk_id": disk_id, **payload}

    try:
        payload_json = json.dumps(full_payload)
    except (TypeError, ValueError) as exc:
        log.warning("indexer.db.outbox_lost", op=op, disk_id=disk_id, error=str(exc), payload=str(payload))
        return

    try:
        conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            outbox_repo.insert(conn, source=source, op=op, payload_json=payload_json)
        finally:
            conn.close()

    except Exception as exc:  # noqa: BLE001
        log.warning(
            "indexer.db.outbox_lost",
            op=op,
            disk_id=disk_id,
            error=str(exc),
            payload=full_payload,
        )


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
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            cursor = conn.execute("SELECT id, mount_path FROM disk WHERE is_mounted=1")
            rows = cursor.fetchall()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        log.warning("indexer.db.disk_lookup_failed", path=str(path), error=str(exc))
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
