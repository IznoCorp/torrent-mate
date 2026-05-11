"""Tests for ``EventBus.emit`` — MRO-walking dispatch, MRO cache, fast path.

Locks Sub-phase 1.3 of the event-bus feature: dispatch ordering (concrete
before ancestor), MRO-cache populate / invalidate, and the no-subscribers
zero-allocation fast path (DESIGN §Performance notes).
"""

from __future__ import annotations

import tracemalloc

from personalscraper.core.event_bus import Event, EventBus


class _Foo(Event):
    """Test-only direct subclass of Event."""


class _Bar(_Foo):
    """Test-only second-level subclass — exercises intermediate-ancestor MRO."""


class _Baz(Event):
    """Unrelated test-only subclass to assert no cross-type dispatch."""


def test_emit_invokes_subscriber_of_exact_type() -> None:
    """A subscriber registered for the concrete type receives the event."""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(_Foo, received.append)
    event = _Foo()
    bus.emit(event)
    assert received == [event]


def test_emit_invokes_subscriber_of_base_event() -> None:
    """A subscriber registered for ``Event`` (base) catches every subclass emit."""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(Event, received.append)
    event = _Foo()
    bus.emit(event)
    assert received == [event]


def test_emit_invokes_subscriber_of_intermediate_ancestor() -> None:
    """An ancestor subscription catches a deeper-derived emit via MRO walk."""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(_Foo, received.append)
    event = _Bar()  # _Bar is a _Foo
    bus.emit(event)
    assert received == [event]


def test_emit_does_not_invoke_unrelated_type_subscribers() -> None:
    """A subscriber for an unrelated type receives nothing on a cross-type emit."""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(_Baz, received.append)
    bus.emit(_Foo())
    assert received == []


def test_emit_ordering_concrete_before_ancestor() -> None:
    """Concrete-type subscribers fire before ancestor subscribers (DESIGN §5)."""
    bus = EventBus()
    order: list[str] = []
    bus.subscribe(_Foo, lambda _e: order.append("concrete"))
    bus.subscribe(Event, lambda _e: order.append("base"))
    bus.emit(_Foo())
    assert order == ["concrete", "base"]


def test_emit_with_no_subscribers_is_noop() -> None:
    """Emitting on a fresh bus with zero subscribers raises nothing and returns."""
    bus = EventBus()
    # Must not raise — the fast path returns before any iteration.
    bus.emit(_Foo())
    assert bus._subscribers == {}  # noqa: SLF001


def test_emit_no_subscribers_zero_allocation() -> None:
    """The empty-bus fast path allocates zero blocks inside ``event_bus.py``.

    Uses ``tracemalloc`` snapshots on either side of 100 emits and filters
    allocations by traceback filename. The event instances themselves are
    constructed in user code (this test module), so they are excluded — the
    contract is that ``event_bus.py`` itself adds nothing on the fast path.
    """
    bus = EventBus()
    # Pre-construct events so per-iteration allocation is on the test, not the bus.
    events = [_Foo() for _ in range(100)]
    tracemalloc.start()
    try:
        snap_before = tracemalloc.take_snapshot()
        for event in events:
            bus.emit(event)
        snap_after = tracemalloc.take_snapshot()
    finally:
        tracemalloc.stop()
    diff = sum(
        stat.count_diff
        for stat in snap_after.compare_to(snap_before, "lineno")
        if stat.traceback and "event_bus.py" in stat.traceback[0].filename
    )
    assert diff == 0, f"fast path allocated {diff} blocks in event_bus.py"


def test_mro_cache_populated_on_first_emit() -> None:
    """The first emit for a given type populates ``_mro_cache``."""
    bus = EventBus()
    bus.subscribe(_Foo, lambda _e: None)
    assert _Foo not in bus._mro_cache  # noqa: SLF001
    bus.emit(_Foo())
    assert _Foo in bus._mro_cache  # noqa: SLF001
    # The cached value is the tuple of callables in dispatch order.
    assert isinstance(bus._mro_cache[_Foo], tuple)  # noqa: SLF001
    assert len(bus._mro_cache[_Foo]) == 1  # noqa: SLF001


def test_mro_cache_invalidated_on_subscribe() -> None:
    """Adding a subscription clears the MRO cache so the next emit re-resolves."""
    bus = EventBus()
    bus.subscribe(_Foo, lambda _e: None)
    bus.emit(_Foo())  # populate cache
    assert _Foo in bus._mro_cache  # noqa: SLF001
    bus.subscribe(_Foo, lambda _e: None)
    assert bus._mro_cache == {}  # noqa: SLF001


def test_mro_cache_invalidated_on_unsubscribe() -> None:
    """Removing a subscription clears the MRO cache so the next emit re-resolves."""
    bus = EventBus()
    token = bus.subscribe(_Foo, lambda _e: None)
    bus.emit(_Foo())
    assert _Foo in bus._mro_cache  # noqa: SLF001
    bus.unsubscribe(token)
    assert bus._mro_cache == {}  # noqa: SLF001
