"""Unit tests for ``personalscraper.app.accounts.authorise`` — the one authorisation path."""

from __future__ import annotations

import pytest

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.authorise import authorise
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import WRITE_RIGHTS, AnyOf, Public, Right, SignedIn, holds
from personalscraper.app.errors import AppForbidden, AppUnauthenticated, RefusalCode

_OPEN = InstanceCeiling(forbidden=frozenset(), read_only=False)
_READ_ONLY = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)


def _actor(
    kind: RoleKind = RoleKind.ORDINARY,
    rights: frozenset[Right] = frozenset(),
    ceiling: InstanceCeiling = _OPEN,
) -> Actor:
    """Build an actor.

    Args:
        kind: The role's kind.
        rights: The rights its role carries.
        ceiling: The instance's ceiling.

    Returns:
        The actor.
    """
    return Actor(account_id="a1", name="Alice", role_id="r1", role_kind=kind, role_rights=rights, ceiling=ceiling)


def test_public_passes_with_no_actor() -> None:
    """A public operation asks nothing."""
    authorise(None, Public())


def test_no_actor_on_signed_in_is_auth_required() -> None:
    """No session on a signed-in operation: 401 ``auth.required``."""
    with pytest.raises(AppUnauthenticated) as caught:
        authorise(None, SignedIn())

    assert caught.value.code is RefusalCode.AUTH_REQUIRED


def test_no_actor_on_a_right_is_auth_required() -> None:
    """No session on a right-gated operation: 401 too, never 403."""
    with pytest.raises(AppUnauthenticated):
        authorise(None, holds(Right.LIBRARY_READ))


def test_admin_holds_a_right_not_in_its_list() -> None:
    """Admin bypasses the list."""
    authorise(_actor(RoleKind.ADMIN), holds(Right.LIBRARY_DELETE))


def test_ceiling_refuses_admin_a_forbidden_write() -> None:
    """The preprod's ceiling refuses ``library.delete`` to Admin: ``instance.forbidden_write``."""
    ceiling = InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)

    with pytest.raises(AppForbidden) as caught:
        authorise(_actor(RoleKind.ADMIN, ceiling=ceiling), holds(Right.LIBRARY_DELETE))

    assert caught.value.code is RefusalCode.INSTANCE_FORBIDDEN_WRITE
    assert caught.value.params == {"right": "library.delete"}


def test_any_of_passes_on_one_held() -> None:
    """``AnyOf`` passes when one of its rights is held."""
    requirement = AnyOf(frozenset({Right.CONFIGURATION_VIEW, Right.SYSTEM_VIEW}))

    authorise(_actor(rights=frozenset({Right.SYSTEM_VIEW})), requirement)


def test_none_held_is_right_missing_with_sorted_rights() -> None:
    """None held: 403 ``right.missing``, the asked rights sorted."""
    requirement = AnyOf(frozenset({Right.SYSTEM_VIEW, Right.CONFIGURATION_VIEW, Right.TRACKERS_VIEW}))

    with pytest.raises(AppForbidden) as caught:
        authorise(_actor(rights=frozenset({Right.LIBRARY_READ})), requirement)

    assert caught.value.code is RefusalCode.RIGHT_MISSING
    assert caught.value.params == {"rights": ["configuration.view", "system.view", "trackers.view"]}


def test_signed_in_write_on_read_only_is_refused() -> None:
    """The session's own write on a read-only instance: 403 ``instance.read_only``."""
    with pytest.raises(AppForbidden) as caught:
        authorise(_actor(ceiling=_READ_ONLY), SignedIn(write=True))

    assert caught.value.code is RefusalCode.INSTANCE_READ_ONLY


def test_signed_in_read_on_read_only_passes() -> None:
    """A signed-in read passes on a read-only instance."""
    authorise(_actor(ceiling=_READ_ONLY), SignedIn())


def test_signed_in_write_on_an_open_instance_passes() -> None:
    """The session's own write passes where the instance is not read-only."""
    authorise(_actor(), SignedIn(write=True))


def test_holds_is_any_of_one() -> None:
    """``holds(right)`` is sugar for an ``AnyOf`` of that right alone."""
    assert holds(Right.LIBRARY_READ) == AnyOf(frozenset({Right.LIBRARY_READ}))
