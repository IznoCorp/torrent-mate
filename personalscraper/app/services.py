"""``AppServices``: every application service one process uses.

The CLI and the web build the same one (Q11), through
:func:`personalscraper.app.composition.build_app_services`. Each lot adds one
field and its builder line.
"""

from __future__ import annotations

from dataclasses import dataclass

from personalscraper.core.event_bus import EventBus


@dataclass(frozen=True)
class AppServices:
    """The application services of one process.

    Attributes:
        event_bus: The process's bus; a service publishes its domain events on it
            after its write commits. No publisher is attached yet.
    """

    event_bus: EventBus

    def close(self) -> None:
        """Release what the services hold: nothing is opened yet, so nothing is released.

        Called once, from the web parent's lifespan (Starlette never runs a mounted
        sub-application's lifespan); a lot adding a store or a publisher closes it here.
        """
