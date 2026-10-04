"""``AccountService``: the account operations a signed-in actor asks for."""

from __future__ import annotations

import secrets
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Final, get_args

from personalscraper.app.accounts.actor import SYSTEM_ROLE_ID, Actor, RoleKind
from personalscraper.app.accounts.avatar import resolve_avatar
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.passwords import hash_password, policy_refusal, verify_password
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


class OwnerAlreadySeeded(Exception):
    """The server's owner is already an account: an Admin, an owner link, or the owner's plex.tv id linked.

    Raised by :meth:`AccountService.create_owner` alone, which only the CLI calls: no route
    raises it, so it carries no refusal code and the CLI words it itself.
    """


@dataclass(frozen=True)
class OwnerPlexIdentity:
    """The managed Plex server owner's plex.tv identity, as plex.tv answers it.

    The owner's account is linked to it so that a later Plex sign-in finds the same link
    (keyed by ``plex_id``) instead of creating a second account.

    Attributes:
        plex_id: plex.tv's stable id.
        plex_uuid: plex.tv's uuid.
        plex_username: plex.tv's username.
    """

    plex_id: int
    plex_uuid: str
    plex_username: str


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
        password_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            repo_factory: Returns the account repository (opening ``app.db`` on first use).
            sessions: The session service.
            bus: The bus the service publishes its domain events on, after a write commits.
            clock: The epoch clock.
            limiter: The password door's failed-attempt limiter; ``None`` builds this
                service's own (one per process, never shared with v0's).
            password_limiter: The limiter of wrong current passwords on a password
                change, keyed by account; ``None`` builds this service's own, apart from
                the door's so neither spends the other's budget.
        """
        self._repo_factory = repo_factory
        self._sessions = sessions
        self._bus = bus
        self._clock = clock
        self._limiter = limiter if limiter is not None else SlidingWindowRateLimiter()
        self._password_limiter = password_limiter if password_limiter is not None else SlidingWindowRateLimiter()

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
        link = repo.plex_link(account.id)
        return AccountView(
            id=account.id,
            name=account.name,
            email=account.email,
            avatar=resolve_avatar(link, account.email),
            role=role_view(role),
            sign_in_kind=sign_in_kind(link),
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
            AppForbidden: ``auth.access_disabled`` — an Admin cut the account; answered
                only once the password is proven, and not counted as a failure.
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
        token = self._open_session_if_allowed(repo, account.id, user_agent=user_agent)
        actor = self._sessions.resolve(token)
        if actor is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        log.info("v1_signed_in", account_id=account.id)
        return SignInResult(account=self._account_view(repo, account, actor), session_token=token)

    def _open_session_if_allowed(self, repo: AccountRepository, account_id: str, *, user_agent: str | None) -> str:
        """Open a session for an account whose identity is proven, unless an Admin cut its access.

        Every sign-in door ends here once the credentials are proven, so the cut account's
        refusal never tells anything to someone who does not hold them; the Plex door
        calls it once the PIN is claimed and the identity proven to hold the account. The
        access is read and the session opened in one ``BEGIN IMMEDIATE`` transaction: a cut
        that commits while scrypt runs is seen here, and can never leave a session live.

        Args:
            repo: The account repository.
            account_id: The account signed in.
            user_agent: The browser's user agent, kept on the session.

        Returns:
            The new session's value.

        Raises:
            AppUnauthenticated: ``auth.refused`` — the account was deleted since it was read.
            AppForbidden: ``auth.access_disabled`` — the account's access is cut.
        """
        with repo.immediate():
            account = repo.account(account_id)
            if account is None:
                raise AppUnauthenticated("The sign-in was refused.", code=RefusalCode.AUTH_REFUSED)
            if not account.sign_in_allowed:
                log.info("v1_sign_in_access_disabled", account_id=account_id)
                raise AppForbidden("This account's access is cut.", code=RefusalCode.AUTH_ACCESS_DISABLED)
            return self._sessions.open(account_id, user_agent=user_agent)

    def set_password(self, email: str, password: str) -> None:
        """Give an account a password — the server's door of last resort (the CLI's only).

        Args:
            email: The account's e-mail, whatever its case.
            password: The new password; only its scrypt hash is kept.

        Raises:
            AppBadRequest: ``password.too_short`` / ``password.too_weak`` (``params.minimum``) —
                the policy every local door applies, checked before the store is read.
            AppNotFound: ``account.unknown`` — no account has that e-mail.
        """
        refusal = policy_refusal(password)
        if refusal is not None:
            raise refusal
        repo = self._repo_factory()
        account = repo.account_by_email(email)
        if account is None:
            raise AppNotFound("No account has this e-mail.", code=RefusalCode.ACCOUNT_UNKNOWN)
        repo.set_password_hash(account.id, hash_password(password), now=self._clock())
        log.info("account_password_set", account_id=account.id)

    def create_owner(self, *, email: str, name: str, password: str, plex: OwnerPlexIdentity) -> str:
        """Seed the managed server's owner: an Admin account linked to its plex.tv identity as ``owner``.

        The server's door of last resort, the CLI's only, on an environment with no owner
        yet: the account signs in by its fallback password (``signInKind`` ``owner``) until a
        Plex sign-in finds the same link. No Plex token is kept. The checks and both writes
        are one ``BEGIN IMMEDIATE`` transaction; nothing is published, no existing account's
        rights move.

        Args:
            email: The owner's e-mail, unique whatever its case.
            name: The display name.
            password: The fallback password; only its scrypt hash is kept.
            plex: The owner's plex.tv identity.

        Returns:
            The new account's key.

        Raises:
            AppBadRequest: ``account.email_invalid`` — a blank name or an e-mail without
                both sides of one ``@``; ``password.required`` — an empty password;
                ``password.too_short`` / ``password.too_weak`` (``params.minimum``) — the policy.
            OwnerAlreadySeeded: An account already holds the Admin role, an owner link, or
                the owner's plex.tv id.
            AppConflict: ``account.email_taken``.
            AppNotFound: ``role.unknown`` — the store has no Admin role.
        """
        name, email = name.strip(), email.strip()
        if not name or not _is_email(email):
            raise AppBadRequest("The owner carries a name and an e-mail.", code=RefusalCode.ACCOUNT_EMAIL_INVALID)
        if not password:
            raise AppBadRequest("The owner needs a password.", code=RefusalCode.PASSWORD_REQUIRED)
        refusal = policy_refusal(password)
        if refusal is not None:
            raise refusal
        # scrypt runs before the writer lock is taken.
        password_hash = hash_password(password)
        repo = self._repo_factory()
        now = self._clock()
        account_id = f"account-{uuid.uuid4().hex}"
        with repo.immediate():
            owner_taken = (
                repo.count_on_role_kind(RoleKind.ADMIN) > 0
                or repo.owner_link() is not None
                or repo.plex_link_by_plex_id(plex.plex_id) is not None
            )
            if owner_taken:
                raise OwnerAlreadySeeded("The server's owner is already an account.")
            if repo.account_by_email(email) is not None:
                raise AppConflict("An account already carries this e-mail.", code=RefusalCode.ACCOUNT_EMAIL_TAKEN)
            role = repo.role(SYSTEM_ROLE_ID)
            if role is None or role.kind is not RoleKind.ADMIN:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            repo.insert_account(
                AccountRow(
                    id=account_id,
                    name=name,
                    email=email,
                    avatar="",
                    role_id=role.id,
                    password_hash=password_hash,
                    created_at=now,
                    updated_at=now,
                )
            )
            repo.upsert_plex_link(
                PlexLinkRow(
                    account_id=account_id,
                    plex_id=plex.plex_id,
                    plex_uuid=plex.plex_uuid,
                    plex_username=plex.plex_username,
                    server_access="owner",
                    token_ciphertext=None,
                    token_stored_at=None,
                    linked_at=now,
                    last_sign_in_at=None,
                )
            )
        log.info("account_owner_created", account_id=account_id, plex_id=plex.plex_id)
        return account_id

    def change_own_password(self, actor: Actor, token: str, *, current_password: str, new_password: str) -> None:
        """Replace the signed-in local account's password, and end its other sessions.

        Order: the account (deleted since the perimeter resolved it); who holds its
        password (the owner's is the CLI's, a Plex-linked account holds none); the limiter,
        keyed by the account; scrypt against the stored hash, or a dummy one when none is
        held, so every refusal costs a real check; the new password's policy. The new hash
        is computed before the writer lock is taken; inside it the checks are read again —
        a hash moved meanwhile means the password typed is no longer the current one —
        then the hash is set and every other session of the account revoked, in one
        transaction. A success does not give the failure budget back.

        Args:
            actor: The signed-in actor.
            token: The caller's session value: the one session kept.
            current_password: The password the account holds now.
            new_password: The password that replaces it; only its scrypt hash is kept.

        Raises:
            AppUnauthenticated: ``auth.required`` — the account was deleted.
            AppForbidden: ``password.held_by_cli`` (the server's owner),
                ``auth.plex_only`` (a Plex-linked account).
            AppTooManyRequests: ``auth.rate_limited`` — the account typed a wrong current
                password too often in the window; checked before scrypt, so the right one
                is refused too.
            AppBadRequest: ``password.current_wrong``; ``password.too_short`` /
                ``password.too_weak`` (``params.minimum``).
        """
        repo = self._repo_factory()
        account = repo.account(actor.account_id)
        if account is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        _refuse_password_held_elsewhere(sign_in_kind(repo.plex_link(account.id)))
        if not self._password_limiter.allow(account.id):
            log.warning("password_change_rate_limited", account_id=account.id)
            raise AppTooManyRequests(
                "Too many wrong current passwords for this account.", code=RefusalCode.AUTH_RATE_LIMITED
            )
        stored = account.password_hash
        matches = (
            verify_password(current_password, stored if stored is not None else _DUMMY_HASH) and stored is not None
        )
        if not matches:
            self._password_limiter.record_failure(account.id)
            log.info("password_change_refused", account_id=account.id)
            raise AppBadRequest("The current password does not match.", code=RefusalCode.PASSWORD_CURRENT_WRONG)
        refusal = policy_refusal(new_password)
        if refusal is not None:
            raise refusal
        new_hash = hash_password(new_password)
        kept = self._sessions.live_session_id(token)
        with repo.immediate():
            current = repo.account(account.id)
            if current is None:
                raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
            _refuse_password_held_elsewhere(sign_in_kind(repo.plex_link(current.id)))
            if current.password_hash != stored:
                raise AppBadRequest(
                    "The password changed since it was checked.", code=RefusalCode.PASSWORD_CURRENT_WRONG
                )
            now = self._clock()
            repo.set_password_hash(current.id, new_hash, now=now)
            revoked = repo.revoke_sessions_of(current.id, except_id=kept, now=now)
        log.info("account_password_changed", account_id=account.id, sessions_revoked=revoked)

    def reset_account_password(self, actor: Actor, account_id: str, *, password: str) -> None:
        """Give a local account a provisional password — an Admin's act; its sessions keep running.

        The Admin check comes first: a caller who is not Admin never learns whether an
        account exists. Then the caller's own account, which an Admin changes in Profil with
        its current password (the operator, 2026-10-04); the account; who holds its
        password; the provisional password's own refusals. scrypt runs before the writer lock is taken, and only for
        a password that will be kept.

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
        repo = self._repo_factory()
        with repo.immediate():
            account = repo.account(account_id)
            if account is None:
                raise AppNotFound("No account answers this identity.", code=RefusalCode.ACCOUNT_UNKNOWN)
            _refuse_password_held_elsewhere(sign_in_kind(repo.plex_link(account.id)))
            if password_refusal is not None:
                raise password_refusal
            repo.set_password_hash(account.id, password_hash, now=self._clock())
        log.info("account_password_reset", account_id=account.id, by=actor.account_id)

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
        repo = self._repo_factory()
        revoked = 0
        with repo.immediate():
            account = repo.account(account_id)
            if account is None:
                raise AppNotFound("No account answers this identity.", code=RefusalCode.ACCOUNT_UNKNOWN)
            if sign_in_kind(repo.plex_link(account.id)) is SignInKind.OWNER:
                raise AppForbidden("The server owner's access is never cut.", code=RefusalCode.ACCOUNT_OWNER_ACCESS)
            if account.id == actor.account_id:
                raise AppForbidden("An Admin never cuts its own access.", code=RefusalCode.ACCOUNT_OWN_ACCESS)
            role = repo.role(account.role_id)
            assert role is not None  # an account's role is a foreign key: it always exists
            moved = account.sign_in_allowed is not allowed
            if moved:
                now = self._clock()
                repo.set_sign_in_allowed(account.id, allowed=allowed, now=now)
                if not allowed:
                    revoked = repo.revoke_sessions_of(account.id, except_id=None, now=now)
            summary = self._summary(repo, replace(account, sign_in_allowed=allowed), role)
        if moved and allowed:
            log.info("account_access_given_back", account_id=account.id, by=actor.account_id)
        elif moved:
            log.info("account_access_cut", account_id=account.id, sessions_revoked=revoked, by=actor.account_id)
        return summary

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
            sign_in_allowed=account.sign_in_allowed,
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
        if not name or not _is_email(email):
            raise AppBadRequest("A local account carries a name and an e-mail.", code=RefusalCode.ACCOUNT_EMAIL_INVALID)
        password_refusal = _provisional_refusal(password)
        # scrypt runs before the writer lock is taken, and only for a password that will be kept.
        password_hash = hash_password(password) if password_refusal is None and password is not None else None
        repo = self._repo_factory()
        now = self._clock()
        account_id = f"account-{uuid.uuid4().hex}"
        with repo.immediate():
            role = repo.role(role_id)
            if role is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            _refuse_escalation(actor, role)
            if role.kind is RoleKind.ADMIN:
                _refuse_admin_given_by_another(repo, actor)
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
            The account on its new role.

        Raises:
            AppNotFound: ``account.unknown``, ``role.unknown``.
            AppForbidden: ``role.own_role``, ``account.admin_untouchable``, ``role.escalation``,
                ``account.admin_owner_only``; ``account.owner_admin`` — the server owner's
                account put on another role, checked before the last-Admin guard.
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
            if target.kind is RoleKind.ADMIN and current.kind is not RoleKind.ADMIN:
                _refuse_admin_given_by_another(repo, actor)
            if target.kind is not RoleKind.ADMIN and sign_in_kind(repo.plex_link(account.id)) is SignInKind.OWNER:
                raise AppForbidden(
                    "The server owner's account never leaves the Admin role.", code=RefusalCode.ACCOUNT_OWNER_ADMIN
                )
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
        held = _rights(rights)
        typed = name.strip()
        if not typed:
            raise AppBadRequest("A role carries the name the manager typed.", code=RefusalCode.ROLE_NAME_REQUIRED)
        role = RoleRow(id=f"role-{uuid.uuid4().hex}", name=typed, kind=RoleKind.ORDINARY, rights=held)
        repo = self._repo_factory()
        with repo.immediate():
            _refuse_name_taken(repo, typed, except_id=None)
            if not _within(actor, held):
                raise AppForbidden(
                    "The role would hold rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION
                )
            repo.insert_role(role, now=self._clock())
        log.info("role_created", role_id=role.id, by=actor.account_id)
        return role_view(role)

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
            if new_name is not None:
                _refuse_name_taken(repo, new_name, except_id=role.id)
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
        repo = self._repo_factory()
        with repo.immediate():
            role = repo.role(role_id)
            if role is None:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            if role.kind is RoleKind.ADMIN:
                raise AppConflict("The Admin role is never deleted.", code=RefusalCode.ROLE_SYSTEM_IMMUTABLE)
            if role.default_for:
                raise AppConflict("A newcomer starts on this role.", code=RefusalCode.ROLE_DEFAULT)
            if repo.accounts_on_role(role.id):
                raise AppConflict("An account holds this role.", code=RefusalCode.ROLE_IN_USE)
            if not _within(actor, role.rights):
                raise AppForbidden("The role holds rights the caller's does not.", code=RefusalCode.ROLE_ESCALATION)
            repo.delete_role(role.id)
        log.info("role_deleted", role_id=role_id, by=actor.account_id)

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
        ``password.required`` (absent or empty), the policy's ``password.too_short`` /
        ``password.too_weak`` with its ``minimum``, or ``None`` when it meets the policy.
    """
    if not password:
        return AppBadRequest("A local account starts with a provisional password.", code=RefusalCode.PASSWORD_REQUIRED)
    return policy_refusal(password)


def _refuse_password_held_elsewhere(kind: SignInKind) -> None:
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


def _refuse_admin_given_by_another(repo: AccountRepository, actor: Actor) -> None:
    """Refuse the Admin role given by anyone but the managed Plex server's owner (the operator, 2026-10-04).

    Args:
        repo: The account repository.
        actor: The caller.

    Raises:
        AppForbidden: ``account.admin_owner_only``.
    """
    if sign_in_kind(repo.plex_link(actor.account_id)) is not SignInKind.OWNER:
        raise AppForbidden("Only the server's owner gives the Admin role.", code=RefusalCode.ACCOUNT_ADMIN_OWNER_ONLY)


def _refuse_name_taken(repo: AccountRepository, name: str, *, except_id: str | None) -> None:
    """Refuse a role name another role carries, compared trimmed and regardless of case.

    Case is folded by ``str.lower`` — Unicode's default lowercase mapping, the very one
    the maquette's ``toLowerCase`` applies — never ``casefold``, which would make
    « STRASSE » and « straße » one name here and two there. A seeded role never renamed
    carries no name (its words are the interface's), so it takes none.

    Args:
        repo: The account repository.
        name: The name asked for, trimmed.
        except_id: The role being renamed, which may keep its own name; ``None`` at creation.

    Raises:
        AppConflict: ``role.name_taken``.
    """
    wanted = name.lower()
    for role in repo.roles():
        if role.id != except_id and role.name is not None and role.name.strip().lower() == wanted:
            raise AppConflict("Another role already carries this name.", code=RefusalCode.ROLE_NAME_TAKEN)
