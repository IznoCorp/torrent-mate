"""Per-action watchdog: bounded, fail-isolated execution for one poll cycle (DESIGN §5).

This module is the imperative shell's hang-protection layer, extracted from :mod:`kanbanmate.app.tick`
(LOC budget — :mod:`tick` re-exports every name here under its historical public spelling so callers
and tests that reference ``tick._run_with_watchdog`` / ``tick.WatchdogStatus`` / ``tick._watchdog_executor``
keep working unchanged). It owns the per-tick thread pool and the wrappers that run each command (and
each side-effecting callable) inside it under a bounded timeout, so a single hung adapter call (a stuck
``git`` / ``tmux`` / network op) is abandoned and the tick continues rather than freezing the daemon:

* **Per-action watchdog** — :func:`_run_with_watchdog` (and its launch / value / callable siblings) runs
  one unit of work in a worker thread and bounds *our* wait on it; a timeout or any raised exception is
  caught and logged, never aborting the surrounding tick.
* **Non-blocking shutdown** — :func:`_watchdog_executor` yields the pool and, on exit, shuts it down
  WITHOUT waiting on a wedged worker, making the never-hang guarantee real (the plain ``with
  ThreadPoolExecutor`` would block on ``shutdown(wait=True)``).
* **Authoritative leak signal** — the per-tick timeout registry (:data:`_TIMED_OUT_ACTIONS`) records the
  ONLY genuinely orphaned workers (a ``future.result(timeout=...)`` that actually raised), so the exit
  warning fires only on a real hang and names the offender — not on every benign idle pool worker.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2). This module speaks only
the action command objects (via :mod:`kanbanmate.app.actions` / :class:`~kanbanmate.app.reaper._ReapMove`)
plus the injected :class:`~kanbanmate.app.actions.Deps`; it names no concrete adapter.
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from typing import Final
from weakref import WeakKeyDictionary

from kanbanmate.app.actions import (
    BlockAction,
    DependencyBounceAction,
    Deps,
    LaunchAction,
    ResetAction,
    RollbackAction,
    RunScriptAction,
    TeardownAction,
)
from kanbanmate.app.reaper import _ReapMove

logger = logging.getLogger(__name__)

# Per-tick registry of GENUINELY abandoned actions, keyed by the tick's executor (phase-34): when a
# watchdog wrapper's ``future.result(timeout=...)`` raises ``FutureTimeoutError`` the worker is left
# running unjoinable (a REAL leaked thread) — the wrapper records the action here and
# ``_watchdog_executor`` warns at exit ONLY when non-empty. This replaces the old ``t.is_alive()``
# heuristic, which false-positived on EVERY success (a pool worker stays alive IDLE between tasks, so
# "alive at tick exit" ≠ "hung"); the timeout records are the authoritative never-hang signal. The
# map is weak-keyed on the executor so a tick's records vanish with it (GC'd) — no manual reset.
_TIMED_OUT_ACTIONS: WeakKeyDictionary[ThreadPoolExecutor, list[str]] = WeakKeyDictionary()


def _record_timed_out_action(executor: ThreadPoolExecutor, description: str) -> None:
    """Record that a watchdog-bounded action on ``executor`` timed out (genuine hang).

    Appends ``description`` to the executor's per-tick abandoned-action list (created lazily on first
    timeout). ``_watchdog_executor`` reads the list at tick exit to warn about REAL leaked threads —
    a worker abandoned mid-call by :class:`~concurrent.futures.TimeoutError`, not an idle pool worker.

    Args:
        executor: The tick's shared thread pool the timed-out action ran in (the registry key).
        description: A short human-readable name of the action that hung (e.g. ``"LaunchAction"`` or
            the callable's label), surfaced in the exit warning so the leak is attributable.
    """
    _TIMED_OUT_ACTIONS.setdefault(executor, []).append(description)


def _run_with_watchdog(
    executor: ThreadPoolExecutor,
    command: LaunchAction
    | TeardownAction
    | ResetAction
    | BlockAction
    | RollbackAction
    | DependencyBounceAction
    | RunScriptAction
    | _ReapMove,
    deps: Deps,
    timeout: float,
) -> bool:
    """Execute one command under a bounded timeout, isolating any failure.

    The command runs in a worker thread so a hung adapter call can be abandoned after ``timeout``
    seconds (DESIGN §5). Both a timeout and any raised exception are caught and logged; neither
    aborts the surrounding tick.

    Args:
        executor: The shared thread pool the action runs in.
        command: The command object to execute.
        deps: The injected adapter bundle.
        timeout: The per-action watchdog budget in seconds.

    Returns:
        ``True`` if the action completed cleanly, ``False`` on timeout or exception.
    """
    future = executor.submit(command.execute, deps)
    try:
        future.result(timeout=timeout)
        return True
    except FutureTimeoutError:
        # The worker thread is left running (it cannot be force-killed); the watchdog only
        # bounds *our* wait so the daemon stays responsive. The next tick's diff/state guards
        # keep the result idempotent even if the abandoned action later completes. Record the
        # genuine hang so ``_watchdog_executor`` can warn about the REAL leaked thread at tick exit
        # (phase-34) — an idle pool worker is NOT a leak, but this abandoned-mid-call one is.
        _record_timed_out_action(executor, type(command).__name__)
        logger.warning(
            "action %s timed out after %.0fs; continuing", type(command).__name__, timeout
        )
        return False
    except Exception:  # noqa: BLE001 — one bad action must never abort the whole tick
        logger.exception("action %s raised; continuing", type(command).__name__)
        return False


class WatchdogStatus(enum.Enum):
    """Tri-state outcome of a watchdog-bounded LAUNCH dispatch (defect 13).

    The boolean :func:`_run_with_watchdog` collapses a TIMEOUT and an EXCEPTION into one ``False``,
    but the launch slot-release path must tell them apart:

    Members:
        OK: The action completed cleanly within the budget.
        FAILED: The action RAISED — it definitively did NOT create a session, so the reserved slot
            must be released (no live agent backs it).
        UNKNOWN: The action TIMED OUT — the worker thread is abandoned but STILL RUNNING and may yet
            create the tmux session late. Releasing the slot here would let that late launch run an
            agent with no slot (cap+1), so the slot is KEPT; the drain's already-running guard
            adjudicates next tick (a completed launch leaves a RUNNING state that holds the slot; a
            truly dead one is reconciled by the reaper).
    """

    OK = "ok"
    FAILED = "failed"
    UNKNOWN = "unknown"


def _run_launch_with_watchdog(
    executor: ThreadPoolExecutor,
    command: LaunchAction,
    deps: Deps,
    timeout: float,
) -> WatchdogStatus:
    """Run a LAUNCH dispatch under the watchdog, returning a TRI-STATE status (defect 13).

    Identical isolation to :func:`_run_with_watchdog` but distinguishes a TIMEOUT (``UNKNOWN`` — the
    abandoned worker may still create the session) from an EXCEPTION (``FAILED`` — no session
    created). The caller releases the reserved slot ONLY on ``FAILED``; on ``UNKNOWN`` it keeps the
    slot so a late-completing launch never runs an agent without one (the cap+1 the boolean watchdog
    allowed). Port of the phase-13 deferred residual (IMPLEMENTATION.md:252-254).

    Args:
        executor: The shared thread pool the launch runs in.
        command: The :class:`~kanbanmate.app.actions.LaunchAction` to dispatch.
        deps: The injected adapter bundle.
        timeout: The per-action watchdog budget in seconds.

    Returns:
        :attr:`WatchdogStatus.OK` on a clean run, :attr:`WatchdogStatus.UNKNOWN` on timeout,
        :attr:`WatchdogStatus.FAILED` on an exception.
    """
    future = executor.submit(command.execute, deps)
    try:
        future.result(timeout=timeout)
        return WatchdogStatus.OK
    except FutureTimeoutError:
        # The abandoned worker is still running and may create the tmux session late — record the
        # genuine leaked thread (phase-34) and return UNKNOWN so the caller KEEPS the slot.
        _record_timed_out_action(executor, type(command).__name__)
        logger.warning(
            "launch %s timed out after %.0fs; keeping the slot (status UNKNOWN, defect 13)",
            type(command).__name__,
            timeout,
        )
        return WatchdogStatus.UNKNOWN
    except Exception:  # noqa: BLE001 — one bad launch must never abort the whole tick
        logger.exception("launch %s raised; continuing", type(command).__name__)
        return WatchdogStatus.FAILED


def _run_value_with_watchdog(
    executor: ThreadPoolExecutor,
    fn: Callable[[], tuple[int, str]],
    timeout: float,
) -> tuple[bool, tuple[int, str]]:
    """Run a VALUE-returning check-script call under the same bounded watchdog (15.6).

    The check-script seam (``run_check_script``) returns an ``(exit_code, output)`` verdict, which
    the void-returning :func:`_run_with_watchdog` cannot surface. This variant runs ``fn`` in the
    shared worker thread and returns ``(ok, verdict)``: ``ok`` is ``True`` iff ``fn`` completed
    within ``timeout`` (mirroring :func:`_run_with_watchdog`'s timeout/exception isolation), and
    ``verdict`` is ``fn``'s return value on success or a safe ``(0, "")`` placeholder on
    timeout/exception. The subprocess inside ``fn`` is itself 120s-bounded in the workspace adapter;
    this watchdog additionally bounds a hung ``gh`` inside the script so the sweep stays responsive.

    Args:
        executor: The shared thread pool the call runs in.
        fn: The zero-arg callable producing the ``(exit_code, output)`` verdict.
        timeout: The per-action watchdog budget in seconds.

    Returns:
        ``(ok, (exit_code, output))`` — ``ok`` is ``False`` (with a ``(0, "")`` placeholder verdict)
        on timeout or exception, so the caller can skip routing a phantom verdict.
    """
    future = executor.submit(fn)
    try:
        return True, future.result(timeout=timeout)
    except FutureTimeoutError:
        # Record the genuine hang (phase-34): the worker is abandoned mid-call and leaks, so the
        # exit warning in ``_watchdog_executor`` should fire — distinct from a benign idle worker.
        _record_timed_out_action(executor, "check-script")
        logger.warning("check-script timed out after %.0fs; continuing", timeout)
        return False, (0, "")
    except Exception:  # noqa: BLE001 — a wedged script must never abort the whole tick
        logger.exception("check-script raised; continuing")
        return False, (0, "")


def _run_callable_with_watchdog(
    executor: ThreadPoolExecutor,
    fn: Callable[[], object],
    timeout: float,
    *,
    label: str,
) -> bool:
    """Run a void/side-effecting callable under the bounded watchdog (#6).

    The general-purpose sibling of :func:`_run_with_watchdog` (which needs an action object with an
    ``.execute`` method). Used to bound the launch-gate's pre-create ``ensure_worktree`` call, which
    ran DIRECTLY on the tick thread before #6 — a network-touching ``git fetch`` outside any
    watchdog. Now it runs in the shared worker thread bounded by ``timeout``, so a hung pre-create
    can never freeze the daemon. Both timeout and exception are caught and logged.

    Args:
        executor: The shared thread pool the call runs in.
        fn: The zero-arg callable to run (its return value is discarded).
        timeout: The per-action watchdog budget in seconds.
        label: A short name for the call, used in the timeout/error log line.

    Returns:
        ``True`` if ``fn`` completed cleanly within ``timeout``, ``False`` on timeout or exception.
    """
    future = executor.submit(fn)
    try:
        future.result(timeout=timeout)
        return True
    except FutureTimeoutError:
        # Record the genuine hang (phase-34) under the caller-supplied label so the exit warning
        # can name the leaked pre-create/gate call — an idle pool worker must NOT trip the warning.
        _record_timed_out_action(executor, label)
        logger.warning("%s timed out after %.0fs; continuing", label, timeout)
        return False
    except Exception:  # noqa: BLE001 — a hung pre-create must never abort the whole tick
        logger.exception("%s raised; continuing", label)
        return False


#: Short grace period (seconds) given to idle pool workers to wind down after the non-blocking
#: shutdown, before any leak is assessed. A ``ThreadPoolExecutor`` worker parks IDLE on the work
#: queue between tasks and exits a beat after ``shutdown()`` signals it; this brief join lets that
#: happen so a just-finished action's worker is never mistaken for a hang (phase-34). It does NOT
#: gate the never-hang guarantee — the authoritative leak signal is the timeout registry, not
#: aliveness — so it is intentionally tiny.
_IDLE_WORKER_GRACE_S: Final[float] = 0.2


@contextmanager
def _watchdog_executor() -> Iterator[ThreadPoolExecutor]:
    """Yield the per-tick thread pool with a NON-BLOCKING shutdown (#6, real never-hang).

    The plain ``with ThreadPoolExecutor(...)`` calls ``shutdown(wait=True)`` on exit, which BLOCKS
    until every worker finishes — so one hung adapter call (the very case the per-action watchdog
    abandons) would freeze the whole daemon at tick exit, defeating the never-hang guarantee
    (CLAUDE.md). This context manager instead, on exit, calls
    ``shutdown(wait=False, cancel_futures=True)`` so the tick returns IMMEDIATELY even if a worker is
    wedged.

    **Leak detection (phase-34).** It warns about an abandoned thread using the AUTHORITATIVE signal:
    the per-tick timeout registry (:data:`_TIMED_OUT_ACTIONS`), populated by the watchdog wrappers
    whenever a ``future.result(timeout=...)`` actually raised ``TimeoutError``. That is the only case
    where a worker is genuinely orphaned. The previous implementation counted ``t.is_alive()`` on the
    pool's ``_threads``, but a ``ThreadPoolExecutor`` worker stays alive IDLE (parked on the work
    queue) BETWEEN tasks — so that check fired a FALSE POSITIVE after EVERY successful action, even
    when the action completed and had effects on the board. Now the warning fires only on a real hang
    and names the offending action(s), so the leak is both correct and attributable. As a belt-and-
    braces nicety, idle workers get a short grace join (:data:`_IDLE_WORKER_GRACE_S`) after the
    non-blocking shutdown so a just-finished worker has wound down before exit — but no leak is
    inferred from aliveness; the timeout records are the sole signal.

    A running worker cannot be force-killed (Python has no thread-kill), so a truly wedged adapter
    call leaks ONE thread per occurrence; the warning makes that visible, and the next tick's
    diff/state guards keep the result idempotent if the abandoned action later completes.

    Yields:
        A :class:`~concurrent.futures.ThreadPoolExecutor` for the tick's watchdog-bounded actions.
    """
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kanban-tick")
    try:
        yield executor
    finally:
        # NON-BLOCKING: return immediately even if a worker is wedged. ``cancel_futures=True`` drops
        # any not-yet-started work; a running worker cannot be force-killed but the tick no longer
        # waits on it.
        executor.shutdown(wait=False, cancel_futures=True)
        # Give idle workers a tiny grace to wind down post-shutdown so a just-finished action's
        # worker is not lingering — purely cosmetic; the leak verdict is the timeout registry below.
        for t in getattr(executor, "_threads", ()):
            t.join(timeout=_IDLE_WORKER_GRACE_S)
        # Warn ONLY when a watchdog wrapper recorded a genuine timeout this tick — those are the REAL
        # leaked threads (abandoned mid-call). An idle/just-finished pool worker is NOT a leak, so it
        # no longer trips this warning (the old ``is_alive()`` heuristic did, on every action).
        abandoned = _TIMED_OUT_ACTIONS.pop(executor, [])
        if abandoned:
            logger.warning(
                "tick exiting with %d abandoned hung action(s) (worker thread leaked, cannot be "
                "force-killed); NOT waiting (never-hang). Abandoned: %s",
                len(abandoned),
                ", ".join(abandoned),
            )
