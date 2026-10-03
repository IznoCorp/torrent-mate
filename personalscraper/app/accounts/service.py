"""``AccountService``: the account operations a signed-in actor asks for."""

from __future__ import annotations

import secrets
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final, get_args

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.passwords import PASSWORD_MINIMUM, hash_password, verify_password
from personalscraper.app.accounts.ratelimit import SlidingWindowRateLimiter
from personalscraper.app.accounts.repository import AccountRepository, AccountRow, PlexLinkRow, RoleRow, StartKind
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.accounts.views import AccountSummaryView, AccountView, RoleView, RosterView, SignInKind
from personalscraper.app.errors import (
    AppBadRequest,
    AppConflict,
    AppForbidden,
    AppNotFound,
    AppTooManyRequests,
    AppUnauthenticated,
    RefusalCode,
)
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("app.accounts.service")

#: The contract's order of the start kinds (``Role.defaultFor``).
_START_ORDER: Final[tuple[StartKind, ...]] = get_args(StartKind)

# Constant work: scrypt runs against this hash when there is no real one to check (an
# unknown e-mail, an account without a password), so every refusal takes the time of a
# real check and the delay never tells which e-mails exist. Random, so it never matches.
_DUMMY_HASH: Final[str] = hash_password(secrets.token_urlsafe(32))


