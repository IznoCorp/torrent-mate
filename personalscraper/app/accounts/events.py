"""The accounts' domain events: E8, an account's rights moved."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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
