"""Tests for ``AppContext`` — Sub-phase 2.1.

Locks the frozen dataclass shape, the carry-by-reference contract, and the
event-bus usability sanity check.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import Mock

from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import Event, EventBus
from tests.fixtures.event_bus import CollectingSubscriber


class _Foo(Event):
    """Test stub — outside production registry by Invariant 9."""


def test_app_context_is_frozen() -> None:
    """``AppContext`` is a frozen dataclass with exactly three fields."""
    expected = {"config", "settings", "event_bus"}
    field_names = {f.name for f in dataclasses.fields(AppContext)}
    assert field_names == expected
    bundle = AppContext(config=Mock(), settings=Mock(), event_bus=EventBus())
    try:
        bundle.config = Mock()  # type: ignore[misc]
    except (AttributeError, dataclasses.FrozenInstanceError):
        pass
    else:  # pragma: no cover
        raise AssertionError("AppContext must be frozen")


def test_app_context_carries_provided_services() -> None:
    """Each field stores the exact object passed at construction (by reference)."""
    config = Mock(name="config")
    settings = Mock(name="settings")
    bus = EventBus()
    bundle = AppContext(config=config, settings=settings, event_bus=bus)
    assert bundle.config is config
    assert bundle.settings is settings
    assert bundle.event_bus is bus


def test_app_context_event_bus_is_usable() -> None:
    """The bundled event_bus dispatches subscribed events end-to-end."""
    bundle = AppContext(config=Mock(), settings=Mock(), event_bus=EventBus())
    with CollectingSubscriber(bundle.event_bus, _Foo) as sub:
        event = _Foo()
        bundle.event_bus.emit(event)
    assert sub.received == [event]
