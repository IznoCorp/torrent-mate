"""Unit tests for ``PlexSignInService`` — the Plex door (K1 P1-7).

plex.tv is the operator's recorded captures (``docs/reference/_samples/plex-account/``),
replayed by a fake session behind a REAL :class:`PlexAccountClient`, so every answer goes
through the client's own parsing; the Plex server is a fake answering its machine
identifier. No test reaches plex.tv or a Plex server.

The matrix, as the operator ruled it: the server's owner — cross-checked against the account
behind the server's own token — starts on Admin, a Plex Home member on the ``plexHome`` role,
any other user of the server on the ``plexGuest`` role; a local account whose e-mail matches is
linked and demoted to its Plex kind's role, its password dropped, save the owner who keeps both;
an identity with no access, or which lost it, is refused ``auth.refused`` with nothing stored;
plex.tv down, the server down and a token refused are told apart; a PIN is bound to the browser
that started it, checked at most once a second, and used by one sign-in only.
"""

from __future__ import annotations

import copy
import io
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import structlog
from cryptography.fernet import Fernet

from personalscraper.api.plex_account import PlexAccountClient
from personalscraper.app.accounts.actor import SYSTEM_ROLE_ID
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.passwords import hash_password
from personalscraper.app.accounts.plex_sign_in import (
    CLIENT_IDENTIFIER_SETTING,
    PlexPending,
    PlexPinStarted,
    PlexSignInService,
)
from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.service import AccountService, SignInResult
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.accounts.token_vault import TokenVault
from personalscraper.app.accounts.views import SignInKind
from personalscraper.app.errors import (
    AppBadRequest,
    AppConflict,
    AppForbidden,
    AppRefusal,
    AppUnauthenticated,
    AppUnavailable,
    RefusalCode,
)
from personalscraper.app.store.store import AppStore
from personalscraper.conf.environment import Environment
from personalscraper.core.event_bus import EventBus

SAMPLES = Path(__file__).resolve().parents[4] / "docs" / "reference" / "_samples" / "plex-account"

#: The planted secrets of the leak suite: none may reach a log, a refusal, an answer or a repr.
USER_TOKEN = "PLANTED-plex-user-token-8e21"
SERVER_TOKEN = "PLANTED-server-token-5a90"
CODE = "plantedpincode0123456789cd"
EMAIL = "planted.person@example.com"
#: This server's machine identifier, as the captures redact it (``server-identity.json``).
MACHINE = "REDACTED-machine-1"
#: A server the captured account reaches, not owned and not Home (``resources-owner.json``).
SHARED_MACHINE = "REDACTED-machine-3"
#: The captured identity's plex.tv id (``user-200.json``).
PLEX_ID = 900002
PIN_ID = 900001
_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)


def _sample(name: str) -> Any:
    """Read one capture's body.

    Args:
        name: The capture's stem.

    Returns:
        Its ``body``.
    """
    return copy.deepcopy(json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))["body"])


class _Response:
    """A minimal ``requests.Response`` stand-in."""

    def __init__(self, status: int, body: Any) -> None:
        """Build the answer.

        Args:
            status: HTTP status.
            body: A JSON value.
        """
        self.status_code = status
        self._body = body

    def json(self) -> Any:
        """Return the JSON body.

        Returns:
            The body.
        """
        return self._body


def _user(plex_id: int = PLEX_ID, email: str = EMAIL, *, confirmed: bool = True) -> dict[str, Any]:
    """The captured identity, its id, e-mail and e-mail confirmation set.

    Args:
        plex_id: Its plex.tv id.
        email: Its e-mail.
        confirmed: Whether plex.tv confirmed the e-mail (the capture redacts it).

    Returns:
        ``user-200.json``'s body.
    """
    body: dict[str, Any] = _sample("user-200")
    body.update(id=plex_id, email=email, authToken=None, confirmed=confirmed)
    return body


