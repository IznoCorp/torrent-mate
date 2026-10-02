"""The environment's ``app`` store: ``app.db``, ``app-dev.db`` or ``app-staging.db``.

One more SQLite file beside ``library`` and ``acquire`` (Q2/Q13: three stores by owner,
one file per environment by suffix). It holds the application layer's own state; its
baseline adopts ``push_subscription`` (K1 adds the accounts and the foreign key).

Concurrency model: the same as ``acquire/store.py``. WAL plus ``busy_timeout`` in the
canonical PRAGMA set; the core ``db_lock`` is taken only briefly around open + migrate
and released at once. It is a strict leaf, never held across another lock, so the lock
order is ``pipeline.lock > indexer_lock > acquire.db.lock > app.db.lock``.

Lazy open: :func:`build_app_store` returns an inert handle (no directory, no connection,
no lock, no migration); the file opens on the first access to :attr:`AppStore.push`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Final

from personalscraper.app.store.errors import AppMigrationError
from personalscraper.conf.environment import StoreName, store_path
from personalscraper.core.sqlite import apply_migrations, db_lock, open_db
from personalscraper.logger import get_logger
from personalscraper.push.store import SqlitePushSubscriptionStore

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("app.store")

_MIGRATIONS_DIR: Final = Path(__file__).parent / "migrations"

# Generous timeout for the BRIEF open+migrate lock (never 0: several short-lived
# processes can legitimately contend for it on a first boot).
_MIGRATION_LOCK_TIMEOUT_S: Final = 10.0


class AppStore:
    """The environment's ``app.db``: inert until first use; ``db_lock`` → ``open_db`` → ``apply_migrations``."""

    def __init__(self, db_path: Path) -> None:
        """Build an inert handle; nothing is opened.

        Args:
            db_path: The ``app`` store file of the environment.
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._push: SqlitePushSubscriptionStore | None = None
        self._closed = False

    def _ensure_open(self) -> sqlite3.Connection:
        """Open the connection and migrate the schema on first access.

        Returns:
            The open connection to the ``app`` store.

        Raises:
            RuntimeError: If the store has already been closed.
            AppMigrationError: If a pending migration fails to apply.
        """
        if self._closed:
            raise RuntimeError("AppStore is closed")
        if self._conn is not None:
            return self._conn

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with db_lock(self._db_path, timeout=_MIGRATION_LOCK_TIMEOUT_S):
            conn = open_db(self._db_path)
            apply_migrations(conn, _MIGRATIONS_DIR, error_factory=AppMigrationError)

        self._conn = conn
        log.info("app.store.opened", db_path=str(self._db_path))
        return conn

    @property
    def push(self) -> SqlitePushSubscriptionStore:
        """The push subscriptions (opens, and migrates, the store on first access).

        Returns:
            The push subscription store over this store's connection.
        """
        conn = self._ensure_open()
        if self._push is None:
            self._push = SqlitePushSubscriptionStore(conn)
        return self._push

    def close(self) -> None:
        """Close the connection if it was opened; idempotent and fail-soft."""
        self._closed = True
        self._push = None
        if self._conn is None:
            return
        try:
            self._conn.close()
        except Exception as exc:  # noqa: BLE001 — fail-soft close contract
            log.warning("app.store.close_conn_failed", error=str(exc))
        self._conn = None
        log.info("app.store.closed", db_path=str(self._db_path))


def build_app_store(config: Config) -> AppStore:
    """Build an INERT :class:`AppStore` at the environment's ``app`` store path.

    Args:
        config: The typed configuration; ``paths.data_dir`` and ``PERSONALSCRAPER_ENV``
            name the file.

    Returns:
        An inert :class:`AppStore`; opens nothing until first use.
    """
    return AppStore(store_path(config.paths.data_dir, StoreName.APP))
