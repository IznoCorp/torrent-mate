"""Action-run service behind ``POST /api/maintenance/actions/{id}/run``.

The route module (``web/routes/maintenance.py``) keeps only the endpoint
definitions, dependency wiring, and response shaping; the option validation,
the atomic duplicate/dry-run-first guards, the run-row reservation, and the
detached-runner spawn live here (route/service split, DESIGN T10).

The reservation reuses the single ``reserve_run_row`` engine skeleton
(``app/_runner_engine.py``) — this module supplies only the maintenance-specific
guards and the missing-DB rule; it never re-implements ``BEGIN IMMEDIATE``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from personalscraper.app._runner_engine import reserve_run_row
from personalscraper.app.errors import AppConflict, AppInternalError, AppPreconditionRequired, AppValidationError
from personalscraper.app.maintenance.registry import MaintenanceAction, canonical_options_json
from personalscraper.app.run_queue import QUEUE_STEP_NAME, QUEUE_WAITING_STATUS
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter

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
        AppValidationError: 422 with a ``detail`` message describing the first validation failure.
    """
    registered = {opt.name: opt for opt in action.options}

    # Unknown keys.
    for key in body_options:
        if key not in registered:
            raise AppValidationError(f"Unknown option: {key!r}")

    # Missing required options.
    for opt in action.options:
        if opt.required and opt.name not in body_options:
            raise AppValidationError(f"Missing required option: {opt.name!r}")

    # Type / enum validation for each provided key.
    for key, value in body_options.items():
        opt = registered[key]

        if opt.type == "bool":
            if not isinstance(value, bool):
                raise AppValidationError(f"Option {key!r} must be a boolean")
        elif opt.type == "int":
            # bool is a subclass of int — reject it explicitly.
            if not isinstance(value, int) or isinstance(value, bool):
                raise AppValidationError(f"Option {key!r} must be an integer")
        elif opt.type == "str":
            if not isinstance(value, str):
                raise AppValidationError(f"Option {key!r} must be a string")
        elif opt.type == "enum":
            if not isinstance(value, str):
                raise AppValidationError(f"Option {key!r} must be a string")
            if opt.enum_values and value not in opt.enum_values:
                raise AppValidationError(
                    f"Option {key!r}: {value!r} is not a valid value. Allowed: {', '.join(opt.enum_values)}"
                )


