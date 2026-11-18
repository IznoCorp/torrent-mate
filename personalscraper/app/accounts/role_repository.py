"""The roles' rows in ``app.db`` — a role, its rights and the start kinds it begins.

Rows ↔ :class:`~personalscraper.app.accounts.model.Role`, and nothing more: no rule lives here
(who may rename a role, when it may be deleted — those are the model's, asked by the services).
The base keeps its own constraints (one admin role, one role per start kind) and this module
lets them surface as ``sqlite3.IntegrityError``.

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, a method writing several statements runs them under a SAVEPOINT, and a service that
needs several calls to be one act wraps them in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import Final

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.ids import RoleId
from personalscraper.app.accounts.model import Role, StartKind
from personalscraper.app.accounts.rights import Right
from personalscraper.app.store.transaction import atomic
from personalscraper.core.sqlite import serialised

#: The savepoint a multi-statement write runs under; its name predates the split by aggregate,
#: and is kept so a failure's SQL and log are unchanged.
_SAVEPOINT: Final = "account_repository"


class RoleRepository:
    """The roles' rows over one ``app.db`` connection it is GIVEN; it opens nothing."""

    def __init__(self, conn: sqlite3.Connection, *, lock: threading.RLock | None = None) -> None:
        """Wrap an open, migrated ``app.db`` connection.

        Args:
            conn: The connection, in autocommit mode.
            lock: The lock every user of ``conn`` holds around it (the store's); a lock of
                its own when ``conn`` is this repository's alone.
        """
        self._conn = conn
        self._lock = lock if lock is not None else threading.RLock()

    def _role_rows(self, where: str = "", params: tuple[object, ...] = ()) -> list[Role]:
        """Read roles with their rights and start kinds, in creation order.

        Args:
            where: An optional ``WHERE`` clause on ``role``.
            params: Its parameters.

        Returns:
            The roles.
        """
        roles = self._conn.execute(
            f"SELECT id, name, kind FROM role {where} ORDER BY created_at, rowid",  # noqa: S608 — fixed clauses
            params,
        ).fetchall()
        rights: dict[RoleId, set[Right]] = {}
        for role_id, right_name in self._conn.execute("SELECT role_id, right_name FROM role_right"):
            rights.setdefault(role_id, set()).add(Right(right_name))
        starts: dict[RoleId, set[StartKind]] = {}
        for start, role_id in self._conn.execute("SELECT start, role_id FROM role_start"):
            starts.setdefault(role_id, set()).add(start)
        return [
            Role(
                id=role_id,
                name=name,
                kind=RoleKind(kind),
                rights=frozenset(rights.get(role_id, ())),
                default_for=frozenset(starts.get(role_id, ())),
            )
            for role_id, name, kind in roles
        ]

    @serialised
    def roles(self) -> list[Role]:
        """Every role, in creation order (the seeds first, in seed order).

        Returns:
            The roles.
        """
        return self._role_rows()

    @serialised
    def role(self, role_id: RoleId) -> Role | None:
        """One role by key.

        Args:
            role_id: Its key.

        Returns:
            The role, or ``None``.
        """
        rows = self._role_rows("WHERE id = ?", (role_id,))
        return rows[0] if rows else None

    @serialised
    def insert_role(self, role: Role, *, now: float) -> None:
        """Insert a role, its rights and its start kinds, as one unit.

        Args:
            role: The role.
            now: Its creation time (epoch seconds).

        Raises:
            sqlite3.IntegrityError: On a taken key, a second admin role or a start kind already held.
        """
        with atomic(self._conn, _SAVEPOINT):
            self._conn.execute(
                "INSERT INTO role (id, name, kind, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (role.id, role.name, role.kind.value, now, now),
            )
            self._conn.executemany(
                "INSERT INTO role_right (role_id, right_name) VALUES (?, ?)",
                [(role.id, right.value) for right in sorted(role.rights)],
            )
            self._conn.executemany(
                "INSERT INTO role_start (start, role_id) VALUES (?, ?)",
                [(start, role.id) for start in sorted(role.default_for)],
            )

    @serialised
    def update_role(self, role_id: RoleId, *, name: str | None, rights: frozenset[Right] | None, now: float) -> None:
        """Rename a role and/or replace its rights; ``None`` leaves a field as it was.

        Args:
            role_id: Its key.
            name: The new name, stored as given.
            rights: The new rights, replacing the old list whole.
            now: The change time (epoch seconds).
        """
        with atomic(self._conn, _SAVEPOINT):
            if name is not None:
                self._conn.execute("UPDATE role SET name = ? WHERE id = ?", (name, role_id))
            if rights is not None:
                self._conn.execute("DELETE FROM role_right WHERE role_id = ?", (role_id,))
                self._conn.executemany(
                    "INSERT INTO role_right (role_id, right_name) VALUES (?, ?)",
                    [(role_id, right.value) for right in sorted(rights)],
                )
            self._conn.execute("UPDATE role SET updated_at = ? WHERE id = ?", (now, role_id))

    @serialised
    def delete_role(self, role_id: RoleId) -> None:
        """Delete a role; its rights go with it (``ON DELETE CASCADE``).

        Args:
            role_id: Its key.

        Raises:
            sqlite3.IntegrityError: When an account holds it or a start kind names it.
        """
        self._conn.execute("DELETE FROM role WHERE id = ?", (role_id,))

    @serialised
    def role_for_start(self, start: StartKind) -> Role | None:
        """The role a new account of one start kind begins on.

        Args:
            start: The start kind.

        Returns:
            The role, or ``None`` when no role is named for it.
        """
        row = self._conn.execute("SELECT role_id FROM role_start WHERE start = ?", (start,)).fetchone()
        return self.role(row[0]) if row else None

    @serialised
    def set_role_start(self, start: StartKind, role_id: RoleId) -> None:
        """Name the role a start kind begins on, replacing the previous one.

        Args:
            start: The start kind.
            role_id: The role.

        Raises:
            sqlite3.IntegrityError: On an unknown role.
        """
        self._conn.execute(
            "INSERT INTO role_start (start, role_id) VALUES (?, ?)"
            " ON CONFLICT (start) DO UPDATE SET role_id = excluded.role_id",
            (start, role_id),
        )
