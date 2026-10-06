"""Unit tests for the accounts' domain objects and the refusal order the services call them in.

Each ``check_*`` is tried alone, then every adjacent pair of a use case's refusal order in
which both refusals apply at once: the earlier one wins. A pair whose two refusals can never
apply together (a missing role carries no rights to escalate, a blank name is never taken) has
no test.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.model import (
    Account,
    AccountId,
    Grantor,
    PlexLink,
    Role,
    RoleId,
    SignInKind,
    is_email,
    rights_named,
)
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.roles import RoleService
from personalscraper.app.accounts.roster import RosterService
from personalscraper.app.errors import AppRefusal, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.core.event_bus import EventBus

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
_PASSWORD = "A provisional one 1!"
#: The manager's role: it manages accounts but is not Admin.
_MANAGER_RIGHTS = frozenset({Right.ACCOUNTS_MANAGE, Right.LIBRARY_READ, Right.ACQUISITION_REQUEST})
#: Rights the manager's role does not hold.
_WIDER = frozenset({Right.LIBRARY_READ, Right.ACQUISITION_PILOT_ANY})

_ADMIN_ROLE = Role(id=RoleId("admin"), name=None, kind=RoleKind.ADMIN, rights=frozenset())
_MANAGER_ROLE = Role(id=RoleId("manager"), name="Manager", kind=RoleKind.ORDINARY, rights=_MANAGER_RIGHTS)
_GUEST_ROLE = Role(id=RoleId("local-guest"), name=None, kind=RoleKind.ORDINARY, rights=frozenset({Right.LIBRARY_READ}))
_WIDE_ROLE = Role(id=RoleId("wide"), name="Wide", kind=RoleKind.ORDINARY, rights=_WIDER)


def _actor(account_id: str, role: Role) -> Actor:
    """An actor on a role, under no ceiling.

    Args:
        account_id: Its account.
        role: Its role.

    Returns:
        The actor.
    """
    return Actor(
        account_id=AccountId(account_id),
        name=account_id,
        role_id=role.id,
        role_kind=role.kind,
        role_rights=role.rights,
        ceiling=_NO_CEILING,
    )


def _link(account_id: str, server_access: str) -> PlexLink:
    """A Plex link with no kept token.

    Args:
        account_id: The linked account.
        server_access: ``owner`` or ``shared``.

    Returns:
        The link.
    """
    return PlexLink(
        account_id=AccountId(account_id),
        plex_id=hash(account_id) % 10_000,
        plex_uuid=f"uuid-{account_id}",
        plex_username=account_id,
        server_access=server_access,  # type: ignore[arg-type]
        token_ciphertext=None,
        token_stored_at=None,
        linked_at=1.0,
        last_sign_in_at=None,
    )


def _account(account_id: str, role_id: str, *, link: str | None = None, created_at: float = 1.0) -> Account:
    """An account with no password.

    Args:
        account_id: Its key; its e-mail is ``<key>@example.org``.
        role_id: Its role.
        link: Its Plex link's server access, or ``None`` for a local account.
        created_at: Its creation time.

    Returns:
        The account.
    """
    return Account(
        id=AccountId(account_id),
        name=account_id,
        email=f"{account_id}@example.org",
        avatar="",
        role_id=RoleId(role_id),
        password_hash=None,
        created_at=created_at,
        updated_at=created_at,
        plex_link=_link(account_id, link) if link is not None else None,
    )


def _code(call: Callable[[], object]) -> RefusalCode | None:
    """The code of the refusal a call raises.

    Args:
        call: The call, expected to refuse.

    Returns:
        The refusal's code.
    """
    with pytest.raises(AppRefusal) as caught:
        call()
    return caught.value.code


def _detail(call: Callable[[], object]) -> str:
    """The text of the refusal a call raises.

    Args:
        call: The call, expected to refuse.

    Returns:
        The refusal's ``detail``.
    """
    with pytest.raises(AppRefusal) as caught:
        call()
    return caught.value.detail


class TestRole:
    """``Role``: the Admin role's immutability and what a deletion depends on."""

    def test_is_admin(self) -> None:
        """Only the Admin kind is Admin."""
        assert _ADMIN_ROLE.is_admin
        assert not _MANAGER_ROLE.is_admin

    def test_the_admin_role_is_not_mutable(self) -> None:
        """``role.system_immutable``."""
        assert _code(_ADMIN_ROLE.check_mutable) is RefusalCode.ROLE_SYSTEM_IMMUTABLE

    def test_an_ordinary_role_is_mutable(self) -> None:
        """Nothing refused."""
        _MANAGER_ROLE.check_mutable()

    def test_the_admin_role_is_not_deletable(self) -> None:
        """``role.system_immutable``, with its own text."""
        assert _code(lambda: _ADMIN_ROLE.check_deletable(holders=0)) is RefusalCode.ROLE_SYSTEM_IMMUTABLE
        assert _detail(lambda: _ADMIN_ROLE.check_deletable(holders=0)) == "The Admin role is never deleted."

    def test_a_starting_role_is_not_deletable(self) -> None:
        """``role.default``, even held by nobody."""
        starting = Role(
            id=RoleId("household"),
            name=None,
            kind=RoleKind.ORDINARY,
            rights=frozenset(),
            default_for=frozenset({"plexHome"}),
        )
        assert _code(lambda: starting.check_deletable(holders=0)) is RefusalCode.ROLE_DEFAULT

    def test_a_held_role_is_not_deletable(self) -> None:
        """``role.in_use``."""
        assert _code(lambda: _MANAGER_ROLE.check_deletable(holders=1)) is RefusalCode.ROLE_IN_USE

    def test_a_free_role_is_deletable(self) -> None:
        """Nothing refused."""
        _MANAGER_ROLE.check_deletable(holders=0)

    def test_system_immutable_comes_before_default(self) -> None:
        """An Admin role a start kind names: ``role.system_immutable``."""
        role = Role(
            id=RoleId("admin"), name=None, kind=RoleKind.ADMIN, rights=frozenset(), default_for=frozenset({"plexHome"})
        )
        assert _code(lambda: role.check_deletable(holders=0)) is RefusalCode.ROLE_SYSTEM_IMMUTABLE

    def test_default_comes_before_in_use(self) -> None:
        """A starting role an account holds: ``role.default``."""
        role = Role(
            id=RoleId("household"),
            name=None,
            kind=RoleKind.ORDINARY,
            rights=frozenset(),
            default_for=frozenset({"plexHome"}),
        )
        assert _code(lambda: role.check_deletable(holders=2)) is RefusalCode.ROLE_DEFAULT


