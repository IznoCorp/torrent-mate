"""The environment's ``app`` store: ``app.db``, ``app-dev.db`` or ``app-staging.db``.

One more SQLite file beside ``library`` and ``acquire`` (Q2/Q13: three stores by owner,
one file per environment by suffix). It holds the application layer's own state: the
push subscriptions, and the accounts with their roles, Plex links and sessions — a push
subscription belongs to an account, and goes with it. Each aggregate is reached through its
own repository over the one connection and its lock; :meth:`AppStore.immediate` makes calls
across them one transaction.

Concurrency model: the same as ``acquire/store.py``. WAL plus ``busy_timeout`` in the
canonical PRAGMA set; the core ``db_lock`` is taken only briefly around open + migrate
and released at once. It is a strict leaf, never held across another lock, so the lock
order is ``pipeline.lock > indexer_lock > acquire.db.lock > app.db.lock``.

Lazy open: :func:`build_app_store` returns an inert handle (no directory, no connection,
no lock, no migration); the file opens on the first access to a repository or to
:meth:`AppStore.immediate`. That first access may come from several threads of the web's
threadpool at once: a thread lock makes exactly one of them open the connection.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final

from personalscraper.app.accounts.account_repository import AccountRepository
from personalscraper.app.accounts.notice_repository import NoticeRepository, PreferenceRepository
from personalscraper.app.accounts.pin_repository import PlexPinRepository
from personalscraper.app.accounts.role_repository import RoleRepository
from personalscraper.app.accounts.session_repository import SessionRepository
from personalscraper.app.store.errors import AppMigrationError
from personalscraper.app.store.setting_repository import SettingRepository
from personalscraper.app.supervisor.lease_repository import LeaseRepository
from personalscraper.app.supervisor.queue_repository import QueueRepository
from personalscraper.conf.environment import StoreName, store_path
from personalscraper.core.sqlite import apply_migrations, db_lock, open_db, safe_rollback
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
        self._roles: RoleRepository | None = None
        self._accounts: AccountRepository | None = None
        self._sessions: SessionRepository | None = None
        self._pins: PlexPinRepository | None = None
        self._settings: SettingRepository | None = None
        self._runs: QueueRepository | None = None
        self._lease: LeaseRepository | None = None
        self._notices: NoticeRepository | None = None
        self._preferences: PreferenceRepository | None = None
        self._closed = False
        # ``db_lock`` serialises open + migrate across processes only; this one serialises
        # the threads of one process, so concurrent first accesses open a single connection.
        self._open_lock = threading.Lock()
        # Python's sqlite3 does not make concurrent use of one connection safe: the
        # repositories over it hold this one lock around every use.
        self._conn_lock = threading.RLock()

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
        conn = self._conn
        if conn is not None:
            return conn
        with self._open_lock:
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

    @contextmanager
    def immediate(self) -> Iterator[None]:
        """Run the calls inside as one transaction holding the writer lock.

        Yields:
            Nothing; every write inside commits on exit, or none does.

        Raises:
            BaseException: Whatever the block raised, after the rollback; a refused
                ``COMMIT`` is rolled back too, so the writer lock is never kept.
        """
        conn = self._ensure_open()
        # The lock spans the whole transaction: no other thread's statement may land
        # inside it on the shared connection; this thread's calls re-enter it.
        with self._conn_lock:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                # SQLite may already have ended the transaction (SQLITE_FULL, IOERR): a bare
                # ROLLBACK would then raise and hide the block's own error.
                safe_rollback(conn)
                raise
            try:
                conn.execute("COMMIT")
            except BaseException:
                safe_rollback(conn)
                raise

    @contextmanager
    def snapshot(self) -> Iterator[None]:
        """Run the reads inside as one consistent view, without the writer lock.

        A deferred transaction: WAL fixes its snapshot at the first read, so every read inside sees
        the base as of that instant, while a writer (the supervisor's every-2-seconds writes) is
        neither waited for nor held up.

        Yields:
            Nothing; the transaction is ended on exit and nothing is written.

        Raises:
            BaseException: Whatever the block raised, after the transaction is ended.
        """
        conn = self._ensure_open()
        with self._conn_lock:
            conn.execute("BEGIN")
            try:
                yield
            finally:
                safe_rollback(conn)

    @property
    def push(self) -> SqlitePushSubscriptionStore:
        """The push subscriptions (opens, and migrates, the store on first access).

        Returns:
            The push subscription store over this store's connection.
        """
        conn = self._ensure_open()
        if self._push is None:
            self._push = SqlitePushSubscriptionStore(conn, lock=self._conn_lock)
        return self._push

    @property
    def roles(self) -> RoleRepository:
        """The roles' rows (opens, and migrates, the store on first access).

        Returns:
            The role repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._roles is None:
            self._roles = RoleRepository(conn, lock=self._conn_lock)
        return self._roles

    @property
    def accounts(self) -> AccountRepository:
        """The accounts' rows (opens, and migrates, the store on first access).

        Returns:
            The account repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._accounts is None:
            self._accounts = AccountRepository(conn, lock=self._conn_lock)
        return self._accounts

    @property
    def sessions(self) -> SessionRepository:
        """The sessions' rows (opens, and migrates, the store on first access).

        Returns:
            The session repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._sessions is None:
            self._sessions = SessionRepository(conn, lock=self._conn_lock)
        return self._sessions

    @property
    def pins(self) -> PlexPinRepository:
        """The Plex sign-in PINs' rows (opens, and migrates, the store on first access).

        Returns:
            The Plex PIN repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._pins is None:
            self._pins = PlexPinRepository(conn, lock=self._conn_lock)
        return self._pins

    @property
    def settings(self) -> SettingRepository:
        """The application settings (opens, and migrates, the store on first access).

        Returns:
            The setting repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._settings is None:
            self._settings = SettingRepository(conn, lock=self._conn_lock)
        return self._settings

    @property
    def runs(self) -> QueueRepository:
        """The queue of asked runs (opens, and migrates, the store on first access).

        Returns:
            The queue repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._runs is None:
            self._runs = QueueRepository(conn, lock=self._conn_lock)
        return self._runs

    @property
    def lease(self) -> LeaseRepository:
        """The supervisor's lease (opens, and migrates, the store on first access).

        Returns:
            The lease repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._lease is None:
            self._lease = LeaseRepository(conn, lock=self._conn_lock)
        return self._lease

    @property
    def notices(self) -> NoticeRepository:
        """The accounts' in-app notices (opens, and migrates, the store on first access).

        Returns:
            The notice repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._notices is None:
            self._notices = NoticeRepository(conn, lock=self._conn_lock)
        return self._notices

    @property
    def preferences(self) -> PreferenceRepository:
        """The accounts' push switches (opens, and migrates, the store on first access).

        Returns:
            The preference repository over this store's connection.
        """
        conn = self._ensure_open()
        if self._preferences is None:
            self._preferences = PreferenceRepository(conn, lock=self._conn_lock)
        return self._preferences

    def close(self) -> None:
        """Close the connection if it was opened; idempotent and fail-soft."""
        # Under the open lock: a first access still opening finishes first, and its
        # connection is the one closed here, never one left behind.
        with self._open_lock:
            self._closed = True
            self._push = None
            self._roles = None
            self._accounts = None
            self._sessions = None
            self._pins = None
            self._settings = None
            self._runs = None
            self._lease = None
            self._notices = None
            self._preferences = None
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
