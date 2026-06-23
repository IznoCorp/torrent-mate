"""Enqueue operator pill-override intents (cockpit PR3).

``kanban pill set-health|note|clear`` enqueue ``pill_*`` :class:`~kanbanmate.core.intent.Intent`s;
the **daemon** applies them by writing the override markers its ``report_status`` step reads — the
operator can pin the health pill (e.g. ``WAITING`` during an incident) + post a dashboard note, then
``clear`` to revert to the computed health. Operator-only (the bare ``kanban`` CLI is agent-excluded).
``--wait`` blocks on the daemon's result.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from kanbanmate.ports.store import StateStore

#: Result states that end a ``--wait`` poll.
_TERMINAL_STATES: frozenset[str] = frozenset({"done", "rejected"})


def _enqueue(store: StateStore, kind: str, args: dict[str, object], start: float) -> str:
    """Persist a board-wide operator pill intent, nudge the daemon, return its id.

    CONVENTION (P3): every ``enqueue_intent`` is paired with ``nudge_daemon`` so the sleeping daemon
    wakes within one slice and drains the intent near-instantly instead of waiting out a full poll
    interval (the operator move-latency collapse, mirroring ``cli/move`` / ``bin/kanban_move``). The
    nudge is internally best-effort, so a failure degrades to the normal full-interval cadence.
    """
    intent_id = uuid.uuid4().hex[:12]
    store.enqueue_intent(
        intent_id,
        {"kind": kind, "issue": None, "args": args, "requested_at": start, "caller": "operator"},
    )
    store.nudge_daemon()
    return intent_id


def _wait(
    store: StateStore,
    intent_id: str,
    label: str,
    done_verb: str,
    *,
    timeout: float,
    poll_interval: float,
    sleep: Callable[[float], object],
    clock: Callable[[], float],
    start: float,
) -> str:
    """Poll the daemon's result until terminal or ``timeout``, then format the outcome."""
    deadline = start + timeout
    while clock() < deadline:
        result = store.load_intent_result(intent_id)
        state = result.get("state") if result else None
        if isinstance(state, str) and state in _TERMINAL_STATES:
            detail = str(result.get("detail", "")) if result else ""
            verb = done_verb if state == "done" else "REJECTED"
            return f"{label} {verb} — {detail}".rstrip(" —")
        sleep(poll_interval)
    return f"{label} still pending after {timeout:.0f}s — the daemon may be down (check `kanban doctor`)."


def set_health(
    store: StateStore,
    *,
    enum: str,
    note: str | None = None,
    wait: bool = False,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    now: float | None = None,
    sleep: Callable[[float], object] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> str:
    """Enqueue a ``pill_set_health`` override (force the pill enum, optional note)."""
    start = now if now is not None else clock()
    args: dict[str, object] = {"enum": enum}
    if note:
        args["note"] = note
    intent_id = _enqueue(store, "pill_set_health", args, start)
    if not wait:
        return (
            f"kanban pill set-health: enqueued {enum} (intent {intent_id}); the daemon applies it on "
            f"its next tick (~10s). Use --wait to block on the result."
        )
    return _wait(
        store,
        intent_id,
        f"kanban pill set-health: {enum}",
        "applied",
        timeout=timeout,
        poll_interval=poll_interval,
        sleep=sleep,
        clock=clock,
        start=start,
    )


def note(
    store: StateStore,
    *,
    text: str,
    wait: bool = False,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    now: float | None = None,
    sleep: Callable[[float], object] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> str:
    """Enqueue a ``pill_note`` (set the operator dashboard note)."""
    start = now if now is not None else clock()
    intent_id = _enqueue(store, "pill_note", {"text": text}, start)
    if not wait:
        return (
            f"kanban pill note: enqueued (intent {intent_id}); the daemon applies it on its next "
            f"tick (~10s). Use --wait to block on the result."
        )
    return _wait(
        store,
        intent_id,
        "kanban pill note:",
        "set",
        timeout=timeout,
        poll_interval=poll_interval,
        sleep=sleep,
        clock=clock,
        start=start,
    )


def clear(
    store: StateStore,
    *,
    wait: bool = False,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    now: float | None = None,
    sleep: Callable[[float], object] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> str:
    """Enqueue a ``pill_clear`` (drop the override → revert to the computed health)."""
    start = now if now is not None else clock()
    intent_id = _enqueue(store, "pill_clear", {}, start)
    if not wait:
        return (
            f"kanban pill clear: enqueued (intent {intent_id}); the daemon applies it on its next "
            f"tick (~10s). Use --wait to block on the result."
        )
    return _wait(
        store,
        intent_id,
        "kanban pill clear:",
        "cleared",
        timeout=timeout,
        poll_interval=poll_interval,
        sleep=sleep,
        clock=clock,
        start=start,
    )
