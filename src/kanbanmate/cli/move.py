"""Enqueue an operator board-move intent (cockpit PR2).

``kanban move <issue> <column>`` enqueues a move :class:`~kanbanmate.core.intent.Intent` into the
``~/.kanban/intents/`` queue then nudges the daemon (0.4.0) so it wakes from its inter-tick sleep and
drains the move near-instantly; the **daemon** is the sole executor — it applies the move on its tick
(re-validating + advancing the diff baseline so the move never re-fires a launch). ``--wait`` blocks
on the result the daemon writes (``done`` / ``rejected``) up to a timeout, then surfaces it.

This is the **operator** path: the bare ``kanban`` CLI is intentionally excluded from agents
(``adapters/perms``), so only the operator reaches this command. ``<column>`` is a column KEY (as
shown by ``kanban state``).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from kanbanmate.ports.store import StateStore

#: Result states that end the ``--wait`` poll (the daemon wrote a terminal outcome).
_TERMINAL_STATES: frozenset[str] = frozenset({"done", "rejected"})


def move(
    store: StateStore,
    *,
    issue: int,
    to_col: str,
    wait: bool = False,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    now: float | None = None,
    sleep: Callable[[float], object] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> str:
    """Enqueue a move intent (operator authority) and optionally wait for the daemon's result.

    Args:
        store: The state store (the intent queue lives under its root).
        issue: The ticket's issue number to move.
        to_col: The destination column KEY (as shown by ``kanban state``).
        wait: When ``True``, block polling the result file until terminal or ``timeout``.
        timeout: The ``--wait`` budget in seconds.
        poll_interval: The ``--wait`` poll cadence in seconds.
        now: The enqueue timestamp (the drain orders by it); ``None`` reads the clock.
        sleep: The sleep callable (injected for tests).
        clock: The wall-clock callable (injected for tests).

    Returns:
        A human message describing the enqueue (and, with ``--wait``, the terminal outcome or a
        timeout hint).
    """
    start = now if now is not None else clock()
    intent_id = uuid.uuid4().hex[:12]
    store.enqueue_intent(
        intent_id,
        {
            "kind": "move",
            "issue": issue,
            "args": {"to_col": to_col},
            "requested_at": start,
            "caller": "operator",
        },
    )
    # Nudge the daemon so it wakes from its inter-tick sleep and drains this intent near-instantly
    # rather than after a full poll interval (0.4.0). Best-effort: the store method swallows any
    # failure, degrading to the normal full-interval cadence. CONVENTION: every ``enqueue_intent`` is
    # paired with ``nudge_daemon`` (see also ``bin/kanban_move``; future PR3 enqueuers follow).
    store.nudge_daemon()
    if not wait:
        return (
            f"kanban move: enqueued #{issue} → {to_col} (intent {intent_id}); the daemon applies it "
            f"on its next tick (~10s). Use --wait to block on the result."
        )

    deadline = start + timeout
    while clock() < deadline:
        result = store.load_intent_result(intent_id)
        state = result.get("state") if result else None
        if state in _TERMINAL_STATES:
            detail = str(result.get("detail", "")) if result else ""
            verb = "applied" if state == "done" else "REJECTED"
            return f"kanban move: #{issue} → {to_col} {verb} — {detail}".rstrip(" —")
        sleep(poll_interval)

    return (
        f"kanban move: #{issue} → {to_col} still pending after {timeout:.0f}s — the daemon may be "
        f"down (check `kanban doctor`)."
    )
