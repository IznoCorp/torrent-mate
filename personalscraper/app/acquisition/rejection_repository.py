"""The suggestions an account rejected, as rows in ``app.db`` (K3-G7, operator ruling O-9 A).

A rejection is the rejecting account's: every read and write names the account, and no read ever
counts another's. A row holds a title's identity in the deck, ``(provider, provider_id, kind)``,
never the deck row's key: a refresh replaces the deck, and the rejection stays.

:class:`SuggestionRejectionRepository` is rows and nothing more; :class:`AccountRejections` is the
store the :class:`~personalscraper.app.acquisition.suggestions.Suggestions` service reads and
writes through, for the account of the actor it is given.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable, Collection, Sequence
from typing import TYPE_CHECKING

from personalscraper.core.sqlite import serialised

if TYPE_CHECKING:
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.acquisition.suggestions import SuggestionKey
    from personalscraper.app.store.store import AppStore

__all__ = ["AccountRejections", "SuggestionRejectionRepository"]


class SuggestionRejectionRepository:
    """The ``suggestion_rejection`` rows over one ``app.db`` connection it is GIVEN; it opens nothing."""

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
    def add(self, account_id: str, key: SuggestionKey, *, now: float) -> None:
        """Record that an account rejected a title; one already recorded is left as it was.

        Args:
            account_id: The account.
            key: The title, ``(provider, provider_id, kind)``.
            now: When it was rejected (epoch seconds).

        Raises:
            sqlite3.IntegrityError: The account does not exist.
        """
        self._conn.execute(
            "INSERT INTO suggestion_rejection (account_id, provider, provider_id, kind, rejected_at)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT (account_id, provider, provider_id, kind) DO NOTHING",
            (account_id, *key, now),
        )

    @serialised
    def remove(self, account_id: str, key: SuggestionKey) -> bool:
        """Forget an account's rejection of a title.

        Args:
            account_id: The account.
            key: The title, ``(provider, provider_id, kind)``.

        Returns:
            Whether the account had rejected it.
        """
        cursor = self._conn.execute(
            "DELETE FROM suggestion_rejection WHERE account_id = ? AND provider = ? AND provider_id = ? AND kind = ?",
            (account_id, *key),
        )
        return cursor.rowcount > 0

    @serialised
    def rejected(self, account_id: str, keys: Sequence[SuggestionKey]) -> set[SuggestionKey]:
        """Name which of ``keys`` an account rejected.

        Args:
            account_id: The account.
            keys: The titles to check.

        Returns:
            The keys among ``keys`` the account rejected.
        """
        if not keys:
            return set()
        wanted = ", ".join(["(?, ?, ?)"] * len(keys))
        rows = self._conn.execute(
            "SELECT provider, provider_id, kind FROM suggestion_rejection"  # noqa: S608 — placeholders only
            f" WHERE account_id = ? AND (provider, provider_id, kind) IN (VALUES {wanted})",
            (account_id, *(part for key in keys for part in key)),
        ).fetchall()
        return {(str(provider), str(provider_id), str(kind)) for provider, provider_id, kind in rows}


class AccountRejections:
    """The rejections of the actor's own account, over the environment's ``app.db``."""

    def __init__(self, app_store: AppStore, *, clock: Callable[[], float] = time.time) -> None:
        """Hold the store; nothing is opened yet.

        Args:
            app_store: The environment's ``app.db``.
            clock: Reads the time a rejection is stamped with (epoch seconds).
        """
        self._app_store = app_store
        self._clock = clock

    def rejected(self, actor: Actor, keys: Sequence[SuggestionKey]) -> Collection[SuggestionKey]:
        """Name which of ``keys`` the actor's own account rejected.

        Args:
            actor: The reader; another account's rejection never counts.
            keys: The titles to check.

        Returns:
            The keys among ``keys`` the account rejected.
        """
        return self._app_store.suggestion_rejections.rejected(actor.account_id, keys)

    def reject(self, actor: Actor, key: SuggestionKey) -> None:
        """Record that the actor's account rejected a title.

        Args:
            actor: Whose rejection it is.
            key: The title.
        """
        self._app_store.suggestion_rejections.add(actor.account_id, key, now=self._clock())

    def undo(self, actor: Actor, key: SuggestionKey) -> bool:
        """Forget the actor's account's rejection of a title.

        Args:
            actor: Whose rejection it is.
            key: The title.

        Returns:
            Whether the account had rejected it.
        """
        return self._app_store.suggestion_rejections.remove(actor.account_id, key)
