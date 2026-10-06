"""``RoleService``: the roles of the accounts screen — create, rename or re-right, delete.

Every method is authorised by ``@requires`` before it reads a row.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.model import Grantor, Role, RoleId, rights_named
from personalscraper.app.accounts.views import RoleView, role_view
from personalscraper.app.errors import AppBadRequest, AppConflict, AppNotFound, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("app.accounts.roles")


def _refuse_name_taken(store: AppStore, name: str, *, except_id: RoleId | None) -> None:
    """Refuse a role name another role carries, compared trimmed and regardless of case.

    Case is folded by ``str.lower`` — Unicode's default lowercase mapping, the very one
    the maquette's ``toLowerCase`` applies — never ``casefold``, which would make
    « STRASSE » and « straße » one name here and two there. A seeded role never renamed
    carries no name (its words are the interface's), so it takes none.

    Args:
        store: The ``app`` store.
        name: The name asked for, trimmed.
        except_id: The role being renamed, which may keep its own name; ``None`` at creation.

    Raises:
        AppConflict: ``role.name_taken``.
    """
    wanted = name.lower()
    for role in store.roles.roles():
        if role.id != except_id and role.name is not None and role.name.strip().lower() == wanted:
            raise AppConflict("Another role already carries this name.", code=RefusalCode.ROLE_NAME_TAKEN)


def _grantor(store: AppStore, actor: Actor) -> Grantor:
    """The caller as the one who gives rights, read in the transaction.

    Args:
        store: The ``app`` store.
        actor: The caller.

    Returns:
        The grantor, owner of the managed Plex server or not.
    """
    return Grantor.of(actor, store.accounts.plex_link(actor.account_id))


class RoleService:
    """Creates, changes and deletes roles for a signed-in actor."""

    def __init__(
        self,
        store: AppStore,
        bus: EventBus,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            bus: The bus the service publishes its domain events on, after a write commits.
            clock: The epoch clock.
        """
        self._store = store
        self._bus = bus
        self._clock = clock

    @requires("createRole")
    def create_role(self, actor: Actor, *, name: str, rights: Sequence[str]) -> RoleView:
        """Create an ordinary role under the name typed; nothing is published (no account holds it yet).

        Order of the refusals (the maquette's): the rights named; the name, required and
        free; the escalation. The name check and the insert are one ``BEGIN IMMEDIATE``
        transaction, so two creations cannot both take one name.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            name: Its name, trimmed; none is ever made up for it (the operator, 2026-10-04).
            rights: The rights it carries.

        Returns:
            The new role.

        Raises:
            AppBadRequest: ``right.unknown`` — a name that is no right; ``role.name_required``
                — a blank name.
            AppConflict: ``role.name_taken`` — another role carries the name, compared
                trimmed and regardless of case.
            AppForbidden: ``role.escalation`` — a caller who is not Admin gives rights its
                own role does not hold.
        """
        held = rights_named(rights)
        typed = name.strip()
        if not typed:
            raise AppBadRequest("A role carries the name the manager typed.", code=RefusalCode.ROLE_NAME_REQUIRED)
        role = Role(id=RoleId(f"role-{uuid.uuid4().hex}"), name=typed, kind=RoleKind.ORDINARY, rights=held)
        store = self._store
        with store.immediate():
            _refuse_name_taken(store, typed, except_id=None)
            _grantor(store, actor).check_may_give_rights(held)
            store.roles.insert_role(role, now=self._clock())
        log.info("role_created", role_id=role.id, by=actor.account_id)
        return role_view(role)

    @requires("updateRole")
    def update_role(
        self, actor: Actor, role_id: str, *, name: str | None = None, rights: Sequence[str] | None = None
    ) -> RoleView:
        """Rename a role or set its rights; E8 names its accounts once the change commits.

        The Admin role is never modified. A caller who is not Admin never touches its own
        role, never gives rights its own does not hold, and renames only a role whose
        rights its own holds. A blank name is ignored; a name another role carries is refused,
        the role's own kept in any case. A change that moves nothing
        publishes nothing; a role nobody holds publishes nothing.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            role_id: The role.
            name: Its new name; ``None`` keeps it.
            rights: Its new rights, replacing the list whole; ``None`` keeps them.

        Returns:
            The role as it now stands.

        Raises:
            AppBadRequest: ``right.unknown``.
            AppNotFound: ``role.unknown``.
            AppConflict: ``role.system_immutable`` — the Admin role; ``role.name_taken`` —
                another role carries the new name, compared trimmed and regardless of case.
            AppForbidden: ``role.own_role``, ``role.escalation``.
        """
        held = rights_named(rights) if rights is not None else None
        new_name = name.strip() if name is not None and name.strip() else None
        store = self._store
        with store.immediate():
            role = store.roles.role(RoleId(role_id))
            if role is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            role.check_mutable()
            grantor = _grantor(store, actor)
            grantor.check_may_change_role(role)
            if held is not None:
                grantor.check_may_give_rights(held)
            if name is not None:
                grantor.check_may_rename(role)
            if new_name is not None:
                _refuse_name_taken(store, new_name, except_id=role.id)
            rights_moved = held is not None and held != role.rights
            renamed = new_name is not None and new_name != role.name
            if rights_moved or renamed:
                store.roles.update_role(
                    role.id,
                    name=new_name if renamed else None,
                    rights=held if rights_moved else None,
                    now=self._clock(),
                )
            holders = tuple(store.accounts.accounts_on_role(role.id))
            updated = store.roles.role(role.id)
        assert updated is not None  # the transaction above read and kept it
        if rights_moved or renamed:
            log.info("role_updated", role_id=role.id, rights_moved=rights_moved, renamed=renamed, by=actor.account_id)
        if (rights_moved or renamed) and holders:
            cause = RightsChangeCause.ROLE_RIGHTS_CHANGED if rights_moved else RightsChangeCause.ROLE_RENAMED
            self._bus.emit(AccountRightsChanged(account_ids=holders, cause=cause))
        return role_view(updated)

    @requires("deleteRole")
    def delete_role(self, actor: Actor, role_id: str) -> None:
        """Delete a role nothing depends on; nothing is published (no account held it).

        Order of the refusals (the contract's): the role; the Admin role; a role a
        newcomer starts on, even held by nobody (ruling A); a role an account holds; to a
        caller who is not Admin, a role whose rights its own does not include. The checks
        and the delete are one ``BEGIN IMMEDIATE`` transaction, so an account put on the
        role meanwhile is seen.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            role_id: The role.

        Raises:
            AppNotFound: ``role.unknown``.
            AppConflict: ``role.system_immutable`` — the Admin role; ``role.default`` — a
                newcomer starts on it; ``role.in_use`` — an account holds it.
            AppForbidden: ``role.escalation``.
        """
        store = self._store
        with store.immediate():
            role = store.roles.role(RoleId(role_id))
            if role is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            role.check_deletable(holders=len(store.accounts.accounts_on_role(role.id)))
            _grantor(store, actor).check_may_give(role)
            store.roles.delete_role(role.id)
        log.info("role_deleted", role_id=role_id, by=actor.account_id)
