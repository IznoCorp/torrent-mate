"""Decision run reservation — atomic concurrency guard + pipeline_run row insert.

Mirrors :func:`personalscraper.web.routes.maintenance._reserve_run_row` with a
narrower concurrency guard: only ``command='scrape-resolve'`` rows are checked,
so decision resolves block each other without blocking other maintenance actions.

Route-side (runs in the web process before the 202 response). The reserved row
is claimed with the web process's pid (guaranteed alive) — the caller updates it
to the spawned runner's pid right after spawn, matching the maintenance runner
pattern (R8).

Sub-phase 2.3 — journal wiring for decision run reservation.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger

log = get_logger(__name__)


def _safe_rollback(conn: sqlite3.Connection) -> None:
    """Roll back *conn* best-effort, ignoring "no transaction active" errors.

    Mirrors :func:`personalscraper.web.routes.maintenance._safe_rollback`.
    Copied inline rather than imported from the routes module to avoid pulling
    in FastAPI router, subprocess, and disk-scanning dependencies transitively.

    Args:
        conn: The connection to roll back.
    """
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


def _guard_no_running_resolve(conn: sqlite3.Connection, decision_id: int) -> None:
    """Raise 409 when a live scrape-resolve for *decision_id* is already running.

    Queries ``pipeline_run`` for rows with ``kind='maintenance'``,
    ``command='scrape-resolve'``, ``outcome='running'``, AND
    ``json_extract(options_json, '$.decision_id') = decision_id`` — the guard is
    scoped to THIS decision so two DIFFERENT decisions resolve concurrently
    (webui-ux phase 4), while a double-launch of the SAME decision still 409s.
    Liveness is checked via ``os.kill(pid, 0)``; rows with a dead or NULL pid are
    stale (crashed runner / pre-pid migration) and are ignored — we never mutate
    them here.

    Same-staging-path exclusivity across two distinct decision rows is enforced
    one layer down by :func:`personalscraper.lock.acquire_scrape_resolve_lock`
    (sha1 of the staging path), so this per-``decision_id`` reservation guard and
    the per-item CLI lock together cover both the same-decision and same-path
    races.

    Args:
        conn: An open connection (inside the reserve transaction).
        decision_id: The ``scrape_decision.id`` being resolved — the guard is
            scoped to running resolves of THIS decision only.

    Raises:
        HTTPException: 409 when a live scrape-resolve runner for *decision_id* is
            found.
    """
    rows = conn.execute(
        "SELECT run_uid, pid FROM pipeline_run "
        "WHERE kind='maintenance' AND command='scrape-resolve' AND outcome='running' "
        "AND json_extract(options_json, '$.decision_id') = ?",
        (decision_id,),
    ).fetchall()
    for row in rows:
        run_uid_db = row["run_uid"]
        pid_db = row["pid"]
        if pid_db is None:
            # NULL pid → stale row (pre-pid-migration or a runner that crashed
            # before claiming its pid).
            log.info("resolve_stale_row_ignored", run_uid=run_uid_db, pid=None)
            continue
        try:
            os.kill(pid_db, 0)
        except ProcessLookupError:
            # Dead process → stale row (crashed runner).
            log.info("resolve_stale_row_ignored", run_uid=run_uid_db, pid=pid_db)
            continue
        except PermissionError:
            # Process exists but owned by another user → treat as alive.
            raise HTTPException(status_code=409, detail="This decision is already resolving")
        else:
            raise HTTPException(status_code=409, detail="This decision is already resolving")


def _reserve_decision_run(
    db_path: Path,
    *,
    run_uid: str,
    decision_id: int,
    provider: str,
    provider_id: int,
) -> None:
    """Atomically guard per-decision concurrency and reserve a ``pipeline_run`` row.

    Opens one connection under ``BEGIN IMMEDIATE`` so the concurrency check and
    the ``pipeline_run`` INSERT are a single serialised transaction, closing the
    check→insert TOCTOU race: a second concurrent resolve POST **for the same
    decision** blocks on the write lock, then observes the freshly-inserted
    running row and gets 409.  Resolves of DIFFERENT decisions do not block each
    other — the guard is scoped to ``decision_id`` (webui-ux phase 4).

    The row is reserved with the web process's pid (guaranteed alive) — the
    caller updates it to the spawned runner's pid right after spawn, matching
    the maintenance-runner pattern (R8).

    On a DB error while verifying concurrency this function is **fail-CLOSED**
    (409 ``'Cannot verify'``) — a resolve WRITES to staging and must never
    proceed without concurrency protection (mirrors Finding E from the
    maintenance route).

    Row shape (canonical — match the runner's ``insert(…, if_absent=True)``):

    * ``kind`` = ``'maintenance'``
    * ``command`` = ``'scrape-resolve'``
    * ``options_json`` = ``{"decision_id": N, "provider": "tmdb|tvdb",
      "provider_id": N}`` (sorted keys, compact separators)
    * ``trigger`` = ``'web'``
    * ``dry_run`` = 0
    * ``outcome`` = ``'running'``
    * ``pid`` = ``os.getpid()`` (web process, replaced by caller after spawn)

    Args:
        db_path: Absolute path to ``library.db``.
        run_uid: The unique run identifier (``uuid4().hex``), generated by the
            caller before calling this function.
        decision_id: The ``scrape_decision.id`` being resolved.
        provider: Metadata provider name (``'tmdb'`` or ``'tvdb'``).
        provider_id: Numeric identifier assigned by the provider.

    Raises:
        HTTPException: 409 when a scrape-resolve for THIS ``decision_id`` is
            already running with a live pid, or when the DB cannot be read to
            verify concurrency.
    """
    options = {"decision_id": decision_id, "provider": provider, "provider_id": provider_id}
    options_json = json.dumps(options, sort_keys=True, separators=(",", ":"))

    if not db_path.exists():
        # No DB yet (fresh install / test) — nothing to guard or reserve.
        return

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            _guard_no_running_resolve(conn, decision_id)
            conn.execute(
                "INSERT INTO pipeline_run "
                "(run_uid, trigger, dry_run, started_at, outcome, steps_json, pid, "
                "kind, command, options_json) "
                "VALUES (?, 'web', 0, ?, 'running', '[]', ?, 'maintenance', 'scrape-resolve', ?)",
                (run_uid, time.time(), os.getpid(), options_json),
            )
            conn.execute("COMMIT")
        except HTTPException:
            _safe_rollback(conn)
            raise
        except sqlite3.OperationalError as exc:
            _safe_rollback(conn)
            log.warning("resolve_reserve_db_error", run_uid=run_uid, error=str(exc))
            # Fail-CLOSED: a resolve WRITES to staging — must never proceed
            # without concurrency verification (Finding E).
            raise HTTPException(
                status_code=409,
                detail="Cannot verify no scrape-resolve is running",
            ) from exc
    finally:
        conn.close()
