"""Maintenance action runner — subprocess wrapper spawned by the POST handler.

Executable as ``python -m personalscraper.web.maintenance.runner``. Reads its
configuration from environment variables (set by :func:`_spawn_runner` in
``personalscraper.web.routes.maintenance``) and is responsible for:

1. Writing a ``pipeline_run`` row (``kind='maintenance'``).
2. Resolving the action from :data:`REGISTRY` and building the CLI argv.
3. Holding ``pipeline.lock`` for the child's whole lifetime (live
   write/destructive actions whose CLI does not self-acquire — see
   :data:`_CLI_SELF_LOCKING`).
4. Spawning the ``library-*`` CLI command as a subprocess.
5. Streaming each output line to Redis (fail-soft) and a 64 KiB ring buffer.
6. Finalizing the ``pipeline_run`` row on exit.

Environment contract (canonical — match :func:`_spawn_runner`):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_MAINT_COMMAND`` — mandatory, e.g. ``"library-clean"``.
* ``PERSONALSCRAPER_MAINT_OPTIONS_JSON`` — mandatory, canonical options JSON.
* ``PERSONALSCRAPER_MAINT_DRY_RUN`` — mandatory, ``"1"`` or ``"0"``.

Exit codes:

* ``0`` — the CLI subprocess completed successfully.
* ``1`` — the CLI subprocess exited non-zero (error), or ``pipeline.lock``
  could not be acquired (a pipeline run won the race).
* ``2`` — misconfiguration (missing env, unknown action, config load failure,
  DB insert failure).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from collections import deque
from types import FrameType
from typing import Any

from personalscraper.conf.loader import load_config
from personalscraper.lock import acquire_pipeline_lock, release_lock, scrape_locks_dir_for
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.maintenance.registry import REGISTRY, MaintenanceAction

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum bytes retained in the in-memory ring buffer (≈ last 64 KiB of
#: command output stored as ``output_tail`` in ``pipeline_run``).
RING_BUFFER_BYTES = 64 * 1024

#: Outcome string used for CLI exit-code-0 success.
OUTCOME_SUCCESS = "success"

#: Outcome string used for CLI non-zero exit.
OUTCOME_ERROR = "error"

#: Outcome string used when the runner is killed via SIGTERM.
OUTCOME_KILLED = "killed"

#: Exit code used after a SIGTERM-initiated shutdown (128 + SIGTERM).
_SIGTERM_EXIT_CODE = 143

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
# Derived by reading each library-* source file (sub-phase 3.3).  This table
# SHOULD live in the registry alongside ``dry_run`` / ``options`` but registry
# changes are out of scope (noted for the orchestrator).

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
# every other live (non-dry-run) write/destructive action the runner acquires
# the lock itself before spawning the child and releases it on every exit path.

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
        A command-line argument list starting with ``sys.executable``,
        suitable for ``subprocess.Popen``.

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
# Ring buffer
# ---------------------------------------------------------------------------


class _RingBuffer:
    """Append-only character ring buffer with a maximum byte size.

    Stores lines as a ``deque`` of strings and tracks total character count.
    When the total exceeds *max_bytes*, the oldest lines are evicted until
    the buffer is back under the limit.

    Args:
        max_bytes: Maximum total characters to retain.
    """

    def __init__(self, max_bytes: int = RING_BUFFER_BYTES) -> None:
        """Initialize an empty ring buffer.

        Args:
            max_bytes: Maximum total characters to retain (including
                newlines). Defaults to :data:`RING_BUFFER_BYTES`.
        """
        self._max = max_bytes
        self._lines: deque[str] = deque()
        self._size = 0

    def append(self, line: str) -> None:
        """Append *line*; evict oldest lines if the buffer exceeds the cap.

        Args:
            line: A single line of output (trailing newline is the caller's
                responsibility if needed).
        """
        self._lines.append(line)
        self._size += len(line)
        while self._size > self._max and self._lines:
            removed = self._lines.popleft()
            self._size -= len(removed)

    def to_str(self) -> str:
        """Return the full buffer contents as a single string.

        Returns:
            The concatenated buffer lines, or an empty string when the
            buffer is empty.
        """
        return "".join(self._lines)


# ---------------------------------------------------------------------------
# Redis publish (fail-soft)
# ---------------------------------------------------------------------------


def _redis_publish_line(
    redis: Any,
    line: str,
    run_uid: str,
    seq: int,
    stream_key: str,
    stream_maxlen: int,
) -> None:
    """Publish a single output line to Redis as a ``maintenance.run_log`` event.

    The envelope shape matches :func:`event_to_envelope` (``{"_type", "data"}``)
    so the WebSocket relay in ``personalscraper.web.ws.relay`` forwards it
    verbatim without requiring an :class:`Event` subclass in the catalog.
    The ``_type`` is ``"maintenance.run_log"`` and the ``data`` payload
    carries ``{run_uid, line, seq}``.

    Any Redis exception is caught and logged once (fail-soft — Redis
    unavailability must never kill the subprocess).

    Args:
        redis: A ``redis.Redis`` connection (or ``None`` when Redis is
            disabled / unreachable at boot).
        line: The output line to publish.
        run_uid: The maintenance run identifier.
        seq: Monotonic line sequence number (0-based).
        stream_key: The Redis Stream key.
        stream_maxlen: Maximum stream length for ``XADD``.
    """
    if redis is None:
        return
    envelope = {
        "_type": "maintenance.run_log",
        "data": {"run_uid": run_uid, "line": line, "seq": seq},
    }
    try:
        redis.xadd(
            stream_key,
            {"envelope": json.dumps(envelope), "type": "maintenance.run_log"},
            maxlen=stream_maxlen,
            approximate=True,
        )
    except Exception:
        # fail-soft — log once, suppress subsequent failures.
        if not getattr(_redis_publish_line, "_warned", False):
            log.warning(
                "maintenance_runner_redis_publish_failed",
                run_uid=run_uid,
                seq=seq,
                exc_info=True,
            )
            _redis_publish_line._warned = True  # type: ignore[attr-defined]


def _get_redis(web_config: Any) -> Any | None:
    """Create a lazily-connected sync Redis client, or ``None`` on failure.

    Args:
        web_config: The ``WebConfig`` model from the loaded application config.

    Returns:
        A ``redis.Redis`` instance, or ``None`` when ``web.enabled`` is
        ``False`` or the connection setup fails.
    """
    if not web_config.enabled:
        return None
    try:
        import redis as _redis

        return _redis.Redis.from_url(
            web_config.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    except Exception:
        log.warning(
            "maintenance_runner_redis_init_failed",
            redis_url=web_config.redis_url,
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Child process termination
# ---------------------------------------------------------------------------


def _kill_child_group(proc: subprocess.Popen[str]) -> None:
    """Best-effort terminate the child's whole process group with ``SIGTERM``.

    The CLI child is spawned with ``start_new_session=True`` so it is its own
    process-group leader; killing the group also reaps any grandchildren (e.g.
    a destructive ``--apply`` command that itself spawned helpers). A killed
    runner must never orphan a live destructive child.

    SAFETY: ``pid`` and the resolved ``pgid`` must both be real ints > 1
    before ``killpg`` runs. POSIX leaves ``killpg(pgrp<=1, sig)`` undefined —
    glibc/Linux turns pgrp 1 into ``kill(-1, sig)``, a SIGTERM broadcast to
    every process the user owns. A ``MagicMock`` pid coerces to 1 via
    ``__index__``, so an unguarded call from a test killed the whole GitHub
    Actions runner (CI incident 2026-07-08, PR #230: five consecutive
    "runner has received a shutdown signal" kills at 91-94%).

    Args:
        proc: The child :class:`subprocess.Popen` handle.
    """
    pid = proc.pid
    if type(pid) is not int or pid <= 1:
        # Not a real child pid (mock, sentinel, or corrupt) — never resolve a
        # group from it. Fall back to terminating the handle directly.
        _terminate_quietly(proc)
        return
    try:
        pgid = os.getpgid(pid)
    except Exception:
        # Already-dead child — nothing left to signal beyond the handle.
        _terminate_quietly(proc)
        return
    if pgid <= 1:
        # A pgid of 0/1 must never be signalled: killpg(1) broadcasts on Linux.
        _terminate_quietly(proc)
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except Exception:
        _terminate_quietly(proc)


def _terminate_quietly(proc: subprocess.Popen[str]) -> None:
    """Call ``proc.terminate()`` swallowing every error (best-effort cleanup).

    Args:
        proc: The child :class:`subprocess.Popen` handle.
    """
    try:
        proc.terminate()
    except Exception as exc:
        log.warning("maintenance_runner_terminate_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the maintenance action subprocess.

    This is the single entry point invoked by
    ``python -m personalscraper.web.maintenance.runner``. It reads env vars,
    ensures the ``pipeline_run`` row exists (the POST handler reserves it
    first — see :func:`personalscraper.web.routes.maintenance.action_run`),
    claims it with this process's pid, acquires ``pipeline.lock`` for the
    child's lifetime (live write/destructive actions outside
    :data:`_CLI_SELF_LOCKING` — R11), spawns the CLI subprocess, streams
    output to Redis and a ring buffer, then finalizes the row.

    The insert→stream→finalize region is fully guarded: any exception (config
    failure aside) finalizes the row with an outcome so it is **never** left
    ``'running'`` (Finding A). A ``SIGTERM`` (sent by the web ``kill`` control)
    terminates the child process group and finalizes the row ``'killed'``.

    Exit codes: 0 on CLI success, 1 on CLI error or pipeline-lock loss,
    2 on misconfiguration, 143 on SIGTERM.
    """
    # 1. Read env.
    run_uid, command, options_json, dry_run = _read_mandatory_env()

    # 2. Load config (respects PERSONALSCRAPER_CONFIG env).
    try:
        config = load_config()
    except Exception as exc:
        log.error(
            "maintenance_runner_config_load_failed",
            run_uid=run_uid,
            error=str(exc),
        )
        sys.exit(2)

    db_path = config.indexer.db_path
    if db_path is None:
        log.error(
            "maintenance_runner_no_db_path",
            run_uid=run_uid,
        )
        sys.exit(2)
    web_config = config.web

    # 3. Resolve action.
    action = _resolve_action(command)

    # 4. Build CLI argv.
    argv = _build_argv(action, options_json, dry_run)

    # 5. Ensure the pipeline_run row exists (idempotent) and claim its pid.
    #    The POST handler reserves the row synchronously before spawning us, so
    #    ``if_absent=True`` makes this a no-op in the normal flow while still
    #    creating the row for a direct invocation. ``update_pid`` then claims
    #    the row with this process's pid so a crashed runner leaves a dead-pid
    #    (stale) row rather than a live-pid (blocking) one.
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=dry_run,
        pid=os.getpid(),
        kind="maintenance",
        command=command,
        options_json=options_json,
        if_absent=True,
    )
    writer.update_pid(run_uid, os.getpid())

    # 6. Stream buffers + SIGTERM handler. The child is stored in a mutable
    #    holder so the handler (installed before the spawn) can reach it.
    ring = _RingBuffer()
    child: dict[str, subprocess.Popen[str]] = {}

    # Pipeline-lock ownership (R11): a live (non-dry-run) write/destructive
    # action must hold ``pipeline.lock`` for the child's whole lifetime so a
    # concurrent pipeline run cannot start while the library is being mutated.
    # Commands in :data:`_CLI_SELF_LOCKING` acquire it themselves in the child.
    lock_file = config.paths.data_dir / "pipeline.lock"
    hold_lock = action.risk in ("write", "destructive") and not dry_run and action.id not in _CLI_SELF_LOCKING
    lock_acquired = False

    def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Terminate the child group, release the lock, finalize ``'killed'``."""
        proc_ref = child.get("proc")
        if proc_ref is not None:
            _kill_child_group(proc_ref)
        writer.finalize(run_uid, OUTCOME_KILLED, output_tail=ring.to_str())
        if lock_acquired:
            # os._exit below bypasses the try/finally that normally releases.
            release_lock(lock_file)
        log.warning("maintenance_runner_killed", run_uid=run_uid, command=command)
        # os._exit bypasses the streaming try/except below so the 'killed'
        # outcome is not overwritten by an 'error' finalize.
        os._exit(_SIGTERM_EXIT_CODE)

    signal.signal(signal.SIGTERM, _on_sigterm)

    # 6b. Acquire the pipeline lock (after the SIGTERM handler is installed so
    #     a kill arriving mid-run still releases it). ``acquire_lock`` is the
    #     atomic authority (O_CREAT|O_EXCL) — losing it means a pipeline run
    #     grabbed the lock after the route's probes: finalize 'error', exit 1.
    if hold_lock:
        if not acquire_pipeline_lock(lock_file, scrape_locks_dir_for(config.paths.data_dir)):
            writer.finalize(run_uid, OUTCOME_ERROR, error="Pipeline lock held")
            log.error(
                "maintenance_runner_lock_held",
                run_uid=run_uid,
                command=command,
            )
            sys.exit(1)
        lock_acquired = True

    # Steps 7-9 run under try/finally so every exit path (sys.exit raises
    # SystemExit) releases the pipeline lock. Only os._exit in the SIGTERM
    # handler bypasses this — that handler releases the lock itself.
    try:
        # 7. Spawn subprocess.
        log.info(
            "maintenance_runner_starting",
            run_uid=run_uid,
            command=command,
            dry_run=dry_run,
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
                "maintenance_runner_spawn_failed",
                run_uid=run_uid,
                command=command,
                error=str(exc),
            )
            writer.finalize(run_uid, OUTCOME_ERROR, error=str(exc))
            sys.exit(2)

        child["proc"] = proc

        # 8. Stream output — ring buffer + Redis. Any failure here finalizes the
        #    row 'error' so it is never left 'running'.
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
                "maintenance_runner_stream_failed",
                run_uid=run_uid,
                command=command,
                exc_info=True,
            )
            sys.exit(1)

        # 9. Finalize.
        output_tail = ring.to_str()
        if rc == 0:
            writer.finalize(run_uid, OUTCOME_SUCCESS, output_tail=output_tail)
            log.info(
                "maintenance_runner_completed",
                run_uid=run_uid,
                command=command,
                rc=rc,
                lines=seq,
            )
        else:
            # On failure, capture the last portion of output as the error context.
            error_tail = output_tail[-2000:] if len(output_tail) > 2000 else output_tail
            writer.finalize(run_uid, OUTCOME_ERROR, error=error_tail, output_tail=output_tail)
            log.error(
                "maintenance_runner_failed",
                run_uid=run_uid,
                command=command,
                rc=rc,
                lines=seq,
            )

        sys.exit(rc)
    finally:
        if lock_acquired:
            release_lock(lock_file)


if __name__ == "__main__":
    main()