class TestAccount:
    """``Account``: how it signs in, and the access, Admin seat and password it keeps."""

    @pytest.mark.parametrize(
        ("link", "kind"), [(None, SignInKind.LOCAL), ("owner", SignInKind.OWNER), ("shared", SignInKind.PLEX)]
    )
    def test_sign_in_kind_comes_from_the_plex_link(self, link: str | None, kind: SignInKind) -> None:
        """No link is local; an owner link is the owner; any other is Plex."""
        assert _account("account-a", "household", link=link).sign_in_kind is kind

    def test_the_owners_access_is_never_cut(self) -> None:
        """``account.owner_access``."""
        owner = _account("account-owner", "admin", link="owner")
        assert _code(lambda: owner.check_access_cut(by=AccountId("account-admin"))) is RefusalCode.ACCOUNT_OWNER_ACCESS

    def test_ones_own_access_is_never_cut(self) -> None:
        """``account.own_access``."""
        admin = _account("account-admin", "admin")
        assert _code(lambda: admin.check_access_cut(by=AccountId("account-admin"))) is RefusalCode.ACCOUNT_OWN_ACCESS

    def test_another_accounts_access_is_cut(self) -> None:
        """Nothing refused."""
        _account("account-guest", "local-guest", link="shared").check_access_cut(by=AccountId("account-admin"))

    def test_owner_access_comes_before_own_access(self) -> None:
        """The owner cutting its own access: ``account.owner_access``."""
        owner = _account("account-owner", "admin", link="owner")
        assert _code(lambda: owner.check_access_cut(by=AccountId("account-owner"))) is RefusalCode.ACCOUNT_OWNER_ACCESS

    def test_the_owner_never_leaves_admin(self) -> None:
        """``account.owner_admin``, however many Admins remain."""
        owner = _account("account-owner", "admin", link="owner")

        def refused() -> object:
            return owner.check_leaves_admin(current=_ADMIN_ROLE, target=_GUEST_ROLE, admins=3)

        assert _code(refused) is RefusalCode.ACCOUNT_OWNER_ADMIN

    def test_the_last_admin_never_leaves_admin(self) -> None:
        """``account.last_admin``."""
        admin = _account("account-admin", "admin")

        def refused() -> object:
            return admin.check_leaves_admin(current=_ADMIN_ROLE, target=_GUEST_ROLE, admins=1)

        assert _code(refused) is RefusalCode.ACCOUNT_LAST_ADMIN

    def test_an_admin_among_others_leaves_admin(self) -> None:
        """Nothing refused."""
        _account("account-admin", "admin").check_leaves_admin(current=_ADMIN_ROLE, target=_GUEST_ROLE, admins=2)

    def test_the_owner_kept_on_admin_is_not_refused(self) -> None:
        """A target on Admin leaves nothing."""
        owner = _account("account-owner", "admin", link="owner")
        owner.check_leaves_admin(current=_ADMIN_ROLE, target=_ADMIN_ROLE, admins=1)

    def test_owner_admin_comes_before_last_admin(self) -> None:
        """The owner alone on Admin, leaving it: ``account.owner_admin``."""
        owner = _account("account-owner", "admin", link="owner")

        def refused() -> object:
            return owner.check_leaves_admin(current=_ADMIN_ROLE, target=_GUEST_ROLE, admins=1)

        assert _code(refused) is RefusalCode.ACCOUNT_OWNER_ADMIN

    @pytest.mark.parametrize(
        ("link", "code"), [("owner", RefusalCode.PASSWORD_HELD_BY_CLI), ("shared", RefusalCode.AUTH_PLEX_ONLY)]
    )
    def test_a_password_held_elsewhere_is_refused(self, link: str, code: RefusalCode) -> None:
        """The owner's is the CLI's; a Plex account holds none."""
        assert _code(_account("account-a", "admin", link=link).check_password_held_here) is code

    def test_a_local_password_is_held_here(self) -> None:
        """Nothing refused."""
        _account("account-a", "local-guest").check_password_held_here()


