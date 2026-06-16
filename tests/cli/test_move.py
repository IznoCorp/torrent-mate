"""Tests for the operator move-intent CLI (:mod:`kanbanmate.cli.move`, cockpit PR2).

Drives ``move`` against an in-memory store fake: enqueue-without-wait records an intent + returns a
hint; ``--wait`` blocks on the daemon's result and surfaces done/rejected; and a result that never
turns terminal times out with a daemon-down hint. ``sleep``/``clock`` are injected so no real time
passes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kanbanmate.cli.move import move


@dataclass
class _FakeStore:
    intents: dict[str, dict[str, object]] = field(default_factory=dict)
    results: dict[str, dict[str, object]] = field(default_factory=dict)
    nudges: int = 0

    def enqueue_intent(self, intent_id: str, payload: dict[str, object]) -> None:
        self.intents[intent_id] = dict(payload)

    def load_intent_result(self, intent_id: str) -> dict[str, object] | None:
        return self.results.get(intent_id)

    def nudge_daemon(self) -> None:
        # Record the nudge so a test can assert the enqueue-side wiring fires (0.4.0).
        self.nudges += 1


def test_enqueue_without_wait_records_intent() -> None:
    store = _FakeStore()
    msg = move(store, issue=8, to_col="Done", now=100.0)  # type: ignore[arg-type]
    assert "enqueued #8 → Done" in msg
    assert len(store.intents) == 1
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "move"
    assert payload["issue"] == 8
    assert payload["args"] == {"to_col": "Done"}
    assert payload["caller"] == "operator"


def test_enqueue_nudges_the_daemon() -> None:
    """Every enqueue pairs with a daemon nudge so the move drains near-instantly (0.4.0)."""
    store = _FakeStore()
    move(store, issue=8, to_col="Done", now=100.0)  # type: ignore[arg-type]
    assert store.nudges == 1


def test_wait_returns_done_result() -> None:
    store = _FakeStore()
    # The "daemon" writes a done result on the first poll (the id is the one enqueue created).
    clock_values = iter([100.0, 100.0, 100.5])  # start, loop-check-1, ...

    def _clock() -> float:
        return next(clock_values)

    def _sleep(_seconds: float) -> None:
        # On the first sleep, simulate the daemon completing the intent.
        intent_id = next(iter(store.intents))
        store.results[intent_id] = {"state": "done", "detail": "moved Backlog->Done"}

    msg = move(
        store,  # type: ignore[arg-type]
        issue=8,
        to_col="Done",
        wait=True,
        now=100.0,
        sleep=_sleep,
        clock=_clock,
    )
    assert "applied" in msg
    assert "moved Backlog->Done" in msg


def test_wait_returns_rejected_result() -> None:
    store = _FakeStore()

    def _sleep(_seconds: float) -> None:
        intent_id = next(iter(store.intents))
        store.results[intent_id] = {"state": "rejected", "detail": "unknown destination column"}

    msg = move(
        store,  # type: ignore[arg-type]
        issue=8,
        to_col="Nope",
        wait=True,
        now=100.0,
        timeout=5.0,
        sleep=_sleep,
        clock=iter([100.0, 100.0, 101.0]).__next__,
    )
    assert "REJECTED" in msg
    assert "unknown destination column" in msg


def test_wait_times_out_with_daemon_down_hint() -> None:
    store = _FakeStore()
    # Clock jumps past the deadline immediately → no terminal result ever seen.
    msg = move(
        store,  # type: ignore[arg-type]
        issue=8,
        to_col="Done",
        wait=True,
        now=100.0,
        timeout=5.0,
        sleep=lambda _s: None,
        clock=iter([100.0, 200.0]).__next__,
    )
    assert "still pending" in msg
    assert "kanban doctor" in msg
