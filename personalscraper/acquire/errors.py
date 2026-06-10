"""Acquire-lobe SQLite exceptions — rich subclasses of the core markers.

These mirror the ``IndexerXxxError`` subclasses in
:mod:`personalscraper.indexer.db`: they re-parent onto the bare
``core.sqlite.errors.Sqlite*Error`` markers so that, for example,
``isinstance(AcquireLockError(123), SqliteLockError)`` is ``True``, while
carrying actionable, attribute-bearing messages.

Each constructor signature matches the ``error_factory`` callable expected by
the corresponding core helper so the class itself can be passed directly:

  * :class:`AcquireLockError` ``(pid)``        → ``db_lock(error_factory=...)``
  * :class:`AcquireMigrationError` ``(version)`` → ``apply_migrations(error_factory=...)``
  * :class:`AcquireCorruptError` ``(db_path, quarantine_path)`` →
    ``OpenDbErrorFactories(corrupt=...)``

Import direction: stdlib + ``core.sqlite.errors`` only (acquire/ must never
import indexer/ or any triage package).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteLockError,
    SqliteMigrationError,
)


class AcquireLockError(SqliteLockError):
    """Raised when the ``acquire.db`` writer lock is held by a live process.

    Args:
        pid: PID of the process currently holding the lock.
    """

    def __init__(self, pid: int) -> None:
        """Initialize with the PID of the lock holder.

        Args:
            pid: PID of the live process holding the ``acquire.db`` lock.
        """
        self.pid = pid
        super().__init__(
            f"Acquire writer lock held by PID {pid}. "
            f"Another acquire-lobe step is running; wait for it to finish or "
            f"kill PID {pid} if it is stale."
        )


class AcquireMigrationError(SqliteMigrationError):
    """Raised when applying an ``acquire.db`` migration script fails.

    The database is restored from the pre-migration snapshot before this
    exception propagates (see the core applier's closed-connection invariant).

    Args:
        version: The migration version number that failed (e.g. ``1`` for
            ``001_init.sql``).
    """

    def __init__(self, version: int) -> None:
        """Initialize with the failed migration version number.

        Args:
            version: Numeric prefix of the migration script that failed.
        """
        self.version = version
        super().__init__(
            f"Acquire migration {version:03d} failed; database restored from "
            f"snapshot. Inspect the migration SQL before retrying."
        )


class AcquireCorruptError(SqliteCorruptError):
    """Raised when ``acquire.db`` is malformed and has been quarantined.

    Args:
        db_path: Original DB path.
        quarantine_path: Path the corrupt file was renamed to.
    """

    def __init__(self, db_path: Path, quarantine_path: Path) -> None:
        """Initialize with the original and quarantine paths.

        Args:
            db_path: The path of the corrupt ``acquire.db``.
            quarantine_path: Where the corrupt file was moved aside to.
        """
        self.db_path = db_path
        self.quarantine_path = quarantine_path
        super().__init__(
            f"acquire.db at {db_path} is corrupt; quarantined to "
            f"{quarantine_path}. A fresh database will be created on next boot."
        )


__all__ = [
    "AcquireCorruptError",
    "AcquireLockError",
    "AcquireMigrationError",
]