@dataclass(frozen=True)
class SignInResult:
    """A password sign-in that succeeded.

    Attributes:
        account: The signed-in account.
        session_token: The new session's cookie value — handed to the browser once, never logged.
    """

    account: AccountView
    session_token: str = field(repr=False)


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
        limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            repo_factory: Returns the account repository (opening ``app.db`` on first use).
            sessions: The session service.
            bus: The bus the service publishes its domain events on, after a write commits.
            clock: The epoch clock.
            limiter: The password door's failed-attempt limiter; ``None`` builds this
                service's own (one per process, never shared with v0's).
        """
        self._repo_factory = repo_factory
        self._sessions = sessions
        self._bus = bus
        self._clock = clock
        self._limiter = limiter if limiter is not None else SlidingWindowRateLimiter()

    def _account_view(self, repo: AccountRepository, account: AccountRow, actor: Actor) -> AccountView:
        """Map an account and its actor to the account's view.

        Args:
            repo: The account repository.
            account: The account.
            actor: The actor it signs in as (its role and ceiling).

        Returns:
            The view.

        Raises:
            AppUnauthenticated: ``auth.required`` — the account's role was deleted.
        """
        role = repo.role(actor.role_id)
        if role is None:
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
        if account is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        return self._account_view(repo, account, actor)

    def sign_in_with_password(
        self, email: str, password: str, *, client_key: str, user_agent: str | None
    ) -> SignInResult:
        """Open a session from an e-mail and a password — the password door.

        The door is a local account's only way in and the Plex server owner's fallback; a
        Plex-linked account other than the owner signs in through Plex only. Every failure
        is the same refusal, after the same scrypt work, so no attempt tells which e-mails
        the server knows (the contract's anti-enumeration). Order: the limiter; the account
        by e-mail, whatever its case; scrypt against its hash, or a dummy one; the refusal
        (counted against ``client_key``) or a NEW session — a value the caller already
        holds is never adopted. A success does not give the failure budget back: failures
        expire with the window alone, or a client holding any valid account could walk the
        limiter round.

        Args:
            email: The e-mail typed.
            password: The password typed.
            client_key: Who is trying, for the limiter (``rate_limit_key``'s answer).
            user_agent: The browser's user agent, kept on the session.

        Returns:
            The signed-in account and its new session's value.

        Raises:
            AppTooManyRequests: ``auth.rate_limited`` — ``client_key`` failed too often in
                the window; checked first, so the right password is refused too.
            AppUnauthenticated: ``auth.refused`` — an unknown e-mail, no password, a wrong
                one, or a Plex-linked account that is not the server's owner.
        """
        if not self._limiter.allow(client_key):
            log.warning("v1_sign_in_rate_limited", client_key=client_key)
            raise AppTooManyRequests("Too many failed sign-ins from this client.", code=RefusalCode.AUTH_RATE_LIMITED)
        repo = self._repo_factory()
        account = repo.account_by_email(email)
        stored = account.password_hash if account is not None else None
        matches = verify_password(password, stored if stored is not None else _DUMMY_HASH) and stored is not None
        signs_in_with_plex = account is not None and sign_in_kind(repo.plex_link(account.id)) is SignInKind.PLEX
        if account is None or not matches or signs_in_with_plex:
            self._limiter.record_failure(client_key)
            log.info("v1_sign_in_refused", client_key=client_key)
            raise AppUnauthenticated("The sign-in was refused.", code=RefusalCode.AUTH_REFUSED)
        token = self._sessions.open(account.id, user_agent=user_agent)
        actor = self._sessions.resolve(token)
        if actor is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        log.info("v1_signed_in", account_id=account.id)
        return SignInResult(account=self._account_view(repo, account, actor), session_token=token)

    def set_password(self, email: str, password: str) -> None:
        """Give an account a password — the server's door of last resort (the CLI's only).

        Args:
            email: The account's e-mail, whatever its case.
            password: The new password; only its scrypt hash is kept.

        Raises:
            AppNotFound: ``account.unknown`` — no account has that e-mail.
        """
        repo = self._repo_factory()
        account = repo.account_by_email(email)
        if account is None:
            raise AppNotFound("No account has this e-mail.", code=RefusalCode.ACCOUNT_UNKNOWN)
        repo.set_password_hash(account.id, hash_password(password), now=self._clock())
        log.info("account_password_set", account_id=account.id)

    def _summary(self, repo: AccountRepository, account: AccountRow, role: RoleRow) -> AccountSummaryView:
        """Map an account and its role to the roster's view.

        Args:
            repo: The account repository.
            account: The account.
            role: Its role.

        Returns:
            The view; ``demoted_from`` stays ``None`` (nothing demotes an account before
            the Plex link).
        """
        return AccountSummaryView(
            id=account.id,
            name=account.name,
            email=account.email,
            role=role_view(role),
            sign_in_kind=sign_in_kind(repo.plex_link(account.id)),
        )

    def read_roster(self, actor: Actor) -> RosterView:
        """Every account and every role, as the accounts screen and the reassign chooser read them.

        A caller who is not Admin never sees an account on the Admin role (M7); every role
        is listed, Admin included.

        Args:
            actor: The signed-in actor (``accounts.manage`` or ``acquisition.reassign``).

        Returns:
            The accounts in creation order, and the roles in creation order.
        """
        repo = self._repo_factory()
        roles = repo.roles()
        by_id = {role.id: role for role in roles}
        sees_admins = actor.role_kind is RoleKind.ADMIN
        return RosterView(
            accounts=tuple(
                self._summary(repo, account, by_id[account.role_id])
                for account in repo.accounts()
                if sees_admins or by_id[account.role_id].kind is not RoleKind.ADMIN
            ),
            roles=tuple(role_view(role) for role in roles),
        )

    def create_account(
        self, actor: Actor, *, name: str, email: str, role_id: str | None = None, password: str | None = None
    ) -> AccountSummaryView:
        """Create a local account, with the provisional password an Admin gives it.

        Order of the refusals (the maquette's): the name and e-mail; the role; the
        escalation; the e-mail taken; the password. Linking an e-mail the managed Plex
        server knows is the Plex sign-in's: every account created here is local. Nothing
        is published: no existing account's rights move.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            name: The display name.
            email: The e-mail, unique whatever its case.
            role_id: The role it starts on; ``None`` or empty for the role local accounts
                start on (``Role.defaultFor`` ``local``).
            password: The provisional password; only its scrypt hash is kept.

        Returns:
            The new account.

        Raises:
            AppBadRequest: ``account.email_invalid`` — a blank name or an e-mail without
                both sides of one ``@``; ``password.required`` / ``password.too_short``
                (``params.minimum``).
            AppNotFound: ``role.unknown``.
            AppForbidden: ``role.escalation`` — a caller who is not Admin gives Admin, or
                a role holding rights its own does not.
            AppConflict: ``account.email_taken``.
        """
        name, email = name.strip(), email.strip()
        if not name or not _is_email(email):
            raise AppBadRequest("A local account carries a name and an e-mail.", code=RefusalCode.ACCOUNT_EMAIL_INVALID)
        password_refusal = _provisional_refusal(password)
        # scrypt runs before the writer lock is taken, and only for a password that will be kept.
        password_hash = hash_password(password) if password_refusal is None and password is not None else None
        repo = self._repo_factory()
        now = self._clock()
        account_id = f"account-{uuid.uuid4().hex}"
        with repo.immediate():
            role = repo.role(role_id) if role_id else repo.role_for_start("local")
            if role is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            _refuse_escalation(actor, role)
            if repo.account_by_email(email) is not None:
                raise AppConflict("An account already carries this e-mail.", code=RefusalCode.ACCOUNT_EMAIL_TAKEN)
            if password_refusal is not None:
                raise password_refusal
            account = AccountRow(
                id=account_id,
                name=name,
                email=email,
                avatar="",
                role_id=role.id,
                password_hash=password_hash,
                created_at=now,
                updated_at=now,
            )
            repo.insert_account(account)
            summary = self._summary(repo, account, role)
        log.info("account_created", account_id=account_id, role_id=role.id, by=actor.account_id)
        return summary

    def update_account(self, actor: Actor, account_id: str, *, role_id: str) -> AccountSummaryView:
        """Put an account on a role; E8 names it once the change commits.

        A caller who is not Admin never touches its own account, an account on the Admin
        role or the Admin role, nor gives rights its own role does not hold. Whoever the
        caller, one account stays on the Admin role. The checks and the write are one
        ``BEGIN IMMEDIATE`` transaction, so two managers cannot each demote "the other"
        last Admin.

        Args:
            actor: The signed-in actor (``accounts.manage``).
            account_id: The account.
            role_id: The role it is put on.

        Returns:
            The account on its new role.

        Raises:
            AppNotFound: ``account.unknown``, ``role.unknown``.
            AppForbidden: ``role.own_role``, ``account.admin_untouchable``, ``role.escalation``.
            AppConflict: ``account.last_admin``.
        """
        repo = self._repo_factory()
        with repo.immediate():
            account = repo.account(account_id)
            if account is None:
                raise AppNotFound("No account answers this identity.", code=RefusalCode.ACCOUNT_UNKNOWN)
            target = repo.role(role_id)
            if target is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            current = repo.role(account.role_id)
            if current is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            if actor.role_kind is not RoleKind.ADMIN:
                if account.id == actor.account_id:
                    raise AppForbidden("A manager never touches its own role.", code=RefusalCode.ROLE_OWN_ROLE)
                if RoleKind.ADMIN in (current.kind, target.kind):
                    raise AppForbidden(
                        "A manager who is not Admin never touches Admin.", code=RefusalCode.ACCOUNT_ADMIN_UNTOUCHABLE
                    )
                _refuse_escalation(actor, target)
            leaves_admin = current.kind is RoleKind.ADMIN and target.kind is not RoleKind.ADMIN
            if leaves_admin and repo.count_on_role_kind(RoleKind.ADMIN) <= 1:
                raise AppConflict("No account would be left on the Admin role.", code=RefusalCode.ACCOUNT_LAST_ADMIN)
            moved = account.role_id != target.id
            if moved:
                repo.set_role(account.id, target.id, now=self._clock())
            summary = self._summary(repo, account, target)
        if moved:
            log.info("account_role_assigned", account_id=account.id, role_id=target.id, by=actor.account_id)
            self._bus.emit(AccountRightsChanged(account_ids=(account.id,), cause=RightsChangeCause.ROLE_ASSIGNED))
        return summary

    def create_role(self, actor: Actor, *, name: str, rights: Sequence[str]) -> RoleView:
        """Create an ordinary role; nothing is published (no account holds it yet).

        Args:
            actor: The signed-in actor (``accounts.manage``).
            name: Its name; blank stores none, and the interface shows its id.
            rights: The rights it carries.

        Returns:
            The new role.

        Raises:
            AppBadRequest: ``right.unknown`` — a name that is no right.
            AppForbidden: ``role.escalation`` — a caller who is not Admin gives rights its
                own role does not hold.
        """
        held = _rights(rights)
        if not _within(actor, held):
            raise AppForbidden("The role would hold rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION)
        role = RoleRow(id=f"role-{uuid.uuid4().hex}", name=name.strip() or None, kind=RoleKind.ORDINARY, rights=held)
        repo = self._repo_factory()
        repo.insert_role(role, now=self._clock())
        log.info("role_created", role_id=role.id, by=actor.account_id)
        return role_view(role)

    def update_role(
        self, actor: Actor, role_id: str, *, name: str | None = None, rights: Sequence[str] | None = None
    ) -> RoleView:
        """Rename a role or set its rights; E8 names its accounts once the change commits.

        The Admin role is never modified. A caller who is not Admin never touches its own
        role, never gives rights its own does not hold, and renames only a role whose
        rights its own holds. A blank name is ignored. A change that moves nothing
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
            AppConflict: ``role.system_immutable`` — the Admin role.
            AppForbidden: ``role.own_role``, ``role.escalation``.
        """
        held = _rights(rights) if rights is not None else None
        new_name = name.strip() if name is not None and name.strip() else None
        repo = self._repo_factory()
        with repo.immediate():
            role = repo.role(role_id)
            if role is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            if role.kind is RoleKind.ADMIN:
                raise AppConflict("The Admin role is not modified.", code=RefusalCode.ROLE_SYSTEM_IMMUTABLE)
            if actor.role_kind is not RoleKind.ADMIN:
                if role.id == actor.role_id:
                    raise AppForbidden("A manager never touches its own role.", code=RefusalCode.ROLE_OWN_ROLE)
                if held is not None and not _within(actor, held):
                    raise AppForbidden(
                        "The role would hold rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION
                    )
                if name is not None and not _within(actor, role.rights):
                    raise AppForbidden(
                        "A manager renames only a role within its own rights.", code=RefusalCode.ROLE_ESCALATION
                    )
            rights_moved = held is not None and held != role.rights
            renamed = new_name is not None and new_name != role.name
            if rights_moved or renamed:
                repo.update_role(
                    role.id,
                    name=new_name if renamed else None,
                    rights=held if rights_moved else None,
                    now=self._clock(),
                )
            holders = tuple(repo.accounts_on_role(role.id))
            updated = repo.role(role.id)
        assert updated is not None  # the transaction above read and kept it
        if rights_moved or renamed:
            log.info("role_updated", role_id=role.id, rights_moved=rights_moved, renamed=renamed, by=actor.account_id)
        if (rights_moved or renamed) and holders:
            cause = RightsChangeCause.ROLE_RIGHTS_CHANGED if rights_moved else RightsChangeCause.ROLE_RENAMED
            self._bus.emit(AccountRightsChanged(account_ids=holders, cause=cause))
        return role_view(updated)

    def sign_out(self, actor: Actor, token: str) -> None:
        """Close the session the actor signed in with.

        Args:
            actor: The signed-in actor (the perimeter resolved it from ``token``).
            token: The session's cookie value.
        """
        self._sessions.close(token)


def _is_email(email: str) -> bool:
    """Whether a text is an e-mail as the accounts screen accepts it: something on both sides of one ``@``.

    Args:
        email: The text, stripped.

    Returns:
        True when it is one.
    """
    local, at, domain = email.rpartition("@")
    return bool(at and local and domain and not any(char.isspace() for char in email))


def _provisional_refusal(password: str | None) -> AppBadRequest | None:
    """Why a provisional password is refused, if it is.

    Args:
        password: The password the Admin typed; ``None`` when absent.

    Returns:
        ``password.required`` (absent or empty), ``password.too_short`` with its
        ``minimum``, or ``None`` when it is long enough.
    """
    if not password:
        return AppBadRequest("A local account starts with a provisional password.", code=RefusalCode.PASSWORD_REQUIRED)
    if len(password) < PASSWORD_MINIMUM:
        return AppBadRequest(
            "The provisional password is too short.",
            code=RefusalCode.PASSWORD_TOO_SHORT,
            params={"minimum": PASSWORD_MINIMUM},
        )
    return None


def _rights(names: Sequence[str]) -> frozenset[Right]:
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


def _within(actor: Actor, rights: frozenset[Right]) -> bool:
    """Whether rights are included in the actor's own role's (Admin includes every right).

    Measured against the role the actor's session resolved, as the perimeter authorised it.

    Args:
        actor: The caller.
        rights: The rights given.

    Returns:
        True when the caller may give them.
    """
    return actor.role_kind is RoleKind.ADMIN or rights <= actor.role_rights


def _refuse_escalation(actor: Actor, role: RoleRow) -> None:
    """Refuse a caller who is not Admin putting an account on Admin, or on a role wider than its own.

    Args:
        actor: The caller.
        role: The role an account would hold.

    Raises:
        AppForbidden: ``role.escalation``.
    """
    if actor.role_kind is RoleKind.ADMIN:
        return
    if role.kind is RoleKind.ADMIN or not _within(actor, role.rights):
        raise AppForbidden("The role holds rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION)
