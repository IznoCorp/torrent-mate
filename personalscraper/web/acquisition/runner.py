"""Grab runner — subprocess wrapper for the per-series manual trigger (OBJ3).

Executable as ``python -m personalscraper.web.acquisition.runner``. Reads its
configuration from environment variables (set by the POST handler in
``personalscraper.web.routes.acquisition``) and is responsible for:

1. Reserving/claiming a ``pipeline_run`` row (``kind='maintenance'``,
   ``command='grab'``) — the POST handler inserts it first (``if_absent=True``).
2. Spawning the acquisition CLI step(s) as detached subprocesses
   (``start_new_session=True``) — one for ``grab`` / ``detect``, three chained
   for ``prime``.
3. Streaming each output line to a 64 KiB ring buffer + Redis (fail-soft).
4. Finalizing the ``pipeline_run`` row on every exit path (never left
   ``'running'``).

The ``grab`` CLI does NOT acquire the global ``pipeline.lock`` (it runs
independently of a full pipeline run, like the scheduled grab cron), and each
wanted item is claimed atomically (``claim_for_search``) so two grabs for the
same series are idempotent — this runner therefore touches no lock.

The ``prime`` command (acq-states phase 6) is the amorce of a freshly followed
series: ``follow detect --series N`` → ``search --followed-id N`` →
``grab --followed-id N``, chained inside the SAME run row and the SAME ring
buffer, each step announced by a ``--- <step> ---`` separator line and the
chain stopping at the first non-zero exit code (the partial output shows where
it stopped). Every step is scoped to the single follow — priming one series
must never trigger a library-wide pass.

Environment contract (canonical — match the spawner):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_ACQ_COMMAND`` — optional: ``"grab"`` (default),
  ``"detect"`` (§5 manual aired-episode discovery — spawns ``follow detect``)
  or ``"prime"`` (the three-step amorce of one follow).
* ``PERSONALSCRAPER_GRAB_FOLLOWED_ID`` — mandatory for ``grab`` and ``prime``;
  unused for ``detect``.

Exit codes:

* ``0`` — every CLI step completed successfully.
* ``1`` — a CLI step exited non-zero (error).
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

#: Accepted values of ``PERSONALSCRAPER_ACQ_COMMAND``.
_COMMANDS = ("grab", "detect", "prime")

#: Commands whose run is scoped to one follow (``FOLLOWED_ID`` mandatory).
_SCOPED_COMMANDS = ("grab", "prime")

#: ``pipeline_run.command`` written for each runner command.
_ROW_COMMANDS = {"grab": "grab", "detect": "follow-detect", "prime": "prime"}


def prime_options_json(followed_id: int) -> str:
    """Canonical ``options_json`` of a ``prime`` run row (stable string).

    The spawner (``create_follow``), the idempotence guard and this runner all
    build the scope string HERE so a reader can never miss a row a writer
    produced — an exact-string comparison is what the guard runs.

    Args:
        followed_id: The followed series the priming run is scoped to.

    Returns:
        ``'{"followed_id": N}'`` — the canonical prime scope string.
    """
    return json.dumps({"followed_id": followed_id})


def _read_mandatory_env() -> tuple[str, str, int | None]:
    """Read the runner env vars; exit 2 on missing/invalid.

    Returns:
        A ``(run_uid, command, followed_id)`` tuple — ``command`` is ``"grab"``,
        ``"detect"`` or ``"prime"``; ``followed_id`` is ``None`` for ``detect``
        and mandatory for the follow-scoped commands.

    Raises:
        SystemExit: 2 when a required var is missing/invalid.
    """
    run_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")
    command = os.environ.get("PERSONALSCRAPER_ACQ_COMMAND", "grab")
    if not run_uid or command not in _COMMANDS:
        log.error(
            "grab_runner_missing_env",
            hint="The spawner MUST set PERSONALSCRAPER_RUN_UID (+ a valid PERSONALSCRAPER_ACQ_COMMAND)",
        )
        sys.exit(2)
    if command not in _SCOPED_COMMANDS:
        return run_uid, command, None
    raw_followed = os.environ.get("PERSONALSCRAPER_GRAB_FOLLOWED_ID")
    if not raw_followed:
        log.error(
            "grab_runner_missing_env",
            command=command,
            hint="The spawner MUST set PERSONALSCRAPER_GRAB_FOLLOWED_ID for a grab/prime run",
        )
        sys.exit(2)
    try:
        followed_id = int(raw_followed)
    except ValueError:
        log.error("grab_runner_bad_followed_id", value=raw_followed)
        sys.exit(2)
    return run_uid, command, followed_id


def _build_argv(command: str, followed_id: int | None) -> list[list[str]]:
    """Build the acquisition CLI step sequence.

    Args:
        command: ``"grab"`` (per-series manual grab), ``"detect"`` (§5 manual
            aired-episode discovery over every active follow) or ``"prime"``
            (the three-step amorce of ONE follow).
        followed_id: The followed series to scope the run to (``None`` for
            detect).

    Returns:
        The steps to run in order, each a command-line argument list starting
        with ``sys.executable``. ``grab`` / ``detect`` yield a single step;
        ``prime`` yields three (detect → search → grab), all scoped to
        *followed_id* so priming one follow never runs a library-wide pass.
    """
    base = [sys.executable, "-m", "personalscraper"]
    if command == "detect":
        return [[*base, "follow", "detect"]]
    scope = str(followed_id)
    if command == "prime":
        return [
            [*base, "follow", "detect", "--series", scope],
            [*base, "search", "--followed-id", scope],
            [*base, "grab", "--followed-id", scope],
        ]
    return [[*base, "grab", "--followed-id", scope]]


def _step_label(argv: list[str]) -> str:
    """Human-readable label of one step, for the ``--- <step> ---`` separator.

    Args:
        argv: The step's full argument list (``[python, -m, personalscraper, …]``).

    Returns:
        The CLI part of the argv (e.g. ``"follow detect --series 42"``).
    """
    return " ".join(argv[3:]) or " ".join(argv)


def _options_json(command: str, followed_id: int | None) -> str:
    """Canonical ``options_json`` for the run row of *command*.

    Args:
        command: The runner command (``"grab"``, ``"detect"`` or ``"prime"``).
        followed_id: The scoped follow, when the command has one.

    Returns:
        The JSON scope string the spawner wrote for the same run, so the
        ``if_absent`` insert below can never produce a divergent duplicate.
    """
    if followed_id is None:
        return "{}"
    if command == "prime":
        return prime_options_json(followed_id)
    return json.dumps({"followed_id": followed_id}, sort_keys=True, separators=(",", ":"))


def main() -> None:
    """Run the acquisition CLI step sequence (see module docstring).

    Reserves/claims the ``pipeline_run`` row, spawns each step in order
    (``grab`` / ``detect``: one step; ``prime``: detect → search → grab),
    streams every output line into the SAME ring buffer, stops at the first
    non-zero exit code, and finalizes the row on every exit path — so a manual
    trigger is tracked exactly like a maintenance run and never leaves a stuck
    ``'running'`` row.
    """
    run_uid, command, followed_id = _read_mandatory_env()

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

    row_command = _ROW_COMMANDS[command]
    options_json = _options_json(command, followed_id)
    steps = _build_argv(command, followed_id)

    # Ensure the pipeline_run row exists (idempotent) and claim its pid.
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command=row_command,
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

    redis = _get_redis(web_config)
    stream_key = web_config.stream_key
    stream_maxlen = web_config.stream_maxlen
    seq = 0

    def _emit(line: str) -> None:
        """Append one line to the ring buffer and publish it (fail-soft).

        Args:
            line: The output line (newline included).
        """
        nonlocal seq
        ring.append(line)
        _redis_publish_line(redis, line, run_uid, seq, stream_key, stream_maxlen)
        seq += 1

    rc = 0
    for argv in steps:
        # A multi-step run announces each step so a partial output shows
        # exactly where the chain stopped.
        if len(steps) > 1:
            _emit(f"--- {_step_label(argv)} ---\n")

        log.info("grab_runner_starting", run_uid=run_uid, command=command, followed_id=followed_id, argv=argv)

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
            writer.finalize(run_uid, OUTCOME_ERROR, error=str(exc), output_tail=ring.to_str() or None)
            sys.exit(2)

        child["proc"] = proc

        try:
            assert proc.stdout is not None  # noqa: S101 — Popen with stdout=PIPE
            for line in proc.stdout:
                _emit(line)
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

        # Stop the chain at the first failing step — the following steps would
        # run on a state the failed one never produced.
        if rc != 0:
            break

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
