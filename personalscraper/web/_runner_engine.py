"""One reserve / spawn / stream / requeue / finalize engine for detached web runners.

Before this module the four detached web runners (maintenance / decisions /
acquisition / pipeline-queue) each re-implemented the same lifecycle — atomic
run-row reservation, subprocess spawn + output streaming, the §6 visible-queue
wait, exit-3 re-queue, and terminal finalize — with subtle per-runner drift
(WEB-BACKEND-01/02, ACQUIRE-04). This module owns that lifecycle exactly once:

* :func:`reserve_run_row` — the single ``BEGIN IMMEDIATE`` + pid-alive guard +
  ``INSERT`` reservation (lifted from ``web/decisions/reserve.py``); the three
  route-side reservations now pass their own concurrency *guard* into it rather
  than copying the transaction skeleton.
* :func:`run_spawn_stream` — the single spawn → stream-capture → exit-3 re-queue
  → finalize lifecycle, parameterised by :class:`RunnerSpec`. The resolve queue's
  SERIAL semantics (#287) are expressed by the spec, not a second code path.
* The shared subprocess helpers (:class:`RingBuffer`, :func:`get_redis`,
  :func:`redis_publish_line`, :func:`kill_child_group`, :func:`terminate_quietly`)
  that previously lived in ``web/maintenance/runner.py`` and were imported by the
  other runners.

Each runner module stays the home of the pieces that MUST resolve in its own
namespace for the white-box test seams and the process-global ``SIGTERM``
handler: env parsing, config load, CLI argv building, the Redis handle, the ring
buffer instance, and the ``_on_sigterm`` closure (which references the module's
``kill_child_group`` / ``release_lock`` so a killed runner never orphans a live
destructive child). The runner builds a :class:`RunnerSpec` from those pieces and
hands it to :func:`run_spawn_stream`; the engine owns everything else.

Pipeline-lock tenure (R11): a live write/destructive maintenance run holds
``pipeline.lock`` for the child's whole lifetime — acquired by the engine before
the spawn (``hold_lock``) and released on every exit path, or probed each
iteration when the CLI self-locks (``probe_lock_each_iter``). A held lock is
never a refusal (§6): the engine waits in the shared VISIBLE queue
(:func:`personalscraper.web.run_queue.wait_in_visible_queue`) until its claim
succeeds or the deadline passes.
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
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

from fastapi import HTTPException

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.run_queue import wait_in_visible_queue

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

#: Maximum bytes retained in the in-memory ring buffer (≈ last 64 KiB of command
#: output stored as ``output_tail`` in ``pipeline_run``).
RING_BUFFER_BYTES = 64 * 1024

#: Outcome string used for CLI exit-code-0 success.
OUTCOME_SUCCESS = "success"

#: Outcome string used for CLI non-zero exit.
OUTCOME_ERROR = "error"

#: Outcome string used when the runner is killed via SIGTERM.
OUTCOME_KILLED = "killed"

#: Exit code used after a SIGTERM-initiated shutdown (128 + SIGTERM).
SIGTERM_EXIT_CODE = 143


# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------


class RingBuffer:
    """Append-only character ring buffer with a maximum byte size.

    Stores lines as a ``deque`` of strings and tracks the total character count.
    When the total exceeds *max_bytes*, the oldest lines are evicted until the
    buffer is back under the limit.

    Args:
        max_bytes: Maximum total characters to retain.
    """

    def __init__(self, max_bytes: int = RING_BUFFER_BYTES) -> None:
        """Initialize an empty ring buffer.

        Args:
            max_bytes: Maximum total characters to retain (including newlines).
                Defaults to :data:`RING_BUFFER_BYTES`.
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
            The concatenated buffer lines, or an empty string when the buffer is
            empty.
        """
        return "".join(self._lines)


# ---------------------------------------------------------------------------
# Redis publish (fail-soft)
# ---------------------------------------------------------------------------


def redis_publish_line(
    redis: Any,
    line: str,
    run_uid: str,
    seq: int,
    stream_key: str,
    stream_maxlen: int,
) -> None:
    """Publish a single output line to Redis as a ``maintenance.run_log`` event.

    The envelope shape matches ``event_to_envelope`` (``{"_type", "data"}``) so
    the WebSocket relay in ``personalscraper.web.ws.relay`` forwards it verbatim
    without requiring an :class:`Event` subclass in the catalog. The ``_type`` is
    ``"maintenance.run_log"`` and the ``data`` payload carries
    ``{run_uid, line, seq}`` (byte-identical across all detached runners).

    Any Redis exception is caught and logged once (fail-soft — Redis
    unavailability must never kill the subprocess).

    Args:
        redis: A ``redis.Redis`` connection (or ``None`` when Redis is disabled /
            unreachable at boot).
        line: The output line to publish.
        run_uid: The run identifier.
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
        if not getattr(redis_publish_line, "_warned", False):
            log.warning(
                "runner_redis_publish_failed",
                run_uid=run_uid,
                seq=seq,
                exc_info=True,
            )
            redis_publish_line._warned = True  # type: ignore[attr-defined]


