"""Indexer SQLite facade — thin wrapper over the event-free ``core.sqlite`` layer.

The neutral connection-opening, writer-lock, PRAGMA, and migration machinery now
lives under :mod:`personalscraper.core.sqlite` (event-free, shared by ``indexer/``
and ``acquire/``).  This module re-wires those primitives into the indexer's
event-aware surface:

* :func:`open_db` keeps its required ``event_bus`` parameter, runs the
  :func:`check_free_space` guard (which emits :class:`DiskFullWarning`), and
  delegates to :func:`personalscraper.core.sqlite._open.open_db` with a bundle of
  rich ``Indexer*Error`` factories so the attribute-bearing exceptions still
  propagate through the open path.
* :func:`check_free_space` is kept VERBATIM here (required-bus contract pin — it
  emits :class:`DiskFullWarning` before raising :class:`IndexerDiskFullError`).
* :func:`indexer_lock`, :func:`apply_migrations`, and :func:`_apply_pragmas` are
  thin shims delegating to the core primitives.

Custom exceptions defined here (re-parented onto the bare ``core.sqlite``
markers so ``isinstance`` works both ways):
- :class:`IndexerLockError` — another process holds the writer lock.
- :class:`IndexerCorruptError` — ``library.db`` is malformed and quarantined.
- :class:`IndexerInvalidPathError` — ``db_path`` resolves to a macFUSE-NTFS mount.
- :class:`IndexerDiskFullError` — not enough free space to proceed.
- :class:`IndexerFKOrphansError` — ``PRAGMA foreign_key_check`` returned rows.
- :class:`IndexerMigrationError` — a migration script failed; DB restored from snapshot.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator

from personalscraper.core.sqlite._lock import db_lock
from personalscraper.core.sqlite._migrate import apply_migrations as _core_apply_migrations
from personalscraper.core.sqlite._open import OpenDbErrorFactories
from personalscraper.core.sqlite._open import open_db as _core_open_db
from personalscraper.core.sqlite._pragmas import apply_pragmas as _apply_pragmas
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
    SqliteLockError,
    SqliteMigrationError,
)
from personalscraper.indexer.events import DiskFullWarning
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus

log = get_logger("indexer.db")

# Re-export the canonical PRAGMA helper under the historical underscore name so
# callers doing ``from personalscraper.indexer.db import _apply_pragmas`` (outbox
# publishers, scanner concurrency workers, best-effort readers) keep working.
__all__ = [
    "IndexerLockError",
    "IndexerCorruptError",
    "IndexerInvalidPathError",
    "IndexerDiskFullError",
    "IndexerFKOrphansError",
    "IndexerMigrationError",
    "check_free_space",
    "open_db",
    "indexer_lock",
    "apply_migrations",
    "_apply_pragmas",
]

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class IndexerLockError(SqliteLockError):
    """Raised when the writer lock is held by a live process.

    Args:
        pid: PID of the process currently holding the lock.
    """

    def __init__(self, pid: int) -> None:
        """Initialize with the PID of the lock holder."""
        self.pid = pid
        super().__init__(f"Indexer writer lock held by PID {pid}")


class IndexerCorruptError(SqliteCorruptError):
    """Raised when ``library.db`` is malformed and has been quarantined.

    Args:
        db_path: Original DB path.
        quarantine_path: Path the corrupt file was renamed to.
    """

    def __init__(self, db_path: Path, quarantine_path: Path) -> None:
        """Initialize with the original and quarantine paths."""
        self.db_path = db_path
        self.quarantine_path = quarantine_path
        super().__init__(
            f"Database at {db_path} is corrupt; quarantined to {quarantine_path}. "
            "Pass rebuild=True to create a fresh database."
        )


class IndexerInvalidPathError(SqliteInvalidPathError):
    """Raised when ``db_path`` resolves to a macFUSE-NTFS (external) mount.

    SQLite WAL mode is unreliable on macFUSE-NTFS; the DB must live on the
    internal APFS volume.

    Args:
        db_path: The rejected path.
        mount_point: The macFUSE-NTFS mount point that contains it.
    """

    def __init__(self, db_path: Path, mount_point: str) -> None:
        """Initialize with the rejected path and the offending mount point."""
        self.db_path = db_path
        self.mount_point = mount_point
        super().__init__(
            f"db_path {db_path} is on a macFUSE/NTFS mount ({mount_point}). "
            "The indexer database must reside on the internal APFS disk."
        )


class IndexerDiskFullError(SqliteDiskFullError):
    """Raised when free disk space is insufficient for the indexer to proceed.

    Args:
        path: The path whose parent partition was checked.
        free_bytes: Available bytes at time of check.
        required_bytes: Minimum bytes needed (2 × expected_growth_bytes).
    """

    def __init__(self, path: Path, free_bytes: int, required_bytes: int) -> None:
        """Initialize with path and space figures."""
        self.path = path
        self.free_bytes = free_bytes
        self.required_bytes = required_bytes
        super().__init__(
            f"Insufficient free space at {path.parent}: {free_bytes} bytes available, {required_bytes} bytes required."
        )


class IndexerFKOrphansError(SqliteFKOrphansError):
    """Raised by :func:`open_db` when ``PRAGMA foreign_key_check`` returns rows.

    A foreign-key orphan is a row whose foreign key references a parent row
    that does not exist. SQLite only enforces FKs at write time when
    ``PRAGMA foreign_keys=ON`` is active on the connection performing the
    write — a script bypassing :func:`open_db` (raw ``sqlite3.connect``,
    sqlite3 CLI, etc.) can therefore insert orphans silently. Phase 1.2 of
    tech-debt 0.16.0 adds the pre-check at :func:`open_db` to surface those
    orphans loudly rather than letting downstream queries return inconsistent
    results.

    Distinct from :class:`IndexerCorruptError` which signals structural
    corruption (malformed file). Orphans are *data integrity* violations,
    the file itself is structurally fine.

    Args:
        db_path: Path of the database whose ``foreign_key_check`` failed.
        orphan_count: Total number of orphan rows reported by the PRAGMA.
        sample: First few orphan rows (for diagnostic; truncated to keep the
            message readable).
    """

    def __init__(
        self,
        db_path: Path,
        orphan_count: int,
        sample: list[tuple[object, ...]] | None = None,
    ) -> None:
        """Initialize with the db path and orphan diagnostic."""
        self.db_path = db_path
        self.orphan_count = orphan_count
        self.sample = sample or []
        sample_str = f" Sample: {self.sample}" if self.sample else ""
        super().__init__(
            f"Database at {db_path} has {orphan_count} foreign-key orphan(s) "
            f"(PRAGMA foreign_key_check returned {orphan_count} row(s)).{sample_str} "
            f"Run `sqlite3 {db_path} 'PRAGMA foreign_key_check;'` to inspect, "
            f"then clean up the orphan rows before retrying."
        )


class IndexerMigrationError(SqliteMigrationError):
    """Raised when applying a migration script fails.

    The database is restored from the pre-migration snapshot before this
    exception propagates to the caller.

    Args:
        version: The migration version number that failed (e.g. 1 for ``001_init.sql``).
    """

    def __init__(self, version: int) -> None:
        """Initialize with the failed migration version number."""
        self.version = version
        super().__init__(f"Migration {version:03d} failed; database restored from snapshot")


# ---------------------------------------------------------------------------
# Disk-full guard (required-bus contract pin — kept VERBATIM, event-aware)
# ---------------------------------------------------------------------------


def check_free_space(
    path: Path,
    expected_growth_bytes: int,
    *,
    event_bus: EventBus,
) -> None:
    """Verify that *path*'s parent partition has enough room for the indexer.

    Raises :class:`IndexerDiskFullError` if ``free < 2 × expected_growth_bytes``.

    Args:
        path: The DB path whose parent partition is checked.
        expected_growth_bytes: Estimated number of bytes the indexer will write.
        event_bus: Required :class:`EventBus`. When the free-space check
            fails, a :class:`DiskFullWarning` is emitted before
            :class:`IndexerDiskFullError` is raised.

    Raises:
        IndexerDiskFullError: When available space is below the safety threshold.
    """
    stat = os.statvfs(path.parent)
    free_bytes = stat.f_frsize * stat.f_bavail
    required_bytes = 2 * expected_growth_bytes
    if free_bytes < required_bytes:
        event_bus.emit(
            DiskFullWarning(
                source="indexer.db.check_free_space",
                disk_path=path,
                free_bytes=free_bytes,
                threshold_bytes=required_bytes,
            ),
        )
        raise IndexerDiskFullError(path, free_bytes, required_bytes)


# See ``personalscraper.indexer._disk_guard.handle_disk_full`` for the
# disk-full recovery path (PRAGMA wal_checkpoint + DiskFullWarning emit).


# ---------------------------------------------------------------------------
# Rich-error factory bundle — wires the attribute-bearing Indexer*Error
# subclasses into the event-free core open_db so they propagate through the
# open path (tests assert pytest.raises(IndexerCorruptError) etc.).
# ---------------------------------------------------------------------------

_OPEN_DB_ERROR_FACTORIES = OpenDbErrorFactories(
    invalid_path=IndexerInvalidPathError,
    corrupt=IndexerCorruptError,
    disk_full=IndexerDiskFullError,
    fk_orphans=IndexerFKOrphansError,
)


# ---------------------------------------------------------------------------
# Core API (thin wrappers over personalscraper.core.sqlite)
# ---------------------------------------------------------------------------


def open_db(
    path: Path,
    expected_growth_bytes: int = 0,
    *,
    rebuild: bool = False,
    allow_fk_orphans: bool = False,
    event_bus: EventBus,
) -> sqlite3.Connection:
    """Open (or create) the indexer SQLite database at *path*.

    Applies the PRAGMAs from DESIGN §6.1:
    ``WAL``, ``synchronous=NORMAL``, ``temp_store=MEMORY``,
    ``cache_size=-65536``, ``mmap_size=268435456``,
    ``wal_autocheckpoint=1000``, ``busy_timeout=5000``,
    ``foreign_keys=ON``.

    Pre-open checks (in order):
    1. Reject *path* on a macFUSE-NTFS mount (:class:`IndexerInvalidPathError`).
    2. If ``expected_growth_bytes > 0``, verify free space (:class:`IndexerDiskFullError`).
    3. Detect a corrupt DB (``DatabaseError: database disk image is malformed``),
       quarantine it to ``<path>.corrupt-<unix_ts>``, and raise
       :class:`IndexerCorruptError` — unless *rebuild* is ``True``, in which case
       the quarantine still happens but a fresh DB is opened.

    Args:
        path: Filesystem path of the SQLite database.
        expected_growth_bytes: Estimated write volume for the session.  When
            non-zero, free-space is verified before opening.
        rebuild: When ``True``, a corrupt existing DB is quarantined and a
            fresh empty DB is created.  When ``False`` (default), corruption
            raises :class:`IndexerCorruptError` immediately.
        allow_fk_orphans: When ``True``, foreign-key orphans are logged as a
            WARNING and the connection is returned instead of raising
            :class:`IndexerFKOrphansError`. Default ``False`` preserves the
            fail-loud DEV #19 contract; only the FK-orphan cleanup path
            (``library-reconcile --clean-fk-orphans``) opts in so it can open a
            dirty DB and repair it (DEV #3).
        event_bus: Required :class:`EventBus` forwarded to
            :func:`check_free_space` so the pre-open free-space guard emits
            :class:`DiskFullWarning` on threshold violation.

    Returns:
        An open :class:`sqlite3.Connection` with all PRAGMAs applied.

    Raises:
        IndexerInvalidPathError: If *path* is on a macFUSE-NTFS volume.
        IndexerDiskFullError: If free space < 2 × *expected_growth_bytes*.
        IndexerCorruptError: If the existing DB is malformed and *rebuild* is False.
    """
    # --- Pre-open free-space guard (event-aware; emits DiskFullWarning) ---
    # Kept in the indexer wrapper because the core open_db is event-free.  The
    # core call below therefore receives expected_growth_bytes=0 (the space check
    # has already happened here, with the event emission and rich raise).
    if expected_growth_bytes > 0:
        check_free_space(path, expected_growth_bytes, event_bus=event_bus)

    # --- Delegate to the event-free core, wiring the rich Indexer*Error factories ---
    # The factory bundle preserves the attribute-bearing exceptions
    # (IndexerInvalidPathError / IndexerCorruptError / IndexerFKOrphansError) so
    # they are raised THROUGH this open path, exactly as the tests assert.
    return _core_open_db(
        path,
        0,
        rebuild=rebuild,
        allow_fk_orphans=allow_fk_orphans,
        errors=_OPEN_DB_ERROR_FACTORIES,
    )


@contextmanager
def indexer_lock(db_path: Path, timeout: float = 0) -> Generator[None, None, None]:
    """Acquire the single-writer lock for the indexer database.

    Thin wrapper over :func:`personalscraper.core.sqlite._lock.db_lock`,
    passing :class:`IndexerLockError` as the ``error_factory`` so a live-lock
    timeout raises the rich, ``.pid``-bearing exception (and stale recovery logs
    ``core.sqlite.lock.stale_recovered``).

    Args:
        db_path: Path of the indexer database (lock files are derived from this).
        timeout: Seconds to wait before declaring a timeout.  ``0`` means
            fail immediately if the lock is unavailable (default).

    Yields:
        ``None`` — the lock is held for the duration of the ``with`` block.

    Raises:
        IndexerLockError: If the lock is held by a live process.
    """
    with db_lock(db_path, timeout=timeout, error_factory=IndexerLockError):
        yield


# ---------------------------------------------------------------------------
# Migration applier (thin wrapper)
# ---------------------------------------------------------------------------


def apply_migrations(conn: sqlite3.Connection, dir_: Path) -> None:
    """Apply pending SQL migration scripts to *conn* in version order.

    Thin wrapper over :func:`personalscraper.core.sqlite._migrate.apply_migrations`,
    passing :class:`IndexerMigrationError` as the ``error_factory`` so a failed
    migration raises the rich, ``.version``-bearing exception.

    See the core function for the full snapshot / apply / restore semantics,
    including the closed-connection invariant on the failure path (the caller
    MUST re-open a fresh connection after :class:`IndexerMigrationError`).

    Args:
        conn: Open :class:`sqlite3.Connection` to the indexer database.
        dir_: Directory that contains the ``*.sql`` migration scripts.

    Raises:
        IndexerMigrationError: When a migration script fails to apply.  The
            database is restored from the pre-migration snapshot and *conn* is
            closed before the exception propagates.
    """
    _core_apply_migrations(conn, dir_, error_factory=IndexerMigrationError)
