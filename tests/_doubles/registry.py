"""Shared ProviderRegistry test doubles with a single behavioural contract.

Only doubles that are behaviourally identical across every consuming tier live
here.  The two EventBus doubles below were previously copy-pasted into both the
unit and the integration registry conftests (and cross-imported by a fan-out
integration test); they record / raise unconditionally, so there is exactly one
contract to share.

The *capability* fakes (``FakeSearchable``, ``FakeRating``, ``FakeArtwork`` …)
are intentionally NOT hoisted here: the unit copies return ``None`` on a miss
(capability-semantics tests) while the integration copies raise ``ApiError``
(circuit-breaker resilience tests).  Those are genuinely different contracts and
must stay local to their tier — see the package docstring.
"""

from __future__ import annotations


class MockEventBus:
    """In-memory EventBus that records emitted events without dispatching.

    Attributes:
        emitted: List of every event passed to ``emit()``.
    """

    def __init__(self) -> None:
        """Initialize an empty emitted-events list."""
        self.emitted: list[object] = []

    def emit(self, event: object) -> None:
        """Append ``event`` to ``self.emitted`` without further dispatch.

        Args:
            event: The event payload to record.
        """
        self.emitted.append(event)


class FailingEventBus:
    """EventBus that raises on every ``emit()`` call.

    Used to verify the registry's ``_event_bus_safe_emit`` swallows failures
    without propagating.
    """

    def emit(self, event: object) -> None:
        """Raise to simulate a bus implementation that has failed.

        Args:
            event: Ignored — this bus never accepts events.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("event bus is broken")
