"""Outbox publish_event entry point — best-effort insert from pipeline mutation points."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from personalscraper.indexer.repos import outbox_repo
from personalscraper.logger import get_logger

log = get_logger("indexer.outbox")


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
        log.warning(
            "indexer.db.outbox_lost",
            op=op,
            disk_id=disk_id,
            error=str(exc),
            error_type=type(exc).__name__,
            payload=str(payload),
            exc_info=True,
        )
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
            error_type=type(exc).__name__,
            payload=full_payload,
            exc_info=True,
        )
