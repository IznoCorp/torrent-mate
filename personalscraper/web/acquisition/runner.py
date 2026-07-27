"""Grab runner — thin config over the shared runner engine (OBJ3 / §5).

Executable as ``python -m personalscraper.web.acquisition.runner``. Reads its
configuration from environment variables (set by the POST handler in
``personalscraper.web.routes.acquisition_triggers``) and delegates the whole
run-row / spawn / stream / finalize lifecycle to
:func:`personalscraper.web._runner_engine.run_spawn_stream` — one step for
``grab`` / ``detect``, three chained steps for ``prime`` (the engine's
``extra_steps``). The grab CLI does not touch ``pipeline.lock`` (each wanted
item is claimed atomically via ``claim_for_search``), so this runner uses no
lock, no visible-queue wait, and no exit-3 re-queue — the simplest engine
configuration.

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
* ``2`` — misconfiguration (missing env, config load failure, spawn failure).
* ``143`` — runner killed via SIGTERM.
* ``1`` — the engine's own failure paths (stream error, queue timeout, a step
  killed for overrunning its 30-minute ceiling).
* **anything else** — the failing CLI step's OWN exit code, passed through
  verbatim by the engine (``sys.exit(rc)``). A step exiting ``3`` therefore
  makes this runner exit ``3``, not ``1``: the code identifies WHAT failed, and
  flattening it to ``1`` would erase that. The chain stops at the first non-zero
  step, so the code always belongs to the step named in the run's ``error``.
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

#: Accepted values of ``PERSONALSCRAPER_ACQ_COMMAND``.
_COMMANDS = ("grab", "detect", "prime")

#: Commands whose run is scoped to one follow (``FOLLOWED_ID`` mandatory).
_SCOPED_COMMANDS = ("grab", "prime")

#: ``pipeline_run.command`` written for each runner command.
_ROW_COMMANDS = {"grab": "grab", "detect": "follow-detect", "prime": "prime"}

#: Wall-clock ceiling for ONE acquisition step (30 min). Every step here talks
#: to trackers and providers over the network, so a hung step is not
#: hypothetical: a server that accepts the TCP connection and never answers
#: blocks the streaming loop forever. Without a ceiling that run row stays
#: 'running' with a LIVE pid, so the idempotence guard 409s every retry and the
#: card is pinned on « vérification en cours » with nothing the operator can do
#: from the UI. Generous on purpose — priming a long-running series legitimately
#: takes minutes; this bounds a hang, it does not pace a slow run.
_STEP_TIMEOUT_S = 1800.0


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


def grab_options_json(followed_id: int) -> str:
    """Canonical ``options_json`` of a ``grab`` run row (stable string).

    The ``grab`` counterpart of :func:`prime_options_json`, and for the same
    reason: the trigger route, the idempotence guard and this runner compare
    the scope string BY EXACT EQUALITY, so it must be built in exactly ONE
    place. It was previously re-typed at each site — three literal
    ``json.dumps`` calls that a single divergent separator would have turned
    into a silent « the guard never matches » bug.

    Note the byte format deliberately differs from the ``prime`` one (compact
    separators + sorted keys, versus the default spacing): the two are distinct
    scopes on purpose — a running grab must never refuse a prime, nor the
    reverse — and the already-deployed rows carry these exact bytes.

    Args:
        followed_id: The followed series the grab run is scoped to.

    Returns:
        ``'{"followed_id":N}'`` — the canonical grab scope string.
    """
    return json.dumps({"followed_id": followed_id}, sort_keys=True, separators=(",", ":"))


def parse_prime_options(options_json: str | None) -> int | None:
    """Extract ``followed_id`` from a prime run's ``options_json``, or ``None``.

    The inverse of :func:`prime_options_json` — same module, same shape, so a
    reader can never interpret a row differently from how the writer built it.

    Args:
        options_json: The raw ``options_json`` column value (may be ``None``
            for runs that predate the column).

    Returns:
        The ``followed_id`` integer, or ``None`` when the value is absent,
        unparseable, or missing the key.
    """
    if options_json is None:
        return None
    try:
        data = json.loads(options_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    fid = data.get("followed_id")
    return fid if isinstance(fid, int) else None


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


def _options_json(command: str, followed_id: int | None) -> str:
    """Canonical ``options_json`` for the run row of *command*.

    Args:
        command: The runner command (``"grab"``, ``"detect"`` or ``"prime"``).
        followed_id: The scoped follow, when the command has one.

    Returns:
        The JSON scope string the spawner wrote for the same run, so the
        ``if_absent`` insert below can never produce a divergent duplicate.
        Both formats come from their single construction site
        (:func:`prime_options_json` / :func:`grab_options_json`) — never
        re-typed here.
    """
    if followed_id is None:
        return "{}"
    if command == "prime":
        return prime_options_json(followed_id)
    return grab_options_json(followed_id)


def main() -> None:
    """Run the acquisition CLI step sequence (see module docstring).

    Reserves/claims the ``pipeline_run`` row, spawns each step in order
    (``grab`` / ``detect``: one step; ``prime``: detect → search → grab),
    streams every output line into the SAME ring buffer, stops at the first
    non-zero exit code, and finalizes the row on every exit path — so a manual
    trigger is tracked exactly like a maintenance run and never leaves a stuck
    ``'running'`` row. The whole lifecycle is owned by the shared engine; this
    module only supplies the env parsing, the step argvs, and the
    process-global SIGTERM handler.
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
            argv=steps[0],
            extra_steps=steps[1:],
            child=child,
            ring=ring,
            redis=_get_redis(web_config),
            stream_key=web_config.stream_key,
            stream_maxlen=web_config.stream_maxlen,
            event_prefix="grab_runner",
            log_context={"command": command, "followed_id": followed_id},
            step_timeout_s=_STEP_TIMEOUT_S,
        )
    )


if __name__ == "__main__":
    main()
