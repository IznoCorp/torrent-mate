"""``CredentialService``: the sign-in doors' shared end, the passwords and the owner's machine acts.

Every method taking an actor is authorised by ``@requires`` before it reads a row;
the actor-less acts (the sign-in door, the owner's machine acts) take none.
"""

from __future__ import annotations

import secrets
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from personalscraper.app.accounts.actor import SYSTEM_ROLE_ID, Actor, RoleKind
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.accounts.model import Account, AccountId, PlexLink, SignInKind, is_email
from personalscraper.app.accounts.passwords import hash_password, policy_refusal, verify_password
from personalscraper.app.accounts.ratelimit import SlidingWindowRateLimiter
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.accounts.views import AccountView, account_view
from personalscraper.app.errors import (
    AppBadRequest,
    AppConflict,
    AppForbidden,
    AppNotFound,
    AppTooManyRequests,
    AppUnauthenticated,
    RefusalCode,
)
from personalscraper.app.store.store import AppStore
from personalscraper.logger import get_logger

log = get_logger("app.accounts.credentials")

# Constant work: scrypt runs against this hash when there is no real one to check (an
# unknown e-mail, an account without a password), so every refusal takes the time of a
# real check and the delay never tells which e-mails exist. Random, so it never matches.
_DUMMY_HASH: Final[str] = hash_password(secrets.token_urlsafe(32))


@dataclass(frozen=True)
class SignInResult:
    """A sign-in that succeeded, by password or by Plex.

    Attributes:
        account: The signed-in account.
        session_token: The new session's cookie value — handed to the browser once, never logged.
    """

    account: AccountView
    session_token: str = field(repr=False)


class OwnerAlreadySeeded(Exception):
    """The server's owner is already an account: an Admin, an owner link, or the owner's plex.tv id linked.

    Raised by :meth:`CredentialService.create_owner` alone, which only the CLI calls: no route
    raises it, so it carries no refusal code and the CLI words it itself.
    """


