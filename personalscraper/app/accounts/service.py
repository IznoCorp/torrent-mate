"""``AccountService``: the account operations a signed-in actor asks for."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, get_args

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.passwords import hash_password, verify_password
from personalscraper.app.accounts.ratelimit import SlidingWindowRateLimiter
from personalscraper.app.accounts.repository import AccountRepository, AccountRow, PlexLinkRow, RoleRow, StartKind
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.accounts.views import AccountView, RoleView, SignInKind
from personalscraper.app.errors import AppNotFound, AppTooManyRequests, AppUnauthenticated, RefusalCode
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

    def sign_out(self, actor: Actor, token: str) -> None:
        """Close the session the actor signed in with.

        Args:
            actor: The signed-in actor (the perimeter resolved it from ``token``).
            token: The session's cookie value.
        """
        self._sessions.close(token)
