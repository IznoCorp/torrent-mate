"""What the account services answer; the v1 models map these, field for field.

Plain frozen dataclasses: no transport type and no interface text. A role's name is
``None`` while a seeded role was never renamed (the interface shows its id's translation);
an account's avatar is ``None`` when it has none.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, get_args

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.avatar import resolve_avatar
from personalscraper.app.accounts.model import Account, Role, SignInKind, StartKind
from personalscraper.app.accounts.rights import Right
from personalscraper.app.errors import AppUnauthenticated, RefusalCode
from personalscraper.i18n import Language

if TYPE_CHECKING:
    from personalscraper.app.store.store import AppStore

# ``Language`` and ``SignInKind`` are part of what the services answer (``AccountView.language``,
# ``sign_in_kind``): the v1 models take them from here, since ``http_v1`` reaches the engine only
# through ``app/``.
__all__ = [
    "AccountSummaryView",
    "AccountView",
    "Language",
    "RoleView",
    "RosterView",
    "SignInKind",
    "account_view",
    "role_view",
]

#: The contract's order of the start kinds (``Role.defaultFor``).
_START_ORDER: Final[tuple[StartKind, ...]] = get_args(StartKind)


@dataclass(frozen=True)
class RoleView:
    """One role.

    Attributes:
        id: Its key.
        name: The name an Admin gave it; ``None`` on a seeded role never renamed.
        kind: ``admin`` or ``ordinary``.
        rights: The rights it carries, sorted; ``()`` for Admin, which bypasses the list.
        default_for: The start kinds whose new accounts begin on it, in the contract's order.
    """

    id: str
    name: str | None
    kind: RoleKind
    rights: tuple[Right, ...]
    default_for: tuple[StartKind, ...]


@dataclass(frozen=True)
class AccountView:
    """The signed-in account, as ``readAccount`` answers it.

    Attributes:
        id: Its key.
        name: Its display name.
        email: Its e-mail.
        avatar: Its picture's address — its Plex avatar, else its Gravatar
            (``accounts.avatar``); ``None`` when it has neither.
        role: Its one role.
        sign_in_kind: How it signs in.
        forbidden_writes: The instance's forbidden writes, sorted (the ceiling, Admin included).
        language: The language it is spoken to in.
    """

    id: str
    name: str
    email: str
    avatar: str | None
    role: RoleView
    sign_in_kind: SignInKind
    forbidden_writes: tuple[Right, ...]
    language: Language


@dataclass(frozen=True)
class AccountSummaryView:
    """One account of the roster.

    Attributes:
        id: Its key.
        name: Its display name.
        email: Its e-mail.
        role: Its one role.
        sign_in_kind: How it signs in.
        sign_in_allowed: Whether it may sign in.
        demoted_from: The role it held before its Plex link demoted it; ``None`` when
            not demoted (nothing demotes an account before the Plex link exists).
    """

    id: str
    name: str
    email: str
    role: RoleView
    sign_in_kind: SignInKind
    sign_in_allowed: bool
    demoted_from: str | None = None


@dataclass(frozen=True)
class RosterView:
    """Every account and every role.

    Attributes:
        accounts: The accounts.
        roles: The roles.
    """

    accounts: tuple[AccountSummaryView, ...]
    roles: tuple[RoleView, ...]


def role_view(role: Role) -> RoleView:
    """Map a role to its view.

    Args:
        role: The role.

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


def account_view(store: AppStore, account: Account, actor: Actor) -> AccountView:
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
    return AccountView(
        id=account.id,
        name=account.name,
        email=account.email,
        avatar=resolve_avatar(account.plex_link, account.email),
        role=role_view(role),
        sign_in_kind=account.sign_in_kind,
        forbidden_writes=tuple(sorted(actor.ceiling.forbidden)),
        language=account.language,
    )
