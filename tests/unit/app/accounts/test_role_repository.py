"""Unit tests for ``personalscraper.app.accounts.role_repository`` — roles ↔ dataclasses over ``app.db``.

Every method round-trips its dataclass; the base's own refusals (a second admin role, a second
role for one start kind) surface as ``sqlite3.IntegrityError``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.model import Role
from personalscraper.app.accounts.rights import Right
from personalscraper.app.accounts.role_repository import RoleRepository
from personalscraper.app.store.store import AppStore

_OWN = frozenset(
    {
        Right.LIBRARY_READ,
        Right.ACQUISITION_REQUEST,
        Right.ACQUISITION_FOLLOW,
        Right.ACQUISITION_TODO_VIEW,
        Right.ACQUISITION_PILOT_OWN,
        Right.ACQUISITION_PAUSE_OWN,
    }
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` on ``tmp_path``.

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
def repo(store: AppStore) -> RoleRepository:
    """The store's role repository.

    Args:
        store: The fresh store.

    Returns:
        Its repository.
    """
    return store.roles


class TestRoles:
    """Roles, their rights and the start kinds."""

    def test_reads_the_five_seeds(self, repo: RoleRepository) -> None:
        """The seeds, in seed order, with their kinds, rights and starts; no seed has a name."""
        assert repo.roles() == [
            Role(id="admin", name=None, kind=RoleKind.ADMIN, rights=frozenset(), default_for=frozenset()),
            Role(id="household", name=None, kind=RoleKind.ORDINARY, rights=_OWN, default_for=frozenset({"plexHome"})),
            Role(
                id="plex-guest",
                name=None,
                kind=RoleKind.ORDINARY,
                rights=frozenset({Right.LIBRARY_READ}),
                default_for=frozenset({"plexGuest"}),
            ),
            Role(id="requester", name=None, kind=RoleKind.ORDINARY, rights=_OWN, default_for=frozenset()),
            Role(
                id="local-guest",
                name=None,
                kind=RoleKind.ORDINARY,
                rights=frozenset({Right.LIBRARY_READ}),
                default_for=frozenset(),
            ),
        ]

    def test_role_reads_one_or_none(self, repo: RoleRepository) -> None:
        """By id; an unknown id is None."""
        role = repo.role("admin")
        assert role is not None and role.kind is RoleKind.ADMIN
        assert repo.role("role-missing") is None

    def test_insert_role_round_trips(self, repo: RoleRepository) -> None:
        """A new role reads back as written, starts included."""
        role = Role(
            id="role-1",
            name="Friends",
            kind=RoleKind.ORDINARY,
            rights=frozenset({Right.LIBRARY_READ, Right.SYSTEM_VIEW}),
        )
        repo.insert_role(role, now=5.0)
        assert repo.role("role-1") == role

    def test_insert_role_with_a_held_start_is_refused_whole(self, repo: RoleRepository) -> None:
        """A start kind already held: IntegrityError, and no half-written role."""
        role = Role(
            id="role-1", name="X", kind=RoleKind.ORDINARY, rights=frozenset(), default_for=frozenset({"plexGuest"})
        )
        with pytest.raises(sqlite3.IntegrityError):
            repo.insert_role(role, now=5.0)
        assert repo.role("role-1") is None

    def test_a_second_admin_role_is_refused(self, repo: RoleRepository) -> None:
        """The base holds one admin role."""
        with pytest.raises(sqlite3.IntegrityError):
            repo.insert_role(Role(id="role-1", name="X", kind=RoleKind.ADMIN, rights=frozenset()), now=5.0)

    def test_update_role_stores_a_name_and_replaces_the_rights(self, repo: RoleRepository) -> None:
        """A rename stores its text; the rights list is replaced whole."""
        repo.update_role("requester", name="Requesters", rights=frozenset({Right.LIBRARY_READ}), now=6.0)
        role = repo.role("requester")
        assert role is not None
        assert (role.name, role.rights) == ("Requesters", frozenset({Right.LIBRARY_READ}))

    def test_update_role_with_nothing_keeps_both(self, repo: RoleRepository) -> None:
        """``None`` leaves the field as it was."""
        repo.update_role("requester", name=None, rights=None, now=6.0)
        role = repo.role("requester")
        assert role is not None
        assert (role.name, role.rights) == (None, _OWN)

    def test_role_for_start(self, repo: RoleRepository) -> None:
        """The role a start kind begins on."""
        role = repo.role_for_start("plexGuest")
        assert role is not None and role.id == "plex-guest"

    def test_set_role_start_moves_the_start(self, repo: RoleRepository) -> None:
        """The start kind now names the other role; the old one loses it."""
        repo.set_role_start("plexGuest", "requester")
        role = repo.role_for_start("plexGuest")
        assert role is not None and role.id == "requester"
        starts = {r.id: r.default_for for r in repo.roles()}
        assert (starts["requester"], starts["plex-guest"]) == (frozenset({"plexGuest"}), frozenset())