def get_redis(web_config: Any) -> Any | None:
    """Create a lazily-connected sync Redis client, or ``None`` on failure.

    Args:
        web_config: The ``WebConfig`` model from the loaded application config.

    Returns:
        A ``redis.Redis`` instance, or ``None`` when ``web.enabled`` is ``False``
        or the connection setup fails.
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
            "runner_redis_init_failed",
            redis_url=web_config.redis_url,
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Child process termination
# ---------------------------------------------------------------------------


def kill_child_group(proc: subprocess.Popen[str]) -> None:
    """Best-effort terminate the child's whole process group with ``SIGTERM``.

    The CLI child is spawned with ``start_new_session=True`` so it is its own
    process-group leader; killing the group also reaps any grandchildren (e.g. a
    destructive ``--apply`` command that itself spawned helpers). A killed runner
    must never orphan a live destructive child.

    SAFETY: ``pid`` and the resolved ``pgid`` must both be real ints > 1 before
    ``killpg`` runs. POSIX leaves ``killpg(pgrp<=1, sig)`` undefined — glibc/Linux
    turns pgrp 1 into ``kill(-1, sig)``, a SIGTERM broadcast to every process the
    user owns. A ``MagicMock`` pid coerces to 1 via ``__index__``, so an unguarded
    call from a test killed the whole GitHub Actions runner (CI incident
    2026-07-08, PR #230: five consecutive "runner has received a shutdown signal"
    kills at 91-94%).

    Args:
        proc: The child :class:`subprocess.Popen` handle.
    """
    pid = proc.pid
    if type(pid) is not int or pid <= 1:
        # Not a real child pid (mock, sentinel, or corrupt) — never resolve a
        # group from it. Fall back to terminating the handle directly.
        terminate_quietly(proc)
        return
    try:
        pgid = os.getpgid(pid)
    except Exception:
        # Already-dead child — nothing left to signal beyond the handle.
        terminate_quietly(proc)
        return
    if pgid <= 1:
        # A pgid of 0/1 must never be signalled: killpg(1) broadcasts on Linux.
        terminate_quietly(proc)
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except Exception:
        terminate_quietly(proc)


def terminate_quietly(proc: subprocess.Popen[str]) -> None:
    """Call ``proc.terminate()`` swallowing every error (best-effort cleanup).

    Args:
        proc: The child :class:`subprocess.Popen` handle.
    """
    try:
        proc.terminate()
    except Exception as exc:
        log.warning("runner_terminate_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Run-row reservation (the ONE atomic reserve — WEB-BACKEND-02 / ACQUIRE-04)
# ---------------------------------------------------------------------------


def safe_rollback(conn: sqlite3.Connection) -> None:
    """Roll back *conn* best-effort, ignoring "no transaction active" errors.

    Args:
        conn: The connection to roll back.
    """
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


def reserve_run_row(
    db_path: Path,
    *,
    run_uid: str,
    kind: str,
    command: str,
    options_json: str,
    dry_run: bool,
    guard: Callable[[sqlite3.Connection], None] | None = None,
    fail_closed: bool = False,
    fail_closed_detail: str = "",
    missing_db: Callable[[], None] | None = None,
    pid: int | None = None,
) -> None:
    """Atomically run *guard* then reserve a running ``pipeline_run`` row.

    Opens one connection under ``BEGIN IMMEDIATE`` so the caller's concurrency
    *guard* (duplicate-action / per-decision / duplicate-queue) and the
    ``pipeline_run`` INSERT are a single serialised transaction: a second
    concurrent reservation blocks on the write lock, then observes the
    freshly-inserted running row and is rejected by the guard, closing the
    check→insert TOCTOU race. This is the single owner of that skeleton — the
    three route-side reservations pass only their *guard* (WEB-BACKEND-02).

    The row is reserved with *pid* (defaulting to the web process's pid, which is
    guaranteed alive) — the caller updates it to the spawned runner's pid right
    after spawn, matching the R8 pattern.

    Args:
        db_path: Absolute path to ``library.db``.
        run_uid: The unique run identifier reserved by the caller.
        kind: Run kind discriminator (``'maintenance'`` for every detached runner).
        command: The ``command`` column value (e.g. ``'library-clean'``).
        options_json: Canonical options JSON (stored + compared by the guard).
        dry_run: ``True`` for a dry run.
        guard: Optional concurrency guard run inside the transaction; it must
            raise :class:`fastapi.HTTPException` to reject the reservation.
        fail_closed: When ``True`` a DB ``OperationalError`` while verifying
            concurrency raises 409 (*fail_closed_detail*) rather than proceeding
            unreserved — for actions that WRITE and must never run without the
            concurrency check.
        fail_closed_detail: The French 409 detail used when *fail_closed* trips.
        missing_db: Optional callback invoked when the DB file does not exist yet
            (fresh install / test); it may raise (e.g. 428 dry-run-first) or be a
            no-op. When ``None`` a missing DB is a silent no-op.
        pid: The pid to reserve the row with; defaults to ``os.getpid()``.

    Raises:
        HTTPException: Whatever *guard* raises, or 409 (*fail_closed_detail*) when
            *fail_closed* and the DB cannot be read. The transaction is rolled
            back before raising.
    """
    if not db_path.exists():
        if missing_db is not None:
            missing_db()
        return

    reserve_pid = os.getpid() if pid is None else pid
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            if guard is not None:
                guard(conn)
            conn.execute(
                "INSERT INTO pipeline_run "
                "(run_uid, trigger, dry_run, started_at, outcome, steps_json, pid, "
                "kind, command, options_json) "
                "VALUES (?, 'web', ?, ?, 'running', '[]', ?, ?, ?, ?)",
                (run_uid, 1 if dry_run else 0, time.time(), reserve_pid, kind, command, options_json),
            )
            conn.execute("COMMIT")
        except HTTPException:
            safe_rollback(conn)
            raise
        except sqlite3.OperationalError as exc:
            safe_rollback(conn)
            log.warning("runner_reserve_db_error", run_uid=run_uid, command=command, error=str(exc))
            if fail_closed:
                # Fail-CLOSED: the action WRITES and must never proceed without
                # the concurrency check (Finding E) — refuse with the real reason.
                raise HTTPException(status_code=409, detail=fail_closed_detail) from exc
            # Permissive (ro / write): proceed to spawn without a reserved row.
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Spawn / stream / requeue / finalize lifecycle (the ONE lifecycle)
# ---------------------------------------------------------------------------


@dataclass
class RunnerSpec:
    """Everything the engine needs to run one detached runner's lifecycle.

    The runner module builds this from its own (patchable) env / config / argv /
    redis pieces and its shared ``child`` holder + ``ring`` buffer, then hands it
    to :func:`run_spawn_stream`. Concurrency=1 for the SERIAL resolve queue (#287)
    is expressed here — it is a lock/requeue policy, not a second code path.

    Attributes:
        writer: Open :class:`PipelineRunWriter` for the run row.
        run_uid: The run row's unique identifier.
        kind: ``pipeline_run.kind`` (``'maintenance'`` for every detached runner).
        command: ``pipeline_run.command``.
        options_json: Canonical ``pipeline_run.options_json``.
        dry_run: ``pipeline_run.dry_run``.
        argv: The CLI argument vector to spawn.
        child: Mutable holder the SIGTERM handler shares — the engine stores the
            live ``Popen`` under ``child["proc"]``.
        ring: The runner's :class:`RingBuffer` instance (shared with the SIGTERM
            handler so the killed-run tail survives).
        redis: The Redis handle (or ``None``) resolved by the runner.
        stream_key: Redis Stream key.
        stream_maxlen: Redis Stream maxlen for ``XADD``.
        event_prefix: Structlog event prefix, e.g. ``"maintenance_runner"`` —
            events are ``{prefix}_starting`` / ``_completed`` / ``_failed`` / ….
        log_context: Extra structured-log fields (command / decision_id / …).
        hold_lock: Acquire ``pipeline.lock`` once before the spawn and hold it for
            the whole lifetime (live write/destructive action whose CLI does not
            self-acquire — R11).
        probe_lock_each_iter: Wait until ``pipeline.lock`` is free before each
            spawn attempt (the CLI self-acquires; the wait is visibility + pacing,
            the child's claim stays the safety authority).
        requeue_on_exit3: Re-queue (PACED, under the shared deadline) when the
            child exits 3 (lock busy at claim time).
        acquire_fn: ``acquire_pipeline_lock`` bound in the runner namespace.
        release_fn: ``release_lock`` bound in the runner namespace.
        is_lock_held_fn: ``is_lock_held`` bound in the runner namespace.
        lock_file: The ``pipeline.lock`` path.
        scrape_locks_dir: The scrape-locks dir passed to ``acquire_pipeline_lock``.
        lock_state: Mutable ``{"acquired": bool}`` the SIGTERM handler reads to
            release the lock on ``os._exit``.
        queue_timeout_s: Total visible-queue wait; the deadline is shared by the
            pre-spawn wait and the exit-3 re-queue so retries never extend it.
        queue_timeout_error: French finalize message when the pre-spawn wait times
            out.
        requeue_timeout_error: French finalize message when the exit-3 re-queue
            exhausts the deadline.
        on_success: Optional hook run after a ``rc == 0`` finalize (the decisions
            §4 continuation) — called before the engine exits 0.
    """

    writer: PipelineRunWriter
    run_uid: str
    kind: str
    command: str
    options_json: str
    dry_run: bool
    argv: list[str]
    child: dict[str, subprocess.Popen[str]]
    ring: RingBuffer
    redis: Any
    stream_key: str
    stream_maxlen: int
    event_prefix: str
    log_context: dict[str, Any] = field(default_factory=dict)
    hold_lock: bool = False
    probe_lock_each_iter: bool = False
    requeue_on_exit3: bool = False
    acquire_fn: Callable[..., bool] | None = None
    release_fn: Callable[[Path], None] | None = None
    is_lock_held_fn: Callable[[Path], bool] | None = None
    lock_file: Path | None = None
    scrape_locks_dir: Path | None = None
    lock_state: dict[str, bool] = field(default_factory=lambda: {"acquired": False})
    queue_timeout_s: float = 1800.0
    queue_timeout_error: str = ""
    requeue_timeout_error: str = ""
    on_success: Callable[[], None] | None = None


def run_spawn_stream(spec: RunnerSpec) -> NoReturn:
    """Run one detached runner's spawn → stream → requeue → finalize lifecycle.

    Ensures the ``pipeline_run`` row exists (idempotent — the POST handler
    reserves it first) and claims its pid, optionally acquires / probes
    ``pipeline.lock`` in the shared visible queue (§6), spawns the CLI child,
    streams its output to the ring buffer + Redis, re-queues on exit-3 when
    configured, finalizes the row on every exit path (never left ``'running'``),
    and releases a held lock in the ``finally``. Always exits the process — the
    caller does not return from here.

    Args:
        spec: The fully-resolved :class:`RunnerSpec`.

    Raises:
        SystemExit: Always. Code ``0`` on CLI success, the child's non-zero code
            on CLI error, ``1`` on a stream failure / queue timeout / lost-lock,
            ``2`` on a spawn failure.
    """
    writer = spec.writer
    run_uid = spec.run_uid

    # Ensure the row exists (idempotent) and claim its pid so a crashed runner
    # leaves a dead-pid (stale) row rather than a live-pid (blocking) one.
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=spec.dry_run,
        pid=os.getpid(),
        kind=spec.kind,
        command=spec.command,
        options_json=spec.options_json,
        if_absent=True,
    )
    writer.update_pid(run_uid, os.getpid())

    queue_deadline = time.monotonic() + spec.queue_timeout_s

    # Pipeline-lock ownership (R11): acquire once and hold for the child's whole
    # lifetime. A held lock is not a refusal (§6) — wait in the visible queue.
    if spec.hold_lock:
        assert spec.acquire_fn is not None and spec.lock_file is not None
        acquire_fn = spec.acquire_fn
        lock_file = spec.lock_file
        scrape_locks_dir = spec.scrape_locks_dir
        if not wait_in_visible_queue(
            try_proceed=lambda: bool(acquire_fn(lock_file, scrape_locks_dir)),
            writer=writer,
            run_uid=run_uid,
            deadline_monotonic=queue_deadline,
            timeout_s=spec.queue_timeout_s,
            timeout_error=spec.queue_timeout_error,
            log_event_prefix=spec.event_prefix,
            log_context=spec.log_context,
            output_tail=spec.ring.to_str,
        ):
            sys.exit(1)
        spec.lock_state["acquired"] = True

    try:
        seq = 0
        attempt = 0
        rc = 0
        while True:
            # Self-locking CLI: wait VISIBLY while the lock is held instead of
            # letting the child die on a busy lock (§6). The child's
            # claim-first-then-verify acquisition stays the ONLY safety authority.
            if spec.probe_lock_each_iter:
                assert spec.is_lock_held_fn is not None and spec.lock_file is not None
                is_lock_held_fn = spec.is_lock_held_fn
                lock_file = spec.lock_file
                if not wait_in_visible_queue(
                    try_proceed=lambda: not is_lock_held_fn(lock_file),
                    writer=writer,
                    run_uid=run_uid,
                    deadline_monotonic=queue_deadline,
                    timeout_s=spec.queue_timeout_s,
                    timeout_error=spec.queue_timeout_error,
                    log_event_prefix=spec.event_prefix,
                    log_context=spec.log_context,
                    output_tail=spec.ring.to_str,
                ):
                    sys.exit(1)

            attempt += 1
            log.info(
                spec.event_prefix + "_starting",
                run_uid=run_uid,
                argv=spec.argv,
                attempt=attempt,
                **spec.log_context,
            )

            try:
                proc = subprocess.Popen(
                    spec.argv,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    bufsize=1,
                    start_new_session=True,
                )
            except (OSError, ValueError) as exc:
                # OSError → exec failure; ValueError → embedded null byte in an arg.
                log.error(spec.event_prefix + "_spawn_failed", run_uid=run_uid, error=str(exc), **spec.log_context)
                writer.finalize(run_uid, OUTCOME_ERROR, error=str(exc))
                sys.exit(2)

            spec.child["proc"] = proc

            # Stream output — ring buffer + Redis. Any failure finalizes 'error'
            # so the row is never left 'running'.
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    spec.ring.append(line)
                    redis_publish_line(spec.redis, line, run_uid, seq, spec.stream_key, spec.stream_maxlen)
                    seq += 1
                rc = proc.wait()
            except Exception as exc:
                kill_child_group(proc)
                output_tail = spec.ring.to_str()
                writer.finalize(run_uid, OUTCOME_ERROR, error=str(exc) or type(exc).__name__, output_tail=output_tail)
                log.error(spec.event_prefix + "_stream_failed", run_uid=run_uid, exc_info=True, **spec.log_context)
                sys.exit(1)

            if spec.requeue_on_exit3 and rc == 3:
                # Exit 3 = lock busy at claim time (the lock was re-acquired
                # between our probe and the child's claim, or a same-item resolve
                # is live) — re-queue PACED under the same deadline so a child
                # that exits 3 forever never spins the runner at full speed.
                spec.child.pop("proc", None)
                if time.monotonic() > queue_deadline:
                    writer.finalize(
                        run_uid, OUTCOME_ERROR, error=spec.requeue_timeout_error, output_tail=spec.ring.to_str()
                    )
                    log.error(
                        spec.event_prefix + "_requeue_timeout", run_uid=run_uid, attempt=attempt, **spec.log_context
                    )
                    sys.exit(1)
                log.info(spec.event_prefix + "_requeued", run_uid=run_uid, attempt=attempt, **spec.log_context)
                time.sleep(1.0 + random.uniform(0.0, 1.0))
                continue
            break

        # Finalize.
        output_tail = spec.ring.to_str()
        if rc == 0:
            writer.finalize(run_uid, OUTCOME_SUCCESS, output_tail=output_tail)
            log.info(spec.event_prefix + "_completed", run_uid=run_uid, rc=rc, lines=seq, **spec.log_context)
            if spec.on_success is not None:
                spec.on_success()
        else:
            # On failure, capture the last portion of output as the error context.
            error_tail = output_tail[-2000:] if len(output_tail) > 2000 else output_tail
            writer.finalize(run_uid, OUTCOME_ERROR, error=error_tail, output_tail=output_tail)
            log.error(spec.event_prefix + "_failed", run_uid=run_uid, rc=rc, lines=seq, **spec.log_context)

        sys.exit(rc)
    finally:
        if spec.lock_state.get("acquired") and spec.release_fn is not None and spec.lock_file is not None:
            spec.release_fn(spec.lock_file)