class _PlexTv:
    """plex.tv, replaying the captures by path and token.

    Each PIN created takes the next id from the captured one, so a test may start several.

    Attributes:
        calls: Every request, as ``(method, path)``.
        down: When True every request fails at the transport.
        pin: The answers to a PIN check, in order; the last repeats.
        users: The identity behind each token; an unknown token answers 401.
        resources: The resource list behind each token.
    """

    def __init__(self) -> None:
        """Answer the owner's captures: the PIN pending then claimed, the user, the owner's resources."""
        claimed = _sample("pin-claimed")
        claimed.update(authToken=USER_TOKEN, code=CODE)
        self.calls: list[tuple[str, str]] = []
        self.down = False
        self.pin: list[_Response] = [_Response(200, claimed)]
        self.users: dict[str, dict[str, Any]] = {USER_TOKEN: _user(), SERVER_TOKEN: _user()}
        self.resources: dict[str, Any] = {USER_TOKEN: _sample("resources-owner")}
        self._next_pin = PIN_ID

    def pending_then_claimed(self) -> None:
        """Answer the first check pending, every later one claimed."""
        pending = _sample("pin-pending")
        pending.update(code=CODE)
        self.pin.insert(0, _Response(200, pending))

    def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        """Answer one request.

        Args:
            method: HTTP method.
            url: Absolute URL.
            **kwargs: ``headers``, ``params``…

        Returns:
            The capture for the path.

        Raises:
            requests.ConnectionError: When :attr:`down`.
        """
        path = urlsplit(url).path
        self.calls.append((method, path))
        if self.down:
            raise requests.ConnectionError(f"planted failure carrying {USER_TOKEN}")
        token = kwargs["headers"].get("X-Plex-Token")
        if method == "POST" and path == "/api/v2/pins":
            created = _sample("pin-created")
            created.update(code=CODE, id=self._next_pin)
            self._next_pin += 1
            return _Response(201, created)
        if path.startswith("/api/v2/pins/"):
            return self.pin.pop(0) if len(self.pin) > 1 else self.pin[0]
        if path == "/api/v2/user":
            user = self.users.get(token or "")
            return _Response(200, user) if user is not None else _Response(401, _sample("user-401"))
        if path == "/api/v2/resources":
            listed = self.resources.get(token or "")
            return _Response(200, listed) if listed is not None else _Response(401, _sample("user-401"))
        return _Response(404, None)

    def count(self, prefix: str) -> int:
        """How many requests reached a path.

        Args:
            prefix: The path's start.

        Returns:
            The count.
        """
        return sum(1 for _, path in self.calls if path.startswith(prefix))


class _Server:
    """The Plex server: its machine identifier, or None while it does not answer.

    Attributes:
        identifier: What ``machine_identifier`` answers.
    """

    def __init__(self, identifier: str | None = MACHINE) -> None:
        """Hold the identifier.

        Args:
            identifier: The answer.
        """
        self.identifier = identifier

    def machine_identifier(self) -> str | None:
        """The server's machine identifier.

        Returns:
            :attr:`identifier`.
        """
        return self.identifier


class _Clock:
    """A settable clock.

    Attributes:
        now: The time it answers (epoch seconds).
    """

    def __init__(self) -> None:
        """Start at the captured PIN's creation (``pin-created.json``: 2026-10-04T12:17:35Z)."""
        self.now = 1_791_116_255.0

    def __call__(self) -> float:
        """Answer the time.

        Returns:
            :attr:`now`.
        """
        return self.now


def _local(account_id: str, email: str, role_id: str, password: str | None = "a local password 1!") -> AccountRow:
    """A local account row.

    Args:
        account_id: Its key.
        email: Its e-mail.
        role_id: Its role.
        password: Its password, hashed here.

    Returns:
        The row.
    """
    return AccountRow(
        id=account_id,
        name=account_id,
        email=email,
        avatar="",
        role_id=role_id,
        password_hash=hash_password(password) if password is not None else None,
        created_at=1.0,
        updated_at=1.0,
    )


