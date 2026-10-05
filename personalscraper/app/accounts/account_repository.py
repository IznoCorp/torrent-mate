"""The accounts' rows in ``app.db`` — an account, its Plex link and its kept token.

Rows ↔ dataclasses, and nothing more: no rule lives here (when an account is demoted, whose
access may be cut — those are the services'). The base keeps its own constraints (an e-mail
unique whatever its case, one account per plex id) and this module lets them surface as
``sqlite3.IntegrityError``.

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, and a service that needs several calls to be one act wraps them in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field, replace
from typing import Literal

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.core.sqlite import serialised
from personalscraper.i18n import Language, configured_language


@dataclass(frozen=True)
class AccountRow:
    """One account.

    Attributes:
        id: Its key, ``account-<uuid4 hex>``.
        name: Its display name.
        email: Its e-mail, as given; unique whatever its case.
        avatar: A stored picture address, ``""`` when none; never read — the picture is
            resolved from the Plex link and the e-mail (``accounts.avatar``).
        role_id: The role it holds.
        password_hash: ``scrypt$N$r$p$salt$hash``; ``None`` when it holds no password.
        created_at: Creation (epoch seconds).
        updated_at: Last change (epoch seconds).
        sign_in_allowed: Whether it may sign in; ``True`` until an Admin cuts it.
        demoted_from: The role it held before its Plex link dropped it to its Plex kind's
            starting role; ``None`` when not demoted, or once an Admin gave it a role.
        language: The language it is spoken to in; a new row starts in the project's
            configured language (the operator, 2026-10-05) until the account chooses.
    """

    id: str
    name: str
    email: str
    avatar: str
    role_id: str
    password_hash: str | None = field(repr=False)
    created_at: float
    updated_at: float
    sign_in_allowed: bool = True
    demoted_from: str | None = None
    language: Language = field(default_factory=configured_language)


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
    token_ciphertext: bytes | None = field(repr=False)
    token_stored_at: float | None
    linked_at: float
    last_sign_in_at: float | None


_ACCOUNT_COLUMNS = (
    "id, name, email, avatar, role_id, password_hash, created_at, updated_at, sign_in_allowed, demoted_from, language"
)
_LINK_COLUMNS = (
    "account_id, plex_id, plex_uuid, plex_username, server_access,"
    " token_ciphertext, token_stored_at, linked_at, last_sign_in_at"
)


def _account(row: tuple[object, ...]) -> AccountRow:
    """Build an :class:`AccountRow` from a row in ``_ACCOUNT_COLUMNS`` order.

    SQLite stores ``sign_in_allowed`` as an integer and ``language`` as text: they are read
    back as a bool and a :class:`Language`.

    Args:
        row: The row.

    Returns:
        The dataclass.
    """
    account = AccountRow(*row)  # type: ignore[arg-type]
    return replace(account, sign_in_allowed=bool(account.sign_in_allowed), language=Language(account.language))


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

    def __init__(self, conn: sqlite3.Connection, *, lock: threading.RLock | None = None) -> None:
        """Wrap an open, migrated ``app.db`` connection.

        Args:
            conn: The connection, in autocommit mode.
            lock: The lock every user of ``conn`` holds around it (the store's); a lock of
                its own when ``conn`` is this repository's alone.
        """
        self._conn = conn
        self._lock = lock if lock is not None else threading.RLock()

    @serialised
    def accounts(self) -> list[AccountRow]:
        """Every account, in creation order.

        Returns:
            The accounts.
        """
        rows = self._conn.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM account ORDER BY created_at, rowid")  # noqa: S608
        return [_account(row) for row in rows]

    @serialised
    def account(self, account_id: str) -> AccountRow | None:
        """One account by key.

        Args:
            account_id: Its key.

        Returns:
            The account, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM account WHERE id = ?", (account_id,)).fetchone()  # noqa: S608
        return _account(row) if row else None

    @serialised
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
        return _account(row) if row else None

    @serialised
    def insert_account(self, account: AccountRow) -> None:
        """Insert an account.

        Args:
            account: The account.

        Raises:
            sqlite3.IntegrityError: On a taken key, a taken e-mail (any case) or an unknown role.
        """
        self._conn.execute(
            f"INSERT INTO account ({_ACCOUNT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",  # noqa: S608
            (
                account.id,
                account.name,
                account.email,
                account.avatar,
                account.role_id,
                account.password_hash,
                account.created_at,
                account.updated_at,
                account.sign_in_allowed,
                account.demoted_from,
                account.language.value,
            ),
        )

    @serialised
    def set_role(self, account_id: str, role_id: str, *, now: float, demoted_from: str | None = None) -> None:
        """Put an account on a role, recording or clearing the role a Plex link demoted it from.

        Args:
            account_id: The account.
            role_id: The role.
            now: The change time (epoch seconds).
            demoted_from: The role a Plex link drops it from; ``None`` — every other
                change — clears any demotion recorded.

        Raises:
            sqlite3.IntegrityError: On an unknown role.
        """
        self._conn.execute(
            "UPDATE account SET role_id = ?, demoted_from = ?, updated_at = ? WHERE id = ?",
            (role_id, demoted_from, now, account_id),
        )

    @serialised
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

    @serialised
    def set_sign_in_allowed(self, account_id: str, *, allowed: bool, now: float) -> None:
        """Allow or cut an account's sign-in.

        Args:
            account_id: The account.
            allowed: True to allow it, False to cut it.
            now: The change time (epoch seconds).
        """
        self._conn.execute(
            "UPDATE account SET sign_in_allowed = ?, updated_at = ? WHERE id = ?", (int(allowed), now, account_id)
        )

    @serialised
    def set_language(self, account_id: str, language: Language, *, now: float) -> None:
        """Set the language an account is spoken to in.

        Args:
            account_id: The account.
            language: The language.
            now: The change time (epoch seconds).
        """
        self._conn.execute(
            "UPDATE account SET language = ?, updated_at = ? WHERE id = ?", (language.value, now, account_id)
        )

    @serialised
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

    @serialised
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

    @serialised
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

    @serialised
    def plex_link_by_plex_id(self, plex_id: int) -> PlexLinkRow | None:
        """The link of one plex.tv identity.

        Args:
            plex_id: plex.tv's id.

        Returns:
            The link, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE plex_id = ?", (plex_id,)).fetchone()  # noqa: S608
        return _link(row) if row else None

    @serialised
    def owner_link(self) -> PlexLinkRow | None:
        """The link of the managed server's owner, whichever account holds it.

        Returns:
            The first link whose ``server_access`` is ``owner``, or ``None``.
        """
        row = self._conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE server_access = 'owner' ORDER BY linked_at, rowid LIMIT 1"  # noqa: S608
        ).fetchone()
        return _link(row) if row else None

    @serialised
    def owner_links(self) -> list[PlexLinkRow]:
        """Every link whose ``server_access`` is ``owner``, oldest first.

        The schema holds no unique index on it, so a stale former owner can sit beside the
        current one: a caller that needs the one owner must refuse more than one.

        Returns:
            The owner links; empty when no account holds one.
        """
        rows = self._conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE server_access = 'owner' ORDER BY linked_at, rowid"  # noqa: S608
        ).fetchall()
        return [_link(row) for row in rows]

    @serialised
    def upsert_plex_link(self, link: PlexLinkRow) -> None:
        """Insert an account's Plex link, or replace the fields of the existing one.

        A link written with no ciphertext keeps the token sealed before, and its date: a
        sign-in with no vault never erases a token kept by one. ``set_token_ciphertext``
        clears it.

        Args:
            link: The link.

        Raises:
            sqlite3.IntegrityError: On a plex id linked to another account, or an unknown account.
        """
        self._conn.execute(
            f"INSERT INTO plex_link ({_LINK_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"  # noqa: S608
            " ON CONFLICT (account_id) DO UPDATE SET plex_id = excluded.plex_id, plex_uuid = excluded.plex_uuid,"
            " plex_username = excluded.plex_username, server_access = excluded.server_access,"
            " token_ciphertext = COALESCE(excluded.token_ciphertext, plex_link.token_ciphertext),"
            " token_stored_at = COALESCE(excluded.token_stored_at, plex_link.token_stored_at),"
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

    @serialised
    def plex_links_with_token(self) -> list[PlexLinkRow]:
        """Every link keeping a token.

        Returns:
            The links, by account key.
        """
        rows = self._conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE token_ciphertext IS NOT NULL ORDER BY account_id"  # noqa: S608
        )
        return [_link(row) for row in rows]

    @serialised
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