class TestGrantor:
    """``Grantor``: what the caller may give, touch and rename, measured against its session's role."""

    def test_of_reads_the_owner_from_the_link(self) -> None:
        """An owner link makes the owner; a shared one or none does not."""
        admin = _actor("account-admin", _ADMIN_ROLE)
        assert Grantor.of(admin, _link("account-admin", "owner")).is_owner
        assert not Grantor.of(admin, _link("account-admin", "shared")).is_owner
        assert not Grantor.of(admin, None).is_owner

    def test_an_admin_gives_any_role(self) -> None:
        """Nothing refused, Admin included."""
        grantor = Grantor(actor=_actor("account-admin", _ADMIN_ROLE), is_owner=False)
        grantor.check_may_give(_ADMIN_ROLE)
        grantor.check_may_give(_WIDE_ROLE)
        grantor.check_may_give_rights(_WIDER)
        grantor.check_may_rename(_WIDE_ROLE)

    @pytest.mark.parametrize("role", [_ADMIN_ROLE, _WIDE_ROLE])
    def test_a_manager_never_gives_admin_nor_a_wider_role(self, role: Role) -> None:
        """``role.escalation``."""
        grantor = Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False)
        assert _code(lambda: grantor.check_may_give(role)) is RefusalCode.ROLE_ESCALATION

    def test_a_manager_gives_a_role_within_its_rights(self) -> None:
        """Nothing refused."""
        Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False).check_may_give(_GUEST_ROLE)

    def test_a_manager_never_gives_wider_rights(self) -> None:
        """``role.escalation``, with the rights' text."""
        grantor = Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False)
        assert _code(lambda: grantor.check_may_give_rights(_WIDER)) is RefusalCode.ROLE_ESCALATION
        assert (
            _detail(lambda: grantor.check_may_give_rights(_WIDER))
            == "The role would hold rights the caller's does not."
        )
        grantor.check_may_give_rights(frozenset({Right.LIBRARY_READ}))

    def test_a_manager_never_renames_a_wider_role(self) -> None:
        """``role.escalation``, with the rename's text."""
        grantor = Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False)
        assert _code(lambda: grantor.check_may_rename(_WIDE_ROLE)) is RefusalCode.ROLE_ESCALATION
        assert (
            _detail(lambda: grantor.check_may_rename(_WIDE_ROLE))
            == "A manager renames only a role within its own rights."
        )
        grantor.check_may_rename(_GUEST_ROLE)

    def test_only_the_owner_gives_admin(self) -> None:
        """``account.admin_owner_only`` for an Admin who is not the owner."""
        admin = _actor("account-admin", _ADMIN_ROLE)
        assert _code(Grantor(actor=admin, is_owner=False).check_may_give_admin) is RefusalCode.ACCOUNT_ADMIN_OWNER_ONLY
        Grantor(actor=admin, is_owner=True).check_may_give_admin()

    def test_a_manager_never_changes_its_own_role(self) -> None:
        """``role.own_role``; an Admin's own role is the Admin one, refused elsewhere."""
        manager = Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False)
        assert _code(lambda: manager.check_may_change_role(_MANAGER_ROLE)) is RefusalCode.ROLE_OWN_ROLE
        manager.check_may_change_role(_GUEST_ROLE)
        Grantor(actor=_actor("account-admin", _ADMIN_ROLE), is_owner=False).check_may_change_role(_ADMIN_ROLE)

    def test_a_manager_never_touches_its_own_account(self) -> None:
        """``role.own_role``."""
        grantor = Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False)
        own = _account("account-manager", "manager")
        assert _code(lambda: grantor.check_may_touch(own, _MANAGER_ROLE, _GUEST_ROLE)) is RefusalCode.ROLE_OWN_ROLE

    @pytest.mark.parametrize(("current", "target"), [(_ADMIN_ROLE, _GUEST_ROLE), (_GUEST_ROLE, _ADMIN_ROLE)])
    def test_a_manager_never_touches_admin(self, current: Role, target: Role) -> None:
        """``account.admin_untouchable``, from Admin or to it."""
        grantor = Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False)
        other = _account("account-other", current.id)

        def refused() -> object:
            return grantor.check_may_touch(other, current, target)

        assert _code(refused) is RefusalCode.ACCOUNT_ADMIN_UNTOUCHABLE

    def test_an_admin_touches_anything(self) -> None:
        """Nothing refused, its own account and Admin included."""
        grantor = Grantor(actor=_actor("account-admin", _ADMIN_ROLE), is_owner=False)
        grantor.check_may_touch(_account("account-admin", "admin"), _ADMIN_ROLE, _GUEST_ROLE)

    def test_own_role_comes_before_admin_untouchable(self) -> None:
        """A manager putting its own account on Admin: ``role.own_role``."""
        grantor = Grantor(actor=_actor("account-manager", _MANAGER_ROLE), is_owner=False)
        own = _account("account-manager", "manager")
        assert _code(lambda: grantor.check_may_touch(own, _MANAGER_ROLE, _ADMIN_ROLE)) is RefusalCode.ROLE_OWN_ROLE


