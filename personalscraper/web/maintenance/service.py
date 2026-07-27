"""Action-run service behind ``POST /api/maintenance/actions/{id}/run``.

The route module (``web/routes/maintenance.py``) keeps only the endpoint
definitions, dependency wiring, and response shaping; the option validation,
the atomic duplicate/dry-run-first guards, the run-row reservation, and the
detached-runner spawn live here (route/service split, DESIGN T10).

The reservation reuses the single ``reserve_run_row`` engine skeleton
(``web/_runner_engine.py``) — this module supplies only the maintenance-specific
guards and the missing-DB rule; it never re-implements ``BEGIN IMMEDIATE``.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from fastapi import HTTPException

from personalscraper.logger import get_logger
from personalscraper.web._runner_engine import reserve_run_row
from personalscraper.web.maintenance.registry import MaintenanceAction

logger = get_logger(__name__)

#: 428 detail returned when a destructive apply lacks a fresh dry-run.
_DRY_RUN_FIRST_DETAIL = (
    "A fresh successful dry-run (within 30 minutes, same options) is required before applying this destructive action"
)

#: French duplicate-refusal detail — the ONLY 409 left on this surface (§6:
#: the sole permitted refusal is idempotence — the same action already running).
_DUPLICATE_ACTION_DETAIL = "Cette action est déjà en cours avec les mêmes options (doublon)."


def _validate_options(action: MaintenanceAction, body_options: dict[str, object]) -> None:
    """Validate *body_options* against the action's registered :class:`ActionOption` entries.

    No coercion is performed — every value must already match the declared type.
    Unknown keys, missing required options, type mismatches, and enum values outside the
    declared set are all rejected with 422.

    Args:
        action: The maintenance action from :data:`REGISTRY`.
        body_options: The ``options`` dict from the :class:`ActionRunRequest` body.

    Raises:
        HTTPException: 422 with a ``detail`` message describing the first validation failure.
    """
    registered = {opt.name: opt for opt in action.options}

    # Unknown keys.
    for key in body_options:
        if key not in registered:
            raise HTTPException(status_code=422, detail=f"Unknown option: {key!r}")

    # Missing required options.
    for opt in action.options:
        if opt.required and opt.name not in body_options:
            raise HTTPException(status_code=422, detail=f"Missing required option: {opt.name!r}")

    # Type / enum validation for each provided key.
    for key, value in body_options.items():
        opt = registered[key]

        if opt.type == "bool":
            if not isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be a boolean")
        elif opt.type == "int":
            # bool is a subclass of int — reject it explicitly.
            if not isinstance(value, int) or isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be an integer")
        elif opt.type == "str":
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be a string")
        elif opt.type == "enum":
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"Option {key!r} must be a string")
            if opt.enum_values and value not in opt.enum_values:
                raise HTTPException(
                    status_code=422,
                    detail=(f"Option {key!r}: {value!r} is not a valid value. Allowed: {', '.join(opt.enum_values)}"),
                )


def _guard_no_duplicate_action(conn: sqlite3.Connection, command: str, options_json: str, dry_run: bool) -> None:
    """Raise 409 when the SAME action (same options, same mode) is live.

    §6 (constitution v2): a busy system is never a reason to refuse — a
    DIFFERENT action reserves its row and waits in the runner's visible queue
    (``web/run_queue.py``). The only refusal left is the strict duplicate:
    same ``command`` AND byte-identical ``options_json`` AND same ``dry_run``
    mode with a live pid (a dry-run preview during a live apply is NOT the
    same action). Rows with a dead or NULL pid are stale (crashed runner /
    pre-pid migration) and are ignored — we never mutate them here.

    Args:
        conn: An open connection (inside the reserve transaction).
        command: The action id being launched.
        options_json: Canonical options JSON (byte-compared).
        dry_run: The launch mode, part of the duplicate identity.

    Raises:
        HTTPException: 409 when the same action with the same options is live.
    """
    rows = conn.execute(
        "SELECT run_uid, pid FROM pipeline_run "
        "WHERE kind='maintenance' AND outcome='running' AND command=? AND options_json=? AND dry_run=?",
        (command, options_json, 1 if dry_run else 0),
    ).fetchall()
    for row in rows:
        run_uid_db = row["run_uid"]
        pid_db = row["pid"]
        if pid_db is None:
            # NULL pid → stale row (pre-pid-migration or a runner that crashed
            # before claiming its pid).
            logger.info("maintenance_stale_row_ignored", run_uid=run_uid_db, pid=None, action_id=command)
            continue
        try:
            os.kill(pid_db, 0)
        except ProcessLookupError:
            # Dead process → stale row (crashed runner).
            logger.info("maintenance_stale_row_ignored", run_uid=run_uid_db, pid=pid_db, action_id=command)
            continue
        except PermissionError:
            # Process exists but owned by another user → treat as alive.
            raise HTTPException(status_code=409, detail=_DUPLICATE_ACTION_DETAIL)
        else:
            raise HTTPException(status_code=409, detail=_DUPLICATE_ACTION_DETAIL)


def _guard_recent_dry_run(conn: sqlite3.Connection, action_id: str, options_json: str) -> None:
    """Raise 428 unless a fresh successful dry-run (same options) exists.

    Args:
        conn: An open connection (inside the reserve transaction).
        action_id: The destructive action being applied.
        options_json: Canonical options JSON compared by string equality.

    Raises:
        HTTPException: 428 when no matching dry-run row exists within 30 minutes.
    """
    cutoff = time.time() - 1800
    row = conn.execute(
        "SELECT 1 FROM pipeline_run "
        "WHERE kind='maintenance' AND command=? AND options_json=? "
        "AND dry_run=1 AND outcome='success' AND ended_at >= ? LIMIT 1",
        (action_id, options_json, cutoff),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=428, detail=_DRY_RUN_FIRST_DETAIL)


def _reserve_run_row(
    db_path: Path,
    *,
    run_uid: str,
    action: MaintenanceAction,
    command: str,
    options_json: str,
    dry_run: bool,
) -> None:
    """Atomically guard duplicates + dry-run-first and reserve the run row.

    Opens one connection under ``BEGIN IMMEDIATE`` so the duplicate check and
    the ``pipeline_run`` INSERT are a single serialised transaction: a second
    concurrent POST of the SAME action blocks on the write lock, then observes
    the freshly-inserted running row (409 duplicate), closing the check→insert
    TOCTOU race (Finding C). The row is reserved with a placeholder pid of the
    web process (guaranteed alive) — the caller updates it to the spawned
    runner's pid right after spawn.

    Guard order: 409 duplicate (same command + same options only, §6) → 428
    dry-run-first → INSERT. A held ``pipeline.lock`` is NOT a refusal anymore:
    the spawned runner waits in the visible queue (``web/run_queue.py``) and
    the run row carries the ``queue`` step while it does.

    On a DB read error while verifying duplicates, a ``destructive`` action is
    fail-CLOSED (409) — the only concurrency protection must never be dropped
    silently (Finding E). ``write`` / ``ro`` actions stay permissive.

    Args:
        db_path: Absolute path to ``library.db``.
        run_uid: The unique run identifier reserved by the caller.
        action: The resolved maintenance action.
        command: The action id (stored in the ``command`` column).
        options_json: Canonical options JSON (stored + compared for 428).
        dry_run: ``True`` for a dry run.

    Raises:
        HTTPException: 409 (already running / cannot verify) or 428 (no fresh
            dry run). The transaction is rolled back before raising.
    """
    destructive = action.risk == "destructive"
    check_concurrency = action.risk in ("write", "destructive")

    def _guard(conn: sqlite3.Connection) -> None:
        """Guard order (§6): 409 duplicate (same command + options) → 428 dry-run-first."""
        if check_concurrency:
            _guard_no_duplicate_action(conn, command, options_json, dry_run)
        if destructive and not dry_run:
            _guard_recent_dry_run(conn, command, options_json)

    def _missing_db() -> None:
        """No DB yet: a destructive apply still needs a prior dry-run → 428."""
        if destructive and not dry_run:
            raise HTTPException(status_code=428, detail=_DRY_RUN_FIRST_DETAIL)

    # The atomic BEGIN IMMEDIATE + INSERT skeleton is owned by the engine; this
    # route supplies only the maintenance-specific guards + the missing-DB rule.
    reserve_run_row(
        db_path,
        run_uid=run_uid,
        kind="maintenance",
        command=command,
        options_json=options_json,
        dry_run=dry_run,
        guard=_guard,
        # Fail-CLOSED for destructive apply: never run a duplicate destructive
        # action when the DB cannot be read (§8). write / ro stay permissive.
        fail_closed=destructive,
        fail_closed_detail=(
            "Impossible de vérifier qu'aucune action identique n'est en cours "
            "(erreur de lecture de la base) — réessayez."
        ),
        missing_db=_missing_db,
    )


def _spawn_runner(run_uid: str, action_id: str, options_json: str, dry_run: bool) -> int:
    """Spawn the maintenance runner as a detached subprocess.

    The runner module (``personalscraper.web.maintenance.runner``) reads its
    configuration from the environment variables set here. It is responsible for
    executing the CLI command, streaming output, and finalizing the
    ``pipeline_run`` row (reserved by the caller before this spawn).

    Args:
        run_uid: The unique run identifier (``uuid4().hex``).
        action_id: The maintenance action id (e.g. ``"library-index"``).
        options_json: Canonical JSON string of validated options (produced by
            :func:`canonical_options_json`).
        dry_run: ``True`` when this is a dry run.

    Returns:
        The pid of the spawned runner process.
    """
    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_MAINT_COMMAND": action_id,
        "PERSONALSCRAPER_MAINT_OPTIONS_JSON": options_json,
        "PERSONALSCRAPER_MAINT_DRY_RUN": "1" if dry_run else "0",
    }
    logger.info(
        "maintenance_run_spawned",
        run_uid=run_uid,
        action_id=action_id,
        dry_run=dry_run,
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "personalscraper.web.maintenance.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid
