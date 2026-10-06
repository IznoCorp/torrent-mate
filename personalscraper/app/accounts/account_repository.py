"""The accounts' rows in ``app.db`` — an account, its Plex link and its kept token.

Rows ↔ :class:`~personalscraper.app.accounts.model.Account` (its Plex link read with it) and
:class:`~personalscraper.app.accounts.model.PlexLink`, and nothing more: no rule lives here (when
an account is demoted, whose access may be cut — those are the model's and the services'). The
base keeps its own constraints (an e-mail unique whatever its case, one account per plex id) and
this module lets them surface as ``sqlite3.IntegrityError``.

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, and a service that needs several calls to be one act wraps them in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import replace

from personalscraper.app.accounts.actor import RoleKind
from personalscraper.app.accounts.model import Account, AccountId, PlexLink, RoleId
from personalscraper.core.sqlite import serialised
from personalscraper.i18n import Language

_ACCOUNT_COLUMNS = (
    "id, name, email, avatar, role_id, password_hash, created_at, updated_at, sign_in_allowed, demoted_from, language"
)
_LINK_COLUMNS = (
    "account_id, plex_id, plex_uuid, plex_username, server_access,"
    " token_ciphertext, token_stored_at, linked_at, last_sign_in_at"
)


def _account(row: tuple[object, ...], link: PlexLink | None) -> Account:
    """Build an :class:`Account` from a row in ``_ACCOUNT_COLUMNS`` order and its Plex link.

    SQLite stores ``sign_in_allowed`` as an integer and ``language`` as text: they are read
    back as a bool and a :class:`Language`.

    Args:
        row: The row.
        link: The account's Plex link, or ``None``.

    Returns:
        The dataclass.
    """
    account = Account(*row)  # type: ignore[arg-type]
    return replace(
        account, sign_in_allowed=bool(account.sign_in_allowed), language=Language(account.language), plex_link=link
    )


def _link(row: tuple[object, ...]) -> PlexLink:
    """Build a :class:`PlexLink` from a row in ``_LINK_COLUMNS`` order.

    Args:
        row: The row.

    Returns:
        The dataclass.
    """
    return PlexLink(*row)  # type: ignore[arg-type]


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
    def accounts(self) -> list[Account]:
        """Every account, in creation order.

        Returns:
            The accounts.
        """
        rows = self._conn.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM account ORDER BY created_at, rowid")  # noqa: S608
        return [self._with_link(row) for row in rows.fetchall()]

    def _with_link(self, row: tuple[object, ...]) -> Account:
        """Build an account from its row, its Plex link read with it.

        Args:
            row: The row, in ``_ACCOUNT_COLUMNS`` order.

        Returns:
            The account.
        """
        return _account(row, self.plex_link(row[0]))  # type: ignore[arg-type]

    @serialised
    def account(self, account_id: AccountId) -> Account | None:
        """One account by key.

        Args:
            account_id: Its key.

        Returns:
            The account, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM account WHERE id = ?", (account_id,)).fetchone()  # noqa: S608
        return self._with_link(row) if row else None

    @serialised
    def account_by_email(self, email: str) -> Account | None:
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
        return self._with_link(row) if row else None

    @serialised
    def insert_account(self, account: Account) -> None:
        """Insert an account; its Plex link is written by :meth:`upsert_plex_link`.

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
    def set_role(
        self, account_id: AccountId, role_id: RoleId, *, now: float, demoted_from: RoleId | None = None
    ) -> None:
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
    def set_password_hash(self, account_id: AccountId, password_hash: str | None, *, now: float) -> None:
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
    def set_sign_in_allowed(self, account_id: AccountId, *, allowed: bool, now: float) -> None:
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
    def set_language(self, account_id: AccountId, language: Language, *, now: float) -> None:
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
    def accounts_on_role(self, role_id: RoleId) -> list[AccountId]:
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
    def plex_link(self, account_id: AccountId) -> PlexLink | None:
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
    def plex_link_by_plex_id(self, plex_id: int) -> PlexLink | None:
        """The link of one plex.tv identity.

        Args:
            plex_id: plex.tv's id.

        Returns:
            The link, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE plex_id = ?", (plex_id,)).fetchone()  # noqa: S608
        return _link(row) if row else None

    @serialised
    def owner_link(self) -> PlexLink | None:
        """The link of the managed server's owner, whichever account holds it.

        Returns:
            The first link whose ``server_access`` is ``owner``, or ``None``.
        """
        row = self._conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE server_access = 'owner' ORDER BY linked_at, rowid LIMIT 1"  # noqa: S608
        ).fetchone()
        return _link(row) if row else None

    @serialised
    def owner_links(self) -> list[PlexLink]:
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
    def upsert_plex_link(self, link: PlexLink) -> None:
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
    def plex_links_with_token(self) -> list[PlexLink]:
        """Every link keeping a token.

        Returns:
            The links, by account key.
        """
        rows = self._conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM plex_link WHERE token_ciphertext IS NOT NULL ORDER BY account_id"  # noqa: S608
        )
        return [_link(row) for row in rows]

    @serialised
    def set_token_ciphertext(self, account_id: AccountId, blob: bytes | None, *, now: float | None) -> None:
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