class TestReadings:
    """The two readings the services share: an e-mail, and right names."""

    @pytest.mark.parametrize(("text", "valid"), [("a@b.org", True), ("a@", False), ("@b", False), ("a b@c.org", False)])
    def test_is_email(self, text: str, valid: bool) -> None:
        """Something on both sides of one ``@``, no space."""
        assert is_email(text) is valid

    def test_rights_named(self) -> None:
        """Known names read; an unknown one is ``right.unknown``."""
        assert rights_named(["library.read"]) == frozenset({Right.LIBRARY_READ})
        assert _code(lambda: rights_named(["no.such"])) is RefusalCode.RIGHT_UNKNOWN


# ── the services' order, where two refusals apply at once ───────────────────


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db``: the owner on Admin, an Admin who is not the owner, a manager, a household member.

    Also a ``wide`` role, wider than the manager's, held by the household member's neighbour.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    app_store.roles.insert_role(_MANAGER_ROLE, now=1.0)
    app_store.roles.insert_role(_WIDE_ROLE, now=1.0)
    for account in (
        _account("account-owner", "admin", created_at=1.0),
        _account("account-admin", "admin", created_at=2.0),
        _account("account-manager", "manager", created_at=3.0),
        _account("account-household", "household", created_at=4.0),
        _account("account-wide", "wide", created_at=5.0),
    ):
        app_store.accounts.insert_account(account)
    app_store.accounts.upsert_plex_link(_link("account-owner", "owner"))
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def roster(store: AppStore) -> RosterService:
    """The roster service.

    Args:
        store: The store.

    Returns:
        The service.
    """
    return RosterService(store, EventBus())


@pytest.fixture
def roles(store: AppStore) -> RoleService:
    """The role service.

    Args:
        store: The store.

    Returns:
        The service.
    """
    return RoleService(store, EventBus())


