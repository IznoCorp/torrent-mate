"""``AppServices``: every application service one process uses.

The CLI and the web build the same one (Q11), through
:func:`personalscraper.app.composition.build_app_services`. Each lot adds one
field and its builder line.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.app.accounts import events as _accounts_events  # noqa: F401 — registers E8 (AccountRightsChanged)
from personalscraper.app.accounts.credentials import CredentialService
from personalscraper.app.accounts.own_sessions import OwnSessionService
from personalscraper.app.accounts.plex_sign_in import PlexSignInService
from personalscraper.app.accounts.roles import RoleService
from personalscraper.app.accounts.roster import RosterService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.build_info import BuildInfo
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor import (
    events as _supervisor_events,  # noqa: F401 — registers RunQueued, RunAdmitted, RunSettled
)
from personalscraper.app.supervisor.service import RunService
from personalscraper.core.event_bus import EventBus

if TYPE_CHECKING:
    from personalscraper.app.composition import LazyProviders
    from personalscraper.app.library.completeness import CatalogueView
    from personalscraper.app.library.deleting import LibraryDeletion
    from personalscraper.app.library.reads import LibraryReads
    from personalscraper.app.library.rescrape import LibraryRescrape
    from personalscraper.app.library.sheets import MediaSheets


@dataclass(frozen=True)
class AppServices:
    """The application services of one process.

    Attributes:
        event_bus: The process's bus; a service publishes its domain events on it
            after its write commits. No publisher is attached yet.
        build_info: The build this process serves (``readVersion``).
        library: The library's listing and membership reads over the index and the aired catalogue.
        sheets: A medium's sheet and poster, over the index, the catalogue and the providers.
        rescrape: A medium's rescrape, launched through the maintenance path.
        deletion: A medium's deletion: its folders, its index rows and its Plex entry.
        catalogue_view: The aired catalogue and the ownership checker the reads and the sheets
            share; it owns them and closes them.
        app_store: The environment's ``app.db``, opened on first use.
        sessions: v1's sessions.
        accounts: The own account and the roster of accounts.
        roles: The roles of the accounts screen.
        credentials: The sign-in doors' shared end, the passwords and the owner's machine acts.
        plex_sign_in: The Plex door.
        own_sessions: The signed-in account's own sessions, listed and revoked.
        runs: The in-process enqueue of a run or an item rescrape.
        owned_providers: The provider registry these services built for themselves, closed
            with them; ``None`` when the process handed its own over, which its owner closes.
    """

    event_bus: EventBus
    build_info: BuildInfo
    library: LibraryReads
    sheets: MediaSheets
    rescrape: LibraryRescrape
    deletion: LibraryDeletion
    catalogue_view: CatalogueView
    app_store: AppStore
    sessions: SessionService
    accounts: RosterService
    roles: RoleService
    credentials: CredentialService
    plex_sign_in: PlexSignInService
    own_sessions: OwnSessionService
    runs: RunService
    owned_providers: LazyProviders | None = None

    def close(self) -> None:
        """Release what the services hold: the catalogue view, ``app.db`` and their own registry, if opened.

        Called once, from the web parent's lifespan (Starlette never runs a mounted
        sub-application's lifespan); a lot adding a store or a publisher closes it here.
        """
        self.catalogue_view.close()
        self.app_store.close()
        if self.owned_providers is not None:
            self.owned_providers.close()