def _live_duplicate(conn: sqlite3.Connection, command: str, options_json: str, dry_run: bool) -> str | None:
    """Find the live run of the SAME action (same options, same mode), if one runs.

    Rows with a dead or NULL pid are stale (crashed runner / pre-pid migration)
    and are ignored — never mutated here. A pid owned by another user is alive.

    Args:
        conn: An open connection whose ``row_factory`` is ``sqlite3.Row``.
        command: The action id.
        options_json: Canonical options JSON (byte-compared).
        dry_run: The launch mode, part of the duplicate identity.

    Returns:
        The live run's ``run_uid``, or ``None`` when none runs.
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
            return str(run_uid_db)
        return str(run_uid_db)
    return None


def _guard_no_duplicate_action(conn: sqlite3.Connection, command: str, options_json: str, dry_run: bool) -> None:
    """Raise 409 when the SAME action (same options, same mode) is live.

    §6 (constitution v2): a busy system is never a reason to refuse — a
    DIFFERENT action reserves its row and waits in the runner's visible queue
    (``app/run_queue.py``). The only refusal left is the strict duplicate:
    same ``command`` AND byte-identical ``options_json`` AND same ``dry_run``
    mode with a live pid (a dry-run preview during a live apply is NOT the
    same action).

    Args:
        conn: An open connection (inside the reserve transaction).
        command: The action id being launched.
        options_json: Canonical options JSON (byte-compared).
        dry_run: The launch mode, part of the duplicate identity.

    Raises:
        AppConflict: 409 when the same action with the same options is live.
    """
    if _live_duplicate(conn, command, options_json, dry_run) is not None:
        raise AppConflict(_DUPLICATE_ACTION_DETAIL)


def running_run_uid(
    action: MaintenanceAction, options: Mapping[str, object], *, db_path: Path, dry_run: bool = False
) -> str | None:
    """Name the live run of an action with these options, as the duplicate guard sees it.

    The reader behind a caller that answers a duplicate launch with the run already
    under way instead of a refusal.

    Args:
        action: The maintenance action.
        options: Its options, canonicalised as a launch canonicalises them.
        db_path: Absolute path to ``library.db``.
        dry_run: The mode the duplicate is sought in.

    Returns:
        The live run's ``run_uid``, or ``None`` when none runs (or ``library.db`` is absent).
    """
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
        return _live_duplicate(conn, action.id, canonical_options_json(dict(options)), dry_run)
    finally:
        conn.close()


def running_run(
    action: MaintenanceAction, options: Mapping[str, object], *, db_path: Path, data_dir: Path
) -> LaunchedRun | None:
    """Name the live run of an action with these options, and whether it waits on the pipeline.

    The joining counterpart of :func:`launch_action`: the same answer for a run already
    under way as for one just launched.

    Args:
        action: The maintenance action (a live apply, never a dry run).
        options: Its options, canonicalised as a launch canonicalises them.
        db_path: Absolute path to ``library.db``.
        data_dir: The pipeline data directory holding ``pipeline.lock``.

    Returns:
        The live run and whether it waits in the visible queue, or ``None`` when none runs.
    """
    run_uid = running_run_uid(action, options, db_path=db_path)
    if run_uid is None:
        return None
    queued = action.risk in ("write", "destructive") and _waits_on_pipeline(
        run_uid, db_path=db_path, lock_file=data_dir / "pipeline.lock"
    )
    return LaunchedRun(run_uid=run_uid, queued=queued)


def _waits_on_pipeline(run_uid: str, *, db_path: Path, lock_file: Path) -> bool:
    """Say whether a live run waits for ``pipeline.lock`` rather than runs.

    The run's own ``queue`` step answers once its runner wrote one. Before that, the run
    waits when another live process holds the lock: a live write holds the lock itself
    while it runs, so a lock held under the run's own pid is no wait.

    Args:
        run_uid: The live run.
        db_path: Absolute path to ``library.db``.
        lock_file: ``pipeline.lock``.

    Returns:
        ``True`` when the run waits in the visible queue.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        apply_pragmas(conn)
        row = conn.execute("SELECT pid, steps_json FROM pipeline_run WHERE run_uid=?", (run_uid,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return False
    pid, steps_json = row
    try:
        steps = json.loads(steps_json) if steps_json else []
    except (json.JSONDecodeError, TypeError):
        steps = []
    queue_steps = [step for step in steps if isinstance(step, dict) and step.get("name") == QUEUE_STEP_NAME]
    if queue_steps:
        return queue_steps[-1].get("status") == QUEUE_WAITING_STATUS
    if not is_lock_held(lock_file):
        return False
    try:
        holder = int(lock_file.read_text().strip())
    except (OSError, ValueError):
        return False
    return holder != pid


def _guard_recent_dry_run(conn: sqlite3.Connection, action_id: str, options_json: str) -> None:
    """Raise 428 unless a fresh successful dry-run (same options) exists.

    Args:
        conn: An open connection (inside the reserve transaction).
        action_id: The destructive action being applied.
        options_json: Canonical options JSON compared by string equality.

    Raises:
        AppPreconditionRequired: 428 when no matching dry-run row exists within 30 minutes.
    """
    cutoff = time.time() - 1800
    row = conn.execute(
        "SELECT 1 FROM pipeline_run "
        "WHERE kind='maintenance' AND command=? AND options_json=? "
        "AND dry_run=1 AND outcome='success' AND ended_at >= ? LIMIT 1",
        (action_id, options_json, cutoff),
    ).fetchone()
    if row is None:
        raise AppPreconditionRequired(_DRY_RUN_FIRST_DETAIL)


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
    the spawned runner waits in the visible queue (``app/run_queue.py``) and
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
        AppConflict: 409 (already running / cannot verify). The transaction is rolled back before raising.
        AppPreconditionRequired: 428 (no fresh dry run). The transaction is rolled back before raising.
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
            raise AppPreconditionRequired(_DRY_RUN_FIRST_DETAIL)

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

    The runner module (``personalscraper.app.maintenance.runner``) reads its
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
        [sys.executable, "-m", "personalscraper.app.maintenance.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid


@dataclass(frozen=True)
class LaunchedRun:
    """A maintenance run reserved and spawned.

    Attributes:
        run_uid: The reserved ``pipeline_run`` row's id.
        queued: Whether ``pipeline.lock`` was held at launch: the runner waits in the
            visible queue until it frees.
    """

    run_uid: str
    queued: bool


def launch_action(
    action: MaintenanceAction,
    options: Mapping[str, object],
    *,
    db_path: Path,
    data_dir: Path,
    dry_run: bool = False,
) -> LaunchedRun:
    """Launch a maintenance action from the application layer: validate, reserve, spawn.

    The same steps as ``POST /api/maintenance/actions/{id}/run``: the options are
    validated, the run row is reserved under the duplicate and dry-run-first guards,
    the detached runner is spawned and claims the row with its pid. A held
    ``pipeline.lock`` is never a refusal: the runner waits in the visible queue.

    Args:
        action: The registry action.
        options: Its options, already typed.
        db_path: Absolute path to ``library.db``.
        data_dir: The pipeline data directory holding ``pipeline.lock``.
        dry_run: ``True`` for a dry run.

    Returns:
        The reserved run and whether it waits on the lock.

    Raises:
        AppValidationError: 422 on options the action refuses, or a dry run of an
            action that has none.
        AppConflict: 409 when the same action with the same options is running.
        AppPreconditionRequired: 428 when a destructive apply has no fresh dry run.
        AppInternalError: 500 when the runner cannot be spawned (its row is finalised ``error``).
    """
    if action.dry_run == "unsupported" and dry_run:
        raise AppValidationError(f"Action {action.id!r} does not support dry-run")
    _validate_options(action, dict(options))
    options_json = canonical_options_json(dict(options))
    run_uid = uuid.uuid4().hex
    _reserve_run_row(
        db_path, run_uid=run_uid, action=action, command=action.id, options_json=options_json, dry_run=dry_run
    )
    try:
        pid = _spawn_runner(run_uid, action.id, options_json, dry_run)
    except (OSError, ValueError) as exc:
        PipelineRunWriter(db_path).finalize(run_uid, "error", error=str(exc))
        logger.error("maintenance_spawn_failed", run_uid=run_uid, action_id=action.id, error=str(exc))
        raise AppInternalError("Failed to spawn maintenance runner") from exc
    PipelineRunWriter(db_path).update_pid(run_uid, pid)
    queued = action.risk in ("write", "destructive") and not dry_run and is_lock_held(data_dir / "pipeline.lock")
    return LaunchedRun(run_uid=run_uid, queued=queued)