class AmbiguousOwner(Exception):
    """Several accounts hold the owner link, so no single owner can be named.

    Raised by :meth:`CredentialService.owner_account_id` alone, which only the CLI calls: no
    route raises it, so it carries no refusal code and the CLI words it itself.
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


class CredentialService:
    """Opens and closes sessions, and holds the account passwords."""

    def __init__(
        self,
        store: AppStore,
        sessions: SessionService,
        *,
        clock: Callable[[], float] = time.time,
        limiter: SlidingWindowRateLimiter | None = None,
        password_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            sessions: The session service.
            clock: The epoch clock.
            limiter: The password door's failed-attempt limiter; ``None`` builds this
                service's own (one per process, never shared with v0's).
            password_limiter: The limiter of wrong current passwords on a password
                change, keyed by account; ``None`` builds this service's own, apart from
                the door's so neither spends the other's budget.
        """
        self._store = store
        self._sessions = sessions
        self._clock = clock
        self._limiter = limiter if limiter is not None else SlidingWindowRateLimiter()
        self._password_limiter = password_limiter if password_limiter is not None else SlidingWindowRateLimiter()

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
        store = self._store
        account = store.accounts.account_by_email(email)
        stored = account.password_hash if account is not None else None
        matches = verify_password(password, stored if stored is not None else _DUMMY_HASH) and stored is not None
        signs_in_with_plex = account is not None and account.sign_in_kind is SignInKind.PLEX
        if account is None or not matches or signs_in_with_plex:
            self._limiter.record_failure(client_key)
            log.info("v1_sign_in_refused", client_key=client_key)
            raise AppUnauthenticated("The sign-in was refused.", code=RefusalCode.AUTH_REFUSED)
        return self.open_proven_session(account.id, user_agent=user_agent)

    def open_proven_session(self, account_id: AccountId, *, user_agent: str | None) -> SignInResult:
        """Open a session for an account whose identity is proven, unless an Admin cut its access.

        Every sign-in door ends here once the credentials are proven, so the cut account's
        refusal never tells anything to someone who does not hold them: the password door
        once the password matches, the Plex door once the PIN is claimed and the identity
        proven to hold the account. The access is read and the session opened in one
        ``BEGIN IMMEDIATE`` transaction: a cut that commits while scrypt or plex.tv runs is
        seen here, and can never leave a session live.

        Args:
            account_id: The account signed in.
            user_agent: The browser's user agent, kept on the session.

        Returns:
            The signed-in account and its new session's value.

        Raises:
            AppUnauthenticated: ``auth.refused`` — the account was deleted since it was read;
                ``auth.required`` — its session no longer resolves.
            AppForbidden: ``auth.access_disabled`` — the account's access is cut.
        """
        store = self._store
        with store.immediate():
            account = store.accounts.account(account_id)
            if account is None:
                raise AppUnauthenticated("The sign-in was refused.", code=RefusalCode.AUTH_REFUSED)
            if not account.sign_in_allowed:
                log.info("v1_sign_in_access_disabled", account_id=account_id)
                raise AppForbidden("This account's access is cut.", code=RefusalCode.AUTH_ACCESS_DISABLED)
            token = self._sessions.open(account_id, user_agent=user_agent)
        actor = self._sessions.resolve(token)
        if actor is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        log.info("v1_signed_in", account_id=account.id)
        return SignInResult(account=account_view(store, account, actor), session_token=token)

    def owner_account_id(self) -> AccountId | None:
        """The key of the account linked as the managed Plex server's owner.

        Returns:
            The account holding the owner link, or ``None`` when no account holds it.

        Raises:
            AmbiguousOwner: Several accounts hold an owner link (the schema does not forbid it):
                picking one could open the session of a stale former owner.
        """
        links = self._store.accounts.owner_links()
        if len(links) > 1:
            raise AmbiguousOwner("Several accounts are linked as the server's owner.")
        return links[0].account_id if links else None

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
        store = self._store
        account = store.accounts.account_by_email(email)
        if account is None:
            raise AppNotFound("No account has this e-mail.", code=RefusalCode.ACCOUNT_UNKNOWN)
        store.accounts.set_password_hash(account.id, hash_password(password), now=self._clock())
        log.info("account_password_set", account_id=account.id)

    def create_owner(self, *, email: str, name: str, password: str, plex: OwnerPlexIdentity) -> AccountId:
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
        if not name or not is_email(email):
            raise AppBadRequest("The owner carries a name and an e-mail.", code=RefusalCode.ACCOUNT_EMAIL_INVALID)
        if not password:
            raise AppBadRequest("The owner needs a password.", code=RefusalCode.PASSWORD_REQUIRED)
        refusal = policy_refusal(password)
        if refusal is not None:
            raise refusal
        # scrypt runs before the writer lock is taken.
        password_hash = hash_password(password)
        store = self._store
        now = self._clock()
        account_id = AccountId(f"account-{uuid.uuid4().hex}")
        with store.immediate():
            owner_taken = (
                store.accounts.count_on_role_kind(RoleKind.ADMIN) > 0
                or store.accounts.owner_link() is not None
                or store.accounts.plex_link_by_plex_id(plex.plex_id) is not None
            )
            if owner_taken:
                raise OwnerAlreadySeeded("The server's owner is already an account.")
            if store.accounts.account_by_email(email) is not None:
                raise AppConflict("An account already carries this e-mail.", code=RefusalCode.ACCOUNT_EMAIL_TAKEN)
            role = store.roles.role(SYSTEM_ROLE_ID)
            if role is None or role.kind is not RoleKind.ADMIN:
                raise AppNotFound("No role answers this identity.", code=RefusalCode.ROLE_UNKNOWN)
            store.accounts.insert_account(
                Account(
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
            store.accounts.upsert_plex_link(
                PlexLink(
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

    @requires("changeOwnPassword")
    def change_own_password(self, actor: Actor, token: str, *, current_password: str, new_password: str) -> None:
        """Replace the signed-in local account's password, and end its other sessions.

        Order: the authorisation (``@requires``: a read-only instance refuses first); the
        account (deleted since the session was resolved); who holds its
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
            AppForbidden: ``instance.read_only`` (``@requires``, before anything is read);
                ``password.held_by_cli`` (the server's owner), ``auth.plex_only`` (a
                Plex-linked account).
            AppTooManyRequests: ``auth.rate_limited`` — the account typed a wrong current
                password too often in the window; checked before scrypt, so the right one
                is refused too.
            AppBadRequest: ``password.current_wrong``; ``password.too_short`` /
                ``password.too_weak`` (``params.minimum``).
        """
        store = self._store
        account = store.accounts.account(actor.account_id)
        if account is None:
            raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
        account.check_password_held_here()
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
        with store.immediate():
            current = store.accounts.account(account.id)
            if current is None:
                raise AppUnauthenticated("The session's account no longer exists.", code=RefusalCode.AUTH_REQUIRED)
            current.check_password_held_here()
            if current.password_hash != stored:
                raise AppBadRequest(
                    "The password changed since it was checked.", code=RefusalCode.PASSWORD_CURRENT_WRONG
                )
            now = self._clock()
            store.accounts.set_password_hash(current.id, new_hash, now=now)
            revoked = store.sessions.revoke_sessions_of(current.id, except_id=kept, now=now)
        log.info("account_password_changed", account_id=account.id, sessions_revoked=revoked)

    @requires("signOut")
    def sign_out(self, actor: Actor, token: str) -> None:
        """Close the session the actor signed in with.

        Args:
            actor: The signed-in actor, resolved from ``token``; authorised by ``@requires``.
            token: The session's cookie value.
        """
        self._sessions.close(token)
