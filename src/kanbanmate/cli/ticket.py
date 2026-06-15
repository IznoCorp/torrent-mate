"""Enqueue operator ticket-CRUD intents (cockpit PR3).

``kanban ticket create|edit|close`` enqueue ``ticket_*`` :class:`~kanbanmate.core.intent.Intent`s;
the **daemon** executes them (create is idempotent multi-step; edit replaces the body; close closes
the issue). This is the **operator** path (the bare ``kanban`` CLI is agent-excluded). ``--wait``
blocks on the daemon's result.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence

from kanbanmate.ports.store import StateStore

#: Result states that end a ``--wait`` poll.
_TERMINAL_STATES: frozenset[str] = frozenset({"done", "rejected"})


def _poll_result(
    store: StateStore,
    intent_id: str,
    *,
    start: float,
    timeout: float,
    poll_interval: float,
    sleep: Callable[[float], object],
    clock: Callable[[], float],
) -> tuple[str, str] | None:
    """Poll an intent's result until terminal or ``timeout``; return ``(state, detail)`` or ``None``."""
    deadline = start + timeout
    while clock() < deadline:
        result = store.load_intent_result(intent_id)
        state = result.get("state") if result else None
        if isinstance(state, str) and state in _TERMINAL_STATES:
            return state, str(result.get("detail", "")) if result else ""
        sleep(poll_interval)
    return None


def _timeout_hint(label: str, timeout: float) -> str:
    """The shared ``--wait`` timeout message (the daemon may be down)."""
    return f"{label} still pending after {timeout:.0f}s — the daemon may be down (check `kanban doctor`)."


def create(
    store: StateStore,
    *,
    title: str,
    body: str = "",
    labels: Sequence[str] = (),
    column: str | None = None,
    wait: bool = False,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    now: float | None = None,
    sleep: Callable[[float], object] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> str:
    """Enqueue a ``ticket_create`` intent (operator) and optionally wait for the daemon's result."""
    start = now if now is not None else clock()
    intent_id = uuid.uuid4().hex[:12]
    args: dict[str, object] = {"title": title, "body": body, "labels": list(labels)}
    if column:
        args["column"] = column
    store.enqueue_intent(
        intent_id,
        {
            "kind": "ticket_create",
            "issue": None,
            "args": args,
            "requested_at": start,
            "caller": "operator",
        },
    )
    if not wait:
        return (
            f"kanban ticket create: enqueued '{title}' (intent {intent_id}); the daemon creates it "
            f"on its next tick (~10s). Use --wait to block on the result."
        )
    outcome = _poll_result(
        store,
        intent_id,
        start=start,
        timeout=timeout,
        poll_interval=poll_interval,
        sleep=sleep,
        clock=clock,
    )
    if outcome is None:
        return _timeout_hint(f"kanban ticket create: '{title}'", timeout)
    state, detail = outcome
    verb = "created" if state == "done" else "REJECTED"
    return f"kanban ticket create: '{title}' {verb} — {detail}".rstrip(" —")


def edit(
    store: StateStore,
    *,
    issue: int,
    body: str,
    wait: bool = False,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    now: float | None = None,
    sleep: Callable[[float], object] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> str:
    """Enqueue a ``ticket_edit`` intent (replace the issue body) and optionally wait."""
    start = now if now is not None else clock()
    intent_id = uuid.uuid4().hex[:12]
    store.enqueue_intent(
        intent_id,
        {
            "kind": "ticket_edit",
            "issue": issue,
            "args": {"body": body},
            "requested_at": start,
            "caller": "operator",
        },
    )
    if not wait:
        return (
            f"kanban ticket edit: enqueued #{issue} (intent {intent_id}); the daemon applies it on "
            f"its next tick (~10s). Use --wait to block on the result."
        )
    outcome = _poll_result(
        store,
        intent_id,
        start=start,
        timeout=timeout,
        poll_interval=poll_interval,
        sleep=sleep,
        clock=clock,
    )
    if outcome is None:
        return _timeout_hint(f"kanban ticket edit: #{issue}", timeout)
    state, detail = outcome
    verb = "edited" if state == "done" else "REJECTED"
    return f"kanban ticket edit: #{issue} {verb} — {detail}".rstrip(" —")


def close(
    store: StateStore,
    *,
    issue: int,
    wait: bool = False,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    now: float | None = None,
    sleep: Callable[[float], object] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> str:
    """Enqueue a ``ticket_close`` intent (close the issue) and optionally wait."""
    start = now if now is not None else clock()
    intent_id = uuid.uuid4().hex[:12]
    store.enqueue_intent(
        intent_id,
        {
            "kind": "ticket_close",
            "issue": issue,
            "args": {},
            "requested_at": start,
            "caller": "operator",
        },
    )
    if not wait:
        return (
            f"kanban ticket close: enqueued #{issue} (intent {intent_id}); the daemon closes it on "
            f"its next tick (~10s). Use --wait to block on the result."
        )
    outcome = _poll_result(
        store,
        intent_id,
        start=start,
        timeout=timeout,
        poll_interval=poll_interval,
        sleep=sleep,
        clock=clock,
    )
    if outcome is None:
        return _timeout_hint(f"kanban ticket close: #{issue}", timeout)
    state, detail = outcome
    verb = "closed" if state == "done" else "REJECTED"
    return f"kanban ticket close: #{issue} {verb} — {detail}".rstrip(" —")
