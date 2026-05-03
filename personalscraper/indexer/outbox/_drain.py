"""Drain logic: dedup, apply with retry, pending-op replay, and the public drain() / drain_if_present()."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, cast

from personalscraper.indexer.config import IndexerConfig
from personalscraper.indexer.outbox._apply import _OP_HANDLERS
from personalscraper.indexer.outbox._disk import _disk_is_mounted
from personalscraper.indexer.outbox._types import DrainStats
from personalscraper.indexer.repos import outbox_repo
from personalscraper.indexer.schema import IndexOutboxRow, OutboxOp
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
                log.error(
                    "indexer.outbox.row_failed",
                    row_id=row.id,
                    op=row.op,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
                return "failed"
            # Non-lock OperationalError: give up immediately.
            log.error(
                "indexer.outbox.row_failed",
                row_id=row.id,
                op=row.op,
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return "failed"
        except Exception as exc:  # noqa: BLE001
            log.error(
                "indexer.outbox.row_failed",
                row_id=row.id,
                op=row.op,
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
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
            op=cast(OutboxOp, op_row.op),
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
                log.error(
                    "indexer.pending_op.replay_failed",
                    row_id=op_row.id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
                break
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "indexer.pending_op.replay_failed",
                    row_id=op_row.id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
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
                        error_type=type(exc).__name__,
                        exc_info=True,
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
            elif outcome == "skip":
                # Unknown op or malformed payload cannot become valid by
                # retrying the same row.  Mark terminal so drain() can make
                # progress and surface the bad row via maintenance queries.
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
