"""Grab runner — thin config over the shared runner engine (OBJ3 / §5).

Executable as ``python -m personalscraper.web.acquisition.runner``. Reads its
configuration from environment variables (set by the POST handler in
``personalscraper.web.routes.acquisition_triggers``) and delegates the whole
run-row / spawn / stream / finalize lifecycle to
:func:`personalscraper.web._runner_engine.run_spawn_stream`. The grab CLI does
not touch ``pipeline.lock`` (each wanted item is claimed atomically via
``claim_for_search``), so this runner uses no lock, no visible-queue wait, and no
exit-3 re-queue — the simplest engine configuration.

Environment contract (canonical — match the spawner):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_ACQ_COMMAND`` — optional: ``"grab"`` (default) or ``"detect"``
  (§5 manual aired-episode discovery — spawns ``follow detect``).
* ``PERSONALSCRAPER_GRAB_FOLLOWED_ID`` — mandatory for ``grab``; unused for
  ``detect``.

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
from personalscraper.web._runner_engine import (
    OUTCOME_KILLED,
    SIGTERM_EXIT_CODE,
    RunnerSpec,
    run_spawn_stream,
)
from personalscraper.web._runner_engine import (
    RingBuffer as _RingBuffer,
)
from personalscraper.web._runner_engine import (
    get_redis as _get_redis,
)
from personalscraper.web._runner_engine import (
    kill_child_group as _kill_child_group,
)
from personalscraper.web._runner_engine import (
    redis_publish_line as _redis_publish_line,  # noqa: F401 — re-export for test/seam parity
)

log = get_logger(__name__)


def _read_mandatory_env() -> tuple[str, str, int | None]:
    """Read the runner env vars; exit 2 on missing/invalid.

    Returns:
        A ``(run_uid, command, followed_id)`` tuple — ``command`` is ``"grab"``
        or ``"detect"``; ``followed_id`` is ``None`` for ``detect``.

    Raises:
        SystemExit: 2 when a required var is missing/invalid.
    """
    run_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")
    command = os.environ.get("PERSONALSCRAPER_ACQ_COMMAND", "grab")
    if not run_uid or command not in ("grab", "detect"):
        log.error(
            "grab_runner_missing_env",
            hint="The spawner MUST set PERSONALSCRAPER_RUN_UID (+ a valid PERSONALSCRAPER_ACQ_COMMAND)",
        )
        sys.exit(2)
    if command == "detect":
        return run_uid, command, None
    raw_followed = os.environ.get("PERSONALSCRAPER_GRAB_FOLLOWED_ID")
    if not raw_followed:
        log.error(
            "grab_runner_missing_env",
            hint="The spawner MUST set PERSONALSCRAPER_GRAB_FOLLOWED_ID for a grab run",
        )
        sys.exit(2)
    try:
        followed_id = int(raw_followed)
    except ValueError:
        log.error("grab_runner_bad_followed_id", value=raw_followed)
        sys.exit(2)
    return run_uid, command, followed_id


def _build_argv(command: str, followed_id: int | None) -> list[str]:
    """Build the acquisition CLI argument list.

    Args:
        command: ``"grab"`` (per-series manual grab) or ``"detect"`` (§5 manual
            aired-episode discovery over every active follow).
        followed_id: The followed series to scope a grab to (``None`` for detect).

    Returns:
        A command-line argument list starting with ``sys.executable``.
    """
    if command == "detect":
        return [sys.executable, "-m", "personalscraper", "follow", "detect"]
    return [sys.executable, "-m", "personalscraper", "grab", "--followed-id", str(followed_id)]


def main() -> None:
    """Run the per-series grab / detect subprocess (see module docstring).

    Reserves/claims the ``pipeline_run`` row, spawns the acquisition CLI, streams
    its output, and finalizes the row on every exit path — so a manual trigger is
    tracked exactly like a maintenance run and never leaves a stuck ``'running'``
    row. The whole lifecycle is owned by the shared engine; this module only
    supplies the env parsing, argv, and the process-global SIGTERM handler.
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

    row_command = "follow-detect" if command == "detect" else "grab"
    options = {} if followed_id is None else {"followed_id": followed_id}
    options_json = json.dumps(options, sort_keys=True, separators=(",", ":"))
    argv = _build_argv(command, followed_id)

    writer = PipelineRunWriter(db_path)
    ring = _RingBuffer()
    child: dict[str, subprocess.Popen[str]] = {}

    def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Terminate the child group, finalize ``'killed'``."""
        proc_ref = child.get("proc")
        if proc_ref is not None:
            _kill_child_group(proc_ref)
        writer.finalize(run_uid, OUTCOME_KILLED, output_tail=ring.to_str())
        log.warning("grab_runner_killed", run_uid=run_uid, followed_id=followed_id)
        os._exit(SIGTERM_EXIT_CODE)

    signal.signal(signal.SIGTERM, _on_sigterm)

    run_spawn_stream(
        RunnerSpec(
            writer=writer,
            run_uid=run_uid,
            kind="maintenance",
            command=row_command,
            options_json=options_json,
            dry_run=False,
            argv=argv,
            child=child,
            ring=ring,
            redis=_get_redis(web_config),
            stream_key=web_config.stream_key,
            stream_maxlen=web_config.stream_maxlen,
            event_prefix="grab_runner",
            log_context={"followed_id": followed_id},
        )
    )


if __name__ == "__main__":
    main()
