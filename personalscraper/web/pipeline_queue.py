"""Visible queue for pipeline runs while ``pipeline.lock`` is held (§6).

``POST /api/pipeline/run`` never answers « occupé » when the lock holder is a
maintenance / resolve run: it reserves a ``pipeline-queue`` row (kind
``maintenance``) via :func:`reserve_queued_pipeline_run`, spawns this module as
a detached waiter, and returns ``202 {queued: true}``. The waiter waits in the
shared visible queue (``web/run_queue.py`` — ``queue`` step on its row), then
hands over to the single trigger authority
(:func:`personalscraper.web.pipeline_trigger.spawn_pipeline_run`) once the
lock frees. The waiter never acquires the lock itself — the spawned
``personalscraper run`` claims it, keeping the single-trigger-authority
invariant intact; a lost race re-queues PACED under the same deadline.

Two rows tell the honest story: the ``pipeline-queue`` row carries the visible
wait (then finalizes ``success`` naming the launched run), and the real run row
(kind ``pipeline``) appears when the CLI starts.
"""

from __future__ import annotations

import json
import os
import random
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import FrameType

from fastapi import HTTPException

from personalscraper.conf.loader import load_config
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web._runner_engine import reserve_run_row
from personalscraper.web.run_queue import wait_in_visible_queue

log = get_logger(__name__)

#: ``command`` value of queue rows (kind='maintenance'). Excluded from the
#: kill-guard newest-running-kind probe (routes/pipeline.py) — a waiting queue
#: row must never shadow the actual lock holder.
PIPELINE_QUEUE_COMMAND = "pipeline-queue"

#: French duplicate-refusal detail (§6: only the strict duplicate refuses).
_DUPLICATE_QUEUE_DETAIL = "Un lancement du pipeline est déjà en file d'attente (doublon)."

_SIGTERM_EXIT_CODE = 143


def _canonical_options(trigger_reason: str, dry_run: bool) -> str:
    """Return the canonical ``options_json`` for a queue row.

    Args:
        trigger_reason: The ``--trigger-reason`` the queued run will carry.
        dry_run: Whether the queued run is a dry run.

    Returns:
        A deterministic JSON string (sorted keys, no spaces) so duplicate
        detection can byte-compare.
    """
    return json.dumps({"dry_run": dry_run, "trigger_reason": trigger_reason}, sort_keys=True, separators=(",", ":"))


