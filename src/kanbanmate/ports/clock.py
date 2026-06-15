"""Clock port: the wall-clock boundary.

The polling loop, heartbeat refresh, and adaptive interval strategy all need
the current time. Reading the clock through a Protocol keeps the functional
core and the imperative shell deterministic under test: production injects a
``time.time``-backed adapter, tests inject a frozen or scripted clock.
"""

from __future__ import annotations

from typing import Protocol


class Clock(Protocol):
    """A source of the current wall-clock time."""

    def now(self) -> float:
        """Return the current time as a POSIX timestamp.

        Returns:
            Seconds since the Unix epoch (the value compared against persisted
            heartbeats and used to age rate-limit windows).
        """
        ...
