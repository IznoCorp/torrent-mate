"""``PlexSignInService``: the Plex door — a PIN plex.tv confirms, an identity with access to this server signed in.

The browser asks the server to start a sign-in (``startPlexSignIn``): the server creates a PIN on
plex.tv, keeps it with the hash of a nonce the browser alone holds (its pin cookie), and answers
plex.tv's page where the person confirms it. The browser then asks, at most once a second,
whether the PIN is claimed (``signInWithPlex``): the server checks it on plex.tv, reads the
identity behind the token it yields and what that identity is to THIS server, and signs it in.

The operator's rulings, as coded here (K1 P1-7; the contract's ``signInWithPlex``):

- **Who gets in.** The server's OWNER, a member of its owner's Plex HOME, a user it is SHARED
  with. Anyone else — and a linked account that lost its access — is refused ``auth.refused``,
  the one code of every unauthenticated refusal, as if the identity did not exist: no account,
  no link, no token kept, nothing.
- **OWNER is cross-checked.** plex.tv answering « owned » for a resource named by a machine
  identifier is not enough — that identifier is no secret. The identity must also be the account
  behind the server's own token (``PLEX_TOKEN``), read once from plex.tv and cached.
- **The first role, by Plex kind**, applied when the account is created or linked, never
  recomputed: Admin for the owner; the role whose ``default_for`` holds ``plexHome`` for a Home
  member, ``plexGuest`` for any other user. No « default » role exists.
- **A local account whose e-mail is the identity's is linked**: from then on it signs in by Plex
  only, its password dropped, and it drops to its Plex kind's role (``demoted_from`` recorded,
  E8 ``plex_linked``) until an Admin promotes it again — no e-mail link ever carries Admin. The
  owner is the exception: put on (or kept on) Admin, and his password kept as the fallback for
  when Plex is down. An e-mail plex.tv has not confirmed, or whose account is another plex.tv
  identity's, is refused.
- **plex.tv down, the server down and a token refused are told apart**: ``plex.unreachable``,
  ``plex.server_unreachable``, ``plex.token_refused`` — none tells whether an identity matches.

The user's token, the PIN code, the nonce and the e-mail never reach a log, a refusal or a
``repr``; the token is kept only sealed in the vault, under the account it signs in.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Final, Protocol

from personalscraper.api.plex_account import (
    PlexAccount,
    PlexAccountClient,
    PlexAccountUnreachable,
    PlexPinExpired,
    PlexServerAccess,
    PlexTokenRefused,
)
from personalscraper.app.accounts.actor import SYSTEM_ROLE_ID
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.repository import (
    AccountRepository,
    AccountRow,
    PlexLinkRow,
    PlexPinRow,
    RoleRow,
    StartKind,
)
from personalscraper.app.accounts.service import AccountService, SignInResult
from personalscraper.app.accounts.token_vault import TokenVault
from personalscraper.app.errors import (
    AppBadRequest,
    AppConflict,
    AppForbidden,
    AppInternalError,
    AppUnauthenticated,
    AppUnavailable,
    RefusalCode,
)
from personalscraper.conf.environment import Environment
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("app.accounts.plex_sign_in")

#: The least time between two checks of one PIN on plex.tv (NE-DOIT-PAS-8; Plex's article).
PIN_CHECK_MIN_INTERVAL_S: Final[float] = 1.0

#: The ``app_setting`` key of this environment's plex.tv client identifier, created once.
CLIENT_IDENTIFIER_SETTING: Final[str] = "plex.client_identifier"

#: The name plex.tv lists under « Authorized Devices », one per environment.
PRODUCTS: Final[Mapping[Environment, str]] = {
    Environment.PROD: "TorrentMate",
    Environment.STAGING: "TorrentMate (staging)",
    Environment.DEV: "TorrentMate (dev)",
}

#: A PIN's lifetime when plex.tv answers no expiry: the thirty minutes the captures show.
_PIN_LIFETIME_FALLBACK_S: Final[int] = 1800

#: The most dead PINs one start deletes.
_PIN_PURGE_LIMIT: Final[int] = 100

#: The Plex kind each non-owner access starts as (``Role.defaultFor``).
_START_KIND: Final[Mapping[PlexServerAccess, StartKind]] = {
    PlexServerAccess.HOME: "plexHome",
    PlexServerAccess.SHARED: "plexGuest",
}


class ServerIdentity(Protocol):
    """The managed Plex server, as the door needs it: its machine identifier (``PlexClient``)."""

    def machine_identifier(self) -> str | None:
        """The server's ``machineIdentifier``.

        Returns:
            The identifier, or ``None`` while the server does not answer.
        """
        ...


@dataclass(frozen=True)
class PlexPinStarted:
    """A Plex sign-in started: what the browser is answered, and the nonce its cookie carries.

    Attributes:
        pin_id: plex.tv's PIN id, the one ``finish`` takes.
        sign_in_url: plex.tv's page where the person confirms the PIN; it carries the PIN
            code, so it is kept out of the ``repr``.
        nonce: The value the pin cookie carries; only its hash is stored. Kept out of the ``repr``.
        max_age_s: The pin cookie's lifetime: until the PIN expires.
    """

    pin_id: int
    sign_in_url: str = field(repr=False)
    nonce: str = field(repr=False)
    max_age_s: int


@dataclass(frozen=True)
class PlexPending:
    """The PIN is not claimed yet: the browser asks again, at most once a second."""


def _nonce_hash(nonce: str) -> str:
    """The stored form of a pin nonce.

    Args:
        nonce: The cookie's value.

    Returns:
        Its sha256, hex.
    """
    return hashlib.sha256(nonce.encode()).hexdigest()


class PlexSignInService:
    """The Plex door: starts a sign-in on plex.tv, then admits the identity it yields."""

    def __init__(
        self,
        repo_factory: Callable[[], AccountRepository],
        accounts: AccountService,
        *,
        vault: TokenVault | None,
        client_factory: Callable[[str, str], PlexAccountClient],
        server: ServerIdentity | None,
        server_token: str,
        environment: Environment,
        forward_url: str | None,
        bus: EventBus,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the door; nothing is opened and plex.tv is not asked until the first call.

        Args:
            repo_factory: Returns the account repository (opening ``app.db`` on first use).
            accounts: The account service, whose public door opens the session.
            vault: The token vault; ``None`` when no key is set — the token is then not kept.
            client_factory: Builds the plex.tv account client from the product and the
                client identifier.
            server: The managed Plex server; ``None`` when no server token is configured,
                and then nobody can be admitted.
            server_token: The server's own Plex token, whose account is the only owner admitted.
            environment: The environment, which names the product on plex.tv.
            forward_url: Where plex.tv sends the sign-in window once confirmed, from the
                configuration — never from the request; ``None`` leaves it on Plex.
            bus: The bus E8 is published on after a link moves an account's role.
            clock: The epoch clock.
        """
        self._repo_factory = repo_factory
        self._accounts = accounts
        self._vault = vault
        self._client_factory = client_factory
        self._server = server
        self._server_token = server_token
        self._environment = environment
        self._forward_url = forward_url
        self._bus = bus
        self._clock = clock
        self._client_lock = threading.Lock()
        self._owner_lock = threading.Lock()
        self._owner_plex_id: int | None = None
        self._account_client: PlexAccountClient | None = None

    def __repr__(self) -> str:
        """Name the door by its environment alone — no token, no identifier.

        Returns:
            ``PlexSignInService(environment=<env>)``.
        """
        return f"PlexSignInService(environment={self._environment.value})"

    # -- start ----------------------------------------------------------------

    def start(self) -> PlexPinStarted:
        """Create a PIN on plex.tv, keep it bound to a fresh nonce, and answer plex.tv's page.

        The PINs no sign-in can use any more — consumed, or past their expiry — are deleted first.

        Returns:
            The PIN's id, plex.tv's page, the nonce for the pin cookie and the cookie's lifetime.

        Raises:
            AppUnavailable: ``plex.server_unreachable`` — no Plex server is configured, so
                nobody could be admitted (plex.tv is not asked); ``plex.unreachable`` —
                plex.tv did not answer.
        """
        if self._server is None:
            log.warning("plex_sign_in.no_server")
            raise AppUnavailable("No Plex server is configured.", code=RefusalCode.PLEX_SERVER_UNREACHABLE)
        client = self._client()
        try:
            pin = client.create_pin()
        except PlexAccountUnreachable:
            raise AppUnavailable("plex.tv did not answer.", code=RefusalCode.PLEX_UNREACHABLE) from None
        now = self._clock()
        nonce = secrets.token_urlsafe(32)
        repo = self._repo_factory()
        repo.purge_pins(now=now, lifetime=_PIN_LIFETIME_FALLBACK_S, limit=_PIN_PURGE_LIMIT)
        repo.insert_pin(
            PlexPinRow(
                pin_id=pin.id,
                code=pin.code,
                nonce_hash=_nonce_hash(nonce),
                created_at=now,
                expires_at=pin.expires_at,
                last_checked_at=None,
                consumed_at=None,
            )
        )
        lifetime = pin.expires_at - now if pin.expires_at is not None else _PIN_LIFETIME_FALLBACK_S
        log.info("plex_sign_in.started", pin_id=pin.id)
        return PlexPinStarted(
            pin_id=pin.id,
            sign_in_url=client.sign_in_url(pin, forward_url=self._forward_url),
            nonce=nonce,
            max_age_s=max(1, int(lifetime)),
        )

    def _client(self) -> PlexAccountClient:
        """The plex.tv account client, under this environment's product and client identifier.

        The identifier is created once, in the same transaction that reads it, so two first
        starts never store two; it never changes after, so the client is built once.

        Returns:
            The client.
        """
        with self._client_lock:
            if self._account_client is None:
                repo = self._repo_factory()
                with repo.immediate():
                    identifier = repo.setting(CLIENT_IDENTIFIER_SETTING)
                    if identifier is None:
                        identifier = uuid.uuid4().hex
                        repo.set_setting(CLIENT_IDENTIFIER_SETTING, identifier)
                self._account_client = self._client_factory(PRODUCTS[self._environment], identifier)
            return self._account_client

    # -- finish ---------------------------------------------------------------

    def finish(self, pin_id: int, *, nonce: str | None, user_agent: str | None) -> SignInResult | PlexPending:
        """Ask whether the PIN is claimed and, once it is, sign in the identity it yields.

        Order: the PIN, bound to this browser (unknown, used, or another browser's nonce:
        ``plex.pin_unknown``) and alive; the check claimed (a check less than a second ago
        answers pending without asking plex.tv); the PIN checked; the identity read; the
        server's identifier; the identity's access to it; the owner cross-checked; then the
        account found, linked or created — refused if an Admin cut it —, the PIN used, the
        token sealed, in one transaction; then the session.

        Args:
            pin_id: The PIN ``start`` answered.
            nonce: The pin cookie's value; ``None`` when the browser sent none.
            user_agent: The browser's user agent, kept on the session.

        Returns:
            The signed-in account and its session, or :class:`PlexPending` while unclaimed.

        Raises:
            AppBadRequest: ``plex.pin_unknown``.
            AppConflict: ``plex.pin_expired`` — past its expiry, or forgotten by plex.tv.
            AppUnauthenticated: ``plex.token_refused`` — plex.tv refused the token the PIN
                yielded; ``auth.refused`` — no access to this server, an owned resource
                under another account than the server's, or an e-mail another identity holds.
            AppForbidden: ``auth.access_disabled`` — the identity holds an account an Admin cut.
            AppUnavailable: ``plex.unreachable``, ``plex.server_unreachable``.
        """
        repo = self._repo_factory()
        now = self._clock()
        row = repo.pin(pin_id)
        bound = (
            row is not None
            and row.consumed_at is None
            and nonce is not None
            and hmac.compare_digest(row.nonce_hash, _nonce_hash(nonce))
        )
        if row is None or not bound:
            log.info("plex_sign_in.pin_unknown", pin_id=pin_id)
            raise AppBadRequest(
                "No Plex sign-in started in this browser answers this PIN.", code=RefusalCode.PLEX_PIN_UNKNOWN
            )
        if row.expires_at is not None and now >= row.expires_at:
            raise AppConflict("The Plex PIN expired.", code=RefusalCode.PLEX_PIN_EXPIRED)
        if self._server is None:
            raise AppUnavailable("No Plex server is configured.", code=RefusalCode.PLEX_SERVER_UNREACHABLE)
        if not repo.claim_pin_check(pin_id, now=now, min_interval=PIN_CHECK_MIN_INTERVAL_S):
            return PlexPending()
        client = self._client()
        try:
            token = client.check_pin(pin_id, row.code)
            if token is None:
                return PlexPending()
            plex = client.account(token)
            access = self._access(client, token, plex)
        except PlexPinExpired:
            raise AppConflict("The Plex PIN expired.", code=RefusalCode.PLEX_PIN_EXPIRED) from None
        except PlexTokenRefused:
            log.info("plex_sign_in.token_refused", pin_id=pin_id)
            raise AppUnauthenticated(
                "plex.tv refused the token the sign-in yielded.", code=RefusalCode.PLEX_TOKEN_REFUSED
            ) from None
        except PlexAccountUnreachable:
            raise AppUnavailable("plex.tv did not answer.", code=RefusalCode.PLEX_UNREACHABLE) from None
        if access is PlexServerAccess.NONE:
            log.info("plex_sign_in.refused", reason="no_access", plex_id=plex.plex_id)
            raise AppUnauthenticated("The sign-in was refused.", code=RefusalCode.AUTH_REFUSED)
        account_id, moved = self._admit(repo, pin_id, plex, access, token)
        if moved:
            self._bus.emit(AccountRightsChanged(account_ids=(account_id,), cause=RightsChangeCause.PLEX_LINKED))
        return self._accounts.open_proven_session(account_id, user_agent=user_agent)

    def _access(self, client: PlexAccountClient, token: str, plex: PlexAccount) -> PlexServerAccess:
        """What the identity is to this server, OWNER only when cross-checked.

        Args:
            client: The plex.tv client.
            token: The identity's token.
            plex: The identity.

        Returns:
            Its access; an owned resource under another account than the server's own is
            answered NONE — refused as if unknown.

        Raises:
            AppUnavailable: ``plex.server_unreachable`` — the server's identifier unread, or
                plex.tv refused the server's own token.
            PlexTokenRefused: plex.tv refused the identity's token.
            PlexAccountUnreachable: plex.tv did not answer.
        """
        assert self._server is not None  # finish refused a door with no server first
        machine = self._server.machine_identifier()
        # An empty identifier names no server: it would match a resource listed with an empty one.
        if not machine:
            log.warning("plex_sign_in.server_unreachable")
            raise AppUnavailable("The Plex server did not answer.", code=RefusalCode.PLEX_SERVER_UNREACHABLE)
        access = client.server_access(token, machine)
        if access is PlexServerAccess.OWNER and plex.plex_id != self._server_owner(client):
            log.warning("plex_sign_in.owner_mismatch", plex_id=plex.plex_id)
            return PlexServerAccess.NONE
        return access

    def _server_owner(self, client: PlexAccountClient) -> int:
        """The plex.tv id of the account behind the server's own token, read once and cached.

        Args:
            client: The plex.tv client.

        Returns:
            The id.

        Raises:
            AppUnavailable: ``plex.server_unreachable`` — plex.tv refused the server's token,
                or none is configured.
            PlexAccountUnreachable: plex.tv did not answer (nothing cached).
        """
        with self._owner_lock:
            if self._owner_plex_id is not None:
                return self._owner_plex_id
            refused = not self._server_token
            if not refused:
                try:
                    self._owner_plex_id = client.account(self._server_token).plex_id
                except PlexTokenRefused:
                    refused = True
            if refused:
                log.warning("plex_sign_in.server_token_refused")
                raise AppUnavailable(
                    "plex.tv refused the Plex server's token.", code=RefusalCode.PLEX_SERVER_UNREACHABLE
                )
            assert self._owner_plex_id is not None
            return self._owner_plex_id

    def _admit(
        self, repo: AccountRepository, pin_id: int, plex: PlexAccount, access: PlexServerAccess, token: str
    ) -> tuple[str, bool]:
        """Find, link or create the identity's account, use the PIN and keep the token — one transaction.

        Args:
            repo: The account repository.
            pin_id: The PIN, used here.
            plex: The identity.
            access: Its access to this server (never NONE).
            token: Its token, sealed under the account when a vault is set.

        Returns:
            The account's key, and whether a link moved its role (E8 to publish).

        Raises:
            AppUnauthenticated: ``auth.refused`` — the e-mail's account is another identity's,
                or plex.tv has not confirmed the e-mail; nothing is written.
            AppForbidden: ``auth.access_disabled`` — the account is cut; nothing is written.
            AppBadRequest: ``plex.pin_unknown`` — another sign-in used the PIN meanwhile.
            AppInternalError: ``internal`` — no role answers the identity's Plex kind.
        """
        owner = access is PlexServerAccess.OWNER
        now = self._clock()
        moved = False
        with repo.immediate():
            link = repo.plex_link_by_plex_id(plex.plex_id)
            if link is not None:
                account = repo.account(link.account_id)
                assert account is not None  # a link's account is a foreign key: it exists
                _refuse_cut(account)
                linked_at = link.linked_at
            else:
                linked_at = now
                found = repo.account_by_email(plex.email)
                if found is None:
                    account = self._create(repo, plex, _first_role(repo, access), now)
                else:
                    # An e-mail plex.tv has not confirmed proves nothing: whoever typed it
                    # would take the local account that holds it.
                    if not plex.confirmed:
                        log.info("plex_sign_in.refused", reason="email_unconfirmed", plex_id=plex.plex_id)
                        raise AppUnauthenticated("The sign-in was refused.", code=RefusalCode.AUTH_REFUSED)
                    if repo.plex_link(found.id) is not None:
                        log.info("plex_sign_in.refused", reason="email_linked_elsewhere", plex_id=plex.plex_id)
                        raise AppUnauthenticated("The sign-in was refused.", code=RefusalCode.AUTH_REFUSED)
                    _refuse_cut(found)
                    account = found
                    moved = self._link_by_email(repo, found, _first_role(repo, access), owner=owner, now=now)
            if not repo.consume_pin(pin_id, now=now):
                raise AppBadRequest(
                    "No Plex sign-in started in this browser answers this PIN.", code=RefusalCode.PLEX_PIN_UNKNOWN
                )
            sealed = self._vault.seal(account.id, token) if self._vault is not None else None
            repo.upsert_plex_link(
                PlexLinkRow(
                    account_id=account.id,
                    plex_id=plex.plex_id,
                    plex_uuid=plex.uuid,
                    plex_username=plex.username,
                    server_access="owner" if owner else "shared",
                    token_ciphertext=sealed,
                    token_stored_at=now if sealed is not None else None,
                    linked_at=linked_at,
                    last_sign_in_at=now,
                )
            )
        if sealed is None:
            log.info("plex_token.not_kept", account_id=account.id)
        log.info("plex_sign_in.admitted", account_id=account.id, access=access.value, linked=link is None)
        return account.id, moved

    @staticmethod
    def _create(repo: AccountRepository, plex: PlexAccount, role: RoleRow, now: float) -> AccountRow:
        """Create the account of an identity met for the first time, on its Plex kind's role, with no password.

        Args:
            repo: The account repository, inside the transaction.
            plex: The identity.
            role: Its first role.
            now: The creation time.

        Returns:
            The new account.
        """
        account = AccountRow(
            id=f"account-{uuid.uuid4().hex}",
            name=plex.title or plex.username or plex.email.partition("@")[0],
            email=plex.email,
            avatar="",
            role_id=role.id,
            password_hash=None,
            created_at=now,
            updated_at=now,
        )
        repo.insert_account(account)
        return account

    @staticmethod
    def _link_by_email(repo: AccountRepository, account: AccountRow, role: RoleRow, *, owner: bool, now: float) -> bool:
        """Link a local account whose e-mail is the identity's: its role and password as the rulings say.

        The owner is put on, or kept on, Admin and keeps his password (the fallback when Plex is
        down). Anyone else drops its password — it signs in by Plex only — and drops to its
        Plex kind's role, the role it held recorded as ``demoted_from`` when it moves.

        Args:
            repo: The account repository, inside the transaction.
            account: The local account.
            role: The role its Plex kind starts on (Admin for the owner).
            owner: Whether the identity is the server's owner.
            now: The change time.

        Returns:
            Whether its role moved.
        """
        moved = account.role_id != role.id
        if moved:
            repo.set_role(account.id, role.id, now=now, demoted_from=None if owner else account.role_id)
        if not owner and account.password_hash is not None:
            repo.set_password_hash(account.id, None, now=now)
        return moved


def _first_role(repo: AccountRepository, access: PlexServerAccess) -> RoleRow:
    """The role an identity starts on: Admin for the owner, else its Plex kind's (``Role.defaultFor``).

    Args:
        repo: The account repository.
        access: The identity's access (never NONE).

    Returns:
        The role.

    Raises:
        AppInternalError: ``internal`` — the store names no role for it.
    """
    role = repo.role(SYSTEM_ROLE_ID) if access is PlexServerAccess.OWNER else repo.role_for_start(_START_KIND[access])
    if role is None:
        log.error("plex_sign_in.no_start_role", access=access.value)
        raise AppInternalError("No role answers this Plex kind.", code=RefusalCode.INTERNAL)
    return role


def _refuse_cut(account: AccountRow) -> None:
    """Refuse an account an Admin cut, before anything is written for it.

    Args:
        account: The account the identity is proven to hold.

    Raises:
        AppForbidden: ``auth.access_disabled``.
    """
    if not account.sign_in_allowed:
        log.info("v1_sign_in_access_disabled", account_id=account.id)
        raise AppForbidden("This account's access is cut.", code=RefusalCode.AUTH_ACCESS_DISABLED)
