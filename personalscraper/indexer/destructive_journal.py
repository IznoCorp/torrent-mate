"""Append-only journal of destructive filesystem operations (§7 / Star City).

Every time the app destroys library content — a REPLACE that supersedes a
previous folder, a disk-clean deletion — it records a ``destructive_op`` row
(who / what / when / where / why). This is the durable audit trail whose
absence turned the Star City incident into a from-scratch reconstruction: with
it, the pipeline can be innocented or accused from the record.

Fail-soft by contract: a journal-write failure must NEVER break the operation
it records (the destruction has value; the log entry is best-effort). All
errors are logged and swallowed. Reads are provided for the forensic surface.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger

log = get_logger(__name__)

#: Recognised destructive operation kinds.
OP_OVERWRITE = "overwrite"
OP_DELETE = "delete"


def record_destruction(
    db_path: Path,
    *,
    op: str,
    path: Path | str,
    actor: str,
    detail: str | None = None,
    run_uid: str | None = None,
) -> None:
    """Append one destructive-operation row (best-effort, never raises).

    Args:
        db_path: Absolute path to ``library.db``.
        op: The operation kind (:data:`OP_OVERWRITE` / :data:`OP_DELETE`).
        path: The absolute filesystem path that was destroyed.
        actor: What performed it (``"dispatch"``, ``"disk-clean"``, …).
        detail: Optional French context / decision string.
        run_uid: Optional correlating ``pipeline_run`` uid.
    """
    try:
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            apply_pragmas(conn)
            conn.execute(
                "INSERT INTO destructive_op (ts, op, path, actor, detail, run_uid) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), op, str(path), actor, detail, run_uid),
            )
        finally:
            conn.close()
    except Exception:
        # A journal failure must never break the destruction it records.
        log.warning("destructive_journal.record_failed", op=op, path=str(path), actor=actor, exc_info=True)


def list_recent(db_path: Path, *, limit: int = 100) -> list[dict[str, object]]:
    """Return the most recent destructive-op rows, newest first (fail-soft).

    Args:
        db_path: Absolute path to ``library.db``.
        limit: Maximum rows to return.

    Returns:
        A list of dicts (``ts``, ``op``, ``path``, ``actor``, ``detail``,
        ``run_uid``), newest first. Empty on any error or missing table.
    """
    try:
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT ts, op, path, actor, detail, run_uid FROM destructive_op ORDER BY ts DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        log.warning("destructive_journal.list_failed", exc_info=True)
        return []


__all__ = ["OP_OVERWRITE", "OP_DELETE", "record_destruction", "list_recent"]
