"""Test fixtures for the EventBus.

Two helpers are exposed:

- ``assert_event_round_trip`` (Sub-phase 1.6): field-by-field equality with a
  1µs timestamp tolerance — round-trip tests cannot use dataclass ``__eq__``
  because the ISO-8601 microsecond rounding leaves ≤1µs residuals.
- ``CollectingSubscriber`` (Sub-phase 1.8): generic subscribe-on-construction
  helper that records every event of its type in ``received``. Supports
  context-manager semantics for auto-close.
"""

from __future__ import annotations

from dataclasses import fields
from types import TracebackType
from typing import Generic, TypeVar

from personalscraper.core.event_bus import Event, EventBus, SubscriptionToken

E = TypeVar("E", bound=Event)

# 1 µs — ISO-8601 ``isoformat`` / ``fromisoformat`` rounding residual bound.
_TIMESTAMP_TOLERANCE_SECONDS = 1e-6


def assert_event_round_trip(original: Event, reconstructed: Event) -> None:
    """Field-by-field equality, tolerating ≤1µs ``timestamp`` drift.

    Required because dataclass ``__eq__`` compares all fields strictly;
    ISO-8601 µs rounding makes raw ``==`` on ``timestamp`` flaky.
    """
    assert type(original) is type(reconstructed), (
        f"type mismatch: {type(original).__name__} vs {type(reconstructed).__name__}"
    )
    for f in fields(original):
        ov = getattr(original, f.name)
        rv = getattr(reconstructed, f.name)
        if f.name == "timestamp":
            drift = abs((rv - ov).total_seconds())
            assert drift <= _TIMESTAMP_TOLERANCE_SECONDS, (
                f"timestamp drift {drift}s exceeds tolerance {_TIMESTAMP_TOLERANCE_SECONDS}s"
            )
        else:
            assert ov == rv, f"field {f.name!r}: {ov!r} != {rv!r}"


class CollectingSubscriber(Generic[E]):
    """Subscribe on construction; record every emit in ``received``.

    Use as a context manager for auto-close. Pass ``event_type=Event`` (the
    default) to catch every subclass via the bus's MRO walk.
    Generic[E] (not PEP 695) keeps Python 3.10 compatibility.
    """

    def __init__(self, bus: EventBus, event_type: type[E] = Event) -> None:  # type: ignore[assignment]
        """Subscribe to ``event_type`` on ``bus`` immediately."""
        self._bus = bus
        self.received: list[E] = []
        self._token: SubscriptionToken | None = bus.subscribe(event_type, self._on_event)

    def _on_event(self, event: Event) -> None:
        """Internal subscriber — appends to ``received``."""
        # Bus MRO walk guarantees the type matches; Generic narrows the list.
        self.received.append(event)  # type: ignore[arg-type]

    def close(self) -> None:
        """Unsubscribe (idempotent — safe to call repeatedly)."""
        if self._token is not None:
            self._bus.unsubscribe(self._token)
            self._token = None

    def __enter__(self) -> CollectingSubscriber[E]:
        """Context-manager entry — already subscribed."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context-manager exit — auto-closes."""
        self.close()
