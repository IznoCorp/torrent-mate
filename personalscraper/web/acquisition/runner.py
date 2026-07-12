"""Grab runner — subprocess wrapper for the per-series manual trigger (OBJ3).

Executable as ``python -m personalscraper.web.acquisition.runner``. Reads its
configuration from environment variables (set by the POST handler in
``personalscraper.web.routes.acquisition``) and is responsible for:

1. Reserving/claiming a ``pipeline_run`` row (``kind='maintenance'``,
   ``command='grab'``) — the POST handler inserts it first (``if_absent=True``).
2. Spawning ``personalscraper grab --followed-id <id>`` as a detached
   subprocess (``start_new_session=True``).
3. Streaming each output line to a 64 KiB ring buffer + Redis (fail-soft).
4. Finalizing the ``pipeline_run`` row on every exit path (never left
   ``'running'``).

The ``grab`` CLI does NOT acquire the global ``pipeline.lock`` (it runs
independently of a full pipeline run, like the scheduled grab cron), and each
wanted item is claimed atomically (``claim_for_search``) so two grabs for the
same series are idempotent — this runner therefore touches no lock.

Environment contract (canonical — match the spawner):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_GRAB_FOLLOWED_ID`` — mandatory, the ``followed_series.id``.

Exit codes:

* ``0`` — the CLI subprocess completed successfully.
* ``1`` — the CLI subprocess exited non-zero (error).
* ``2`` — misconfiguration (missing env, config load failure, spawn failure).
* ``143`` — runner killed via SIGTERM.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from types import FrameType

from personalscraper.conf.loader import load_config
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.maintenance.runner import (
    _get_redis,
    _kill_child_group,
    _redis_publish_line,
    _RingBuffer,
)

log = get_logger(__name__)

OUTCOME_SUCCESS = "success"
OUTCOME_ERROR = "error"
OUTCOME_KILLED = "killed"
_SIGTERM_EXIT_CODE = 143


def _read_mandatory_env() -> tuple[str, int]:
    """Read the two mandatory runner env vars; exit 2 on missing/invalid.

    Returns:
        A ``(run_uid, followed_id)`` tuple.

    Raises:
        SystemExit: 2 when a required var is missing or ``followed_id`` is not
            an integer.
    """
    run_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")
    raw_followed = os.environ.get("PERSONALSCRAPER_GRAB_FOLLOWED_ID")
    if not run_uid or not raw_followed:
        log.error(
            "grab_runner_missing_env",
            hint="The spawner MUST set PERSONALSCRAPER_RUN_UID + PERSONALSCRAPER_GRAB_FOLLOWED_ID",
        )
        sys.exit(2)
    try:
        followed_id = int(raw_followed)
    except ValueError:
        log.error("grab_runner_bad_followed_id", value=raw_followed)
        sys.exit(2)
    return run_uid, followed_id


def _build_argv(followed_id: int) -> list[str]:
    """Build the ``grab --followed-id N`` CLI argument list.

    Args:
        followed_id: The followed series to scope the grab to.

    Returns:
        A command-line argument list starting with ``sys.executable``.
    """
    return [sys.executable, "-m", "personalscraper", "grab", "--followed-id", str(followed_id)]


def main() -> None:
    """Run the per-series grab subprocess (see module docstring).

    Reserves/claims the ``pipeline_run`` row, spawns ``grab --followed-id N``,
    streams its output, and finalizes the row on every exit path — so a manual
    trigger is tracked exactly like a maintenance run and never leaves a stuck
    ``'running'`` row.
    """
    run_uid, followed_id = _read_mandatory_env()

    try:
        config = load_config()
    except Exception as exc:  # noqa: BLE001 — config failure must not orphan a row
        log.error("grab_runner_config_load_failed", run_uid=run_uid, error=str(exc))
        sys.exit(2)

    db_path = config.indexer.db_path
    if db_path is None:
        log.error("grab_runner_no_db_path", run_uid=run_uid)
        sys.exit(2)
    web_config = config.web

    options_json = json.dumps({"followed_id": followed_id}, sort_keys=True, separators=(",", ":"))
    argv = _build_argv(followed_id)

    # Ensure the pipeline_run row exists (idempotent) and claim its pid.
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command="grab",
        options_json=options_json,
        if_absent=True,
    )
    writer.update_pid(run_uid, os.getpid())

    ring = _RingBuffer()
    child: dict[str, subprocess.Popen[str]] = {}

    def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Terminate the child group, finalize ``'killed'``."""
        proc_ref = child.get("proc")
        if proc_ref is not None:
            _kill_child_group(proc_ref)
        writer.finalize(run_uid, OUTCOME_KILLED, output_tail=ring.to_str())
        log.warning("grab_runner_killed", run_uid=run_uid, followed_id=followed_id)
        os._exit(_SIGTERM_EXIT_CODE)

    signal.signal(signal.SIGTERM, _on_sigterm)

    log.info("grab_runner_starting", run_uid=run_uid, followed_id=followed_id, argv=argv)

    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        log.error("grab_runner_spawn_failed", run_uid=run_uid, followed_id=followed_id, error=str(exc))
        writer.finalize(run_uid, OUTCOME_ERROR, error=str(exc))
        sys.exit(2)

    child["proc"] = proc

    redis = _get_redis(web_config)
    stream_key = web_config.stream_key
    stream_maxlen = web_config.stream_maxlen
    seq = 0

    try:
        assert proc.stdout is not None  # noqa: S101 — Popen with stdout=PIPE
        for line in proc.stdout:
            ring.append(line)
            _redis_publish_line(redis, line, run_uid, seq, stream_key, stream_maxlen)
            seq += 1
        rc = proc.wait()
    except Exception as exc:  # noqa: BLE001 — any stream failure must finalize the row
        _kill_child_group(proc)
        writer.finalize(
            run_uid,
            OUTCOME_ERROR,
            error=str(exc) or type(exc).__name__,
            output_tail=ring.to_str(),
        )
        log.error("grab_runner_stream_failed", run_uid=run_uid, followed_id=followed_id, exc_info=True)
        sys.exit(1)

    output_tail = ring.to_str()
    if rc == 0:
        writer.finalize(run_uid, OUTCOME_SUCCESS, output_tail=output_tail)
        log.info("grab_runner_completed", run_uid=run_uid, followed_id=followed_id, rc=rc, lines=seq)
    else:
        error_tail = output_tail[-2000:] if len(output_tail) > 2000 else output_tail
        writer.finalize(run_uid, OUTCOME_ERROR, error=error_tail, output_tail=output_tail)
        log.error("grab_runner_failed", run_uid=run_uid, followed_id=followed_id, rc=rc, lines=seq)

    sys.exit(rc)


if __name__ == "__main__":
    main()
