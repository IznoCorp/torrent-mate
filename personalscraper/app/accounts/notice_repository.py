"""The accounts' in-app notices and push switches, as rows in ``app.db``.

Rows ↔ dataclasses, and nothing more: what raises a notice and who is pushed are the notifier's
rules. A notice holds a code and its parameters — never a sentence: the interface words it in the
account's language. A push type with no switch row is on: a row is written only when the account
turns a type off, or back on.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field

from personalscraper.core.sqlite import serialised

#: A notice parameter: a typed fact, never a word.
NoticeParam = str | int | float


@dataclass(frozen=True)
class NoticeRow:
    """One in-app notice.

    Attributes:
        id: Its key, assigned by the base on insert.
        account_id: The account it is for.
        code: What it tells, as a code the interface words (``account.sign_in.device``).
        params: The code's parameters.
        created_at: When it was raised (epoch seconds).
    """

    id: int
    account_id: str
    code: str
    params: Mapping[str, NoticeParam] = field(hash=False)
    created_at: float


class NoticeRepository:
    """The notices' rows over one ``app.db`` connection it is GIVEN; it opens nothing."""

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
    def insert_notice(self, account_id: str, code: str, params: Mapping[str, NoticeParam], *, now: float) -> int:
        """Write a notice for an account.

        Args:
            account_id: The account.
            code: The notice's code.
            params: Its parameters.
            now: When it is raised (epoch seconds).

        Returns:
            The assigned id.

        Raises:
            sqlite3.IntegrityError: The account does not exist.
        """
        cursor = self._conn.execute(
            "INSERT INTO account_notice (account_id, code, params_json, created_at) VALUES (?, ?, ?, ?)",
            (account_id, code, json.dumps(dict(params), sort_keys=True), now),
        )
        assert cursor.lastrowid is not None  # an INSERT into a rowid table always sets it
        return cursor.lastrowid

    @serialised
    def notices_of(self, account_id: str, *, limit: int) -> list[NoticeRow]:
        """An account's notices, the newest first.

        Args:
            account_id: The account.
            limit: The most returned.

        Returns:
            Its notices.
        """
        rows = self._conn.execute(
            "SELECT id, account_id, code, params_json, created_at FROM account_notice"
            " WHERE account_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
        return [
            NoticeRow(id=row[0], account_id=row[1], code=row[2], params=json.loads(row[3]), created_at=row[4])
            for row in rows
        ]


class PreferenceRepository:
    """The accounts' push switches over one ``app.db`` connection it is GIVEN; it opens nothing."""

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
    def enabled(self, account_id: str, notification_type: str) -> bool:
        """Whether a push type reaches an account's devices.

        Args:
            account_id: The account.
            notification_type: The type (the contract's ``NotificationType``).

        Returns:
            The account's choice; ``True`` when it never made one.
        """
        row = self._conn.execute(
            "SELECT enabled FROM notification_preference WHERE account_id = ? AND type = ?",
            (account_id, notification_type),
        ).fetchone()
        return row is None or bool(row[0])

    @serialised
    def set_enabled(self, account_id: str, notification_type: str, *, enabled: bool, now: float) -> None:
        """Turn a push type on or off for an account, on all its devices.

        Args:
            account_id: The account.
            notification_type: The type.
            enabled: Whether it reaches the account's devices.
            now: The change time (epoch seconds).

        Raises:
            sqlite3.IntegrityError: The account does not exist.
        """
        self._conn.execute(
            "INSERT INTO notification_preference (account_id, type, enabled, updated_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (account_id, type)"
            " DO UPDATE SET enabled = excluded.enabled, updated_at = excluded.updated_at",
            (account_id, notification_type, int(enabled), now),
        )
