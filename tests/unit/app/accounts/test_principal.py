"""Unit tests for ``personalscraper.app.accounts.principal`` — the maquette's ``rightsOf`` and ``isOwn``.

The model is ``frontend/maquette/design/src/lib/rights.ts``: the ceiling subtracts
before the role adds, Admin bypasses the list, « own » is membership among the
requesters or ``acquisition.pilot.any``.
"""

from __future__ import annotations

from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.principal import Principal, RoleKind
from personalscraper.app.accounts.rights import Right

_OPEN = InstanceCeiling(forbidden=frozenset(), read_only=False)


def _principal(
    kind: RoleKind,
    rights: frozenset[Right] = frozenset(),
    ceiling: InstanceCeiling = _OPEN,
) -> Principal:
    """Build a principal of one role kind.

    Args:
        kind: The role's kind.
        rights: The rights its role carries.
        ceiling: The instance's ceiling.

    Returns:
        The principal, account ``a1``.
    """
    return Principal(
        account_id="a1",
        name="Alice",
        role_id="r1",
        role_kind=kind,
        role_rights=rights,
        ceiling=ceiling,
    )


class TestHolds:
    """``holds`` = ``!forbidden.includes(right) && (bypass || carried.has(right))``."""

    def test_admin_holds_a_right_its_list_does_not_name(self) -> None:
        """Admin bypasses the list."""
        assert _principal(RoleKind.ADMIN).holds(Right.LIBRARY_DELETE)

    def test_ordinary_role_holds_what_it_carries_only(self) -> None:
        """An ordinary role holds its rights and nothing else."""
        principal = _principal(RoleKind.ORDINARY, frozenset({Right.LIBRARY_READ}))

        assert principal.holds(Right.LIBRARY_READ)
        assert not principal.holds(Right.LIBRARY_DELETE)

    def test_ceiling_subtracts_before_admin_bypasses(self) -> None:
        """A forbidden write is refused to Admin too."""
        ceiling = InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)
        principal = _principal(RoleKind.ADMIN, ceiling=ceiling)

        assert not principal.holds(Right.LIBRARY_DELETE)
        assert principal.holds(Right.LIBRARY_RESCRAPE)

    def test_holds_any_is_one_held_among_them(self) -> None:
        """``holds_any`` is true when one of the rights is held."""
        principal = _principal(RoleKind.DEFAULT, frozenset({Right.SYSTEM_VIEW}))

        assert principal.holds_any([Right.CONFIGURATION_VIEW, Right.SYSTEM_VIEW])
        assert not principal.holds_any([Right.CONFIGURATION_VIEW, Right.TRACKERS_VIEW])
        assert not principal.holds_any([])


class TestIsRequester:
    """``is_requester`` = ``isOwn``: among the requesters, or ``acquisition.pilot.any``."""

    def test_among_the_requesters(self) -> None:
        """The account is among the requesters."""
        assert _principal(RoleKind.ORDINARY).is_requester(["a2", "a1"])

    def test_pilot_any_makes_every_acquisition_its_own(self) -> None:
        """``acquisition.pilot.any`` makes the account a requester of everything."""
        principal = _principal(RoleKind.ORDINARY, frozenset({Right.ACQUISITION_PILOT_ANY}))

        assert principal.is_requester([])

    def test_neither(self) -> None:
        """Not among them and no ``pilot.any``: not its own."""
        principal = _principal(RoleKind.ORDINARY, frozenset({Right.ACQUISITION_PILOT_OWN}))

        assert not principal.is_requester(["a2"])

    def test_pilot_any_forbidden_by_the_ceiling_does_not_count(self) -> None:
        """The ceiling applies to ``pilot.any`` as to every right."""
        ceiling = InstanceCeiling(forbidden=frozenset({Right.ACQUISITION_PILOT_ANY}), read_only=False)
        principal = _principal(RoleKind.ADMIN, ceiling=ceiling)

        assert not principal.is_requester(["a2"])


def test_system_principal_is_admin_with_no_list() -> None:
    """The CLI's and the schedulers' principal: kind admin, attributed to the given account."""
    principal = Principal.system(_OPEN, account_id="owner", name="Owner")

    assert principal.role_kind is RoleKind.ADMIN
    assert principal.role_rights == frozenset()
    assert principal.account_id == "owner"
    assert principal.name == "Owner"
    assert principal.holds(Right.ACCOUNTS_MANAGE)
