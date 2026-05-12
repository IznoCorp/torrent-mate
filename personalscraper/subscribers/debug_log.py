"""DebugLogSubscriber — verbose event stream for operator debugging.

Subscribes once to :class:`Event`; the bus's MRO walk routes every concrete
subclass to ``on_event``, which logs the JSON-safe payload (``event_to_dict``,
no ``_type`` discriminator) at DEBUG via structlog. Wired by
``personalscraper run --verbose`` (Sub-phase 5.4).
"""

from __future__ import annotations

from personalscraper.core.event_bus import Event, EventBus, SubscriptionToken, event_to_dict
from personalscraper.logger import get_logger

_log = get_logger("debug_log_subscriber")


class DebugLogSubscriber:
    """Pipeline subscriber that logs every event at DEBUG level."""

    name = "debug-log"

    def __init__(self, bus: EventBus) -> None:
        """Register a single ``Event`` subscription and store the token."""
        self._bus = bus
        self._token: SubscriptionToken = bus.subscribe(Event, self.on_event)

    def on_event(self, event: Event) -> None:
        """Log one event emit at DEBUG with the JSON-safe envelope."""
        _log.debug(
            "event_emitted",
            event_type=type(event).__name__,
            event_id=str(event.event_id),
            correlation_id=event.correlation_id,
            source=event.source,
            payload=event_to_dict(event),
        )

    def close(self) -> None:
        """Unsubscribe so the subscriber stops receiving events."""
        self._bus.unsubscribe(self._token)
