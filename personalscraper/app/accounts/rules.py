"""The rules the account services share: the views a row maps to and the guards more than one use case applies."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, get_args

from personalscraper.app.accounts.account_repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.avatar import resolve_avatar
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.role_repository import RoleRow, StartKind
from personalscraper.app.accounts.views import AccountView, RoleView, SignInKind
from personalscraper.app.errors import AppBadRequest, AppForbidden, AppUnauthenticated, RefusalCode
from personalscraper.app.store.store import AppStore

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


def account_view(store: AppStore, account: AccountRow, actor: Actor) -> AccountView:
    """Map an account and its actor to the account's view.

    Args:
        store: The ``app`` store.
        account: The account.
        actor: The actor it signs in as (its role and ceiling).

    Returns:
        The view.

    Raises:
        AppUnauthenticated: ``auth.required`` — the account's role was deleted.
    """
    role = store.roles.role(actor.role_id)
    if role is None:
        raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
    link = store.accounts.plex_link(account.id)
    return AccountView(
        id=account.id,
        name=account.name,
        email=account.email,
        avatar=resolve_avatar(link, account.email),
        role=role_view(role),
        sign_in_kind=sign_in_kind(link),
        forbidden_writes=tuple(sorted(actor.ceiling.forbidden)),
        language=account.language,
    )


def is_email(email: str) -> bool:
    """Whether a text is an e-mail as the accounts screen accepts it: something on both sides of one ``@``.

    Args:
        email: The text, stripped.

    Returns:
        True when it is one.
    """
    local, at, domain = email.rpartition("@")
    return bool(at and local and domain and not any(char.isspace() for char in email))


def refuse_password_held_elsewhere(kind: SignInKind) -> None:
    """Refuse a password write on an account whose password the web does not hold.

    Args:
        kind: How the account signs in.

    Raises:
        AppForbidden: ``password.held_by_cli`` — the server owner's fallback, replaced
            by the CLI only; ``auth.plex_only`` — a Plex-linked account holds none.
    """
    if kind is SignInKind.OWNER:
        raise AppForbidden(
            "The server owner's fallback password is changed on the server only.",
            code=RefusalCode.PASSWORD_HELD_BY_CLI,
        )
    if kind is SignInKind.PLEX:
        raise AppForbidden("This account signs in with Plex.", code=RefusalCode.AUTH_PLEX_ONLY)


def rights_named(names: Sequence[str]) -> frozenset[Right]:
    """Read right names as rights.

    Args:
        names: The names.

    Returns:
        The rights.

    Raises:
        AppBadRequest: ``right.unknown`` — a name that is no right.
    """
    try:
        return frozenset(Right(name) for name in names)
    except ValueError:
        raise AppBadRequest("A right names nothing the server knows.", code=RefusalCode.RIGHT_UNKNOWN) from None


def within(actor: Actor, rights: frozenset[Right]) -> bool:
    """Whether rights are included in the actor's own role's (Admin includes every right).

    Measured against the role the actor's session resolved, as ``@requires`` authorised it.

    Args:
        actor: The caller.
        rights: The rights given.

    Returns:
        True when the caller may give them.
    """
    return actor.role_kind is RoleKind.ADMIN or rights <= actor.role_rights


def refuse_escalation(actor: Actor, role: RoleRow) -> None:
    """Refuse a caller who is not Admin putting an account on Admin, or on a role wider than its own.

    Args:
        actor: The caller.
        role: The role an account would hold.

    Raises:
        AppForbidden: ``role.escalation``.
    """
    if actor.role_kind is RoleKind.ADMIN:
        return
    if role.kind is RoleKind.ADMIN or not within(actor, role.rights):
        raise AppForbidden("The role holds rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION)
