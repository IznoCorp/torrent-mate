"""Tests for ``EventBus.emit`` error isolation and re-entrant safety.

Locks Sub-phase 1.4 of the event-bus feature: per-subscriber try/except,
structlog ``event_emit_failed`` warning, and the immutable-snapshot iteration
contract that makes re-entrant ``subscribe`` / ``unsubscribe`` / ``emit``
safe under all dispatch scenarios.
"""

from __future__ import annotations

import logging

import pytest

from personalscraper.core.event_bus import Event, EventBus


class _Foo(Event):
    """Test-only Event subclass."""


class _Bar(Event):
    """Distinct test-only subclass for re-entrant emit assertions."""


def _has_structlog_event(
    caplog: pytest.LogCaptureFixture,
    event_name: str,
) -> bool:
    """Detect a structlog event by its ``event`` field across caplog records."""
    for rec in caplog.records:
        msg = rec.msg
        if isinstance(msg, dict) and msg.get("event") == event_name:
            return True
        # Fallback: rendered string form may carry the event name as a token.
        if isinstance(msg, str) and event_name in msg:
            return True
    return False


def test_failing_subscriber_does_not_break_dispatch() -> None:
    """A raising subscriber is isolated; later subscribers still receive the event."""
    bus = EventBus()
    received: list[Event] = []

    def bad_cb(_event: Event) -> None:
        raise ValueError("boom — intentional")

    def good_cb(event: Event) -> None:
        received.append(event)

    bus.subscribe(_Foo, bad_cb)
    bus.subscribe(_Foo, good_cb)
    event = _Foo()
    bus.emit(event)  # MUST NOT raise.
    assert received == [event]


def test_failing_subscriber_logged_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    """A failing subscriber emits an ``event_emit_failed`` WARNING via structlog."""
    bus = EventBus()

    def bad_cb(_event: Event) -> None:
        raise RuntimeError("boom")

    bus.subscribe(_Foo, bad_cb)
    with caplog.at_level(logging.WARNING):
        bus.emit(_Foo())
    assert _has_structlog_event(caplog, "event_emit_failed")


def test_subscriber_can_emit_during_handler() -> None:
    """A handler that emits a different event type sees its dispatch complete."""
    bus = EventBus()
    bar_received: list[Event] = []

    def cb_a(_event: Event) -> None:
        bus.emit(_Bar())

    def cb_b(event: Event) -> None:
        bar_received.append(event)

    bus.subscribe(_Foo, cb_a)
    bus.subscribe(_Bar, cb_b)
    bus.emit(_Foo())
    assert len(bar_received) == 1
    assert isinstance(bar_received[0], _Bar)


def test_unsubscribe_during_dispatch_does_not_affect_current_emit() -> None:
    """A subscriber that unsubscribes itself stays in the current emit's snapshot."""
    bus = EventBus()
    invocations: list[str] = []
    cb_x_token: list = []

    def cb_x(_event: Event) -> None:
        invocations.append("x")
        bus.unsubscribe(cb_x_token[0])

    def cb_y(_event: Event) -> None:
        invocations.append("y")

    cb_x_token.append(bus.subscribe(_Foo, cb_x))
    bus.subscribe(_Foo, cb_y)
    # First emit: both x and y fire (snapshot iteration).
    bus.emit(_Foo())
    assert invocations == ["x", "y"]
    # Second emit: only y survives, since x unsubscribed during the first dispatch.
    invocations.clear()
    bus.emit(_Foo())
    assert invocations == ["y"]


def test_subscribe_during_dispatch_does_not_affect_current_emit() -> None:
    """A handler that subscribes a new callback does NOT see it fire on this emit."""
    bus = EventBus()
    invocations: list[str] = []

    def cb_new(_event: Event) -> None:
        invocations.append("new")

    def cb_x(_event: Event) -> None:
        invocations.append("x")
        bus.subscribe(_Foo, cb_new)

    bus.subscribe(_Foo, cb_x)
    # First emit: only x fires; cb_new was registered AFTER the snapshot.
    bus.emit(_Foo())
    assert invocations == ["x"]
    # Second emit: both x and the freshly-registered new fire.
    invocations.clear()
    bus.emit(_Foo())
    assert invocations == ["x", "new"]


def test_recursive_subscriber_caught_as_error_isolation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Self-emitting subscriber: ``RecursionError`` is caught, dispatch returns.

    Documents the caller-responsibility contract from DESIGN §Dispatch
    semantics #4: ``RecursionError`` is a subclass of ``Exception`` and is
    therefore caught by the bus's per-subscriber try/except. The bus logs an
    ``event_emit_failed`` WARNING and returns normally; subscribers MUST NOT
    subscribe to their own emit type.

    The test simulates the recursion-limit hit with an explicit counter rather
    than relying on ``sys.setrecursionlimit``: under ``-n auto`` workers the
    pytest fixture/plugin stack is deep enough that an unbounded ``cb_loop``
    can accumulate hundreds of traceback objects (``exc_info=True`` × depth)
    before the recursion ceiling actually bottoms out, blowing the worker's
    memory budget. The behavior under test — bus catches the exception, logs
    ``event_emit_failed``, returns normally — is identical whether the
    ``RecursionError`` came from a runtime stack overflow or an explicit raise.
    """
    bus = EventBus()
    depth = [0]
    max_depth = 10  # enough recursion to exercise re-entrant dispatch; well under any stack limit

    def cb_loop(_event: Event) -> None:
        """Re-enters bus.emit a bounded number of times, then raises RecursionError.

        The bus's per-subscriber try/except MUST catch the synthetic
        ``RecursionError`` exactly as it would catch a real one, log the
        warning, and unwind cleanly.
        """
        depth[0] += 1
        if depth[0] >= max_depth:
            raise RecursionError("simulated stack overflow")
        bus.emit(_Foo())

    bus.subscribe(_Foo, cb_loop)
    with caplog.at_level(logging.WARNING):
        bus.emit(_Foo())  # MUST NOT raise.
    assert _has_structlog_event(caplog, "event_emit_failed")
    assert depth[0] == max_depth, f"cb_loop should have re-entered exactly {max_depth} times, got {depth[0]}"

    # Subsequent emits without the loop subscriber work fine.
    bus = EventBus()  # fresh bus to drop cb_loop
    received: list[Event] = []
    bus.subscribe(_Foo, received.append)
    event = _Foo()
    bus.emit(event)
    assert received == [event]
