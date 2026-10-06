"""The accounts' domain events: E8, an account's rights moved; a session a Plex sign-in opened."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from personalscraper.app.accounts.ids import AccountId
from personalscraper.core.event_bus import Event


class RightsChangeCause(StrEnum):
    """Why an account's rights moved."""

    ROLE_ASSIGNED = "role_assigned"
    ROLE_RIGHTS_CHANGED = "role_rights_changed"
    ROLE_RENAMED = "role_renamed"
    PLEX_LINKED = "plex_linked"


@dataclass(frozen=True, kw_only=True)
class AccountRightsChanged(Event):
    """E8: the rights, or the role, of some accounts moved; each re-reads its own account.

    Published after the write commits, never on a refused one. It names only the
    accounts touched, so a relay can deliver it to their sessions alone.

    Attributes:
        account_ids: The accounts whose role or rights moved, in creation order.
        cause: Why they moved.
    """

    account_ids: tuple[str, ...]
    cause: RightsChangeCause


@dataclass(frozen=True, kw_only=True)
class PlexSessionOpened(Event):
    """A Plex sign-in opened a new session: its holder is told where (ruling Q4 A).

    Published once the session is open, never for a renewal of a session already open nor
    for a refused sign-in. A Plex sign-in can be phished — whoever has a person confirm a PIN
    signs in as them — so the account hears of every new session, and can end it.

    Attributes:
        account_id: The account signed in.
        device: The browser and system the session's user agent names; ``None`` when it names neither.
    """

    account_id: AccountId
    device: str | None
