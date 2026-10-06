"""The accounts' domain: a role, an account with its Plex link, the one who grants — and the rules they carry.

The services read the facts in one ``BEGIN IMMEDIATE`` transaction, ask these objects, then
write. Each ``check_*`` raises one refusal, or a fixed sequence of them; a service calls the
checks in the order its contract names, and no object ever reorders them.

The ids are typed (``AccountId``, ``RoleId``): a ``NewType`` costs nothing at runtime, so the
wire still carries a plain string, and mypy refuses an account id where a role id is due.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, NewType

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.rights import Right
from personalscraper.app.errors import AppBadRequest, AppConflict, AppForbidden, RefusalCode
from personalscraper.i18n import Language, configured_language

if TYPE_CHECKING:
    from personalscraper.app.accounts.actor import Actor

#: An account's key, ``account-<uuid4 hex>``.
AccountId = NewType("AccountId", str)

#: A role's key: a seed's id, or ``role-<uuid4 hex>``.
RoleId = NewType("RoleId", str)

#: Who starts on a role at a first sign-in or a link: a Plex Home member, a Plex guest. A local
#: account has none — its role is chosen at its creation.
StartKind = Literal["plexHome", "plexGuest"]


class SignInKind(StrEnum):
    """How an account signs in — a fact of the account, never of its role (the contract's ``SignInKind``)."""

    OWNER = "owner"
    PLEX = "plex"
    LOCAL = "local"


@dataclass(frozen=True)
class Role:
    """One role.

    Attributes:
        id: Its key: a seed's id, or ``role-<uuid4 hex>``.
        name: The text an Admin gave it; ``None`` while a seeded role was never renamed
            (the interface then shows the translation of its id).
        kind: ``admin`` (the one Admin role) or ``ordinary``.
        rights: The rights it carries; empty for Admin, which bypasses the list.
        default_for: The start kinds whose new accounts begin on it.
    """

    id: RoleId
    name: str | None
    kind: RoleKind
    rights: frozenset[Right]
    default_for: frozenset[StartKind] = frozenset()

    @property
    def is_admin(self) -> bool:
        """Whether it is the one Admin role."""
        return self.kind is RoleKind.ADMIN

    def check_mutable(self) -> None:
        """Refuse a change to the Admin role.

        Raises:
            AppConflict: ``role.system_immutable``.
        """
        if self.is_admin:
            raise AppConflict("The Admin role is not modified.", code=RefusalCode.ROLE_SYSTEM_IMMUTABLE)

    def check_deletable(self, *, holders: int) -> None:
        """Refuse the deletion of a role something depends on.

        Order: the Admin role; a role a newcomer starts on, even held by nobody (ruling A);
        a role an account holds.

        Args:
            holders: How many accounts hold it.

        Raises:
            AppConflict: ``role.system_immutable``, then ``role.default``, then ``role.in_use``.
        """
        if self.is_admin:
            raise AppConflict("The Admin role is never deleted.", code=RefusalCode.ROLE_SYSTEM_IMMUTABLE)
        if self.default_for:
            raise AppConflict("A newcomer starts on this role.", code=RefusalCode.ROLE_DEFAULT)
        if holders:
            raise AppConflict("An account holds this role.", code=RefusalCode.ROLE_IN_USE)


@dataclass(frozen=True)
class PlexLink:
    """An account's link to its plex.tv identity.

    Attributes:
        account_id: The linked account.
        plex_id: plex.tv's stable id — the identity, never the e-mail.
        plex_uuid: plex.tv's uuid.
        plex_username: plex.tv's username.
        server_access: ``owner`` of the managed server, or ``shared`` with it.
        token_ciphertext: The kept Plex token, encrypted; ``None`` when not kept.
        token_stored_at: When it was stored; ``None`` when not kept.
        linked_at: When the link was made.
        last_sign_in_at: The last Plex sign-in; ``None`` before the first.
    """

    account_id: AccountId
    plex_id: int
    plex_uuid: str
    plex_username: str
    server_access: Literal["owner", "shared"]
    token_ciphertext: bytes | None = field(repr=False)
    token_stored_at: float | None
    linked_at: float
    last_sign_in_at: float | None


def sign_in_kind(link: PlexLink | None) -> SignInKind:
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


@dataclass(frozen=True)
class Account:
    """One account, with its Plex link.

    Attributes:
        id: Its key, ``account-<uuid4 hex>``.
        name: Its display name.
        email: Its e-mail, as given; unique whatever its case.
        avatar: A stored picture address, ``""`` when none; never read — the picture is
            resolved from the Plex link and the e-mail (``accounts.avatar``).
        role_id: The role it holds.
        password_hash: ``scrypt$N$r$p$salt$hash``; ``None`` when it holds no password.
        created_at: Creation (epoch seconds).
        updated_at: Last change (epoch seconds).
        sign_in_allowed: Whether it may sign in; ``True`` until an Admin cuts it.
        demoted_from: The role it held before its Plex link dropped it to its Plex kind's
            starting role; ``None`` when not demoted, or once an Admin gave it a role.
        language: The language it is spoken to in; a new row starts in the project's
            configured language (the operator, 2026-10-05) until the account chooses.
        plex_link: Its link to its plex.tv identity, read with it; ``None`` when not linked.
    """

    id: AccountId
    name: str
    email: str
    avatar: str
    role_id: RoleId
    password_hash: str | None = field(repr=False)
    created_at: float
    updated_at: float
    sign_in_allowed: bool = True
    demoted_from: RoleId | None = None
    language: Language = field(default_factory=configured_language)
    plex_link: PlexLink | None = None

    @property
    def sign_in_kind(self) -> SignInKind:
        """How it signs in, from its Plex link."""
        return sign_in_kind(self.plex_link)

    def check_access_cut(self, *, by: AccountId) -> None:
        """Refuse cutting or giving back an access that is never cut.

        Order: the Plex server's owner, the fallback door; then the caller's own account.

        Args:
            by: The caller's account.

        Raises:
            AppForbidden: ``account.owner_access``, then ``account.own_access``.
        """
        if self.sign_in_kind is SignInKind.OWNER:
            raise AppForbidden("The server owner's access is never cut.", code=RefusalCode.ACCOUNT_OWNER_ACCESS)
        if self.id == by:
            raise AppForbidden("An Admin never cuts its own access.", code=RefusalCode.ACCOUNT_OWN_ACCESS)

    def check_leaves_admin(self, *, current: Role, target: Role, admins: int) -> None:
        """Refuse a role change that takes the Admin role from whom it must stay with.

        Order: the server owner's account never leaves the Admin role, whoever the caller —
        so the one who gives Admin back is never demoted; then one account stays on it.

        Args:
            current: The role it holds.
            target: The role it would be put on.
            admins: How many accounts hold the Admin role.

        Raises:
            AppForbidden: ``account.owner_admin`` — the target is not Admin and the account
                is the server owner's.
            AppConflict: ``account.last_admin`` — the account leaves Admin and holds its last seat.
        """
        if not target.is_admin and self.sign_in_kind is SignInKind.OWNER:
            raise AppForbidden(
                "The server owner's account never leaves the Admin role.", code=RefusalCode.ACCOUNT_OWNER_ADMIN
            )
        if current.is_admin and not target.is_admin and admins <= 1:
            raise AppConflict("No account would be left on the Admin role.", code=RefusalCode.ACCOUNT_LAST_ADMIN)

    def check_password_held_here(self) -> None:
        """Refuse a password write on an account whose password the web does not hold.

        Raises:
            AppForbidden: ``password.held_by_cli`` — the server owner's fallback, replaced
                by the CLI only; ``auth.plex_only`` — a Plex-linked account holds none.
        """
        kind = self.sign_in_kind
        if kind is SignInKind.OWNER:
            raise AppForbidden(
                "The server owner's fallback password is changed on the server only.",
                code=RefusalCode.PASSWORD_HELD_BY_CLI,
            )
        if kind is SignInKind.PLEX:
            raise AppForbidden("This account signs in with Plex.", code=RefusalCode.AUTH_PLEX_ONLY)


@dataclass(frozen=True)
class Grantor:
    """The acting side of an account or role change: the caller, and whether it owns the Plex server.

    Every measure of « within its own rights » is taken against the role the actor's session
    resolved, as ``@requires`` authorised it — not a role read again.

    Attributes:
        actor: The caller.
        is_owner: Whether the caller's account is the managed Plex server's owner.
    """

    actor: Actor
    is_owner: bool

    @classmethod
    def of(cls, actor: Actor, link: PlexLink | None) -> Grantor:
        """The grantor an actor is, from its own account's Plex link.

        Args:
            actor: The caller.
            link: The Plex link of the caller's account, or ``None``.

        Returns:
            The grantor.
        """
        return cls(actor=actor, is_owner=sign_in_kind(link) is SignInKind.OWNER)

    def _within(self, rights: frozenset[Right]) -> bool:
        """Whether rights are included in the actor's own role's (Admin includes every right).

        Args:
            rights: The rights given.

        Returns:
            True when the caller may give them.
        """
        return self.actor.role_kind is RoleKind.ADMIN or rights <= self.actor.role_rights

    def check_may_give(self, role: Role) -> None:
        """Refuse a caller who is not Admin putting an account on Admin, or on a role wider than its own.

        Args:
            role: The role an account would hold.

        Raises:
            AppForbidden: ``role.escalation``.
        """
        if self.actor.role_kind is RoleKind.ADMIN:
            return
        if role.is_admin or not self._within(role.rights):
            raise AppForbidden("The role holds rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION)

    def check_may_give_rights(self, rights: frozenset[Right]) -> None:
        """Refuse a caller putting on a role rights its own role does not hold.

        Args:
            rights: The rights the role would hold.

        Raises:
            AppForbidden: ``role.escalation``.
        """
        if not self._within(rights):
            raise AppForbidden("The role would hold rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION)

    def check_may_rename(self, role: Role) -> None:
        """Refuse a caller renaming a role whose rights its own does not include.

        Args:
            role: The role renamed.

        Raises:
            AppForbidden: ``role.escalation``.
        """
        if not self._within(role.rights):
            raise AppForbidden("A manager renames only a role within its own rights.", code=RefusalCode.ROLE_ESCALATION)

    def check_may_give_admin(self) -> None:
        """Refuse the Admin role given by anyone but the managed Plex server's owner (the operator, 2026-10-04).

        Raises:
            AppForbidden: ``account.admin_owner_only``.
        """
        if not self.is_owner:
            raise AppForbidden(
                "Only the server's owner gives the Admin role.", code=RefusalCode.ACCOUNT_ADMIN_OWNER_ONLY
            )

    def check_may_change_role(self, role: Role) -> None:
        """Refuse a caller who is not Admin touching its own role.

        Args:
            role: The role changed.

        Raises:
            AppForbidden: ``role.own_role``.
        """
        if self.actor.role_kind is not RoleKind.ADMIN and role.id == self.actor.role_id:
            raise AppForbidden("A manager never touches its own role.", code=RefusalCode.ROLE_OWN_ROLE)

    def check_may_touch(self, account: Account, current: Role, target: Role) -> None:
        """Refuse a caller who is not Admin touching its own account, or Admin.

        Args:
            account: The account put on a role.
            current: The role it holds.
            target: The role it would be put on.

        Raises:
            AppForbidden: ``role.own_role``, then ``account.admin_untouchable``; never for an Admin.
        """
        if self.actor.role_kind is RoleKind.ADMIN:
            return
        if account.id == self.actor.account_id:
            raise AppForbidden("A manager never touches its own role.", code=RefusalCode.ROLE_OWN_ROLE)
        if current.is_admin or target.is_admin:
            raise AppForbidden(
                "A manager who is not Admin never touches Admin.", code=RefusalCode.ACCOUNT_ADMIN_UNTOUCHABLE
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
