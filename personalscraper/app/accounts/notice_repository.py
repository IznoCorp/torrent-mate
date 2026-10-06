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
from typing import Final

from personalscraper.core.sqlite import serialised

#: How long a notice is kept, in seconds (90 days): an older one is purged when its account is next
#: told something. A notice is a courtesy, not a record — the sessions list is the lasting truth.
NOTICE_RETENTION_S: Final = 90 * 24 * 3600.0

#: The most notices the table keeps for one account, the newest: the interface reads fifty, so
#: this leaves a margin without letting a busy account grow the table without bound.
NOTICE_CAP_PER_ACCOUNT: Final = 100

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
        read_at: When the account marked it read (epoch seconds); ``None`` while unread.
    """

    id: int
    account_id: str
    code: str
    params: Mapping[str, NoticeParam] = field(hash=False)
    created_at: float
    read_at: float | None = None


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
        """Write a notice for an account, and bound that account's notices.

        Housekeeping happens here, on write: there is no periodic job on ``app.db``. In the same
        call the account's notices older than :data:`NOTICE_RETENTION_S` are deleted, then all but
        its newest :data:`NOTICE_CAP_PER_ACCOUNT`. Only this account's rows are touched.

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
        self._conn.execute(
            "DELETE FROM account_notice WHERE account_id = ? AND created_at < ?",
            (account_id, now - NOTICE_RETENTION_S),
        )
        self._conn.execute(
            "DELETE FROM account_notice WHERE account_id = ? AND id NOT IN"
            " (SELECT id FROM account_notice WHERE account_id = ? ORDER BY created_at DESC, id DESC LIMIT ?)",
            (account_id, account_id, NOTICE_CAP_PER_ACCOUNT),
        )
        return cursor.lastrowid

    @serialised
    def mark_read_up_to(self, account_id: str, up_to: int, *, now: float) -> int:
        """Mark an account's unread notices read, those numbered ``up_to`` or lower.

        A notice raised after the one the account saw has a higher id and stays unread; a notice
        already read keeps its first read time.

        Args:
            account_id: The account; another account's notices are never touched.
            up_to: The highest notice id marked.
            now: The read time (epoch seconds).

        Returns:
            The number of notices newly marked.
        """
        cursor = self._conn.execute(
            "UPDATE account_notice SET read_at = ? WHERE account_id = ? AND id <= ? AND read_at IS NULL",
            (now, account_id, up_to),
        )
        return cursor.rowcount

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
            "SELECT id, account_id, code, params_json, created_at, read_at FROM account_notice"
            " WHERE account_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
        return [
            NoticeRow(
                id=row[0], account_id=row[1], code=row[2], params=json.loads(row[3]), created_at=row[4], read_at=row[5]
            )
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
