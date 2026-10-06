"""The sessions' rows in ``app.db``.

Rows ↔ dataclasses, and nothing more: no rule lives here (how long a session lasts, when it is
renewed — those are the services').

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, and a service that needs several calls to be one act wraps them in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field

from personalscraper.app.accounts.ids import AccountId
from personalscraper.core.sqlite import serialised


@dataclass(frozen=True)
class SessionRow:
    """One session.

    Attributes:
        id: Its key, assigned by the base on insert.
        account_id: The account it signs in.
        token_hash: The sha256 hex of the cookie value; the value is never stored.
        created_at: Creation (epoch seconds).
        expires_at: Its expiry, moved forward at each renewal.
        last_seen_at: Its last renewal (a use is written at most once per renewal interval).
        revoked_at: When it was signed out; ``None`` while live.
        user_agent: The browser's user agent.
    """

    id: int
    account_id: AccountId
    token_hash: str = field(repr=False)
    created_at: float
    expires_at: float
    last_seen_at: float
    revoked_at: float | None
    user_agent: str | None


_SESSION_COLUMNS = "id, account_id, token_hash, created_at, expires_at, last_seen_at, revoked_at, user_agent"


class SessionRepository:
    """The sessions' rows over one ``app.db`` connection it is GIVEN; it opens nothing."""

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

    @serialised
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

    @serialised
    def session(self, session_id: int) -> SessionRow | None:
        """A session by its key, revoked or not.

        Args:
            session_id: The session.

        Returns:
            The session, or ``None``.
        """
        row = self._conn.execute(
            f"SELECT {_SESSION_COLUMNS} FROM session WHERE id = ?",  # noqa: S608
            (session_id,),
        ).fetchone()
        return SessionRow(*row) if row else None

    @serialised
    def live_sessions_of(self, account_id: AccountId, *, now: float) -> list[SessionRow]:
        """An account's live sessions — neither revoked nor expired — the newest first.

        Args:
            account_id: The account.
            now: The current time (epoch seconds); a session expiring at or before it is not live.

        Returns:
            Its live sessions.
        """
        rows = self._conn.execute(
            f"SELECT {_SESSION_COLUMNS} FROM session"  # noqa: S608
            " WHERE account_id = ? AND revoked_at IS NULL AND expires_at > ? ORDER BY created_at DESC, id DESC",
            (account_id, now),
        ).fetchall()
        return [SessionRow(*row) for row in rows]

    @serialised
    def renew_session(self, session_id: int, *, seen_at: float, token_hash: str, expires_at: float, now: float) -> bool:
        """Renew a live session under a new value, if no other renewal came first.

        The write is conditional on ``last_seen_at`` still being the one read: of two
        requests renewing the same session at once, one writes and the other learns it lost.

        Args:
            session_id: The session.
            seen_at: The ``last_seen_at`` the caller read.
            token_hash: The new value's hash.
            expires_at: The new expiry.
            now: The renewal time (epoch seconds), the new ``last_seen_at``.

        Returns:
            Whether the session was renewed; ``False`` when it is revoked or was renewed meanwhile.
        """
        cursor = self._conn.execute(
            "UPDATE session SET token_hash = ?, expires_at = ?, last_seen_at = ?"
            " WHERE id = ? AND last_seen_at = ? AND revoked_at IS NULL",
            (token_hash, expires_at, now, session_id, seen_at),
        )
        return cursor.rowcount == 1

    @serialised
    def revoke_session(self, session_id: int, *, now: float) -> None:
        """Mark a session revoked.

        Args:
            session_id: The session.
            now: The revocation time (epoch seconds).
        """
        self._conn.execute("UPDATE session SET revoked_at = ? WHERE id = ?", (now, session_id))

    @serialised
    def revoke_sessions_of(self, account_id: AccountId, *, except_id: int | None, now: float) -> int:
        """Mark every live session of an account revoked, but one.

        Args:
            account_id: The account.
            except_id: The session kept live; ``None`` revokes them all.
            now: The revocation time (epoch seconds).

        Returns:
            How many sessions were revoked.
        """
        # ``id IS NOT NULL`` holds for every row, so ``except_id=None`` spares none.
        cursor = self._conn.execute(
            "UPDATE session SET revoked_at = ? WHERE account_id = ? AND revoked_at IS NULL AND id IS NOT ?",
            (now, account_id, except_id),
        )
        return cursor.rowcount
