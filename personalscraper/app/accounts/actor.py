"""The actor: who acts, through which role, under which ceiling.

``holds`` is the maquette's ``rightsOf`` and ``is_requester`` its ``isOwn``
(``webui/design/src/lib/rights.ts``): one derivation, read by the
perimeter and by every service that filters by right or by membership.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import Right

#: The role id the system actor carries: the indelible Admin role's key.
SYSTEM_ROLE_ID: Final[str] = "admin"


class RoleKind(StrEnum):
    """The contract's role kinds: the one Admin role and every other one."""

    ADMIN = "admin"
    ORDINARY = "ordinary"


@dataclass(frozen=True)
class Actor:
    """The account a request or an unattended job acts as.

    Attributes:
        account_id: The account's key — what a requester list names it by.
        name: The account's display name.
        role_id: The key of the role it holds (one role per account).
        role_kind: The role's kind; ``admin`` bypasses the rights list.
        role_rights: The rights the role carries (empty for Admin).
        ceiling: The instance's ceiling, subtracted before the role adds.
    """

    account_id: str
    name: str
    role_id: str
    role_kind: RoleKind
    role_rights: frozenset[Right]
    ceiling: InstanceCeiling

    def holds(self, right: Right) -> bool:
        """Whether the actor holds one right.

        Args:
            right: The right asked about.

        Returns:
            True when the ceiling does not forbid it and the role is Admin or carries it.
        """
        if right in self.ceiling.forbidden:
            return False
        return self.role_kind is RoleKind.ADMIN or right in self.role_rights

    def holds_any(self, rights: Iterable[Right]) -> bool:
        """Whether the actor holds at least one of several rights.

        Args:
            rights: The rights asked about.

        Returns:
            True when any one is held.
        """
        return any(self.holds(right) for right in rights)

    def is_requester(self, requester_ids: Iterable[str]) -> bool:
        """Whether an acquisition is the actor's own to act on (§ 17's own tunnel).

        Args:
            requester_ids: The account keys of the acquisition's requesters.

        Returns:
            True when the actor holds ``acquisition.pilot.any`` or is among the requesters.
        """
        if self.holds(Right.ACQUISITION_PILOT_ANY):
            return True
        return self.account_id in requester_ids

    @classmethod
    def system(cls, ceiling: InstanceCeiling, *, account_id: str, name: str) -> Actor:
        """The actor of an in-process client with no session: the CLI, the schedulers.

        What the engine does unattended is attributed to an account (ruling 9: the
        Plex server's owner, else the first Admin); the caller names it.

        Args:
            ceiling: The instance's ceiling, which binds the system too.
            account_id: The account the acts are attributed to.
            name: That account's display name.

        Returns:
            An Admin actor, with no rights list, under ``ceiling``.
        """
        return cls(
            account_id=account_id,
            name=name,
            role_id=SYSTEM_ROLE_ID,
            role_kind=RoleKind.ADMIN,
            role_rights=frozenset(),
            ceiling=ceiling,
        )
