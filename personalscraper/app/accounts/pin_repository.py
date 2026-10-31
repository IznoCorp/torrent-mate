"""The Plex sign-in PINs' rows in ``app.db``.

Rows ↔ dataclasses, and nothing more: no rule lives here (how often plex.tv is polled, how long
a PIN lives — those are the services').

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on
its own, and a service that needs several calls to be one act wraps them in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field

from personalscraper.core.sqlite import serialised


@dataclass(frozen=True)
class PlexPinRow:
    """A Plex sign-in PIN in flight.

    Attributes:
        pin_id: plex.tv's PIN id.
        code: plex.tv's PIN code — what the sign-in page carries; kept out of the ``repr``.
        nonce_hash: The hash of the nonce binding the PIN to the browser that started it.
        created_at: Creation (epoch seconds).
        expires_at: plex.tv's expiry, when known.
        last_checked_at: The last poll of plex.tv.
        consumed_at: When a sign-in used it.
    """

    pin_id: int
    code: str = field(repr=False)
    nonce_hash: str = field(repr=False)
    created_at: float
    expires_at: float | None
    last_checked_at: float | None
    consumed_at: float | None


_PIN_COLUMNS = "pin_id, code, nonce_hash, created_at, expires_at, last_checked_at, consumed_at"


class PlexPinRepository:
    """The Plex PINs' rows over one ``app.db`` connection it is GIVEN; it opens nothing."""

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
    def insert_pin(self, row: PlexPinRow) -> None:
        """Insert a Plex PIN.

        Args:
            row: The PIN.

        Raises:
            sqlite3.IntegrityError: On a taken PIN id.
        """
        self._conn.execute(
            f"INSERT INTO plex_pin ({_PIN_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",  # noqa: S608 — interpolates the module's fixed column constant only
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

    @serialised
    def pin(self, pin_id: int) -> PlexPinRow | None:
        """One Plex PIN.

        Args:
            pin_id: plex.tv's PIN id.

        Returns:
            The PIN, or ``None``.
        """
        row = self._conn.execute(f"SELECT {_PIN_COLUMNS} FROM plex_pin WHERE pin_id = ?", (pin_id,)).fetchone()  # noqa: S608 — interpolates the module's fixed column constant only
        return PlexPinRow(*row) if row else None

    @serialised
    def mark_pin_checked(self, pin_id: int, *, now: float) -> None:
        """Record a poll of plex.tv for a PIN.

        Args:
            pin_id: The PIN.
            now: The poll time (epoch seconds).
        """
        self._conn.execute("UPDATE plex_pin SET last_checked_at = ? WHERE pin_id = ?", (now, pin_id))

    @serialised
    def claim_pin_check(self, pin_id: int, *, now: float, min_interval: float) -> bool:
        """Claim the right to ask plex.tv about a PIN now, if no check was claimed within the interval.

        One conditional write: of two calls inside the interval, one claims and the other
        learns it lost, so plex.tv is asked at most once per interval whatever the callers.
        A consumed PIN is never claimed.

        Args:
            pin_id: The PIN.
            now: The check time (epoch seconds), recorded as ``last_checked_at`` on a claim.
            min_interval: The seconds that must separate two checks.

        Returns:
            Whether this call claimed the check; ``False`` for an unknown or consumed PIN.
        """
        cursor = self._conn.execute(
            "UPDATE plex_pin SET last_checked_at = ? WHERE pin_id = ? AND consumed_at IS NULL"
            " AND (last_checked_at IS NULL OR last_checked_at <= ?)",
            (now, pin_id, now - min_interval),
        )
        return cursor.rowcount == 1

    @serialised
    def consume_pin(self, pin_id: int, *, now: float) -> bool:
        """Mark a PIN used by a sign-in, unless another sign-in already used it.

        Args:
            pin_id: The PIN.
            now: The use time (epoch seconds).

        Returns:
            Whether this call consumed it.
        """
        cursor = self._conn.execute(
            "UPDATE plex_pin SET consumed_at = ? WHERE pin_id = ? AND consumed_at IS NULL", (now, pin_id)
        )
        return cursor.rowcount == 1

    @serialised
    def purge_pins(self, *, now: float, lifetime: float, limit: int) -> int:
        """Delete the PINs no sign-in can use any more: consumed, or past their expiry.

        A PIN plex.tv gave no expiry is past it once ``lifetime`` seconds old. One statement,
        at most ``limit`` rows, so a start never pays for a backlog at once.

        Args:
            now: The current time (epoch seconds).
            lifetime: The lifetime of a PIN stored with no expiry, in seconds.
            limit: The most rows one call deletes.

        Returns:
            The number of PINs deleted.
        """
        cursor = self._conn.execute(
            "DELETE FROM plex_pin WHERE pin_id IN (SELECT pin_id FROM plex_pin WHERE consumed_at IS NOT NULL"
            " OR expires_at <= ? OR (expires_at IS NULL AND created_at <= ?) LIMIT ?)",
            (now, now - lifetime, limit),
        )
        return cursor.rowcount
