"""Visible-queue wait loop shared by the detached web runners (§6).

Constitution §6 (Disponibilité des actions): a legitimate operator action never
answers "busy" — it either executes or waits in a VISIBLE queue (post-mortem
#249: an invisible queue is the founding failure). This module is the single
implementation of that wait, graved by the #287 resolve queue and generalized
to every detached runner that must hold or respect ``pipeline.lock``.

The queue has no dedicated table: it is the waiting runner process plus a
``queue`` step appended to the run row's ``steps_json`` (epoch timestamps per
invariant), surfaced by the existing activity / run-detail endpoints.

Callers keep their own lock acquisition as the ONLY safety authority:

- probe mode (``try_proceed=lambda: not is_lock_held(...)``) is visibility +
  pacing only — the spawned CLI still claims the lock itself (claim-first-
  then-verify, ``personalscraper.lock``) and exits 3 on a lost race, which the
  caller re-queues;
- acquire mode (``try_proceed=lambda: acquire_pipeline_lock(...)``) makes the
  atomic ``O_CREAT|O_EXCL`` claim itself the loop condition, so the wait is
  race-free by construction.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable

from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter

log = get_logger(__name__)

#: Step name appended to ``steps_json`` while a runner waits for the lock.
QUEUE_STEP_NAME = "queue"

#: Step status while waiting (closed with status ``"done"`` when the wait ends).
QUEUE_WAITING_STATUS = "waiting_pipeline_lock"


def wait_in_visible_queue(
    *,
    try_proceed: Callable[[], bool],
    writer: PipelineRunWriter,
    run_uid: str,
    deadline_monotonic: float,
    timeout_s: float,
    timeout_error: str,
    log_event_prefix: str,
    log_context: dict[str, object] | None = None,
    output_tail: Callable[[], str] | None = None,
    poll_base_s: float = 2.0,
) -> bool:
    """Wait visibly until *try_proceed* succeeds or the deadline passes.

    On the first failed attempt a ``queue`` step is appended to the run row
    (status ``waiting_pipeline_lock``); when the wait ends successfully the
    step is closed with the true wait window (status ``done``). On timeout the
    run row is finalized ``error`` with *timeout_error* (French, per §8 — the
    reason is shown, never a bare failure) and ``False`` is returned: the
    caller must exit without proceeding.

    Args:
        try_proceed: Zero-arg callable returning ``True`` when the caller may
            proceed. Probe mode passes a read-only ``is_lock_held`` check;
            acquire mode passes the atomic ``acquire_pipeline_lock`` claim.
        writer: Open :class:`PipelineRunWriter` for the run row.
        run_uid: The run row being made to wait.
        deadline_monotonic: Absolute ``time.monotonic()`` deadline. Shared
            with the caller's re-queue leg so retries never extend the wait.
        timeout_s: The configured total wait, for logging only.
        timeout_error: French finalize message used when the deadline passes.
        log_event_prefix: Structlog event prefix (e.g. ``"decision_runner"``)
            — events emitted are ``{prefix}_queued`` / ``{prefix}_queue_timeout``.
        log_context: Extra structured-log fields (e.g. command / decision id).
        output_tail: Optional callable returning the output ring buffer, folded
            into the timeout finalize so the trace survives.
        poll_base_s: Base poll interval; a 0-1 s jitter is always added.

    Returns:
        ``True`` when *try_proceed* succeeded (queue step closed), ``False``
        when the deadline passed (run row finalized ``error``).
    """
    context = log_context or {}
    queued_since: float | None = None
    while True:
        if try_proceed():
            if queued_since is not None:
                # Leaving the queue — record the wait window truthfully.
                writer.update_step(run_uid, QUEUE_STEP_NAME, queued_since, time.time(), "done")
            return True
        if queued_since is None:
            queued_since = time.time()
            # Structured queue visibility: a 'queue' step on the run row
            # (steps_json is epoch-timestamped per invariant) — the activity
            # endpoint + run detail surface it with no new endpoint.
            writer.update_step(
                run_uid,
                QUEUE_STEP_NAME,
                queued_since,
                queued_since,
                QUEUE_WAITING_STATUS,
            )
            queued_event = log_event_prefix + "_queued"
            log.info(
                queued_event,
                run_uid=run_uid,
                reason="pipeline_lock_held",
                **context,
            )
        if time.monotonic() > deadline_monotonic:
            writer.finalize(
                run_uid,
                "error",
                error=timeout_error,
                output_tail=output_tail() if output_tail is not None else None,
            )
            timeout_event = log_event_prefix + "_queue_timeout"
            log.error(
                timeout_event,
                run_uid=run_uid,
                timeout_s=timeout_s,
                **context,
            )
            return False
        time.sleep(poll_base_s + random.uniform(0.0, 1.0))
