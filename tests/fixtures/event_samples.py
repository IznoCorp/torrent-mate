"""Sample-event factory registry — Sub-phase 1.8 mechanism.

Production events from Phase 3 onwards register a factory here so the
``test_every_event_has_factory`` gate (Sub-phase 1.8 + activated from Phase 3)
can verify that every concrete event in the bus's class registry has a
known-good real-data instance available for round-trip and rendering tests.

Phase 1 ships the registry mechanism but leaves it empty — no concrete
event subclasses exist yet. From Phase 3 the factories accumulate as
events are introduced.
"""

from __future__ import annotations

from collections.abc import Callable

from personalscraper.core.event_bus import Event

# Public registry — keyed by event class. Each entry is a zero-argument
# factory returning a fully-populated event instance with realistic
# (NEVER MagicMock) field values, suitable for envelope round-trip tests.
EVENT_SAMPLE_FACTORIES: dict[type[Event], Callable[[], Event]] = {}


def register_factory(
    event_type: type[Event],
) -> Callable[[Callable[[], Event]], Callable[[], Event]]:
    """Decorator that registers a factory for ``event_type``.

    Use as::

        @register_factory(MyEvent)
        def make_my_event() -> MyEvent:
            return MyEvent(field1="real", field2=Path("/var/data/x.mp4"))

    Args:
        event_type: The concrete ``Event`` subclass the factory produces.

    Returns:
        A no-op decorator that records the factory in
        ``EVENT_SAMPLE_FACTORIES``.

    Raises:
        ValueError: if a factory is already registered for ``event_type`` —
            two factories for one type would let later imports silently
            shadow earlier ones, masking test bugs.
    """

    def _decorator(factory: Callable[[], Event]) -> Callable[[], Event]:
        if event_type in EVENT_SAMPLE_FACTORIES:
            raise ValueError(
                f"Factory for {event_type.__name__} already registered "
                f"(previous: {EVENT_SAMPLE_FACTORIES[event_type]!r})",
            )
        EVENT_SAMPLE_FACTORIES[event_type] = factory
        return factory

    return _decorator


__all__ = ["EVENT_SAMPLE_FACTORIES", "register_factory"]
