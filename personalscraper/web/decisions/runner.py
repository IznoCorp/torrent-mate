"""Decision runner — subprocess wrapper spawned by the resolve POST handler.

Executable as ``python -m personalscraper.web.decisions.runner``. Reads its
configuration from environment variables (set by the POST handler in
``personalscraper.web.routes.decisions``) and is responsible for:

1. Reading the decision row from ``scrape_decision`` (staging_path, status).
2. Writing a ``pipeline_run`` row (``kind='maintenance'``, ``command='scrape-resolve'``).
3. Spawning ``personalscraper scrape-resolve <staging_path> --provider X --id Y`` as a
   detached subprocess (``start_new_session=True``).
4. Streaming each output line to Redis (fail-soft) and a 64 KiB ring buffer.
5. Finalizing the ``pipeline_run`` row on every exit path.

Lock ownership (R11 / webui-ux phase 4): the ``scrape-resolve`` CLI acquires the
SCOPED per-staging-item scrape lock
(:func:`~personalscraper.lock.acquire_scrape_resolve_lock`) for its lifetime — NOT
the global ``pipeline.lock``. That scoped lock is fail-closed against the global
lock (distinct items resolve in parallel; any global holder makes the resolve back
off), so this runner does NOT acquire any lock on the child's behalf. The
``"scrape-resolve"`` entry in
``personalscraper.web.maintenance.runner._CLI_SELF_LOCKING`` is VESTIGIAL for this
path: that set is consulted only by the MAINTENANCE runner (which does not spawn
scrape-resolve); this decisions runner consults no such set and simply never
touches a lock.

Environment contract (canonical — match the spawner):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_DECISION_ID`` — mandatory, the ``scrape_decision.id``.
* ``PERSONALSCRAPER_DECISION_PROVIDER`` — mandatory, ``"tmdb"`` or ``"tvdb"``.
* ``PERSONALSCRAPER_DECISION_PROVIDER_ID`` — mandatory, the provider numeric ID.

Exit codes:

* ``0`` — the CLI subprocess completed successfully.
* ``1`` — the CLI subprocess exited non-zero (error).
* ``2`` — misconfiguration (missing env, missing/non-pending decision, config load
  failure, DB failure, spawn failure).
* ``143`` — runner killed via SIGTERM (same as maintenance runner).
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
from types import FrameType
from typing import cast

from personalscraper.conf.loader import load_config
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.maintenance.runner import (
    _get_redis,
    _kill_child_group,
    _redis_publish_line,
    _RingBuffer,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Outcome string used for CLI exit-code-0 success.
OUTCOME_SUCCESS = "success"

#: Outcome string used for CLI non-zero exit.
OUTCOME_ERROR = "error"

#: Outcome string used when the runner is killed via SIGTERM.
OUTCOME_KILLED = "killed"

#: Exit code used after a SIGTERM-initiated shutdown (128 + SIGTERM).
_SIGTERM_EXIT_CODE = 143

# ---------------------------------------------------------------------------
# Env reading
# ---------------------------------------------------------------------------


def _read_mandatory_env() -> tuple[str, int, str, int]:
    """Read the four mandatory runner env vars; exit 2 on missing.

    Returns:
        A ``(run_uid, decision_id, provider, provider_id)`` tuple.

    Raises:
        SystemExit: 2 when any required env var is missing or has an invalid
            integer value.
    """
    missing: list[str] = []
    for var in (
        "PERSONALSCRAPER_RUN_UID",
        "PERSONALSCRAPER_DECISION_ID",
        "PERSONALSCRAPER_DECISION_PROVIDER",
        "PERSONALSCRAPER_DECISION_PROVIDER_ID",
    ):
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        log.error(
            "decision_runner_missing_env",
            missing=missing,
            hint="The spawner MUST set all four PERSONALSCRAPER_DECISION_* vars",
        )
        sys.exit(2)

    run_uid = os.environ["PERSONALSCRAPER_RUN_UID"]

    try:
        decision_id = int(os.environ["PERSONALSCRAPER_DECISION_ID"])
    except ValueError:
        log.error(
            "decision_runner_bad_decision_id",
            value=os.environ["PERSONALSCRAPER_DECISION_ID"],
        )
        sys.exit(2)

    provider = os.environ["PERSONALSCRAPER_DECISION_PROVIDER"]

    try:
        provider_id = int(os.environ["PERSONALSCRAPER_DECISION_PROVIDER_ID"])
    except ValueError:
        log.error(
            "decision_runner_bad_provider_id",
            value=os.environ["PERSONALSCRAPER_DECISION_PROVIDER_ID"],
        )
        sys.exit(2)

    return run_uid, decision_id, provider, provider_id


# ---------------------------------------------------------------------------
# Decision row reading
# ---------------------------------------------------------------------------


def _read_decision_row(db_path: str, decision_id: int) -> dict[str, object] | None:
    """Read the ``scrape_decision`` row by *decision_id*.

    Opens a short-lived ``sqlite3`` connection and returns ``id``,
    ``staging_path``, and ``status`` as a dict.  Returns ``None`` when the
    row does not exist.

    Args:
        db_path: Path to the indexer SQLite database.
        decision_id: Primary key of the ``scrape_decision`` row.

    Returns:
        A dict with ``id``, ``staging_path``, and ``status`` keys, or
        ``None`` when the row does not exist.
    """
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, staging_path, status FROM scrape_decision WHERE id = ?",
        (decision_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


# ---------------------------------------------------------------------------
# CLI argv building
# ---------------------------------------------------------------------------


def _build_argv(staging_path: str, provider: str, provider_id: int, via: str) -> list[str]:
    """Build the ``scrape-resolve`` CLI argument list.

    Args:
        staging_path: Absolute path to the staging item.
        provider: Metadata provider name (``'tmdb'`` or ``'tvdb'``).
        provider_id: Numeric identifier assigned by the provider.
        via: Resolution provenance (``'pick'`` / ``'search_override'``),
            forwarded so ``resolution_json.via`` is accurate (F09).

    Returns:
        A command-line argument list starting with ``sys.executable``,
        suitable for ``subprocess.Popen``.
    """
    return [
        sys.executable,
        "-m",
        "personalscraper",
        "scrape-resolve",
        staging_path,
        "--provider",
        provider,
        "--id",
        str(provider_id),
        "--via",
        via,
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the decision resolution subprocess.

    This is the single entry point invoked by
    ``python -m personalscraper.web.decisions.runner``. It reads env vars,
    validates the decision row exists and is ``'pending'``, ensures a
    ``pipeline_run`` row exists (``if_absent=True`` — the POST handler
    reserves it first), spawns the CLI subprocess, streams output to Redis
    and a ring buffer, then finalizes the row.

    The insert→stream→finalize region is fully guarded: any exception (config
    failure aside) finalizes the row with an outcome so it is **never** left
    ``'running'`` (Finding A). A ``SIGTERM`` terminates the child process group
    and finalizes the row ``'killed'``.

    Lock ownership (R11 / webui-ux phase 4): the ``scrape-resolve`` CLI acquires
    the SCOPED per-staging-item scrape lock (fail-closed against the global
    ``pipeline.lock``), NOT the global lock itself; this runner does NOT touch any
    lock. The vestigial ``_CLI_SELF_LOCKING`` "scrape-resolve" entry (maintenance
    runner) is irrelevant here — this decisions runner consults no such set.

    Exit codes: 0 on CLI success, 1 on CLI error, 2 on misconfiguration,
    143 on SIGTERM.
    """
    # 1. Read env.
    run_uid, decision_id, provider, provider_id = _read_mandatory_env()

    # 2. Load config (respects PERSONALSCRAPER_CONFIG env).
    try:
        config = load_config()
    except Exception as exc:
        log.error(
            "decision_runner_config_load_failed",
            run_uid=run_uid,
            error=str(exc),
        )
        sys.exit(2)

    db_path = config.indexer.db_path
    if db_path is None:
        log.error(
            "decision_runner_no_db_path",
            run_uid=run_uid,
        )
        sys.exit(2)
    web_config = config.web

    # 3. Build options_json for the pipeline_run row.
    options = {"decision_id": decision_id, "provider": provider, "provider_id": provider_id}
    options_json = json.dumps(options, sort_keys=True, separators=(",", ":"))

    # Resolution provenance (optional — legacy spawners omit it). Defaults to
    # 'pick' so an absent env var never breaks the run (F09).
    via = os.environ.get("PERSONALSCRAPER_DECISION_VIA", "pick")

    # 4. Read and validate the decision row.  This read happens on the
    #    contended library.db BEFORE the guarded stream region — an unguarded
    #    sqlite error here would kill the process and leave the route-reserved
    #    'running' row orphaned forever, so finalize it 'error' first (F06).
    try:
        decision = _read_decision_row(str(db_path), decision_id)
    except sqlite3.Error as exc:
        writer_err = PipelineRunWriter(db_path)
        writer_err.insert(
            run_uid,
            trigger="web",
            dry_run=False,
            pid=os.getpid(),
            kind="maintenance",
            command="scrape-resolve",
            options_json=options_json,
            if_absent=True,
        )
        writer_err.finalize(run_uid, OUTCOME_ERROR, error=f"Decision read failed: {exc}")
        log.error(
            "decision_runner_decision_read_failed",
            run_uid=run_uid,
            decision_id=decision_id,
            error=str(exc),
        )
        sys.exit(2)
    if decision is None:
        writer_err = PipelineRunWriter(db_path)
        writer_err.insert(
            run_uid,
            trigger="web",
            dry_run=False,
            pid=os.getpid(),
            kind="maintenance",
            command="scrape-resolve",
            options_json=options_json,
            if_absent=True,
        )
        writer_err.finalize(run_uid, OUTCOME_ERROR, error=f"Decision {decision_id} not found")
        log.error(
            "decision_runner_decision_not_found",
            run_uid=run_uid,
            decision_id=decision_id,
        )
        sys.exit(2)

    if decision["status"] != "pending":
        writer_err = PipelineRunWriter(db_path)
        writer_err.insert(
            run_uid,
            trigger="web",
            dry_run=False,
            pid=os.getpid(),
            kind="maintenance",
            command="scrape-resolve",
            options_json=options_json,
            if_absent=True,
        )
        writer_err.finalize(
            run_uid,
            OUTCOME_ERROR,
            error=(f"Decision {decision_id} is '{decision['status']}', expected 'pending'"),
        )
        log.error(
            "decision_runner_decision_not_pending",
            run_uid=run_uid,
            decision_id=decision_id,
            status=decision["status"],
        )
        sys.exit(2)

    staging_path = cast(str, decision["staging_path"])

    # 5. Build CLI argv.
    argv = _build_argv(staging_path, provider, provider_id, via)

    # 6. Ensure the pipeline_run row exists (idempotent) and claim its pid.
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command="scrape-resolve",
        options_json=options_json,
        if_absent=True,
    )
    writer.update_pid(run_uid, os.getpid())

    # 7. Stream buffers + SIGTERM handler.  The child is stored in a mutable
    #    holder so the handler (installed before the spawn) can reach it.
    ring = _RingBuffer()
    child: dict[str, subprocess.Popen[str]] = {}

    def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Terminate the child group, finalize ``'killed'``."""
        proc_ref = child.get("proc")
        if proc_ref is not None:
            _kill_child_group(proc_ref)
        writer.finalize(run_uid, OUTCOME_KILLED, output_tail=ring.to_str())
        log.warning(
            "decision_runner_killed",
            run_uid=run_uid,
            decision_id=decision_id,
        )
        # os._exit bypasses the try/finally below so the 'killed' outcome is not
        # overwritten by an 'error' finalize.
        os._exit(_SIGTERM_EXIT_CODE)

    signal.signal(signal.SIGTERM, _on_sigterm)

    try:
        # 8. Spawn subprocess.
        log.info(
            "decision_runner_starting",
            run_uid=run_uid,
            decision_id=decision_id,
            staging_path=staging_path,
            provider=provider,
            provider_id=provider_id,
            argv=argv,
        )

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
            # OSError → exec failure; ValueError → embedded null byte in an arg.
            log.error(
                "decision_runner_spawn_failed",
                run_uid=run_uid,
                decision_id=decision_id,
                error=str(exc),
            )
            writer.finalize(run_uid, OUTCOME_ERROR, error=str(exc))
            sys.exit(2)

        child["proc"] = proc

        # 9. Stream output — ring buffer + Redis.  Any failure here finalizes
        #    the row 'error' so it is never left 'running'.
        redis = _get_redis(web_config)
        stream_key = web_config.stream_key
        stream_maxlen = web_config.stream_maxlen
        seq = 0

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                ring.append(line)
                _redis_publish_line(redis, line, run_uid, seq, stream_key, stream_maxlen)
                seq += 1
            rc = proc.wait()
        except Exception as exc:
            _kill_child_group(proc)
            output_tail = ring.to_str()
            writer.finalize(
                run_uid,
                OUTCOME_ERROR,
                error=str(exc) or type(exc).__name__,
                output_tail=output_tail,
            )
            log.error(
                "decision_runner_stream_failed",
                run_uid=run_uid,
                decision_id=decision_id,
                exc_info=True,
            )
            sys.exit(1)

        # 10. Finalize.
        output_tail = ring.to_str()
        if rc == 0:
            writer.finalize(run_uid, OUTCOME_SUCCESS, output_tail=output_tail)
            log.info(
                "decision_runner_completed",
                run_uid=run_uid,
                decision_id=decision_id,
                rc=rc,
                lines=seq,
            )
        else:
            # On failure, capture the last portion of output as the error context.
            error_tail = output_tail[-2000:] if len(output_tail) > 2000 else output_tail
            writer.finalize(run_uid, OUTCOME_ERROR, error=error_tail, output_tail=output_tail)
            log.error(
                "decision_runner_failed",
                run_uid=run_uid,
                decision_id=decision_id,
                rc=rc,
                lines=seq,
            )

        sys.exit(rc)
    finally:
        # No lock to release here — the scrape-resolve CLI owns the scoped
        # per-item scrape lock for its own lifetime (R11); this runner never
        # acquires a lock on its behalf.
        pass


if __name__ == "__main__":
    main()
