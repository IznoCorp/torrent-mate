"""Unit tests for the accounts screen in ``AccountService``: the roster, accounts and roles, their guards and E8.

The guards are the maquette's (``frontend/maquette/design/src/mocks/handlers/accounts.ts``):
a manager who is not Admin gives only rights its own role holds, never touches its own
role, never touches an account on the Admin role nor gives that role; the "last resort" guard keeps
one account on the Admin role, checked and written in one ``BEGIN IMMEDIATE``. E8
(``AccountRightsChanged``) is published after the commit, naming exactly the accounts
whose role or rights moved, and never on a refusal.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import structlog

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.events import AccountRightsChanged, RightsChangeCause
from personalscraper.app.accounts.passwords import PASSWORD_MINIMUM, verify_password
from personalscraper.app.accounts.repository import AccountRepository, AccountRow, PlexLinkRow, RoleRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.service import AccountService
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.accounts.views import SignInKind
from personalscraper.app.errors import AppBadRequest, AppConflict, AppForbidden, AppNotFound, AppRefusal, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
_PASSWORD = "a provisional one"
#: The manager's role: it manages accounts but is not Admin.
_MANAGER_RIGHTS = frozenset({Right.ACCOUNTS_MANAGE, Right.LIBRARY_READ, Right.ACQUISITION_REQUEST})


def _account(account_id: str, role_id: str, created_at: float) -> AccountRow:
    """An account row with no password.

    Args:
        account_id: Its key; its e-mail is ``<key>@example.org``.
        role_id: Its role.
        created_at: Its creation time, which orders the roster.

    Returns:
        The row.
    """
    return AccountRow(
        id=account_id,
        name=account_id,
        email=f"{account_id}@example.org",
        avatar="",
        role_id=role_id,
        password_hash=None,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db``: one Admin, one manager on its own role, a household member, a local guest.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    repo = app_store.accounts
    repo.insert_role(RoleRow(id="manager", name="Manager", kind=RoleKind.ORDINARY, rights=_MANAGER_RIGHTS), now=1.0)
    repo.insert_account(_account("account-admin", "admin", 1.0))
    repo.insert_account(_account("account-manager", "manager", 2.0))
    repo.insert_account(_account("account-household", "household", 3.0))
    repo.insert_account(_account("account-guest", "local-guest", 4.0))
    try:
        yield app_store
    finally:
        app_store.close()


def _service(store: AppStore, bus: EventBus) -> AccountService:
    """The account service over a store.

    Args:
        store: The store.
        bus: The bus it publishes on.

    Returns:
        The service.
    """
    sessions = SessionService(lambda: store.accounts, ttl_hours=2, ceiling=lambda: _NO_CEILING)
    return AccountService(lambda: store.accounts, sessions, bus)


@pytest.fixture
def bus() -> EventBus:
    """The bus the service publishes on.

    Returns:
        A fresh bus.
    """
    return EventBus()


@pytest.fixture
def published(bus: EventBus) -> list[AccountRightsChanged]:
    """Every E8 the bus carries.

    Args:
        bus: The bus.

    Returns:
        The list the subscriber appends to.
    """
    seen: list[AccountRightsChanged] = []
    bus.subscribe(AccountRightsChanged, seen.append)
    return seen


@pytest.fixture
def accounts(store: AppStore, bus: EventBus) -> AccountService:
    """The account service over the store.

    Args:
        store: The store.
        bus: The bus.

    Returns:
        The service.
    """
    return _service(store, bus)


def _actor_of(repo: AccountRepository, account_id: str) -> Actor:
    """The actor an account signs in as, read from the base.

    Args:
        repo: The repository.
        account_id: The account.

    Returns:
        Its actor, with no ceiling.
    """
    account = repo.account(account_id)
    assert account is not None
    role = repo.role(account.role_id)
    assert role is not None
    return Actor(
        account_id=account.id,
        name=account.name,
        role_id=role.id,
        role_kind=role.kind,
        role_rights=role.rights,
        ceiling=_NO_CEILING,
    )


@pytest.fixture
def admin(store: AppStore) -> Actor:
    """The Admin's actor.

    Args:
        store: The store.

    Returns:
        The actor.
    """
    return _actor_of(store.accounts, "account-admin")


@pytest.fixture
def manager(store: AppStore) -> Actor:
    """The manager's actor (``accounts.manage``, not Admin).

    Args:
        store: The store.

    Returns:
        The actor.
    """
    return _actor_of(store.accounts, "account-manager")


def _refusal(call: Callable[[], object]) -> AppRefusal:
    """Run a call expected to be refused.

    Args:
        call: The call.

    Returns:
        The refusal it raised.
    """
    with pytest.raises(AppRefusal) as caught:
        call()
    return caught.value


class TestReadRoster:
    """``read_roster`` — ``readAccounts``."""

    def test_an_admin_reads_every_account_and_every_role(self, accounts: AccountService, admin: Actor) -> None:
        """Every account in creation order, every role (Admin included)."""
        roster = accounts.read_roster(admin)

        assert [one.id for one in roster.accounts] == [
            "account-admin",
            "account-manager",
            "account-household",
            "account-guest",
        ]
        assert [role.id for role in roster.roles] == [
            "admin",
            "household",
            "plex-guest",
            "requester",
            "local-guest",
            "manager",
        ]

    def test_a_manager_who_is_not_admin_never_sees_an_admin_account(
        self, accounts: AccountService, manager: Actor
    ) -> None:
        """M7: the accounts on the Admin role are left out; the roles are all there."""
        roster = accounts.read_roster(manager)

        assert [one.id for one in roster.accounts] == ["account-manager", "account-household", "account-guest"]
        assert "admin" in [role.id for role in roster.roles]

    def test_a_summary_carries_its_role_and_how_it_signs_in(
        self, store: AppStore, accounts: AccountService, admin: Actor
    ) -> None:
        """The role view, ``signInKind`` from the Plex link, no ``demotedFrom`` yet."""
        store.accounts.upsert_plex_link(
            PlexLinkRow(
                account_id="account-household",
                plex_id=7,
                plex_uuid="uuid-7",
                plex_username="plex-7",
                server_access="shared",
                token_ciphertext=None,
                token_stored_at=None,
                linked_at=1.0,
                last_sign_in_at=None,
            )
        )

        by_id = {one.id: one for one in accounts.read_roster(admin).accounts}

        assert by_id["account-household"].sign_in_kind is SignInKind.PLEX
        assert by_id["account-household"].role.id == "household"
        assert by_id["account-guest"].sign_in_kind is SignInKind.LOCAL
        assert by_id["account-guest"].demoted_from is None


class TestCreateAccount:
    """``create_account`` — ``createAccount``."""

    def test_without_a_role_it_starts_on_the_local_start_role(
        self, store: AppStore, accounts: AccountService, admin: Actor
    ) -> None:
        """No role: the role ``defaultFor`` ``local`` (``local-guest``); the password is kept as scrypt only."""
        created = accounts.create_account(admin, name="New", email="new@example.org", password=_PASSWORD)

        assert created.role.id == "local-guest"
        assert created.sign_in_kind is SignInKind.LOCAL
        assert (created.name, created.email) == ("New", "new@example.org")
        row = store.accounts.account(created.id)
        assert row is not None
        assert row.password_hash is not None
        assert row.password_hash.startswith("scrypt$")
        assert verify_password(_PASSWORD, row.password_hash)

    def test_on_the_role_asked(self, accounts: AccountService, admin: Actor) -> None:
        """A role named: the account starts on it."""
        created = accounts.create_account(
            admin, name="New", email="new@example.org", role_id="requester", password=_PASSWORD
        )
        assert created.role.id == "requester"

    def test_an_admin_creates_an_admin(self, accounts: AccountService, admin: Actor) -> None:
        """Admin gives Admin."""
        created = accounts.create_account(
            admin, name="New", email="new@example.org", role_id="admin", password=_PASSWORD
        )
        assert created.role.kind is RoleKind.ADMIN

    def test_a_manager_creates_on_a_role_within_its_rights(self, accounts: AccountService, manager: Actor) -> None:
        """``local-guest`` carries ``library.read`` alone, which the manager holds."""
        created = accounts.create_account(
            manager, name="New", email="new@example.org", role_id="local-guest", password=_PASSWORD
        )
        assert created.role.id == "local-guest"

    @pytest.mark.parametrize("email", ["", "   ", "no-at-sign", "@example.org", "someone@"])
    def test_an_invalid_email_is_refused(self, accounts: AccountService, admin: Actor, email: str) -> None:
        """400 ``account.email_invalid``."""
        refusal = _refusal(lambda: accounts.create_account(admin, name="New", email=email, password=_PASSWORD))
        assert isinstance(refusal, AppBadRequest)
        assert refusal.code is RefusalCode.ACCOUNT_EMAIL_INVALID

    def test_a_blank_name_is_refused(self, accounts: AccountService, admin: Actor) -> None:
        """400 ``account.email_invalid`` (the mock's: a local account carries a name and an e-mail)."""
        refusal = _refusal(
            lambda: accounts.create_account(admin, name="  ", email="new@example.org", password=_PASSWORD)
        )
        assert isinstance(refusal, AppBadRequest)
        assert refusal.code is RefusalCode.ACCOUNT_EMAIL_INVALID

    def test_an_unknown_role_is_not_found(self, accounts: AccountService, admin: Actor) -> None:
        """404 ``role.unknown``."""
        refusal = _refusal(
            lambda: accounts.create_account(
                admin, name="New", email="new@example.org", role_id="nope", password=_PASSWORD
            )
        )
        assert isinstance(refusal, AppNotFound)
        assert refusal.code is RefusalCode.ROLE_UNKNOWN

    def test_a_manager_never_gives_admin(self, accounts: AccountService, manager: Actor) -> None:
        """403 ``role.escalation``."""
        refusal = _refusal(
            lambda: accounts.create_account(
                manager, name="New", email="new@example.org", role_id="admin", password=_PASSWORD
            )
        )
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_ESCALATION

    def test_a_manager_never_gives_rights_it_does_not_hold(self, accounts: AccountService, manager: Actor) -> None:
        """``household`` carries ``acquisition.follow``, which the manager lacks: 403 ``role.escalation``."""
        refusal = _refusal(
            lambda: accounts.create_account(
                manager, name="New", email="new@example.org", role_id="household", password=_PASSWORD
            )
        )
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_ESCALATION

    def test_a_taken_email_whatever_its_case_conflicts(self, accounts: AccountService, admin: Actor) -> None:
        """409 ``account.email_taken``."""
        refusal = _refusal(
            lambda: accounts.create_account(admin, name="New", email="Account-Guest@Example.ORG", password=_PASSWORD)
        )
        assert isinstance(refusal, AppConflict)
        assert refusal.code is RefusalCode.ACCOUNT_EMAIL_TAKEN

    @pytest.mark.parametrize("password", [None, ""])
    def test_a_local_account_needs_a_password(
        self, accounts: AccountService, admin: Actor, password: str | None
    ) -> None:
        """400 ``password.required``."""
        refusal = _refusal(
            lambda: accounts.create_account(admin, name="New", email="new@example.org", password=password)
        )
        assert isinstance(refusal, AppBadRequest)
        assert refusal.code is RefusalCode.PASSWORD_REQUIRED

    def test_a_short_password_names_the_minimum(self, accounts: AccountService, admin: Actor) -> None:
        """400 ``password.too_short`` with ``minimum``; one character more is accepted."""
        refusal = _refusal(
            lambda: accounts.create_account(
                admin, name="New", email="new@example.org", password="x" * (PASSWORD_MINIMUM - 1)
            )
        )
        assert isinstance(refusal, AppBadRequest)
        assert refusal.code is RefusalCode.PASSWORD_TOO_SHORT
        assert refusal.params == {"minimum": PASSWORD_MINIMUM}
        assert PASSWORD_MINIMUM == 12
        accounts.create_account(admin, name="New", email="new@example.org", password="x" * PASSWORD_MINIMUM)

    def test_a_refused_creation_writes_nothing(self, store: AppStore, accounts: AccountService, admin: Actor) -> None:
        """The e-mail is checked before the password, and nothing is stored on a refusal."""
        before = len(store.accounts.accounts())
        refusal = _refusal(
            lambda: accounts.create_account(admin, name="New", email="account-guest@example.org", password="short")
        )
        assert refusal.code is RefusalCode.ACCOUNT_EMAIL_TAKEN
        assert len(store.accounts.accounts()) == before

    def test_a_creation_publishes_nothing_and_never_logs_the_password(
        self, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """No account's rights moved: no E8; the password is in no log line."""
        with structlog.testing.capture_logs() as logs:
            accounts.create_account(admin, name="New", email="new@example.org", password=_PASSWORD)
        assert published == []
        assert _PASSWORD not in repr(logs)


class TestUpdateAccount:
    """``update_account`` — ``updateAccount``."""

    def test_an_admin_assigns_a_role_and_e8_names_the_account(
        self, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """200 on the new role; one E8 ``role_assigned`` naming the account alone."""
        updated = accounts.update_account(admin, "account-guest", role_id="requester")

        assert updated.role.id == "requester"
        assert [(event.account_ids, event.cause) for event in published] == [
            (("account-guest",), RightsChangeCause.ROLE_ASSIGNED)
        ]

    def test_the_same_role_moves_nothing_and_publishes_nothing(
        self, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """No rights moved: no E8."""
        updated = accounts.update_account(admin, "account-guest", role_id="local-guest")
        assert updated.role.id == "local-guest"
        assert published == []

    def test_an_unknown_account_is_not_found(self, accounts: AccountService, admin: Actor) -> None:
        """404 ``account.unknown``."""
        refusal = _refusal(lambda: accounts.update_account(admin, "nope", role_id="requester"))
        assert isinstance(refusal, AppNotFound)
        assert refusal.code is RefusalCode.ACCOUNT_UNKNOWN

    def test_an_unknown_role_is_not_found(self, accounts: AccountService, admin: Actor) -> None:
        """404 ``role.unknown``."""
        refusal = _refusal(lambda: accounts.update_account(admin, "account-guest", role_id="nope"))
        assert isinstance(refusal, AppNotFound)
        assert refusal.code is RefusalCode.ROLE_UNKNOWN

    def test_a_manager_never_touches_its_own_role(self, accounts: AccountService, manager: Actor) -> None:
        """403 ``role.own_role``."""
        refusal = _refusal(lambda: accounts.update_account(manager, "account-manager", role_id="local-guest"))
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_OWN_ROLE

    def test_a_manager_never_touches_an_admin_account(self, accounts: AccountService, manager: Actor) -> None:
        """403 ``account.admin_untouchable``."""
        refusal = _refusal(lambda: accounts.update_account(manager, "account-admin", role_id="local-guest"))
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ACCOUNT_ADMIN_UNTOUCHABLE

    def test_a_manager_never_gives_admin(self, accounts: AccountService, manager: Actor) -> None:
        """403 ``account.admin_untouchable`` (the mock's code for Admin given by a manager)."""
        refusal = _refusal(lambda: accounts.update_account(manager, "account-guest", role_id="admin"))
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ACCOUNT_ADMIN_UNTOUCHABLE

    def test_a_manager_never_gives_rights_it_does_not_hold(self, accounts: AccountService, manager: Actor) -> None:
        """403 ``role.escalation``."""
        refusal = _refusal(lambda: accounts.update_account(manager, "account-guest", role_id="household"))
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_ESCALATION

    def test_a_manager_assigns_a_role_within_its_rights(self, accounts: AccountService, manager: Actor) -> None:
        """``plex-guest`` carries ``library.read`` alone: allowed."""
        assert accounts.update_account(manager, "account-household", role_id="plex-guest").role.id == "plex-guest"

    def test_demoting_the_last_admin_conflicts_and_publishes_nothing(
        self, store: AppStore, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """409 ``account.last_admin``: the account keeps its role, no E8."""
        refusal = _refusal(lambda: accounts.update_account(admin, "account-admin", role_id="local-guest"))

        assert isinstance(refusal, AppConflict)
        assert refusal.code is RefusalCode.ACCOUNT_LAST_ADMIN
        row = store.accounts.account("account-admin")
        assert row is not None
        assert row.role_id == "admin"
        assert published == []

    def test_an_admin_demotes_another_while_one_is_left(
        self, store: AppStore, accounts: AccountService, admin: Actor
    ) -> None:
        """Two Admins: one may go."""
        store.accounts.insert_account(_account("account-admin-2", "admin", 5.0))
        assert accounts.update_account(admin, "account-admin-2", role_id="local-guest").role.id == "local-guest"

    def test_two_admins_demoting_each_other_at_once_leave_one(self, store: AppStore, tmp_path: Path) -> None:
        """Two managers, two connections, each demotes "the other" last Admin: exactly one 409.

        Each thread waits at a barrier after reading the Admin count. Under one
        ``BEGIN IMMEDIATE`` the second cannot read before the first commits, so the
        barrier times out and the second reads one Admin left; without it both read two
        and both demotions land, leaving no Admin.
        """
        store.accounts.insert_account(_account("account-admin-2", "admin", 5.0))
        actors = {
            "account-admin": _actor_of(store.accounts, "account-admin"),
            "account-admin-2": _actor_of(store.accounts, "account-admin-2"),
        }
        barrier = threading.Barrier(2, timeout=1.0)
        stores = [AppStore(tmp_path / "app.db"), AppStore(tmp_path / "app.db")]

        def _waiting(repo: AccountRepository) -> AccountRepository:
            """Make the repository wait at the barrier after counting the Admins.

            Args:
                repo: The repository of one connection.

            Returns:
                The same repository.
            """
            counted = repo.count_on_role_kind

            def _count(kind: RoleKind) -> int:
                """Count, then wait for the other thread (or time out).

                Args:
                    kind: The role kind.

                Returns:
                    The count.
                """
                count = counted(kind)
                try:
                    barrier.wait()
                except threading.BrokenBarrierError:
                    pass
                return count

            repo.count_on_role_kind = _count  # type: ignore[method-assign]
            return repo

        repos = [_waiting(one.accounts) for one in stores]
        services = [AccountService(lambda repo=repo: repo, None, EventBus()) for repo in repos]  # type: ignore[arg-type,misc]
        outcomes: dict[str, str] = {}

        def _demote(index: int, caller: str, other: str) -> None:
            """Demote the other Admin and record the outcome.

            Args:
                index: Which service (connection).
                caller: The demoting Admin.
                other: The Admin demoted.
            """
            try:
                services[index].update_account(actors[caller], other, role_id="local-guest")
                outcomes[caller] = "ok"
            except AppRefusal as refusal:
                outcomes[caller] = str(refusal.code)

        threads = [
            threading.Thread(target=_demote, args=(0, "account-admin", "account-admin-2")),
            threading.Thread(target=_demote, args=(1, "account-admin-2", "account-admin")),
        ]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)
        finally:
            for one in stores:
                one.close()

        assert sorted(outcomes.values()) == ["account.last_admin", "ok"]
        assert store.accounts.count_on_role_kind(RoleKind.ADMIN) == 1

    def test_e8_is_published_after_the_commit(
        self, store: AppStore, tmp_path: Path, admin: Actor, bus: EventBus
    ) -> None:
        """When E8 arrives, another connection already reads the new role."""
        seen: list[str] = []

        def _read_committed(event: AccountRightsChanged) -> None:
            """Read the account's role from a separate connection.

            Args:
                event: The E8.
            """
            conn = sqlite3.connect(tmp_path / "app.db")
            try:
                seen.append(conn.execute("SELECT role_id FROM account WHERE id = ?", event.account_ids).fetchone()[0])
            finally:
                conn.close()

        bus.subscribe(AccountRightsChanged, _read_committed)
        _service(store, bus).update_account(admin, "account-guest", role_id="requester")

        assert seen == ["requester"]


class TestCreateRole:
    """``create_role`` — ``createRole``."""

    def test_an_admin_creates_an_ordinary_role(
        self, store: AppStore, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """A new ``role-…`` key, ``ordinary``, its name and rights; no E8."""
        created = accounts.create_role(admin, name=" Friends ", rights=["library.read", "trackers.view"])

        assert created.id.startswith("role-")
        assert created.kind is RoleKind.ORDINARY
        assert created.name == "Friends"
        assert created.rights == (Right.LIBRARY_READ, Right.TRACKERS_VIEW)
        assert created.default_for == ()
        assert store.accounts.role(created.id) is not None
        assert published == []

    def test_a_blank_name_is_stored_as_none(self, accounts: AccountService, admin: Actor) -> None:
        """The interface then shows its id, as for a seeded role never renamed."""
        assert accounts.create_role(admin, name="  ", rights=[]).name is None

    def test_an_unknown_right_is_refused(self, accounts: AccountService, admin: Actor) -> None:
        """400 ``right.unknown``."""
        refusal = _refusal(lambda: accounts.create_role(admin, name="X", rights=["library.read", "auth.password"]))
        assert isinstance(refusal, AppBadRequest)
        assert refusal.code is RefusalCode.RIGHT_UNKNOWN

    def test_a_manager_never_creates_a_role_wider_than_its_own(self, accounts: AccountService, manager: Actor) -> None:
        """403 ``role.escalation``."""
        refusal = _refusal(lambda: accounts.create_role(manager, name="X", rights=["library.read", "library.delete"]))
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_ESCALATION

    def test_a_manager_creates_a_role_within_its_own(self, accounts: AccountService, manager: Actor) -> None:
        """A subset of its rights: allowed."""
        assert accounts.create_role(manager, name="X", rights=["library.read"]).rights == (Right.LIBRARY_READ,)


class TestUpdateRole:
    """``update_role`` — ``updateRole``."""

    def test_new_rights_publish_e8_for_every_account_on_the_role(
        self, store: AppStore, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """One E8 ``role_rights_changed`` naming the role's accounts, in creation order."""
        store.accounts.insert_account(_account("account-guest-2", "local-guest", 6.0))

        updated = accounts.update_role(admin, "local-guest", rights=["library.read", "acquisition.request"])

        assert updated.rights == (Right.ACQUISITION_REQUEST, Right.LIBRARY_READ)
        assert [(event.account_ids, event.cause) for event in published] == [
            (("account-guest", "account-guest-2"), RightsChangeCause.ROLE_RIGHTS_CHANGED)
        ]

    def test_a_rename_alone_publishes_role_renamed(
        self, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """A seeded ordinary role is renamable; E8 ``role_renamed``."""
        updated = accounts.update_role(admin, "local-guest", name="Visitors")

        assert updated.name == "Visitors"
        assert [(event.account_ids, event.cause) for event in published] == [
            (("account-guest",), RightsChangeCause.ROLE_RENAMED)
        ]

    def test_rights_and_name_together_publish_rights_changed_once(
        self, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """The rights' cause wins; one event."""
        accounts.update_role(admin, "local-guest", name="Visitors", rights=["library.read", "trackers.view"])
        assert [event.cause for event in published] == [RightsChangeCause.ROLE_RIGHTS_CHANGED]

    def test_a_role_nobody_holds_publishes_nothing(
        self, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """No account on it: no E8."""
        accounts.update_role(admin, "plex-guest", rights=["library.read", "trackers.view"])
        assert published == []

    def test_an_empty_change_publishes_nothing(
        self, accounts: AccountService, admin: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """Neither field, a blank name, or the same rights: unchanged, no E8."""
        assert accounts.update_role(admin, "local-guest").rights == (Right.LIBRARY_READ,)
        assert accounts.update_role(admin, "local-guest", name="  ").name is None
        accounts.update_role(admin, "local-guest", rights=["library.read"])
        assert published == []

    def test_an_unknown_role_is_not_found(self, accounts: AccountService, admin: Actor) -> None:
        """404 ``role.unknown``."""
        refusal = _refusal(lambda: accounts.update_role(admin, "nope", name="X"))
        assert isinstance(refusal, AppNotFound)
        assert refusal.code is RefusalCode.ROLE_UNKNOWN

    @pytest.mark.parametrize(("name", "rights"), [("Boss", None), (None, ["library.read"])])
    def test_the_admin_role_is_immutable(
        self,
        accounts: AccountService,
        admin: Actor,
        published: list[AccountRightsChanged],
        name: str | None,
        rights: list[str] | None,
    ) -> None:
        """409 ``role.system_immutable``, renamed or re-righted, and no E8."""
        refusal = _refusal(lambda: accounts.update_role(admin, "admin", name=name, rights=rights))
        assert isinstance(refusal, AppConflict)
        assert refusal.code is RefusalCode.ROLE_SYSTEM_IMMUTABLE
        assert published == []

    def test_an_unknown_right_is_refused(self, accounts: AccountService, admin: Actor) -> None:
        """400 ``right.unknown``."""
        refusal = _refusal(lambda: accounts.update_role(admin, "local-guest", rights=["auth.password"]))
        assert isinstance(refusal, AppBadRequest)
        assert refusal.code is RefusalCode.RIGHT_UNKNOWN

    def test_a_manager_never_touches_its_own_role(self, accounts: AccountService, manager: Actor) -> None:
        """403 ``role.own_role``, even to narrow it."""
        refusal = _refusal(lambda: accounts.update_role(manager, "manager", rights=["library.read"]))
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_OWN_ROLE

    def test_a_manager_never_widens_a_role_beyond_its_own(
        self, store: AppStore, accounts: AccountService, manager: Actor, published: list[AccountRightsChanged]
    ) -> None:
        """403 ``role.escalation``; the role keeps its rights, no E8."""
        refusal = _refusal(
            lambda: accounts.update_role(manager, "local-guest", rights=["library.read", "library.delete"])
        )
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_ESCALATION
        role = store.accounts.role("local-guest")
        assert role is not None
        assert role.rights == frozenset({Right.LIBRARY_READ})
        assert published == []

    def test_a_manager_never_renames_a_role_beyond_its_own(self, accounts: AccountService, manager: Actor) -> None:
        """``household`` carries rights the manager lacks: 403 ``role.escalation``."""
        refusal = _refusal(lambda: accounts.update_role(manager, "household", name="Family"))
        assert isinstance(refusal, AppForbidden)
        assert refusal.code is RefusalCode.ROLE_ESCALATION

    def test_a_manager_sets_a_role_within_its_own(self, accounts: AccountService, manager: Actor) -> None:
        """Rights within its own and a rename of a role within them: allowed."""
        updated = accounts.update_role(
            manager, "plex-guest", name="Friends", rights=["library.read", "acquisition.request"]
        )
        assert (updated.name, updated.rights) == ("Friends", (Right.ACQUISITION_REQUEST, Right.LIBRARY_READ))
