"""Tests for ``AppContext`` — Sub-phase 2.1.

Locks the frozen dataclass shape, the carry-by-reference contract, and the
event-bus usability sanity check.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, Mock

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import Event, EventBus
from tests.fixtures.event_bus import CollectingSubscriber


class _Foo(Event):
    """Test stub — outside production registry by Invariant 9."""


def test_app_context_is_frozen() -> None:
    """``AppContext`` is a frozen dataclass with exactly six fields.

    The fifth field ``torrent_client`` was added when the torrent client was
    promoted into the boundary bundle (DESIGN D3/D9). The sixth field
    ``tracker_registry`` was added by RP5a (tracker-wiring): the configured
    ``TrackerRegistry`` handle on the boundary bundle.
    """
    expected = {
        "config",
        "settings",
        "event_bus",
        "provider_registry",
        "torrent_client",
        "tracker_registry",
    }
    field_names = {f.name for f in dataclasses.fields(AppContext)}
    assert field_names == expected
    bundle = AppContext(
        config=Mock(),
        settings=Mock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )
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
    registry = MagicMock(spec=ProviderRegistry)
    bundle = AppContext(config=config, settings=settings, event_bus=bus, provider_registry=registry)
    assert bundle.config is config
    assert bundle.settings is settings
    assert bundle.event_bus is bus
    assert bundle.provider_registry is registry


def test_app_context_event_bus_is_usable() -> None:
    """The bundled event_bus dispatches subscribed events end-to-end."""
    bundle = AppContext(
        config=Mock(),
        settings=Mock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )
    with CollectingSubscriber(bundle.event_bus, _Foo) as sub:
        event = _Foo()
        bundle.event_bus.emit(event)
    assert sub.received == [event]
