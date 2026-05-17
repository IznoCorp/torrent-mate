"""Tests for the test-fixture helpers themselves.

Locks Sub-phase 1.8 of the event-bus feature: ``CollectingSubscriber``
behaviour (subscribe-on-construction, type filtering via the bus's MRO walk,
context-manager auto-close) and the ``register_factory`` decorator semantics.
"""

from __future__ import annotations

from personalscraper.core.event_bus import Event, EventBus
from tests.fixtures.event_bus import CollectingSubscriber
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES, register_factory


class _Foo(Event):
    """Test-only subclass."""


class _Bar(Event):
    """Distinct test-only subclass."""


def test_collecting_subscriber_records_events() -> None:
    """Each emit of the subscribed type appends to ``received``."""
    bus = EventBus()
    sub = CollectingSubscriber(bus, _Foo)
    e1 = _Foo()
    e2 = _Foo()
    bus.emit(e1)
    bus.emit(e2)
    assert sub.received == [e1, e2]


def test_collecting_subscriber_filters_by_type() -> None:
    """A subscriber for ``_Foo`` does NOT collect ``_Bar`` (unrelated type)."""
    bus = EventBus()
    sub = CollectingSubscriber(bus, _Foo)
    bus.emit(_Bar())
    assert sub.received == []


def test_collecting_subscriber_collects_via_base_event() -> None:
    """A subscriber for ``Event`` (base) collects every subclass via the MRO walk."""
    bus = EventBus()
    sub = CollectingSubscriber(bus, Event)
    bus.emit(_Foo())
    bus.emit(_Bar())
    assert len(sub.received) == 2


def test_collecting_subscriber_close_unsubscribes() -> None:
    """Calling ``close`` removes the subscription; subsequent emits are not recorded."""
    bus = EventBus()
    sub = CollectingSubscriber(bus, _Foo)
    sub.close()
    bus.emit(_Foo())
    assert sub.received == []
    # Idempotent — calling close again is a no-op.
    sub.close()


def test_collecting_subscriber_context_manager() -> None:
    """``with CollectingSubscriber(...) as sub`` auto-closes on exit."""
    bus = EventBus()
    with CollectingSubscriber(bus, _Foo) as sub:
        bus.emit(_Foo())
        assert len(sub.received) == 1
    # After exit, further emits are NOT recorded.
    bus.emit(_Foo())
    assert len(sub.received) == 1


def test_register_factory_stores_in_registry() -> None:
    """The decorator records the factory in ``EVENT_SAMPLE_FACTORIES``."""

    class _Tmp(Event):
        """Test stub — filtered from the production registry."""

    @register_factory(_Tmp)
    def _make_tmp() -> _Tmp:
        return _Tmp()

    try:
        assert EVENT_SAMPLE_FACTORIES[_Tmp] is _make_tmp
        assert isinstance(_make_tmp(), _Tmp)
    finally:
        EVENT_SAMPLE_FACTORIES.pop(_Tmp, None)
