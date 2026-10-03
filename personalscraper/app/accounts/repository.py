"""The accounts' rows in ``app.db`` — roles, accounts, Plex links, sessions, Plex PINs, settings.

Rows ↔ dataclasses, and nothing more: no rule lives here (who may rename a role, when an
account is demoted, how long a session lasts — those are the services'). The base keeps its
own constraints (one admin role, one role per start kind, an e-mail unique whatever its case,
one account per plex id) and this module lets them surface as ``sqlite3.IntegrityError``.

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, a method writing several statements runs them under a SAVEPOINT, and a service that
needs several calls to be one act wraps them in :meth:`AccountRepository.immediate`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.rights import Right

#: What a new account starts as: a Plex Home member, a Plex guest, a local account.
StartKind = Literal["plexHome", "plexGuest", "local"]


@dataclass(frozen=True)
class RoleRow:
    """One role.

    Attributes:
        id: Its key: a seed's id, or ``role-<uuid4 hex>``.
        name: The text an Admin gave it; ``None`` while a seeded role was never renamed
            (the interface then shows the translation of its id).
        kind: ``admin`` (the one Admin role) or ``ordinary``.
        rights: The rights it carries; empty for Admin, which bypasses the list.
        default_for: The start kinds whose new accounts begin on it.
    """

    id: str
    name: str | None
    kind: RoleKind
    rights: frozenset[Right]
    default_for: frozenset[StartKind] = frozenset()


@dataclass(frozen=True)
class AccountRow:
    """One account.

    Attributes:
        id: Its key, ``account-<uuid4 hex>``.
        name: Its display name.
        email: Its e-mail, as given; unique whatever its case.
        avatar: Its avatar, ``""`` when none.
        role_id: The role it holds.
        password_hash: ``scrypt$N$r$p$salt$hash``; ``None`` when it holds no password.
        created_at: Creation (epoch seconds).
        updated_at: Last change (epoch seconds).
    """

    id: str
    name: str
    email: str
    avatar: str
    role_id: str
    password_hash: str | None
    created_at: float
    updated_at: float


@dataclass(frozen=True)
class PlexLinkRow:
    """An account's link to its plex.tv identity.

    Attributes:
        account_id: The linked account.
        plex_id: plex.tv's stable id — the identity, never the e-mail.
        plex_uuid: plex.tv's uuid.
        plex_username: plex.tv's username.
        server_access: ``owner`` of the managed server, or ``shared`` with it.
        token_ciphertext: The kept Plex token, encrypted; ``None`` when not kept.
        token_stored_at: When it was stored; ``None`` when not kept.
        linked_at: When the link was made.
        last_sign_in_at: The last Plex sign-in; ``None`` before the first.
    """

    account_id: str
    plex_id: int
    plex_uuid: str
    plex_username: str
    server_access: Literal["owner", "shared"]
    token_ciphertext: bytes | None
    token_stored_at: float | None
    linked_at: float
    last_sign_in_at: float | None


@dataclass(frozen=True)
class SessionRow:
    """One session.

    Attributes:
        id: Its key, assigned by the base on insert.
        account_id: The account it signs in.
        token_hash: The sha256 hex of the cookie value; the value is never stored.
        created_at: Creation (epoch seconds).
        expires_at: Its hard expiry.
        last_seen_at: Its last use.
        revoked_at: When it was signed out; ``None`` while live.
        user_agent: The browser's user agent.
    """

    id: int
    account_id: str
    token_hash: str
    created_at: float
    expires_at: float
    last_seen_at: float
    revoked_at: float | None
    user_agent: str | None


@dataclass(frozen=True)
class PlexPinRow:
    """A Plex sign-in PIN in flight.

    Attributes:
        pin_id: plex.tv's PIN id.
        code: plex.tv's PIN code.
        nonce_hash: The hash of the nonce binding the PIN to the browser that started it.
        created_at: Creation (epoch seconds).
        expires_at: plex.tv's expiry, when known.
        last_checked_at: The last poll of plex.tv.
        consumed_at: When a sign-in used it.
    """

    pin_id: int
    code: str
    nonce_hash: str
    created_at: float
    expires_at: float | None
    last_checked_at: float | None
    consumed_at: float | None


_ACCOUNT_COLUMNS = "id, name, email, avatar, role_id, password_hash, created_at, updated_at"
_LINK_COLUMNS = (
    "account_id, plex_id, plex_uuid, plex_username, server_access,"
    " token_ciphertext, token_stored_at, linked_at, last_sign_in_at"
)
_SESSION_COLUMNS = "id, account_id, token_hash, created_at, expires_at, last_seen_at, revoked_at, user_agent"
_PIN_COLUMNS = "pin_id, code, nonce_hash, created_at, expires_at, last_checked_at, consumed_at"


def _link(row: tuple[object, ...]) -> PlexLinkRow:
    """Build a :class:`PlexLinkRow` from a row in ``_LINK_COLUMNS`` order.

    Args:
        row: The row.

    Returns:
        The dataclass.
    """
    return PlexLinkRow(*row)  # type: ignore[arg-type]


class AccountRepository:
    """The accounts' rows over one ``app.db`` connection it is GIVEN; it opens nothing."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Wrap an open, migrated ``app.db`` connection.

        Args:
            conn: The connection, in autocommit mode.
        """
        self._conn = conn

    @contextmanager
    def immediate(self) -> Iterator[None]:
        """Run the calls inside as one transaction holding the writer lock.

        Yields:
            Nothing; every write inside commits on exit, or none does.

        Raises:
            BaseException: Whatever the block raised, after the rollback.
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    @contextmanager
    def _atomic(self) -> Iterator[None]:
        """Run one method's several statements as a unit; nests inside :meth:`immediate`.

        Yields:
            Nothing.

        Raises:
            BaseException: Whatever the block raised, after rolling back to the savepoint.
        """
        self._conn.execute("SAVEPOINT account_repository")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK TO account_repository")
            self._conn.execute("RELEASE account_repository")
            raise
        self._conn.execute("RELEASE account_repository")

    # ── roles ────────────────────────────────────────────────────────────────

    def _role_rows(self, where: str = "", params: tuple[object, ...] = ()) -> list[RoleRow]:
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
        rights: dict[str, set[Right]] = {}
        for role_id, right_name in self._conn.execute("SELECT role_id, right_name FROM role_right"):
            rights.setdefault(role_id, set()).add(Right(right_name))
        starts: dict[str, set[StartKind]] = {}
        for start, role_id in self._conn.execute("SELECT start, role_id FROM role_start"):
            starts.setdefault(role_id, set()).add(start)
        return [
            RoleRow(
                id=role_id,
                name=name,
                kind=RoleKind(kind),
                rights=frozenset(rights.get(role_id, ())),
                default_for=frozenset(starts.get(role_id, ())),
            )
            for role_id, name, kind in roles
        ]

    def roles(self) -> list[RoleRow]:
        """Every role, in creation order (the seeds first, in seed order).

        Returns:
            The roles.
        """
        return self._role_rows()

    def role(self, role_id: str) -> RoleRow | None:
        """One role by key.

        Args:
            role_id: Its key.

        Returns:
            The role, or ``None``.
        """
        rows = self._role_rows("WHERE id = ?", (role_id,))
        return rows[0] if rows else None

    def insert_role(self, role: RoleRow, *, now: float) -> None:
        """Insert a role, its rights and its start kinds, as one unit.

        Args:
            role: The role.
            now: Its creation time (epoch seconds).

        Raises:
            sqlite3.IntegrityError: On a taken key, a second admin role or a start kind already held.
        """
        with self._atomic():
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

    def update_role(self, role_id: str, *, name: str | None, rights: frozenset[Right] | None, now: float) -> None:
        """Rename a role and/or replace its rights; ``None`` leaves a field as it was.

        Args:
            role_id: Its key.
            name: The new name, stored as given.
            rights: The new rights, replacing the old list whole.
            now: The change time (epoch seconds).
        """
        with self._atomic():
            if name is not None:
                self._conn.execute("UPDATE role SET name = ? WHERE id = ?", (name, role_id))
            if rights is not None:
                self._conn.execute("DELETE FROM role_right WHERE role_id = ?", (role_id,))
                self._conn.executemany(
                    "INSERT INTO role_right (role_id, right_name) VALUES (?, ?)",
                    [(role_id, right.value) for right in sorted(rights)],
                )
            self._conn.execute("UPDATE role SET updated_at = ? WHERE id = ?", (now, role_id))

    def role_for_start(self, start: StartKind) -> RoleRow | None:
        """The role a new account of one start kind begins on.

        Args:
            start: The start kind.

        Returns:
            The role, or ``None`` when no role is named for it.
        """
        row = self._conn.execute("SELECT role_id FROM role_start WHERE start = ?", (start,)).fetchone()
        return self.role(row[0]) if row else None

    def set_role_start(self, start: StartKind, role_id: str) -> None:
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

    # ── accounts ─────────────────────────────────────────────────────────────

    def accounts(self) -> list[AccountRow]:
        """Every account, in creation order.

        Returns:
            The accounts.
        """
        rows = self._conn.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM account ORDER BY created_at, rowid")  # noqa: S608
        return [AccountRow(*row) for row in rows]

    def account(self, account_id: str) -> AccountRow | None:
        """One account by key.

        Args:
            account_id: Its key.

        Returns:
            The account, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM account WHERE id = ?", (account_id,)).fetchone()  # noqa: S608
        return AccountRow(*row) if row else None

    def account_by_email(self, email: str) -> AccountRow | None:
        """One account by e-mail, whatever its case.

        Args:
            email: The e-mail.

        Returns:
            The account, or ``None``.
        """
        row = self._conn.execute(
            f"SELECT {_ACCOUNT_COLUMNS} FROM account WHERE lower(email) = lower(?)",  # noqa: S608
            (email,),
        ).fetchone()
        return AccountRow(*row) if row else None

    def insert_account(self, account: AccountRow) -> None:
        """Insert an account.

        Args:
            account: The account.

        Raises:
            sqlite3.IntegrityError: On a taken key, a taken e-mail (any case) or an unknown role.
        """
        self._conn.execute(
            f"INSERT INTO account ({_ACCOUNT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",  # noqa: S608
            (
                account.id,
                account.name,
                account.email,
                account.avatar,
                account.role_id,
                account.password_hash,
                account.created_at,
                account.updated_at,
            ),
        )

    def set_role(self, account_id: str, role_id: str, *, now: float) -> None:
        """Put an account on a role.

        Args:
            account_id: The account.
            role_id: The role.
            now: The change time (epoch seconds).

        Raises:
            sqlite3.IntegrityError: On an unknown role.
        """
        self._conn.execute("UPDATE account SET role_id = ?, updated_at = ? WHERE id = ?", (role_id, now, account_id))

    def set_password_hash(self, account_id: str, password_hash: str | None, *, now: float) -> None:
        """Store or clear an account's password hash.

        Args:
            account_id: The account.
            password_hash: The hash, or ``None`` to clear it.
            now: The change time (epoch seconds).
        """
        self._conn.execute(
            "UPDATE account SET password_hash = ?, updated_at = ? WHERE id = ?", (password_hash, now, account_id)
        )

    def count_on_role_kind(self, kind: RoleKind) -> int:
        """How many accounts hold a role of one kind.

        Args:
            kind: The role kind.

        Returns:
            The count.
        """
        row = self._conn.execute(
            "SELECT count(*) FROM account JOIN role ON role.id = account.role_id WHERE role.kind = ?", (kind.value,)
        ).fetchone()
        return int(row[0])

    def accounts_on_role(self, role_id: str) -> list[str]:
        """The keys of the accounts holding one role, in creation order.

        Args:
            role_id: The role.

        Returns:
            The account keys.
        """
        rows = self._conn.execute(
            "SELECT id FROM account WHERE role_id = ? ORDER BY created_at, rowid", (role_id,)
        ).fetchall()
        return [row[0] for row in rows]

    # ── plex links ───────────────────────────────────────────────────────────

    def plex_link(self, account_id: str) -> PlexLinkRow | None:
        """An account's Plex link.

        Args:
            account_id: The account.

        Returns:
            The link, or ``None``.
        """
        row = self._conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE account_id = ?",  # noqa: S608
            (account_id,),
        ).fetchone()
        return _link(row) if row else None

    def plex_link_by_plex_id(self, plex_id: int) -> PlexLinkRow | None:
        """The link of one plex.tv identity.

        Args:
            plex_id: plex.tv's id.

        Returns:
            The link, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE plex_id = ?", (plex_id,)).fetchone()  # noqa: S608
        return _link(row) if row else None

    def upsert_plex_link(self, link: PlexLinkRow) -> None:
        """Insert an account's Plex link, or replace every field of the existing one.

        Args:
            link: The link.

        Raises:
            sqlite3.IntegrityError: On a plex id linked to another account, or an unknown account.
        """
        self._conn.execute(
            f"INSERT INTO plex_link ({_LINK_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"  # noqa: S608
            " ON CONFLICT (account_id) DO UPDATE SET plex_id = excluded.plex_id, plex_uuid = excluded.plex_uuid,"
            " plex_username = excluded.plex_username, server_access = excluded.server_access,"
            " token_ciphertext = excluded.token_ciphertext, token_stored_at = excluded.token_stored_at,"
            " linked_at = excluded.linked_at, last_sign_in_at = excluded.last_sign_in_at",
            (
                link.account_id,
                link.plex_id,
                link.plex_uuid,
                link.plex_username,
                link.server_access,
                link.token_ciphertext,
                link.token_stored_at,
                link.linked_at,
                link.last_sign_in_at,
            ),
        )

    def plex_links_with_token(self) -> list[PlexLinkRow]:
        """Every link keeping a token.

        Returns:
            The links, by account key.
        """
        rows = self._conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE token_ciphertext IS NOT NULL ORDER BY account_id"  # noqa: S608
        )
        return [_link(row) for row in rows]

    def set_token_ciphertext(self, account_id: str, blob: bytes | None, *, now: float | None) -> None:
        """Store, replace or clear an account's kept token.

        Args:
            account_id: The account.
            blob: The ciphertext, or ``None`` to forget it.
            now: The storage time, or ``None`` when forgetting.
        """
        self._conn.execute(
            "UPDATE plex_link SET token_ciphertext = ?, token_stored_at = ? WHERE account_id = ?",
            (blob, now, account_id),
        )

    # ── sessions ─────────────────────────────────────────────────────────────

    def insert_session(self, row: SessionRow) -> int:
        """Insert a session; its ``id`` is ignored and assigned by the base.

        Args:
            row: The session.

        Returns:
            The assigned id.

        Raises:
            sqlite3.IntegrityError: On a taken hash or an unknown account.
        """
        cursor = self._conn.execute(
            "INSERT INTO session (account_id, token_hash, created_at, expires_at, last_seen_at, revoked_at, user_agent)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                row.account_id,
                row.token_hash,
                row.created_at,
                row.expires_at,
                row.last_seen_at,
                row.revoked_at,
                row.user_agent,
            ),
        )
        assert cursor.lastrowid is not None  # an INSERT into a rowid table always sets it
        return cursor.lastrowid

    def session_by_hash(self, token_hash: str) -> SessionRow | None:
        """A session by its cookie value's hash, revoked or not.

        Args:
            token_hash: The hash.

        Returns:
            The session, or ``None``.
        """
        row = self._conn.execute(
            f"SELECT {_SESSION_COLUMNS} FROM session WHERE token_hash = ?",  # noqa: S608
            (token_hash,),
        ).fetchone()
        return SessionRow(*row) if row else None

    def touch_session(self, session_id: int, *, now: float) -> None:
        """Record a session's use.

        Args:
            session_id: The session.
            now: The use time (epoch seconds).
        """
        self._conn.execute("UPDATE session SET last_seen_at = ? WHERE id = ?", (now, session_id))

    def revoke_session(self, session_id: int, *, now: float) -> None:
        """Mark a session revoked.

        Args:
            session_id: The session.
            now: The revocation time (epoch seconds).
        """
        self._conn.execute("UPDATE session SET revoked_at = ? WHERE id = ?", (now, session_id))

    # ── pins, settings ───────────────────────────────────────────────────────

    def insert_pin(self, row: PlexPinRow) -> None:
        """Insert a Plex PIN.

        Args:
            row: The PIN.

        Raises:
            sqlite3.IntegrityError: On a taken PIN id.
        """
        self._conn.execute(
            f"INSERT INTO plex_pin ({_PIN_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",  # noqa: S608
            (
                row.pin_id,
                row.code,
                row.nonce_hash,
                row.created_at,
                row.expires_at,
                row.last_checked_at,
                row.consumed_at,
            ),
        )

    def pin(self, pin_id: int) -> PlexPinRow | None:
        """One Plex PIN.

        Args:
            pin_id: plex.tv's PIN id.

        Returns:
            The PIN, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_PIN_COLUMNS} FROM plex_pin WHERE pin_id = ?", (pin_id,)).fetchone()  # noqa: S608
        return PlexPinRow(*row) if row else None

    def mark_pin_checked(self, pin_id: int, *, now: float) -> None:
        """Record a poll of plex.tv for a PIN.

        Args:
            pin_id: The PIN.
            now: The poll time (epoch seconds).
        """
        self._conn.execute("UPDATE plex_pin SET last_checked_at = ? WHERE pin_id = ?", (now, pin_id))

    def consume_pin(self, pin_id: int, *, now: float) -> None:
        """Mark a PIN used by a sign-in.

        Args:
            pin_id: The PIN.
            now: The use time (epoch seconds).
        """
        self._conn.execute("UPDATE plex_pin SET consumed_at = ? WHERE pin_id = ?", (now, pin_id))

    def setting(self, key: str) -> str | None:
        """One application setting.

        Args:
            key: Its key.

        Returns:
            Its value, or ``None``.
        """
        row = self._conn.execute("SELECT value FROM app_setting WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Store an application setting, replacing its value.

        Args:
            key: Its key.
            value: Its value.
        """
        self._conn.execute(
            "INSERT INTO app_setting (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