_OWNER = _actor("account-owner", _ADMIN_ROLE)
_ADMIN = _actor("account-admin", _ADMIN_ROLE)
_MANAGER = _actor("account-manager", _MANAGER_ROLE)


class TestCreateAccountOrder:
    """``create_account``: email_invalid → role.unknown → escalation → admin_owner_only → email_taken → password."""

    def test_email_invalid_before_role_unknown(self, roster: RosterService) -> None:
        """A bad e-mail on a missing role: ``account.email_invalid``."""

        def refused() -> object:
            return roster.create_account(_ADMIN, name="N", email="nope", role_id="gone", password=_PASSWORD)

        assert _code(refused) is RefusalCode.ACCOUNT_EMAIL_INVALID

    def test_escalation_before_admin_owner_only(self, roster: RosterService) -> None:
        """A manager, not the owner, giving Admin: ``role.escalation``."""

        def refused() -> object:
            return roster.create_account(_MANAGER, name="N", email="n@x.org", role_id="admin", password=_PASSWORD)

        assert _code(refused) is RefusalCode.ROLE_ESCALATION

    def test_admin_owner_only_before_email_taken(self, roster: RosterService) -> None:
        """An Admin who is not the owner giving Admin on a taken e-mail: ``account.admin_owner_only``."""

        def refused() -> object:
            return roster.create_account(
                _ADMIN, name="N", email="account-household@example.org", role_id="admin", password=_PASSWORD
            )

        assert _code(refused) is RefusalCode.ACCOUNT_ADMIN_OWNER_ONLY

    def test_email_taken_before_the_password(self, roster: RosterService) -> None:
        """A taken e-mail with no password: ``account.email_taken``."""

        def refused() -> object:
            return roster.create_account(
                _ADMIN, name="N", email="ACCOUNT-HOUSEHOLD@example.org", role_id="local-guest", password=None
            )

        assert _code(refused) is RefusalCode.ACCOUNT_EMAIL_TAKEN


class TestUpdateAccountOrder:
    """``update_account``: unknown → role.unknown → own_role → admin_untouchable → escalation → … → last_admin."""

    def test_account_unknown_before_role_unknown(self, roster: RosterService) -> None:
        """A missing account on a missing role: ``account.unknown``."""
        assert (
            _code(lambda: roster.update_account(_ADMIN, "account-gone", role_id="gone")) is RefusalCode.ACCOUNT_UNKNOWN
        )

    def test_own_role_before_admin_untouchable(self, roster: RosterService) -> None:
        """A manager putting its own account on Admin: ``role.own_role``."""
        assert (
            _code(lambda: roster.update_account(_MANAGER, "account-manager", role_id="admin"))
            is RefusalCode.ROLE_OWN_ROLE
        )

    def test_admin_untouchable_before_escalation(self, roster: RosterService) -> None:
        """A manager putting an account on Admin (an escalation too): ``account.admin_untouchable``."""

        def refused() -> object:
            return roster.update_account(_MANAGER, "account-household", role_id="admin")

        assert _code(refused) is RefusalCode.ACCOUNT_ADMIN_UNTOUCHABLE

    def test_owner_admin_before_last_admin(self, store: AppStore, roster: RosterService) -> None:
        """The owner alone on Admin, put on another role: ``account.owner_admin``."""
        store.accounts.set_role(AccountId("account-admin"), RoleId("household"), now=9.0)

        def refused() -> object:
            return roster.update_account(_OWNER, "account-owner", role_id="household")

        assert _code(refused) is RefusalCode.ACCOUNT_OWNER_ADMIN


class TestSetAccountAccessOrder:
    """``set_account_access``: access_admin_only → unknown → owner_access → own_access."""

    def test_access_admin_only_before_unknown(self, roster: RosterService) -> None:
        """A manager on a missing account: ``account.access_admin_only``."""

        def refused() -> object:
            return roster.set_account_access(_MANAGER, "account-gone", allowed=False)

        assert _code(refused) is RefusalCode.ACCOUNT_ACCESS_ADMIN_ONLY

    def test_owner_access_before_own_access(self, roster: RosterService) -> None:
        """The owner cutting its own access: ``account.owner_access``."""

        def refused() -> object:
            return roster.set_account_access(_OWNER, "account-owner", allowed=False)

        assert _code(refused) is RefusalCode.ACCOUNT_OWNER_ACCESS


