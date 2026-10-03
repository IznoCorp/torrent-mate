"""Unit tests for ``personalscraper.app.accounts.actor`` — the maquette's ``rightsOf`` and ``isOwn``.

The model is ``frontend/maquette/design/src/lib/rights.ts``: the ceiling subtracts
before the role adds, Admin bypasses the list, « own » is membership among the
requesters or ``acquisition.pilot.any``.
"""

from __future__ import annotations

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import Right

_OPEN = InstanceCeiling(forbidden=frozenset(), read_only=False)


def _actor(
    kind: RoleKind,
    rights: frozenset[Right] = frozenset(),
    ceiling: InstanceCeiling = _OPEN,
) -> Actor:
    """Build an actor of one role kind.

    Args:
        kind: The role's kind.
        rights: The rights its role carries.
        ceiling: The instance's ceiling.

    Returns:
        The actor, account ``a1``.
    """
    return Actor(
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
        assert _actor(RoleKind.ADMIN).holds(Right.LIBRARY_DELETE)

    def test_ordinary_role_holds_what_it_carries_only(self) -> None:
        """An ordinary role holds its rights and nothing else."""
        actor = _actor(RoleKind.ORDINARY, frozenset({Right.LIBRARY_READ}))

        assert actor.holds(Right.LIBRARY_READ)
        assert not actor.holds(Right.LIBRARY_DELETE)

    def test_ceiling_subtracts_before_admin_bypasses(self) -> None:
        """A forbidden write is refused to Admin too."""
        ceiling = InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)
        actor = _actor(RoleKind.ADMIN, ceiling=ceiling)

        assert not actor.holds(Right.LIBRARY_DELETE)
        assert actor.holds(Right.LIBRARY_RESCRAPE)

    def test_holds_any_is_one_held_among_them(self) -> None:
        """``holds_any`` is true when one of the rights is held."""
        actor = _actor(RoleKind.ORDINARY, frozenset({Right.SYSTEM_VIEW}))

        assert actor.holds_any([Right.CONFIGURATION_VIEW, Right.SYSTEM_VIEW])
        assert not actor.holds_any([Right.CONFIGURATION_VIEW, Right.TRACKERS_VIEW])
        assert not actor.holds_any([])


class TestIsRequester:
    """``is_requester`` = ``isOwn``: among the requesters, or ``acquisition.pilot.any``."""

    def test_among_the_requesters(self) -> None:
        """The account is among the requesters."""
        assert _actor(RoleKind.ORDINARY).is_requester(["a2", "a1"])

    def test_pilot_any_makes_every_acquisition_its_own(self) -> None:
        """``acquisition.pilot.any`` makes the account a requester of everything."""
        actor = _actor(RoleKind.ORDINARY, frozenset({Right.ACQUISITION_PILOT_ANY}))

        assert actor.is_requester([])

    def test_neither(self) -> None:
        """Not among them and no ``pilot.any``: not its own."""
        actor = _actor(RoleKind.ORDINARY, frozenset({Right.ACQUISITION_PILOT_OWN}))

        assert not actor.is_requester(["a2"])

    def test_pilot_any_forbidden_by_the_ceiling_does_not_count(self) -> None:
        """The ceiling applies to ``pilot.any`` as to every right."""
        ceiling = InstanceCeiling(forbidden=frozenset({Right.ACQUISITION_PILOT_ANY}), read_only=False)
        actor = _actor(RoleKind.ADMIN, ceiling=ceiling)

        assert not actor.is_requester(["a2"])


def test_system_actor_is_admin_with_no_list() -> None:
    """The CLI's and the schedulers' actor: kind admin, attributed to the given account."""
    actor = Actor.system(_OPEN, account_id="owner", name="Owner")

    assert actor.role_kind is RoleKind.ADMIN
    assert actor.role_rights == frozenset()
    assert actor.account_id == "owner"
    assert actor.name == "Owner"
    assert actor.holds(Right.ACCOUNTS_MANAGE)
