"""``AccountService``: the account operations a signed-in actor asks for."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Final, get_args

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.repository import AccountRepository, PlexLinkRow, RoleRow, StartKind
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.accounts.views import AccountView, RoleView, SignInKind
from personalscraper.app.errors import AppUnauthenticated, RefusalCode
from personalscraper.core.event_bus import EventBus

#: The contract's order of the start kinds (``Role.defaultFor``).
_START_ORDER: Final[tuple[StartKind, ...]] = get_args(StartKind)


def role_view(role: RoleRow) -> RoleView:
    """Map a role row to its view.

    Args:
        role: The row.

    Returns:
        The view, rights sorted, start kinds in the contract's order.
    """
    return RoleView(
        id=role.id,
        name=role.name,
        kind=role.kind,
        rights=tuple(sorted(role.rights)),
        default_for=tuple(start for start in _START_ORDER if start in role.default_for),
    )


def sign_in_kind(link: PlexLinkRow | None) -> SignInKind:
    """How an account signs in, from its Plex link.

    Args:
        link: The account's Plex link, or ``None``.

    Returns:
        ``owner`` for the managed server's owner, ``plex`` for any other linked
        account, ``local`` for an account with no link.
    """
    if link is None:
        return SignInKind.LOCAL
    return SignInKind.OWNER if link.server_access == "owner" else SignInKind.PLEX


class AccountService:
    """Reads and acts on accounts for a signed-in actor."""

    def __init__(
        self,
        repo_factory: Callable[[], AccountRepository],
        sessions: SessionService,
        bus: EventBus,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            repo_factory: Returns the account repository (opening ``app.db`` on first use).
            sessions: The session service.
            bus: The bus the service publishes its domain events on, after a write commits.
            clock: The epoch clock.
        """
        self._repo_factory = repo_factory
        self._sessions = sessions
        self._bus = bus
        self._clock = clock

    def read_account(self, actor: Actor) -> AccountView:
        """The signed-in account, its role and the instance's forbidden writes.

        Args:
            actor: The signed-in actor.

        Returns:
            The account's view; ``forbidden_writes`` is the actor's ceiling, sorted.

        Raises:
            AppUnauthenticated: ``auth.required`` — the account or its role was deleted
                since the session was resolved.
        """
        repo = self._repo_factory()
        account = repo.account(actor.account_id)
        role = repo.role(actor.role_id)
        if account is None or role is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        return AccountView(
            id=account.id,
            name=account.name,
            email=account.email,
            avatar=account.avatar or None,
            role=role_view(role),
            sign_in_kind=sign_in_kind(repo.plex_link(account.id)),
            forbidden_writes=tuple(sorted(actor.ceiling.forbidden)),
        )

    def sign_out(self, actor: Actor, token: str) -> None:
        """Close the session the actor signed in with.

        Args:
            actor: The signed-in actor (the perimeter resolved it from ``token``).
            token: The session's cookie value.
        """
        self._sessions.close(token)
