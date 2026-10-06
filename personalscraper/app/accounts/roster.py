"""``RosterService``: the own account and the accounts screen's roster of accounts.

Every method taking an actor is authorised by ``@requires`` before it reads a row.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import replace

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.model import Account, Grantor, Role, is_email
from personalscraper.app.accounts.passwords import hash_password, policy_refusal
from personalscraper.app.accounts.views import (
    AccountSummaryView,
    AccountView,
    RosterView,
    account_view,
    role_view,
)
from personalscraper.app.errors import (
    AppBadRequest,
    AppConflict,
    AppForbidden,
    AppNotFound,
    AppUnauthenticated,
    RefusalCode,
)
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus
from personalscraper.i18n import Language
from personalscraper.logger import get_logger

log = get_logger("app.accounts.roster")


def _provisional_refusal(password: str | None) -> AppBadRequest | None:
    """Why a provisional password is refused, if it is.

    Args:
        password: The password the Admin typed; ``None`` when absent.

    Returns:
        ``password.required`` (absent or empty), the policy's ``password.too_short`` /
        ``password.too_weak`` with its ``minimum``, or ``None`` when it meets the policy.
    """
    if not password:
        return AppBadRequest("A local account starts with a provisional password.", code=RefusalCode.PASSWORD_REQUIRED)
    return policy_refusal(password)


def _grantor(store: AppStore, actor: Actor) -> Grantor:
    """The caller as the one who gives a role, read in the transaction.

    Args:
        store: The ``app`` store.
        actor: The caller.

    Returns:
        The grantor, owner of the managed Plex server or not.
    """
    return Grantor.of(actor, store.accounts.plex_link(actor.account_id))


class RosterService:
    """Reads and acts on accounts for a signed-in actor."""

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

    @requires("readAccount")
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
        store = self._store
        account = store.accounts.account(actor.account_id)
        if account is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        return account_view(store, account, actor)

    @requires("setOwnLanguage")
    def set_own_language(self, actor: Actor, language: Language) -> AccountView:
        """Set the language the signed-in account is spoken to in — its own row, and no other.

        A session act like the password change: no right to name; the read-only instance
        refuses it, authorised by ``@requires`` (the rights table's ``SignedIn(write=True)``).

        Args:
            actor: The signed-in actor.
            language: The language chosen.

        Returns:
            The account, as now held.

        Raises:
            AppUnauthenticated: ``auth.required`` — the account was deleted since the session
                was resolved.
        """
        store = self._store
        with store.immediate():
            account = store.accounts.account(actor.account_id)
            if account is None:
                raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
            store.accounts.set_language(account.id, language, now=self._clock())
            view = account_view(store, replace(account, language=language), actor)
        log.info("account_language_set", account_id=account.id, language=language.value)
        return view

    @requires("resetAccountPassword")
    def reset_account_password(self, actor: Actor, account_id: str, *, password: str) -> None:
        """Give a local account a provisional password — an Admin's act; its sessions end.

        The Admin check comes first: a caller who is not Admin never learns whether an
        account exists. Then the caller's own account, which an Admin changes in Profil with
        its current password (the operator, 2026-10-04); the account; who holds its
        password; the provisional password's own refusals. scrypt runs before the writer lock is taken, and only for
        a password that will be kept. The password is set and every session of the account is revoked in one
        ``BEGIN IMMEDIATE`` transaction, so a session opened with the old password is refused on its next request.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            account_id: The account.
            password: The provisional password; only its scrypt hash is kept.

        Raises:
            AppForbidden: ``password.reset_admin_only`` — the caller's role is not Admin,
                whatever the account, its own included; ``password.reset_own`` — an Admin's
                own account; ``password.held_by_cli``, ``auth.plex_only``.
            AppNotFound: ``account.unknown``.
            AppBadRequest: ``password.required`` / ``password.too_short`` /
                ``password.too_weak`` (``params.minimum``).
        """
        if actor.role_kind is not RoleKind.ADMIN:
            raise AppForbidden("Only an Admin resets a password.", code=RefusalCode.PASSWORD_RESET_ADMIN_ONLY)
        if account_id == actor.account_id:
            raise AppForbidden(
                "An Admin changes its own password with its current one.", code=RefusalCode.PASSWORD_RESET_OWN
            )
        password_refusal = _provisional_refusal(password)
        password_hash = hash_password(password) if password_refusal is None else None
        store = self._store
        with store.immediate():
            account = store.accounts.account(AccountId(account_id))
            if account is None:
                raise AppNotFound("No account answers this identity.", code=RefusalCode.ACCOUNT_UNKNOWN)
            account.check_password_held_here()
            if password_refusal is not None:
                raise password_refusal
            now = self._clock()
            store.accounts.set_password_hash(account.id, password_hash, now=now)
            revoked = store.sessions.revoke_sessions_of(account.id, except_id=None, now=now)
        log.info("account_password_reset", account_id=account.id, sessions_revoked=revoked, by=actor.account_id)

    @requires("setAccountAccess")
    def set_account_access(self, actor: Actor, account_id: str, *, allowed: bool) -> AccountSummaryView:
        """Allow or cut an account's sign-in — an Admin's act.

        The Admin check comes first: a caller who is not Admin never learns whether an
        account exists. Then the account; the Plex server's owner, the fallback door, is
        never cut; nor is the caller's own account. The value the account already holds
        writes nothing. Cutting sets the access and revokes every session of the account in
        one ``BEGIN IMMEDIATE`` transaction, so its next request is refused; giving it back
        opens no session. Nothing is published: no right moves.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            account_id: The account.
            allowed: True to allow its sign-in, False to cut it.

        Returns:
            The account, with its access as set.

        Raises:
            AppForbidden: ``account.access_admin_only`` — the caller's role is not Admin,
                whatever the account; ``account.owner_access``; ``account.own_access``.
            AppNotFound: ``account.unknown``.
        """
        if actor.role_kind is not RoleKind.ADMIN:
            raise AppForbidden(
                "Only an Admin cuts or gives back an account's access.", code=RefusalCode.ACCOUNT_ACCESS_ADMIN_ONLY
            )
        store = self._store
        revoked = 0
        with store.immediate():
            account = store.accounts.account(AccountId(account_id))
            if account is None:
                raise AppNotFound("No account answers this identity.", code=RefusalCode.ACCOUNT_UNKNOWN)
            account.check_access_cut(by=actor.account_id)
            role = store.roles.role(account.role_id)
            assert role is not None  # an account's role is a foreign key: it always exists
            moved = account.sign_in_allowed is not allowed
            if moved:
                now = self._clock()
                store.accounts.set_sign_in_allowed(account.id, allowed=allowed, now=now)
                if not allowed:
                    revoked = store.sessions.revoke_sessions_of(account.id, except_id=None, now=now)
            summary = self._summary(replace(account, sign_in_allowed=allowed), role)
        if moved and allowed:
            log.info("account_access_given_back", account_id=account.id, by=actor.account_id)
        elif moved:
            log.info("account_access_cut", account_id=account.id, sessions_revoked=revoked, by=actor.account_id)
        return summary

    @staticmethod
    def _summary(account: Account, role: Role) -> AccountSummaryView:
        """Map an account and its role to the roster's view.

        Args:
            account: The account.
            role: Its role.

        Returns:
            The view, with the role a Plex link demoted it from when it was.
        """
        return AccountSummaryView(
            id=account.id,
            name=account.name,
            email=account.email,
            role=role_view(role),
            sign_in_kind=account.sign_in_kind,
            sign_in_allowed=account.sign_in_allowed,
            demoted_from=account.demoted_from,
        )

    @requires("readAccounts")
    def read_roster(self, actor: Actor) -> RosterView:
        """Every account and every role, as the accounts screen and the reassign chooser read them.

        A caller who is not Admin never sees an account on the Admin role (M7); every role
        is listed, Admin included.

        Args:
            actor: The signed-in actor (``accounts.manage`` or ``acquisition.reassign``).

        Returns:
            The accounts in creation order, and the roles in creation order.
        """
        store = self._store
        roles = store.roles.roles()
        by_id = {role.id: role for role in roles}
        sees_admins = actor.role_kind is RoleKind.ADMIN
        return RosterView(
            accounts=tuple(
                self._summary(account, by_id[account.role_id])
                for account in store.accounts.accounts()
                if sees_admins or by_id[account.role_id].kind is not RoleKind.ADMIN
            ),
            roles=tuple(role_view(role) for role in roles),
        )

    @requires("createAccount")
    def create_account(
        self, actor: Actor, *, name: str, email: str, role_id: str, password: str | None = None
    ) -> AccountSummaryView:
        """Create a local account, with the provisional password an Admin gives it.

        Order of the refusals (the maquette's): the name and e-mail; the role; the
        escalation; the Admin role given by anyone but the server's owner; the e-mail
        taken; the password. Linking an e-mail the managed Plex
        server knows is the Plex sign-in's: every account created here is local. Nothing
        is published: no existing account's rights move.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            name: The display name.
            email: The e-mail, unique whatever its case.
            role_id: The role it starts on — required (the operator, 2026-10-04): nothing
                is chosen for the manager.
            password: The provisional password; only its scrypt hash is kept.

        Returns:
            The new account.

        Raises:
            AppBadRequest: ``account.email_invalid`` — a blank name or an e-mail without
                both sides of one ``@``; ``password.required`` / ``password.too_short`` /
                ``password.too_weak`` (``params.minimum``).
            AppNotFound: ``role.unknown``.
            AppForbidden: ``role.escalation`` — a caller who is not Admin gives Admin, or
                a role holding rights its own does not; ``account.admin_owner_only`` — an
                Admin who is not the server's owner gives Admin.
            AppConflict: ``account.email_taken``.
        """
        name, email = name.strip(), email.strip()
        if not name or not is_email(email):
            raise AppBadRequest("A local account carries a name and an e-mail.", code=RefusalCode.ACCOUNT_EMAIL_INVALID)
        password_refusal = _provisional_refusal(password)
        # scrypt runs before the writer lock is taken, and only for a password that will be kept.
        password_hash = hash_password(password) if password_refusal is None and password is not None else None
        store = self._store
        now = self._clock()
        account_id = AccountId(f"account-{uuid.uuid4().hex}")
        with store.immediate():
            role = store.roles.role(RoleId(role_id))
            if role is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            grantor = _grantor(store, actor)
            grantor.check_may_give(role)
            if role.is_admin:
                grantor.check_may_give_admin()
            if store.accounts.account_by_email(email) is not None:
                raise AppConflict("An account already carries this e-mail.", code=RefusalCode.ACCOUNT_EMAIL_TAKEN)
            if password_refusal is not None:
                raise password_refusal
            account = Account(
                id=account_id,
                name=name,
                email=email,
                avatar="",
                role_id=role.id,
                password_hash=password_hash,
                created_at=now,
                updated_at=now,
            )
            store.accounts.insert_account(account)
            summary = self._summary(account, role)
        log.info("account_created", account_id=account_id, role_id=role.id, by=actor.account_id)
        return summary

    @requires("updateAccount")
    def update_account(self, actor: Actor, account_id: str, *, role_id: str) -> AccountSummaryView:
        """Put an account on a role; E8 names it once the change commits.

        A caller who is not Admin never touches its own account, an account on the Admin
        role or the Admin role, nor gives rights its own role does not hold. Only the
        server's owner puts an account on the Admin role (the operator, 2026-10-04), and the
        owner's own account never leaves it, whoever the caller — the owner included — so the
        one who gives Admin back is never demoted. Whoever the caller, one account stays on
        the Admin role. The checks and the write are one
        ``BEGIN IMMEDIATE`` transaction, so two managers cannot each demote "the other"
        last Admin.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            account_id: The account.
            role_id: The role it is put on.

        Returns:
            The account on its new role, its Plex link's demotion cleared.

        Raises:
            AppNotFound: ``account.unknown``, ``role.unknown``.
            AppForbidden: ``role.own_role``, ``account.admin_untouchable``, ``role.escalation``,
                ``account.admin_owner_only``; ``account.owner_admin`` — the server owner's
                account put on another role, checked before the last-Admin guard.
            AppConflict: ``account.last_admin``.
        """
        store = self._store
        with store.immediate():
            account = store.accounts.account(AccountId(account_id))
            if account is None:
                raise AppNotFound("No account answers this identity.", code=RefusalCode.ACCOUNT_UNKNOWN)
            target = store.roles.role(RoleId(role_id))
            if target is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            current = store.roles.role(account.role_id)
            if current is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            grantor = _grantor(store, actor)
            grantor.check_may_touch(account, current, target)
            grantor.check_may_give(target)
            if target.is_admin and not current.is_admin:
                grantor.check_may_give_admin()
            account.check_leaves_admin(
                current=current, target=target, admins=store.accounts.count_on_role_kind(RoleKind.ADMIN)
            )
            moved = account.role_id != target.id
            # A role given is an Admin's decision: it clears the demotion a Plex link
            # recorded, even when it confirms the role the link dropped the account to.
            if moved or account.demoted_from is not None:
                store.accounts.set_role(account.id, target.id, now=self._clock())
            summary = self._summary(replace(account, demoted_from=None), target)
        if moved:
            log.info("account_role_assigned", account_id=account.id, role_id=target.id, by=actor.account_id)
            self._bus.emit(AccountRightsChanged(account_ids=(account.id,), cause=RightsChangeCause.ROLE_ASSIGNED))
        return summary
