"""``AppServices``: every application service one process uses.

The CLI and the web build the same one (Q11), through
:func:`personalscraper.app.composition.build_app_services`. Each lot adds one
field and its builder line.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.app.accounts.service import AccountService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.build_info import BuildInfo
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus

if TYPE_CHECKING:
    from personalscraper.app.library.service import LibraryService


@dataclass(frozen=True)
class AppServices:
    """The application services of one process.

    Attributes:
        event_bus: The process's bus; a service publishes its domain events on it
            after its write commits. No publisher is attached yet.
        build_info: The build this process serves (``readVersion``).
        library: The library's reads over the index, the aired catalogue and the providers.
        app_store: The environment's ``app.db``, opened on first use.
        sessions: v1's sessions.
        accounts: The account operations.
    """

    event_bus: EventBus
    build_info: BuildInfo
    library: LibraryService
    app_store: AppStore
    sessions: SessionService
    accounts: AccountService

    def close(self) -> None:
        """Release what the services hold: the library's readers and the ``app.db`` connection, if opened.

        Called once, from the web parent's lifespan (Starlette never runs a mounted
        sub-application's lifespan); a lot adding a store or a publisher closes it here.
        """
        self.library.close()
        self.app_store.close()
