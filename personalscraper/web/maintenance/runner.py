"""Maintenance action runner — thin config over the shared runner engine.

Executable as ``python -m personalscraper.web.maintenance.runner``. Reads its
configuration from environment variables (set by :func:`_spawn_runner` in
``personalscraper.web.routes.maintenance``), resolves the action from
:data:`REGISTRY`, builds the CLI argv, decides the ``pipeline.lock`` policy, then
delegates the run-row / spawn / stream / requeue / finalize lifecycle to
:func:`personalscraper.web._runner_engine.run_spawn_stream`.

Pipeline-lock ownership (R11): write/destructive actions hold ``pipeline.lock``
for their whole subprocess lifetime — acquired by the engine (``hold_lock``) for
actions whose CLI does not self-acquire, or probed each iteration
(``probe_lock_each_iter``) for the three self-locking CLIs. A held lock is never a
refusal (§6): the engine waits in the shared VISIBLE queue.

Environment contract (canonical — match :func:`_spawn_runner`):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_MAINT_COMMAND`` — mandatory, e.g. ``"library-clean"``.
* ``PERSONALSCRAPER_MAINT_OPTIONS_JSON`` — mandatory, canonical options JSON.
* ``PERSONALSCRAPER_MAINT_DRY_RUN`` — mandatory, ``"1"`` or ``"0"``.

Exit codes:

* ``0`` — the CLI subprocess completed successfully.
* ``1`` — the CLI subprocess exited non-zero (error), or the queue deadline
  passed while waiting for ``pipeline.lock``.
* ``2`` — misconfiguration (missing env, unknown action, config load failure,
  DB insert failure).
* ``143`` — runner killed via SIGTERM.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from types import FrameType
from typing import Any

from personalscraper.conf.loader import load_config
from personalscraper.lock import acquire_pipeline_lock, is_lock_held, release_lock, scrape_locks_dir_for
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web._runner_engine import (
    OUTCOME_KILLED,
    RING_BUFFER_BYTES,
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
from personalscraper.web._runner_engine import (
    terminate_quietly as _terminate_quietly,  # noqa: F401 — re-export for test/seam parity
)
from personalscraper.web.maintenance.registry import REGISTRY, MaintenanceAction

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Outcome string used for CLI exit-code-0 success.
OUTCOME_SUCCESS = "success"

#: Outcome string used for CLI non-zero exit.
OUTCOME_ERROR = "error"

# ``RING_BUFFER_BYTES``, ``OUTCOME_KILLED`` and ``SIGTERM_EXIT_CODE`` are imported
# from the engine and kept in the module namespace for backwards-compatible seams.
_SIGTERM_EXIT_CODE = SIGTERM_EXIT_CODE
_RING_BUFFER_BYTES = RING_BUFFER_BYTES

# ---------------------------------------------------------------------------
# Dry-run style table
# ---------------------------------------------------------------------------
# Each maintenance action uses one of two CLI conventions for dry-run:
#
#   "flag"  — the CLI has a ``--dry-run`` flag (default ``False``).
#             DRY_RUN=1 → append ``--dry-run``.
#             DRY_RUN=0 → nothing (already the default).
#
#   "apply" — the CLI has an ``--apply`` flag; the **absence** of ``--apply``
#             means dry-run (safe default).
#             DRY_RUN=1 → nothing (default is dry-run).
#             DRY_RUN=0 → append ``--apply``.
#
# Derived by reading each library-* source file (sub-phase 3.3).

_DRY_RUN_STYLE: dict[str, str] = {
    # ── "flag" commands (--dry-run) ──────────────────────────────────────
    "library-index": "flag",
    "library-scan": "flag",
    "library-backfill-ids": "flag",
    "library-init-canonical": "flag",
    "library-repair": "flag",
    "library-reconcile": "flag",
    "library-gc": "flag",
    "library-rescrape": "flag",
    "library-refresh-path": "flag",
    # ── "apply" commands (--apply, absent=dr) ─────────────────────────────
    "library-clean": "apply",
    "library-validate": "apply",
    "library-fix-nfo": "apply",
    "library-fix-orphan-files": "apply",
    "library-fix-season-counts": "apply",
    "library-dedup-titles": "apply",
    "library-fix-canonical-provider": "apply",
    "library-relink": "apply",
}

# ---------------------------------------------------------------------------
# Pipeline-lock ownership table (R11)
# ---------------------------------------------------------------------------
# DESIGN (maint-dash §4): write/destructive actions hold ``pipeline.lock`` for
# their whole subprocess lifetime — acquired by the CLI command itself where it
# already does, by the runner otherwise. Ground truth (read from each CLI
# source): exactly three commands self-acquire, and only in their live (apply)
# mode:
#
#   library-clean     — acquires when ``--apply``          (library/maintenance.py)
#   library-validate  — acquires when ``--fix --apply``    (library/maintenance.py)
#   library-rescrape  — acquires when NOT ``--dry-run``    (library/analyze.py)
#
# The runner must NOT acquire for these: the child's own ``acquire_lock`` would
# observe the runner's live pid and exit 1 ("Another instance is running"). For
# every other live (non-dry-run) write/destructive action the engine acquires the
# lock before spawning the child and releases it on every exit path.

_CLI_SELF_LOCKING: frozenset[str] = frozenset(
    {
        "library-clean",
        "library-validate",
        "library-rescrape",
        "scrape-resolve",
    }
)

# ---------------------------------------------------------------------------
# Env reading
# ---------------------------------------------------------------------------


def _read_mandatory_env() -> tuple[str, str, str, bool]:
    """Read the four mandatory runner env vars; exit 2 on missing.

    Returns:
        A ``(run_uid, command, options_json, dry_run)`` tuple.
    """
    missing: list[str] = []
    for var in (
        "PERSONALSCRAPER_RUN_UID",
        "PERSONALSCRAPER_MAINT_COMMAND",
        "PERSONALSCRAPER_MAINT_OPTIONS_JSON",
        "PERSONALSCRAPER_MAINT_DRY_RUN",
    ):
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        log.error(
            "maintenance_runner_missing_env",
            missing=missing,
            hint="The spawner MUST set all four PERSONALSCRAPER_MAINT_* vars",
        )
        sys.exit(2)

    run_uid = os.environ["PERSONALSCRAPER_RUN_UID"]
    command = os.environ["PERSONALSCRAPER_MAINT_COMMAND"]
    options_json = os.environ["PERSONALSCRAPER_MAINT_OPTIONS_JSON"]
    dry_run = os.environ["PERSONALSCRAPER_MAINT_DRY_RUN"] == "1"

    return run_uid, command, options_json, dry_run


# ---------------------------------------------------------------------------
# Action resolution
# ---------------------------------------------------------------------------


def _resolve_action(command: str) -> MaintenanceAction:
    """Look up *command* in :data:`REGISTRY`.

    Args:
        command: The CLI command id (e.g. ``"library-clean"``).

    Returns:
        The matching :class:`MaintenanceAction`.

    Raises:
        SystemExit: 2 when *command* is not in the registry.
    """
    registry_index = {a.id: a for a in REGISTRY}
    action = registry_index.get(command)
    if action is None:
        log.error(
            "maintenance_runner_unknown_action",
            command=command,
            known=sorted(registry_index.keys()),
        )
        sys.exit(2)
    return action


# ---------------------------------------------------------------------------
# CLI argv building
# ---------------------------------------------------------------------------


def _build_argv(
    action: MaintenanceAction,
    options_json: str,
    dry_run: bool,
) -> list[str]:
    """Build the ``library-*`` CLI argument list from validated options.

    Args:
        action: The resolved maintenance action from the registry.
        options_json: Canonical JSON string of validated options.
        dry_run: ``True`` when ``PERSONALSCRAPER_MAINT_DRY_RUN`` is ``"1"``.

    Returns:
        A command-line argument list starting with ``sys.executable``, suitable
        for ``subprocess.Popen``.

    Raises:
        SystemExit: 2 when *options_json* is not valid JSON.
    """
    try:
        options: dict[str, Any] = json.loads(options_json)
    except json.JSONDecodeError as exc:
        log.error(
            "maintenance_runner_bad_options_json",
            options_json=options_json,
            error=str(exc),
        )
        sys.exit(2)

    argv: list[str] = [sys.executable, "-m", "personalscraper", action.id]

    # Collect positional (required) values — registry convention: required ⇒
    # positional argument (no --flag prefix). They are appended LAST, after a
    # ``--`` separator (Finding H), so a value that starts with ``-`` can never
    # be reparsed as a flag by click.
    positionals: list[str] = []
    for opt in action.options:
        if not opt.required:
            continue
        value = options.get(opt.name)
        if value is None:
            log.error(
                "maintenance_runner_missing_required_option",
                command=action.id,
                option=opt.name,
            )
            sys.exit(2)
        positionals.append(str(value))

    # Optional flags.
    for opt in action.options:
        if opt.required:
            continue
        if opt.name not in options:
            continue
        value = options[opt.name]
        if opt.type == "bool":
            if value is True:
                argv.append(f"--{opt.name}")
            # bool False → omit
        else:
            # str / int / enum
            argv.extend([f"--{opt.name}", str(value)])

    # ── Dry-run flag ─────────────────────────────────────────────────────
    if action.dry_run == "supported":
        style = _DRY_RUN_STYLE.get(action.id, "flag")
        if style == "flag" and dry_run:
            argv.append("--dry-run")
        elif style == "apply" and not dry_run:
            # library-validate enforces ``--apply requires --fix`` (Finding B):
            # an apply run must emit BOTH flags, otherwise the CLI exits 1. The
            # bare (dry-run) invocation stays the validation report.
            if action.id == "library-validate":
                argv.append("--fix")
            argv.append("--apply")

    # ── Positional separator (Finding H) ─────────────────────────────────
    if positionals:
        argv.append("--")
        argv.extend(positionals)

    return argv


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the maintenance action subprocess (see module docstring).

    Reads env, resolves the action, builds the CLI argv, decides the R11 lock
    policy, installs the process-global SIGTERM handler (which kills the child
    group, finalizes ``'killed'`` and releases a held lock), then hands the whole
    spawn / stream / requeue / finalize lifecycle to the shared engine.
    """
    run_uid, command, options_json, dry_run = _read_mandatory_env()

    try:
        config = load_config()
    except Exception as exc:
        log.error("maintenance_runner_config_load_failed", run_uid=run_uid, error=str(exc))
        sys.exit(2)

    db_path = config.indexer.db_path
    if db_path is None:
        log.error("maintenance_runner_no_db_path", run_uid=run_uid)
        sys.exit(2)
    web_config = config.web

    action = _resolve_action(command)
    argv = _build_argv(action, options_json, dry_run)

    writer = PipelineRunWriter(db_path)
    ring = _RingBuffer()
    child: dict[str, subprocess.Popen[str]] = {}

    # Pipeline-lock ownership (R11). A live (non-dry-run) write/destructive action
    # holds the lock for the child's whole lifetime; commands in
    # :data:`_CLI_SELF_LOCKING` acquire it themselves in the child, so the runner
    # only PROBES (visibility + pacing) and re-queues on the child's exit-3.
    lock_file = config.paths.data_dir / "pipeline.lock"
    live_write = action.risk in ("write", "destructive") and not dry_run
    hold_lock = live_write and action.id not in _CLI_SELF_LOCKING
    child_self_locks = live_write and action.id in _CLI_SELF_LOCKING
    lock_state = {"acquired": False}

    def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Terminate the child group, release a held lock, finalize ``'killed'``."""
        proc_ref = child.get("proc")
        if proc_ref is not None:
            _kill_child_group(proc_ref)
        writer.finalize(run_uid, OUTCOME_KILLED, output_tail=ring.to_str())
        if lock_state["acquired"]:
            # os._exit below bypasses the engine's finally that normally releases.
            release_lock(lock_file)
        log.warning("maintenance_runner_killed", run_uid=run_uid, command=command)
        os._exit(_SIGTERM_EXIT_CODE)

    signal.signal(signal.SIGTERM, _on_sigterm)

    queue_timeout_s = float(os.environ.get("PERSONALSCRAPER_MAINT_QUEUE_TIMEOUT", "1800"))

    run_spawn_stream(
        RunnerSpec(
            writer=writer,
            run_uid=run_uid,
            kind="maintenance",
            command=command,
            options_json=options_json,
            dry_run=dry_run,
            argv=argv,
            child=child,
            ring=ring,
            redis=_get_redis(web_config),
            stream_key=web_config.stream_key,
            stream_maxlen=web_config.stream_maxlen,
            event_prefix="maintenance_runner",
            log_context={"command": command},
            hold_lock=hold_lock,
            probe_lock_each_iter=child_self_locks,
            requeue_on_exit3=child_self_locks,
            acquire_fn=acquire_pipeline_lock,
            release_fn=release_lock,
            is_lock_held_fn=is_lock_held,
            lock_file=lock_file,
            scrape_locks_dir=scrape_locks_dir_for(config.paths.data_dir),
            lock_state=lock_state,
            queue_timeout_s=queue_timeout_s,
            queue_timeout_error=(
                "Délai d'attente dépassé : pipeline.lock toujours tenu après "
                f"{int(queue_timeout_s)}s — action abandonnée, relancez-la."
            ),
            requeue_timeout_error=(
                "Délai d'attente dépassé : verrou toujours occupé après "
                f"{int(queue_timeout_s)}s de tentatives — action abandonnée."
            ),
        )
    )


if __name__ == "__main__":
    main()