def _link(account_id: str, plex_id: int, server_access: str) -> PlexLinkRow:
    """A Plex link with no token kept.

    Args:
        account_id: The linked account.
        plex_id: Its plex.tv id.
        server_access: ``owner`` or ``shared``.

    Returns:
        The link.
    """
    return PlexLinkRow(
        account_id=account_id,
        plex_id=plex_id,
        plex_uuid=f"uuid-{plex_id}",
        plex_username=f"plex-{plex_id}",
        server_access=server_access,  # type: ignore[arg-type]
        token_ciphertext=None,
        token_stored_at=None,
        linked_at=1.0,
        last_sign_in_at=None,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` with its five seeded roles.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def plextv() -> _PlexTv:
    """plex.tv over the captures.

    Returns:
        The fake.
    """
    return _PlexTv()


@pytest.fixture
def server() -> _Server:
    """This Plex server, answering its captured machine identifier.

    Returns:
        The fake.
    """
    return _Server()


@pytest.fixture
def clock() -> _Clock:
    """The service's clock.

    Returns:
        The clock.
    """
    return _Clock()


@pytest.fixture
def bus() -> EventBus:
    """The bus E8 travels on.

    Returns:
        A fresh bus.
    """
    return EventBus()


@pytest.fixture
def published(bus: EventBus) -> list[AccountRightsChanged]:
    """Every E8 published.

    Args:
        bus: The bus.

    Returns:
        The list.
    """
    seen: list[AccountRightsChanged] = []
    bus.subscribe(AccountRightsChanged, seen.append)
    return seen


@pytest.fixture
def vault() -> TokenVault:
    """A vault with one key.

    Returns:
        The vault.
    """
    return TokenVault([Fernet.generate_key()])


def _build(
    store: AppStore,
    plextv: _PlexTv,
    server: _Server | None,
    clock: _Clock,
    bus: EventBus,
    vault: TokenVault | None,
    *,
    server_token: str = SERVER_TOKEN,
    forward_url: str | None = None,
) -> PlexSignInService:
    """The Plex door over the store, plex.tv and the server.

    Args:
        store: The store.
        plextv: plex.tv.
        server: The Plex server, or None when none is configured.
        clock: The clock.
        bus: The bus.
        vault: The token vault, or None.
        server_token: The server's own Plex token.
        forward_url: Where plex.tv sends the window once confirmed.

    Returns:
        The service.
    """
    sessions = SessionService(lambda: store.accounts, idle_days=1, ceiling=lambda: _NO_CEILING)
    accounts = AccountService(lambda: store.accounts, sessions, bus)
    return PlexSignInService(
        lambda: store.accounts,
        accounts,
        vault=vault,
        client_factory=lambda product, client_id: PlexAccountClient(
            product=product,
            client_identifier=client_id,
            session=plextv,  # type: ignore[arg-type]
        ),
        server=server,
        server_token=server_token,
        environment=Environment.DEV,
        forward_url=forward_url,
        bus=bus,
        clock=clock,
    )


@pytest.fixture
def door(
    store: AppStore, plextv: _PlexTv, server: _Server, clock: _Clock, bus: EventBus, vault: TokenVault
) -> PlexSignInService:
    """The Plex door, wired to the fakes.

    Args:
        store: The store.
        plextv: plex.tv.
        server: The Plex server.
        clock: The clock.
        bus: The bus.
        vault: The vault.

    Returns:
        The service.
    """
    return _build(store, plextv, server, clock, bus, vault)


def _sign_in(door: PlexSignInService, clock: _Clock) -> SignInResult:
    """Start a sign-in, then finish it once plex.tv answers the PIN claimed.

    Args:
        door: The door.
        clock: The clock, moved past the check interval.

    Returns:
        The sign-in.
    """
    started = door.start()
    clock.now += 2.0
    result = door.finish(started.pin_id, nonce=started.nonce, user_agent="pytest")
    assert isinstance(result, SignInResult)
    return result


def _refusal(call: Any) -> AppRefusal:
    """Run a call expected to refuse.

    Args:
        call: A no-argument callable.

    Returns:
        The refusal raised.
    """
    with pytest.raises(AppRefusal) as raised:
        call()
    return raised.value


def _nothing_stored(store: AppStore) -> None:
    """Assert the store holds no account, link or session.

    Args:
        store: The store.
    """
    conn = store.accounts._conn
    for table in ("account", "plex_link", "session"):
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0  # noqa: S608 — fixed names


class TestStart:
    """``start`` — ``startPlexSignIn``."""

    def test_a_pin_its_sign_in_page_and_a_nonce_only_its_hash_stored(
        self, door: PlexSignInService, store: AppStore, clock: _Clock
    ) -> None:
        """The PIN is stored with the nonce's hash; the page carries the code, the product and the client id."""
        started = door.start()

        assert isinstance(started, PlexPinStarted)
        assert started.pin_id == PIN_ID
        row = store.accounts.pin(PIN_ID)
        assert row is not None and row.code == CODE and row.consumed_at is None
        assert row.nonce_hash != started.nonce and started.nonce not in row.nonce_hash
        query = parse_qs(urlsplit(started.sign_in_url).fragment.lstrip("?"))
        assert query["code"] == [CODE]
        assert query["context[device][product]"] == ["TorrentMate (dev)"]
        assert query["clientID"] == [store.accounts.setting(CLIENT_IDENTIFIER_SETTING)]
        assert "forwardUrl" not in query
        assert started.max_age_s == 1800  # the captured expiresAt, thirty minutes on

    def test_the_client_identifier_is_created_once_and_reused(
        self, door: PlexSignInService, store: AppStore, plextv: _PlexTv
    ) -> None:
        """Two starts, one identifier, the same on both sign-in pages."""
        first = door.start()
        identifier = store.accounts.setting(CLIENT_IDENTIFIER_SETTING)
        second = door.start()

        assert identifier
        assert store.accounts.setting(CLIENT_IDENTIFIER_SETTING) == identifier
        for started in (first, second):
            assert parse_qs(urlsplit(started.sign_in_url).fragment.lstrip("?"))["clientID"] == [identifier]

    def test_the_forward_address_is_the_configured_one(
        self, store: AppStore, plextv: _PlexTv, server: _Server, clock: _Clock, bus: EventBus
    ) -> None:
        """``forwardUrl`` is configuration, never anything the request carries."""
        door = _build(store, plextv, server, clock, bus, None, forward_url="https://tm.example.org/")
        query = parse_qs(urlsplit(door.start().sign_in_url).fragment.lstrip("?"))
        assert query["forwardUrl"] == ["https://tm.example.org/"]

    def test_plex_tv_down_is_unavailable_plex_unreachable(
        self, door: PlexSignInService, plextv: _PlexTv, store: AppStore
    ) -> None:
        """503 ``plex.unreachable``; no PIN stored."""
        plextv.down = True
        refusal = _refusal(door.start)
        assert isinstance(refusal, AppUnavailable)
        assert refusal.code is RefusalCode.PLEX_UNREACHABLE
        assert store.accounts.pin(PIN_ID) is None

    def test_no_server_configured_is_server_unreachable_and_asks_nothing(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus
    ) -> None:
        """No Plex server to check access against: 503 ``plex.server_unreachable`` before plex.tv is asked."""
        door = _build(store, plextv, None, clock, bus, None)
        refusal = _refusal(door.start)
        assert isinstance(refusal, AppUnavailable)
        assert refusal.code is RefusalCode.PLEX_SERVER_UNREACHABLE
        assert plextv.calls == []


class TestFirstSignIn:
    """A Plex identity met for the first time: its account is created on its Plex kind's role."""

    def test_the_owner_starts_on_admin_linked_as_owner_its_token_sealed(
        self, door: PlexSignInService, store: AppStore, vault: TokenVault
    ) -> None:
        """OWNER, cross-checked: a new account on Admin, link ``owner``, the token kept under the account."""
        result = _sign_in(door, _clock_of(door))

        assert result.account.role.id == SYSTEM_ROLE_ID
        assert result.account.sign_in_kind is SignInKind.OWNER
        assert result.account.email == EMAIL
        link = store.accounts.plex_link(result.account.id)
        assert link is not None and (link.plex_id, link.server_access) == (PLEX_ID, "owner")
        assert link.token_ciphertext is not None
        assert vault.open(result.account.id, link.token_ciphertext) == USER_TOKEN
        account = store.accounts.account(result.account.id)
        assert account is not None and account.password_hash is None

    def test_a_home_member_starts_on_the_plex_home_role(
        self, door: PlexSignInService, store: AppStore, plextv: _PlexTv
    ) -> None:
        """HOME: the role whose ``default_for`` holds ``plexHome``; stored as ``shared``."""
        plextv.resources[USER_TOKEN] = _sample("resources-home-derived")
        result = _sign_in(door, _clock_of(door))

        home = store.accounts.role_for_start("plexHome")
        assert home is not None and result.account.role.id == home.id
        assert result.account.sign_in_kind is SignInKind.PLEX
        link = store.accounts.plex_link(result.account.id)
        assert link is not None and link.server_access == "shared"

    def test_a_shared_user_starts_on_the_plex_guest_role(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus, vault: TokenVault
    ) -> None:
        """SHARED: the role whose ``default_for`` holds ``plexGuest``."""
        door = _build(store, plextv, _Server(SHARED_MACHINE), clock, bus, vault)
        result = _sign_in(door, clock)

        guest = store.accounts.role_for_start("plexGuest")
        assert guest is not None and result.account.role.id == guest.id
        assert result.account.sign_in_kind is SignInKind.PLEX

    def test_a_second_sign_in_finds_the_same_account_its_role_unchanged(
        self, door: PlexSignInService, store: AppStore
    ) -> None:
        """The owner signs in twice: one account, still Admin, the link's last sign-in moved."""
        clock = _clock_of(door)
        first = _sign_in(door, clock)
        clock.now += 10.0
        second = _sign_in(door, clock)

        assert second.account.id == first.account.id
        assert second.account.role.id == SYSTEM_ROLE_ID
        assert len(store.accounts.accounts()) == 1
        link = store.accounts.plex_link(first.account.id)
        assert link is not None and link.last_sign_in_at == clock.now

    def test_a_returning_user_is_found_by_plex_id_after_an_email_change(
        self, door: PlexSignInService, store: AppStore, plextv: _PlexTv
    ) -> None:
        """The plex.tv e-mail changed: the link by ``plex_id`` still finds the account; no second one."""
        clock = _clock_of(door)
        first = _sign_in(door, clock)
        plextv.users[USER_TOKEN] = _user(email="another.address@example.com")
        clock.now += 10.0
        second = _sign_in(door, clock)

        assert second.account.id == first.account.id
        assert len(store.accounts.accounts()) == 1

    def test_no_vault_signs_in_keeps_no_token_and_says_so_once(
        self, store: AppStore, plextv: _PlexTv, server: _Server, clock: _Clock, bus: EventBus
    ) -> None:
        """Without ``PLEX_TOKEN_KEYS``: signed in, no ciphertext, one ``plex_token.not_kept``."""
        door = _build(store, plextv, server, clock, bus, None)
        with structlog.testing.capture_logs() as logs:
            result = _sign_in(door, clock)

        link = store.accounts.plex_link(result.account.id)
        assert link is not None and link.token_ciphertext is None
        assert [entry["event"] for entry in logs].count("plex_token.not_kept") == 1


def _clock_of(door: PlexSignInService) -> _Clock:
    """The clock a door was built with.

    Args:
        door: The door.

    Returns:
        Its clock.
    """
    clock = door._clock
    assert isinstance(clock, _Clock)
    return clock


class TestOwnerCrossCheck:
    """OWNER is admitted only when the identity is the account behind the server's own token."""

    def test_an_owned_resource_under_another_account_is_refused_and_nothing_stored(
        self, door: PlexSignInService, store: AppStore, plextv: _PlexTv
    ) -> None:
        """The resource says owned, the server's token belongs to someone else: 401 ``auth.refused``."""
        plextv.users[SERVER_TOKEN] = _user(plex_id=900099)
        clock = _clock_of(door)
        started = door.start()
        clock.now += 2.0

        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))

        assert isinstance(refusal, AppUnauthenticated)
        assert refusal.code is RefusalCode.AUTH_REFUSED
        _nothing_stored(store)

    def test_the_server_account_is_read_once(self, door: PlexSignInService, plextv: _PlexTv) -> None:
        """Two owner sign-ins: the server token's identity is asked once (cached)."""
        clock = _clock_of(door)
        _sign_in(door, clock)
        clock.now += 10.0
        _sign_in(door, clock)

        server_reads = [call for call in plextv.calls if call == ("GET", "/api/v2/user")]
        assert len(server_reads) == 3  # the user twice, the server's token once

    def test_a_server_token_plex_tv_refuses_is_server_unreachable(
        self, door: PlexSignInService, store: AppStore, plextv: _PlexTv
    ) -> None:
        """The server's own token refused: nobody is admitted as owner — 503 ``plex.server_unreachable``."""
        del plextv.users[SERVER_TOKEN]
        clock = _clock_of(door)
        started = door.start()
        clock.now += 2.0

        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))

        assert isinstance(refusal, AppUnavailable)
        assert refusal.code is RefusalCode.PLEX_SERVER_UNREACHABLE
        _nothing_stored(store)

    def test_a_shared_user_never_asks_for_the_server_account(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus
    ) -> None:
        """The cross-check is the owner's: a shared sign-in reads the user's identity only."""
        door = _build(store, plextv, _Server(SHARED_MACHINE), clock, bus, None)
        _sign_in(door, clock)
        assert [call for call in plextv.calls if call == ("GET", "/api/v2/user")] == [("GET", "/api/v2/user")]


class TestLinkByEmail:
    """A local account whose e-mail is the Plex identity's: linked on its first Plex sign-in."""

    def test_a_local_account_is_linked_demoted_and_its_password_dropped(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus, published: list[AccountRightsChanged]
    ) -> None:
        """Shared user: the same account, on ``plexGuest``'s role, ``demoted_from`` its old role, no password, E8."""
        store.accounts.insert_account(_local("account-local", EMAIL.upper(), "requester"))
        door = _build(store, plextv, _Server(SHARED_MACHINE), clock, bus, None)

        result = _sign_in(door, clock)

        guest = store.accounts.role_for_start("plexGuest")
        assert guest is not None
        assert result.account.id == "account-local"
        assert (result.account.role.id, result.account.sign_in_kind) == (guest.id, SignInKind.PLEX)
        account = store.accounts.account("account-local")
        assert account is not None
        assert (account.demoted_from, account.password_hash) == ("requester", None)
        assert [(event.account_ids, event.cause) for event in published] == [
            (("account-local",), RightsChangeCause.PLEX_LINKED)
        ]

    def test_an_admin_linked_by_email_is_demoted_too(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus
    ) -> None:
        """No e-mail link carries Admin (the operator's ruling): a local Admin drops to its kind's role."""
        store.accounts.insert_account(_local("account-admin", EMAIL, SYSTEM_ROLE_ID))
        store.accounts.insert_account(_local("account-other-admin", "other@example.org", SYSTEM_ROLE_ID))
        plextv.resources[USER_TOKEN] = _sample("resources-home-derived")
        door = _build(store, plextv, _Server(), clock, bus, None)

        result = _sign_in(door, clock)

        home = store.accounts.role_for_start("plexHome")
        assert home is not None and result.account.role.id == home.id
        account = store.accounts.account("account-admin")
        assert account is not None and account.demoted_from == SYSTEM_ROLE_ID

    def test_a_link_already_on_the_kind_role_records_no_demotion_and_publishes_nothing(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus, published: list[AccountRightsChanged]
    ) -> None:
        """The role does not move: no ``demoted_from``, no E8; the password is still dropped."""
        store.accounts.insert_account(_local("account-local", EMAIL, "plex-guest"))
        door = _build(store, plextv, _Server(SHARED_MACHINE), clock, bus, None)

        _sign_in(door, clock)

        account = store.accounts.account("account-local")
        assert account is not None and (account.demoted_from, account.password_hash) == (None, None)
        assert published == []

    def test_the_owner_found_by_email_keeps_admin_and_his_password(
        self, door: PlexSignInService, store: AppStore, published: list[AccountRightsChanged]
    ) -> None:
        """The owner's local account: linked ``owner``, put on Admin, its password kept as the fallback."""
        store.accounts.insert_account(_local("account-owner", EMAIL, "requester"))
        before = store.accounts.account("account-owner")

        result = _sign_in(door, _clock_of(door))

        assert result.account.id == "account-owner"
        assert (result.account.role.id, result.account.sign_in_kind) == (SYSTEM_ROLE_ID, SignInKind.OWNER)
        account = store.accounts.account("account-owner")
        assert before is not None and account is not None
        assert account.password_hash == before.password_hash
        assert account.demoted_from is None
        assert [(event.account_ids, event.cause) for event in published] == [
            (("account-owner",), RightsChangeCause.PLEX_LINKED)
        ]

    def test_the_owner_seeded_by_the_cli_is_found_by_plex_id_and_keeps_his_password(
        self, door: PlexSignInService, store: AppStore
    ) -> None:
        """``create_owner``'s account (owner link, no token): the same account, Admin, password kept."""
        store.accounts.insert_account(_local("account-owner", "owner.elsewhere@example.org", SYSTEM_ROLE_ID))
        store.accounts.upsert_plex_link(_link("account-owner", PLEX_ID, "owner"))
        before = store.accounts.account("account-owner")

        result = _sign_in(door, _clock_of(door))

        assert result.account.id == "account-owner"
        assert result.account.role.id == SYSTEM_ROLE_ID
        account = store.accounts.account("account-owner")
        assert before is not None and account is not None and account.password_hash == before.password_hash
        assert len(store.accounts.accounts()) == 1

    def test_an_email_held_by_an_account_linked_to_another_identity_is_refused(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus
    ) -> None:
        """The e-mail's account is another plex.tv identity's: 401 ``auth.refused``, nothing changed."""
        store.accounts.insert_account(_local("account-taken", EMAIL, "household"))
        store.accounts.upsert_plex_link(_link("account-taken", 777, "shared"))
        door = _build(store, plextv, _Server(SHARED_MACHINE), clock, bus, None)
        started = door.start()
        clock.now += 2.0

        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))

        assert isinstance(refusal, AppUnauthenticated) and refusal.code is RefusalCode.AUTH_REFUSED
        assert len(store.accounts.accounts()) == 1
        link = store.accounts.plex_link("account-taken")
        assert link is not None and link.plex_id == 777

    @pytest.mark.parametrize("machine", [MACHINE, SHARED_MACHINE], ids=["owner", "shared"])
    def test_an_unconfirmed_email_links_nothing_and_is_refused(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus, vault: TokenVault, machine: str
    ) -> None:
        """plex.tv has not confirmed the e-mail: 401 ``auth.refused``; the local account untouched, nothing stored."""
        store.accounts.insert_account(_local("account-local", EMAIL, "requester"))
        before = store.accounts.account("account-local")
        plextv.users[USER_TOKEN] = _user(confirmed=False)
        door = _build(store, plextv, _Server(machine), clock, bus, vault)
        started = door.start()
        clock.now += 2.0

        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))

        assert isinstance(refusal, AppUnauthenticated) and refusal.code is RefusalCode.AUTH_REFUSED
        assert store.accounts.account("account-local") == before
        assert store.accounts.accounts() == [before]
        conn = store.accounts._conn
        for table in ("plex_link", "session"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0  # noqa: S608 — fixed names

    def test_a_linked_account_no_longer_signs_in_by_password(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus
    ) -> None:
        """After its link, the password door refuses it ``auth.refused`` (SSO only)."""
        store.accounts.insert_account(_local("account-local", EMAIL, "requester", password="a local password 1!"))
        door = _build(store, plextv, _Server(SHARED_MACHINE), clock, bus, None)
        _sign_in(door, clock)
        sessions = SessionService(lambda: store.accounts, idle_days=1, ceiling=lambda: _NO_CEILING)
        accounts = AccountService(lambda: store.accounts, sessions, bus)

        refusal = _refusal(
            lambda: accounts.sign_in_with_password(EMAIL, "a local password 1!", client_key="k", user_agent=None)
        )

        assert isinstance(refusal, AppUnauthenticated) and refusal.code is RefusalCode.AUTH_REFUSED


class TestRefusals:
    """Every way a Plex sign-in is refused, each with its contract code."""

    def _finish(self, door: PlexSignInService, clock: _Clock) -> AppRefusal:
        """Start, then finish expecting a refusal.

        Args:
            door: The door.
            clock: The clock.

        Returns:
            The refusal.
        """
        started = door.start()
        clock.now += 2.0
        return _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))

    def test_no_access_is_refused_as_if_unknown_and_nothing_stored(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus, vault: TokenVault
    ) -> None:
        """NONE: 401 ``auth.refused`` — no account, no link, no ciphertext, no session."""
        door = _build(store, plextv, _Server("REDACTED-machine-9"), clock, bus, vault)
        refusal = self._finish(door, clock)
        assert isinstance(refusal, AppUnauthenticated) and refusal.code is RefusalCode.AUTH_REFUSED
        _nothing_stored(store)

    def test_no_access_refuses_a_matching_local_account_and_leaves_it_untouched(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus
    ) -> None:
        """NONE with a local account on the e-mail: refused; the account stays local, password and role kept."""
        store.accounts.insert_account(_local("account-local", EMAIL, "requester"))
        before = store.accounts.account("account-local")
        door = _build(store, plextv, _Server("REDACTED-machine-9"), clock, bus, None)

        refusal = self._finish(door, clock)

        assert refusal.code is RefusalCode.AUTH_REFUSED
        assert store.accounts.account("account-local") == before
        assert store.accounts.plex_link("account-local") is None

    def test_an_account_that_lost_access_is_refused(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus
    ) -> None:
        """A linked account whose identity no longer reaches the server: 401 ``auth.refused``, no session."""
        store.accounts.insert_account(_local("account-gone", "gone@example.org", "household", password=None))
        store.accounts.upsert_plex_link(_link("account-gone", PLEX_ID, "shared"))
        door = _build(store, plextv, _Server("REDACTED-machine-9"), clock, bus, None)

        refusal = self._finish(door, clock)

        assert isinstance(refusal, AppUnauthenticated) and refusal.code is RefusalCode.AUTH_REFUSED
        assert store.accounts._conn.execute("SELECT count(*) FROM session").fetchone()[0] == 0

    def test_an_account_an_admin_cut_is_access_disabled_and_nothing_written(
        self, store: AppStore, plextv: _PlexTv, clock: _Clock, bus: EventBus, vault: TokenVault
    ) -> None:
        """Proven to hold a cut account: 403 ``auth.access_disabled``; no token kept, no session."""
        store.accounts.insert_account(_local("account-cut", "cut@example.org", "household", password=None))
        store.accounts.upsert_plex_link(_link("account-cut", PLEX_ID, "shared"))
        store.accounts.set_sign_in_allowed("account-cut", allowed=False, now=2.0)
        door = _build(store, plextv, _Server(SHARED_MACHINE), clock, bus, vault)

        refusal = self._finish(door, clock)

        assert isinstance(refusal, AppForbidden) and refusal.code is RefusalCode.AUTH_ACCESS_DISABLED
        link = store.accounts.plex_link("account-cut")
        assert link is not None and link.token_ciphertext is None and link.last_sign_in_at is None
        assert store.accounts._conn.execute("SELECT count(*) FROM session").fetchone()[0] == 0

    def test_a_token_plex_tv_refuses_is_token_refused(self, door: PlexSignInService, plextv: _PlexTv) -> None:
        """The claimed token answered 401: 401 ``plex.token_refused``."""
        del plextv.users[USER_TOKEN]
        refusal = self._finish(door, _clock_of(door))
        assert isinstance(refusal, AppUnauthenticated) and refusal.code is RefusalCode.PLEX_TOKEN_REFUSED

    def test_plex_tv_down_at_the_check_is_plex_unreachable(
        self, door: PlexSignInService, plextv: _PlexTv, store: AppStore
    ) -> None:
        """plex.tv down: 503 ``plex.unreachable`` — not a refusal of the token; nothing stored."""
        clock = _clock_of(door)
        started = door.start()
        plextv.down = True
        clock.now += 2.0
        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))
        assert isinstance(refusal, AppUnavailable) and refusal.code is RefusalCode.PLEX_UNREACHABLE
        _nothing_stored(store)

    @pytest.mark.parametrize("identifier", [None, ""])
    def test_the_server_down_admits_nobody(
        self, door: PlexSignInService, server: _Server, store: AppStore, identifier: str | None
    ) -> None:
        """The server's identifier unread, or read empty: 503 ``plex.server_unreachable``, nobody admitted."""
        server.identifier = identifier
        refusal = self._finish(door, _clock_of(door))
        assert isinstance(refusal, AppUnavailable) and refusal.code is RefusalCode.PLEX_SERVER_UNREACHABLE
        _nothing_stored(store)


class TestPin:
    """The PIN: bound to its browser, checked once a second, used once."""

    def test_pending_answers_pending(self, door: PlexSignInService, plextv: _PlexTv, store: AppStore) -> None:
        """Unclaimed: ``PlexPending``, nothing signed in, the PIN still open."""
        plextv.pending_then_claimed()
        clock = _clock_of(door)
        started = door.start()
        clock.now += 2.0
        assert isinstance(door.finish(started.pin_id, nonce=started.nonce, user_agent=None), PlexPending)
        row = store.accounts.pin(PIN_ID)
        assert row is not None and row.consumed_at is None
        clock.now += 2.0
        assert isinstance(door.finish(started.pin_id, nonce=started.nonce, user_agent=None), SignInResult)

    def test_two_finishes_within_a_second_make_one_check(self, door: PlexSignInService, plextv: _PlexTv) -> None:
        """The second call inside the interval answers pending without asking plex.tv."""
        plextv.pending_then_claimed()
        clock = _clock_of(door)
        started = door.start()
        clock.now += 2.0
        first = door.finish(started.pin_id, nonce=started.nonce, user_agent=None)
        clock.now += 0.4
        second = door.finish(started.pin_id, nonce=started.nonce, user_agent=None)

        assert isinstance(first, PlexPending) and isinstance(second, PlexPending)
        assert plextv.count("/api/v2/pins/") == 1

    def test_a_foreign_nonce_is_pin_unknown(self, door: PlexSignInService, plextv: _PlexTv) -> None:
        """Another browser's PIN: 400 ``plex.pin_unknown``, plex.tv not asked."""
        started = door.start()
        _clock_of(door).now += 2.0
        for nonce in ("not-the-nonce", None):
            refusal = _refusal(lambda nonce=nonce: door.finish(started.pin_id, nonce=nonce, user_agent=None))
            assert isinstance(refusal, AppBadRequest) and refusal.code is RefusalCode.PLEX_PIN_UNKNOWN
        assert plextv.count("/api/v2/pins/") == 0

    def test_an_unknown_pin_is_pin_unknown(self, door: PlexSignInService) -> None:
        """A PIN this server never started: 400 ``plex.pin_unknown``."""
        refusal = _refusal(lambda: door.finish(123, nonce="anything", user_agent=None))
        assert isinstance(refusal, AppBadRequest) and refusal.code is RefusalCode.PLEX_PIN_UNKNOWN

    def test_a_used_pin_is_pin_unknown(self, door: PlexSignInService) -> None:
        """A PIN a sign-in used: 400 ``plex.pin_unknown`` — one PIN, one session."""
        clock = _clock_of(door)
        started = door.start()
        clock.now += 2.0
        door.finish(started.pin_id, nonce=started.nonce, user_agent=None)
        clock.now += 2.0
        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))
        assert isinstance(refusal, AppBadRequest) and refusal.code is RefusalCode.PLEX_PIN_UNKNOWN

    def test_plex_tv_forgetting_the_pin_is_pin_expired(self, door: PlexSignInService, plextv: _PlexTv) -> None:
        """A check answered 404: 409 ``plex.pin_expired``."""
        plextv.pin = [_Response(404, None)]
        clock = _clock_of(door)
        started = door.start()
        clock.now += 2.0
        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))
        assert isinstance(refusal, AppConflict) and refusal.code is RefusalCode.PLEX_PIN_EXPIRED

    def test_a_pin_past_its_expiry_is_pin_expired_without_asking(
        self, door: PlexSignInService, plextv: _PlexTv
    ) -> None:
        """Past the expiry plex.tv gave: 409 ``plex.pin_expired``, plex.tv not asked."""
        clock = _clock_of(door)
        started = door.start()
        row = door._repo_factory().pin(started.pin_id)
        assert row is not None and row.expires_at is not None
        clock.now = row.expires_at + 1.0
        refusal = _refusal(lambda: door.finish(started.pin_id, nonce=started.nonce, user_agent=None))
        assert isinstance(refusal, AppConflict) and refusal.code is RefusalCode.PLEX_PIN_EXPIRED
        assert plextv.count("/api/v2/pins/") == 0


class TestNoLeak:
    """The token, the PIN code and the e-mail never reach a log, a refusal, an E8 or a repr."""

    def _planted_texts(self, captured: io.StringIO, logs: list[dict[str, Any]]) -> str:
        """Join everything a run printed or logged.

        Args:
            captured: The rendered console.
            logs: The structured records.

        Returns:
            One text.
        """
        return captured.getvalue() + json.dumps(logs, default=str)

    def test_nothing_secret_escapes_a_sign_in_or_a_refusal(
        self,
        store: AppStore,
        plextv: _PlexTv,
        server: _Server,
        clock: _Clock,
        bus: EventBus,
        vault: TokenVault,
        published: list[AccountRightsChanged],
    ) -> None:
        """A link by e-mail, a refusal on plex.tv down, a refusal of no access: no planted value anywhere."""
        store.accounts.insert_account(_local("account-local", EMAIL, "requester"))
        door = _build(store, plextv, server, clock, bus, vault)
        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        logging.getLogger().addHandler(handler)
        texts: list[str] = []
        email_free: list[str] = []
        try:
            with structlog.testing.capture_logs() as logs:
                started = door.start()
                email_free += [repr(started), str(started), repr(door), repr(store.accounts.pin(started.pin_id))]
                clock.now += 2.0
                result = door.finish(started.pin_id, nonce=started.nonce, user_agent=None)
                assert isinstance(result, SignInResult)
                texts += [repr(result), repr(store.accounts.plex_link(result.account.id))]
                email_free += [repr(event) for event in published]
                plextv.down = True
                email_free.append(json.dumps(vars(_refusal(door.start)), default=str))
                plextv.down = False
                none_door = _build(store, plextv, _Server("REDACTED-machine-9"), clock, bus, vault)
                other = none_door.start()
                clock.now += 2.0
                refusal = _refusal(lambda: none_door.finish(other.pin_id, nonce=other.nonce, user_agent=None))
                email_free += [str(refusal), json.dumps(vars(refusal), default=str)]
        finally:
            logging.getLogger().removeHandler(handler)

        printed = self._planted_texts(captured, logs).lower()
        everything = "\n".join(texts + email_free).lower() + printed
        for secret in (USER_TOKEN, SERVER_TOKEN, CODE):
            assert secret.lower() not in everything
        assert EMAIL.lower() not in "\n".join(email_free).lower() + printed
