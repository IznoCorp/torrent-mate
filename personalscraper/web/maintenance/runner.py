"""Maintenance action runner — subprocess wrapper spawned by the POST handler.

Executable as ``python -m personalscraper.web.maintenance.runner``. Reads its
configuration from environment variables (set by :func:`_spawn_runner` in
``personalscraper.web.routes.maintenance``) and is responsible for:

1. Writing a ``pipeline_run`` row (``kind='maintenance'``).
2. Resolving the action from :data:`REGISTRY` and building the CLI argv.
3. Spawning the ``library-*`` CLI command as a subprocess.
4. Streaming each output line to Redis (fail-soft) and a 64 KiB ring buffer.
5. Finalizing the ``pipeline_run`` row on exit.

Environment contract (canonical — match :func:`_spawn_runner`):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_MAINT_COMMAND`` — mandatory, e.g. ``"library-clean"``.
* ``PERSONALSCRAPER_MAINT_OPTIONS_JSON`` — mandatory, canonical options JSON.
* ``PERSONALSCRAPER_MAINT_DRY_RUN`` — mandatory, ``"1"`` or ``"0"``.

Exit codes:

* ``0`` — the CLI subprocess completed successfully.
* ``1`` — the CLI subprocess exited non-zero (error)
* ``2`` — misconfiguration (missing env, unknown action, config load failure,
  DB insert failure).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import deque
from typing import Any

from personalscraper.conf.loader import load_config
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

    # Positional (required) options first — registry convention: required ⇒
    # positional argument (no --flag prefix).
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
        argv.append(str(value))

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
            argv.append("--apply")

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
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the maintenance action subprocess.

    This is the single entry point invoked by
    ``python -m personalscraper.web.maintenance.runner``. It reads env vars,
    writes the ``pipeline_run`` row, spawns the CLI subprocess, streams
    output to Redis and a ring buffer, then finalizes the row.

    Exit codes: 0 on CLI success, 1 on CLI error, 2 on misconfiguration.
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

    # 5. Insert pipeline_run row.
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=dry_run,
        pid=os.getpid(),
        kind="maintenance",
        command=command,
        options_json=options_json,
    )

    # 6. Spawn subprocess.
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
            bufsize=1,
        )
    except OSError as exc:
        log.error(
            "maintenance_runner_spawn_failed",
            run_uid=run_uid,
            command=command,
            error=str(exc),
        )
        writer.finalize(run_uid, OUTCOME_ERROR, error=str(exc))
        sys.exit(2)

    # 7. Stream output — ring buffer + Redis.
    ring = _RingBuffer()
    redis = _get_redis(web_config)
    stream_key = web_config.stream_key
    stream_maxlen = web_config.stream_maxlen
    seq = 0

    assert proc.stdout is not None
    for line in proc.stdout:
        ring.append(line)
        _redis_publish_line(redis, line, run_uid, seq, stream_key, stream_maxlen)
        seq += 1

    rc = proc.wait()

    # 8. Finalize.
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


if __name__ == "__main__":
    main()