def reserve_queued_pipeline_run(db_path: Path, *, trigger_reason: str, dry_run: bool) -> str:
    """Atomically reserve a ``pipeline-queue`` row and spawn the waiter.

    Mirrors ``web/decisions/reserve.py``: one connection, ``BEGIN IMMEDIATE``,
    duplicate guard (same options, live pid) then INSERT — a second concurrent
    POST blocks on the write lock and observes the fresh row (409 duplicate).

    Args:
        db_path: Absolute path to ``library.db``.
        trigger_reason: Forwarded to the queued run (e.g. ``"web"``).
        dry_run: Whether the queued run is a dry run.

    Returns:
        The queue row's ``run_uid``.

    Raises:
        HTTPException: 409 when an identical queued launch is already waiting,
            or when the duplicate check cannot be verified.
    """
    run_uid = uuid.uuid4().hex
    options_json = _canonical_options(trigger_reason, dry_run)

    def _guard(conn: sqlite3.Connection) -> None:
        """409 when an identical queued launch (same options, live pid) is waiting."""
        rows = conn.execute(
            "SELECT run_uid, pid FROM pipeline_run "
            "WHERE kind='maintenance' AND command=? AND outcome='running' AND options_json=?",
            (PIPELINE_QUEUE_COMMAND, options_json),
        ).fetchall()
        for row in rows:
            pid_db = row["pid"]
            if pid_db is None:
                continue
            try:
                os.kill(pid_db, 0)
            except ProcessLookupError:
                continue
            except PermissionError:
                raise HTTPException(status_code=409, detail=_DUPLICATE_QUEUE_DETAIL)
            raise HTTPException(status_code=409, detail=_DUPLICATE_QUEUE_DETAIL)

    # The atomic BEGIN IMMEDIATE + INSERT skeleton is owned by the engine; this
    # module supplies only the duplicate-queue guard.
    reserve_run_row(
        db_path,
        run_uid=run_uid,
        kind="maintenance",
        command=PIPELINE_QUEUE_COMMAND,
        options_json=options_json,
        dry_run=dry_run,
        guard=_guard,
        fail_closed=True,
        fail_closed_detail=(
            "Impossible de vérifier qu'aucun lancement n'est déjà en file "
            "(erreur de lecture de la base) — réessayez."
        ),
    )

    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_PQ_TRIGGER_REASON": trigger_reason,
        "PERSONALSCRAPER_PQ_DRY_RUN": "1" if dry_run else "0",
    }
    try:
        proc = subprocess.Popen(  # noqa: S603 — fixed argv, no shell, first-party module.
            [sys.executable, "-m", "personalscraper.web.pipeline_queue"],
            start_new_session=True,
            env=env,
        )
    except (OSError, ValueError) as exc:
        PipelineRunWriter(db_path).finalize(run_uid, "error", error=str(exc))
        log.error("pipeline_queue_spawn_failed", run_uid=run_uid, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to spawn pipeline queue waiter") from exc
    PipelineRunWriter(db_path).update_pid(run_uid, proc.pid)
    log.info("pipeline_queue_reserved", run_uid=run_uid, trigger_reason=trigger_reason, dry_run=dry_run)
    return run_uid


def main() -> None:
    """Wait for ``pipeline.lock`` to free, then launch the pipeline run.

    Entry point of ``python -m personalscraper.web.pipeline_queue``. Reads its
    env (run_uid of the reserved queue row, trigger reason, dry-run flag),
    waits in the shared visible queue, then hands over to
    ``spawn_pipeline_run``. Every exit path finalizes the queue row so it is
    never left ``'running'``.

    Exit codes: 0 on hand-over, 1 on queue timeout, 2 on misconfiguration,
    143 on SIGTERM.
    """
    run_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")
    trigger_reason = os.environ.get("PERSONALSCRAPER_PQ_TRIGGER_REASON", "web")
    dry_run = os.environ.get("PERSONALSCRAPER_PQ_DRY_RUN") == "1"
    if not run_uid:
        log.error("pipeline_queue_missing_env", missing=["PERSONALSCRAPER_RUN_UID"])
        sys.exit(2)

    try:
        config = load_config()
    except Exception as exc:
        log.error("pipeline_queue_config_load_failed", run_uid=run_uid, error=str(exc))
        sys.exit(2)
    db_path = config.indexer.db_path
    if db_path is None:
        log.error("pipeline_queue_no_db_path", run_uid=run_uid)
        sys.exit(2)

    writer = PipelineRunWriter(db_path)
    writer.update_pid(run_uid, os.getpid())
    pipeline_lock = config.paths.data_dir / "pipeline.lock"
    queue_timeout_s = float(os.environ.get("PERSONALSCRAPER_PIPELINE_QUEUE_TIMEOUT", "1800"))
    queue_deadline = time.monotonic() + queue_timeout_s

    def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Finalize the queue row ``'killed'`` on SIGTERM (web kill control)."""
        writer.finalize(run_uid, "killed")
        log.warning("pipeline_queue_killed", run_uid=run_uid)
        os._exit(_SIGTERM_EXIT_CODE)

    signal.signal(signal.SIGTERM, _on_sigterm)

    from personalscraper.web.pipeline_trigger import spawn_pipeline_run

    while True:
        if not wait_in_visible_queue(
            try_proceed=lambda: not is_lock_held(pipeline_lock),
            writer=writer,
            run_uid=run_uid,
            deadline_monotonic=queue_deadline,
            timeout_s=queue_timeout_s,
            timeout_error=(
                "Délai d'attente dépassé : pipeline.lock toujours tenu après "
                f"{int(queue_timeout_s)}s — lancement du pipeline abandonné, relancez-le."
            ),
            log_event_prefix="pipeline_queue",
        ):
            sys.exit(1)

        new_uid = spawn_pipeline_run(config.paths.data_dir, trigger_reason=trigger_reason, dry_run=dry_run)
        if new_uid is None:
            # Lost the race (the lock was re-claimed between our probe and the
            # spawn probe) — re-queue PACED under the same deadline.
            if time.monotonic() > queue_deadline:
                writer.finalize(
                    run_uid,
                    "error",
                    error=(
                        "Délai d'attente dépassé : verrou toujours occupé après "
                        f"{int(queue_timeout_s)}s de tentatives — lancement abandonné."
                    ),
                )
                log.error("pipeline_queue_requeue_timeout", run_uid=run_uid)
                sys.exit(1)
            log.info("pipeline_queue_requeued", run_uid=run_uid)
            time.sleep(1.0 + random.uniform(0.0, 1.0))
            continue

        writer.finalize(run_uid, "success", output_tail=f"Run pipeline lancé : {new_uid}\n")
        log.info("pipeline_queue_handed_over", run_uid=run_uid, launched_run_uid=new_uid)
        sys.exit(0)


if __name__ == "__main__":
    main()