class TestResetAccountPasswordOrder:
    """``reset_account_password``: reset_admin_only → reset_own → unknown → held elsewhere → password."""

    def test_reset_admin_only_before_reset_own(self, roster: RosterService) -> None:
        """A manager resetting its own password: ``password.reset_admin_only``."""

        def refused() -> object:
            return roster.reset_account_password(_MANAGER, "account-manager", password=_PASSWORD)

        assert _code(refused) is RefusalCode.PASSWORD_RESET_ADMIN_ONLY

    def test_reset_own_before_unknown(self, roster: RosterService) -> None:
        """An Admin whose account is gone, resetting it: ``password.reset_own``."""
        ghost = _actor("account-ghost", _ADMIN_ROLE)

        def refused() -> object:
            return roster.reset_account_password(ghost, "account-ghost", password=_PASSWORD)

        assert _code(refused) is RefusalCode.PASSWORD_RESET_OWN

    def test_held_elsewhere_before_the_password(self, roster: RosterService) -> None:
        """The owner's account given an empty password: ``password.held_by_cli``."""

        def refused() -> object:
            return roster.reset_account_password(_ADMIN, "account-owner", password="")

        assert _code(refused) is RefusalCode.PASSWORD_HELD_BY_CLI


class TestCreateRoleOrder:
    """``create_role``: right.unknown → name_required → name_taken → escalation."""

    def test_right_unknown_before_name_required(self, roles: RoleService) -> None:
        """An unknown right under a blank name: ``right.unknown``."""
        assert _code(lambda: roles.create_role(_ADMIN, name=" ", rights=["no.such"])) is RefusalCode.RIGHT_UNKNOWN

    def test_name_taken_before_escalation(self, roles: RoleService) -> None:
        """A manager taking a name with wider rights: ``role.name_taken``."""

        def refused() -> object:
            return roles.create_role(_MANAGER, name=" WIDE ", rights=[r.value for r in _WIDER])

        assert _code(refused) is RefusalCode.ROLE_NAME_TAKEN


class TestUpdateRoleOrder:
    """``update_role``: right.unknown → unknown → system_immutable → own_role → escalation ×2 → name_taken."""

    def test_right_unknown_before_role_unknown(self, roles: RoleService) -> None:
        """An unknown right on a missing role: ``right.unknown``."""
        assert _code(lambda: roles.update_role(_ADMIN, "gone", rights=["no.such"])) is RefusalCode.RIGHT_UNKNOWN

    def test_own_role_before_escalation(self, roles: RoleService) -> None:
        """A manager widening its own role: ``role.own_role``."""

        def refused() -> object:
            return roles.update_role(_MANAGER, "manager", rights=[r.value for r in _WIDER])

        assert _code(refused) is RefusalCode.ROLE_OWN_ROLE

    def test_rights_escalation_before_rename_escalation(self, roles: RoleService) -> None:
        """A manager widening and renaming a wider role: the rights' ``role.escalation``."""

        def refused() -> object:
            return roles.update_role(_MANAGER, "wide", name="Renamed", rights=[r.value for r in _WIDER])

        assert _detail(refused) == "The role would hold rights the caller's does not."

    def test_rename_escalation_before_name_taken(self, roles: RoleService) -> None:
        """A manager renaming a wider role to a taken name: ``role.escalation``."""
        assert _code(lambda: roles.update_role(_MANAGER, "wide", name="Manager")) is RefusalCode.ROLE_ESCALATION


class TestDeleteRoleOrder:
    """``delete_role``: unknown → system_immutable → default → in_use → escalation."""

    def test_system_immutable_before_default(self, store: AppStore, roles: RoleService) -> None:
        """The Admin role a start kind names: ``role.system_immutable``."""
        store.roles.set_role_start("plexHome", RoleId("admin"))
        assert _code(lambda: roles.delete_role(_ADMIN, "admin")) is RefusalCode.ROLE_SYSTEM_IMMUTABLE

    def test_default_before_in_use(self, roles: RoleService) -> None:
        """``household`` starts the Plex Home members and an account holds it: ``role.default``."""
        assert _code(lambda: roles.delete_role(_ADMIN, "household")) is RefusalCode.ROLE_DEFAULT

    def test_in_use_before_escalation(self, roles: RoleService) -> None:
        """A manager deleting a held role wider than its own: ``role.in_use``."""
        assert _code(lambda: roles.delete_role(_MANAGER, "wide")) is RefusalCode.ROLE_IN_USE
