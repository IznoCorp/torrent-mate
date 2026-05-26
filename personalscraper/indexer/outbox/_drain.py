"""Drain logic: dedup, apply with retry, pending-op replay, and the public drain() / drain_if_present."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, cast

from personalscraper.indexer.config import IndexerConfig
from personalscraper.indexer.outbox._apply import _OP_HANDLERS
from personalscraper.indexer.outbox._disk import _disk_is_mounted
from personalscraper.indexer.outbox._types import DrainStats
from personalscraper.indexer.repos import log_repo, outbox_repo
from personalscraper.indexer.schema import IndexOutboxRow, OutboxOp, ScanEventRow, ScanRunRow
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
# Paranoia-branch scan_event helpers (DEV #31)
# ---------------------------------------------------------------------------


def _rel_path_for_paranoia(op: str, payload: dict[str, Any]) -> str | None:
    """Extract the canonical ``rel_path`` for the paranoia-branch scan_event payload.

    The quick-mode paranoia branch (DESIGN §17.1) queries ``scan_event`` rows
    with ``event LIKE 'outbox.%'`` and resolves their ``rel_path`` field.
    Different ops store the relevant path under different payload keys:

    - ``move``: uses ``dst_rel_path`` (destination of the move)
    - all others: uses ``rel_path``

    Args:
        op: Outbox operation type (e.g. ``'move'``, ``'nfo_write'``).
        payload: Parsed JSON payload dict for the outbox row.

    Returns:
        The resolved relative path string, or ``None`` if the field is absent.
    """
    if op == "move":
        raw = payload.get("dst_rel_path")
    else:
        raw = payload.get("rel_path")
    return str(raw) if raw is not None else None


def _insert_outbox_scan_event(
    conn: sqlite3.Connection,
    drain_scan_run_id: int,
    op: str,
    payload: dict[str, Any],
) -> None:
    """Insert a ``scan_event`` row recording a successful outbox drain step.

    Called inside the same ``BEGIN IMMEDIATE`` transaction as the handler and
    ``mark_done`` so the event is atomic with the drain effect.  The
    ``quick-mode`` paranoia branch (DESIGN §17.1) queries these rows
    (``event LIKE 'outbox.%'``) to detect FS mutations that the dir-mtime
    walk would miss.

    Failures are logged at ``warning`` level and silently swallowed — the
    scan_event row is audit-trail only and must not roll back the drain.

    Args:
        conn: Open SQLite connection inside an active transaction.
        drain_scan_run_id: PK of the ``scan_run`` row created for this drain
            session (satisfies the NOT NULL FK constraint on ``scan_event``).
        op: Outbox operation type (e.g. ``'move'``, ``'nfo_write'``).
        payload: Parsed JSON payload dict for the outbox row.
    """
    now = int(time.time())
    rel_path = _rel_path_for_paranoia(op, payload)
    disk_id = payload.get("disk_id")

    # Build a minimal payload for the paranoia branch: rel_path is mandatory
    # (the branch skips rows without it).  disk_id and filename are included
    # for additional context and to support future per-disk filtering.
    event_payload: dict[str, Any] = {}
    if disk_id is not None:
        event_payload["disk_id"] = disk_id
    if rel_path is not None:
        event_payload["rel_path"] = rel_path
    filename = payload.get("filename")
    if filename is not None:
        event_payload["filename"] = filename

    try:
        log_repo.insert_scan_event(
            conn,
            ScanEventRow(
                id=0,
                scan_id=drain_scan_run_id,
                ts=now,
                item_id=None,
                file_id=None,
                event=f"outbox.{op}",
                payload_json=json.dumps(event_payload),
            ),
        )
    except sqlite3.Error as exc:
        # Audit-trail failure must not abort the drain — log and continue.
        log.warning(
            "indexer.outbox.scan_event_insert_failed",
            op=op,
            error=str(exc),
            error_type=type(exc).__name__,
        )


# ---------------------------------------------------------------------------
# Drain session scan_run lifecycle
# ---------------------------------------------------------------------------


def _create_drain_scan_run(conn: sqlite3.Connection) -> int:
    """Insert a ``scan_run`` row representing this outbox drain session.

    The ``scan_event.scan_id`` column has a NOT NULL FK to ``scan_run``, so
    every outbox scan_event must reference a real scan_run row.  We create a
    dedicated row per drain() call (mode=``'outbox_drain'``) so the outbox
    events are distinguishable from scanner-initiated events in the audit log.

    Args:
        conn: Open SQLite connection.

    Returns:
        The ``rowid`` of the newly inserted ``scan_run`` row.
    """
    # The drain creates a scan_run row to anchor the paranoia-branch
    # scan_event rows (DEV #31). Mode 'repair' is reused since outbox
    # drain is semantically a repair pass (reconciling FS state with
    # DB state). The schema's CHECK constraint accepts 'repair' (cf.
    # migration 001 line 250). A dedicated 'outbox_drain' mode would
    # require a migration which is heavier than this naming choice
    # justifies — 'repair' captures the intent adequately.
    now = int(time.time())
    return log_repo.insert_scan_run(
        conn,
        ScanRunRow(
            id=0,
            generation=0,
            mode="repair",
            disk_filter=None,
            started_at=now,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        ),
    )


def _finish_drain_scan_run(conn: sqlite3.Connection, drain_scan_run_id: int) -> None:
    """Mark the drain session ``scan_run`` row as ``'ok'``.

    Best-effort: failures are silently ignored since the drain itself has
    already completed.

    Args:
        conn: Open SQLite connection.
        drain_scan_run_id: PK of the drain ``scan_run`` row to finalise.
    """
    try:
        log_repo.update_scan_run_status(
            conn,
            id=drain_scan_run_id,
            status="ok",
            finished_at=int(time.time()),
        )
    except sqlite3.Error as exc:
        log.warning(
            "indexer.outbox.drain_run_finish_failed",
            drain_scan_run_id=drain_scan_run_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )


# ---------------------------------------------------------------------------
# Single-row apply with retry
# ---------------------------------------------------------------------------


def _apply_row_with_retry(
    conn: sqlite3.Connection,
    row: IndexOutboxRow,
    drain_scan_run_id: int | None = None,
) -> str:
    """Attempt to apply a single outbox row with lock-retry semantics.

    Processes the row in its own short transaction.  On
    ``OperationalError: database is locked``, retries up to :data:`_MAX_RETRIES`
    times with backoff.  After exhaustion, the row is left to the caller to
    mark as ``'failed'``.

    On success, a ``scan_event`` row is inserted within the same transaction
    (``event='outbox.<op>'``) so the quick-mode paranoia branch (DESIGN §17.1)
    can detect FS mutations without a full dir-mtime walk.

    Args:
        conn: Open SQLite connection (WAL mode, ``isolation_level=None``).
        row: The outbox row to apply.
        drain_scan_run_id: PK of the ``scan_run`` row for this drain session,
            used as the FK on the ``scan_event`` insert.

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
                # Insert the paranoia-branch scan_event inside the same
                # transaction so the event is atomic with the drain effect
                # (DESIGN §17.1, DEV #31 fix). Skipped when no
                # drain_scan_run_id was provided (test contexts that
                # exercise the lock-retry logic without setting up a
                # scan_run row).
                if drain_scan_run_id is not None:
                    _insert_outbox_scan_event(conn, drain_scan_run_id, row.op, payload)
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
    - On each successful row application, a ``scan_event`` row with
      ``event='outbox.<op>'`` is inserted atomically so the quick-mode
      paranoia branch (DESIGN §17.1) can detect FS mutations (DEV #31 fix).

    Args:
        conn: Open SQLite connection to ``library.db``.
        config: Indexer configuration (used for future policy knobs;
            currently not accessed beyond type contract).

    Returns:
        :class:`DrainStats` with counts of applied, deduped, deferred,
        failed, and replayed rows.
    """
    stats = DrainStats()

    # --- Create a scan_run row for this drain session (DEV #31) ---
    # scan_event.scan_id is NOT NULL → every outbox scan_event must reference
    # a real scan_run row.  We create one per drain() call with mode='outbox_drain'.
    drain_scan_run_id = _create_drain_scan_run(conn)

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
            outcome = _apply_row_with_retry(conn, row, drain_scan_run_id)
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

    # --- Finalise the drain scan_run row ---
    _finish_drain_scan_run(conn, drain_scan_run_id)

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
