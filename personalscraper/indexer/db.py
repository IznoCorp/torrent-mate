"""SQLite connection management, writer-lock, disk-full guard, and migration applier.

Provides :func:`open_db` which applies the canonical PRAGMAs from DESIGN §6.1,
:func:`indexer_lock` backed by a :class:`filelock.FileLock`, :func:`apply_migrations`
which applies pending ``*.sql`` scripts in sorted order, and helpers for detecting and
recovering from disk-full conditions and corrupt databases.

Custom exceptions defined here:
- :class:`IndexerLockError` — another process holds the writer lock.
- :class:`IndexerCorruptError` — ``library.db`` is malformed and quarantined.
- :class:`IndexerInvalidPathError` — ``db_path`` resolves to a macFUSE-NTFS mount.
- :class:`IndexerDiskFullError` — not enough free space to proceed.
- :class:`IndexerMigrationError` — a migration script failed; DB restored from snapshot.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator

from filelock import FileLock, Timeout

from personalscraper.indexer.events import DiskFullWarning
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus

log = get_logger("indexer.db")

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class IndexerLockError(RuntimeError):
    """Raised when the writer lock is held by a live process.

    Args:
        pid: PID of the process currently holding the lock.
    """

    def __init__(self, pid: int) -> None:
        """Initialize with the PID of the lock holder."""
        self.pid = pid
        super().__init__(f"Indexer writer lock held by PID {pid}")


class IndexerCorruptError(RuntimeError):
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


class IndexerInvalidPathError(ValueError):
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


class IndexerDiskFullError(OSError):
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


class IndexerFKOrphansError(RuntimeError):
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


class IndexerMigrationError(RuntimeError):
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
# Helpers
# ---------------------------------------------------------------------------

_MACFUSE_FSTYPES = frozenset({"fuse_osxfuse", "osxfuse", "macfuse", "ntfs", "fuse-t"})


def _find_ntfs_mount(path: Path) -> str | None:
    """Return the macFUSE-NTFS mount point that contains *path*, or ``None``.

    Parses the output of the macOS ``mount`` command to find the most specific
    (longest) mount point that is a prefix of *path* and whose filesystem type
    is one of the known macFUSE/NTFS types.

    Args:
        path: Filesystem path to check.

    Returns:
        The matching mount-point string, or ``None`` if the path is not on a
        macFUSE-NTFS volume.
    """
    try:
        result = subprocess.run(["mount"], capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    resolved = str(path.resolve())
    best: str | None = None

    for line in result.stdout.splitlines():
        # macOS mount line format:
        #   /dev/disk2s1 on /Volumes/Disk1 (ufsd_NTFS, local, noatime)
        #   map auto_home on /home (autofs, automounted, nobrowse)
        parts = line.split(" on ", 1)
        if len(parts) != 2:
            continue
        rest = parts[1]
        # Split mount point from options: "/Volumes/Disk1 (ufsd_NTFS, ...)"
        paren_idx = rest.find(" (")
        if paren_idx == -1:
            continue
        mount_point = rest[:paren_idx].strip()
        options_str = rest[paren_idx + 2 :].rstrip(")")
        fstype_raw = options_str.split(",")[0].strip().lower()

        # Check if any known macFUSE/NTFS token appears in fstype_raw
        is_ntfs = any(t in fstype_raw for t in _MACFUSE_FSTYPES)
        if not is_ntfs:
            continue

        # Check if this mount point is a prefix of our resolved path
        if resolved == mount_point or resolved.startswith(mount_point.rstrip("/") + "/"):
            # Pick the most specific (longest) match
            if best is None or len(mount_point) > len(best):
                best = mount_point

    return best


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
# Core API
# ---------------------------------------------------------------------------


def open_db(
    path: Path,
    expected_growth_bytes: int = 0,
    *,
    rebuild: bool = False,
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
    # --- macFUSE-NTFS check (defense-in-depth; the conf validator catches most) ---
    ntfs_mount = _find_ntfs_mount(path)
    if ntfs_mount is not None:
        raise IndexerInvalidPathError(path, ntfs_mount)

    # --- Pre-open free-space guard ---
    if expected_growth_bytes > 0:
        check_free_space(path, expected_growth_bytes, event_bus=event_bus)

    # --- Corruption check ---
    # Signals produced by SQLite when the file is corrupt or not a valid DB at all.
    _CORRUPT_SIGNALS = ("malformed", "file is not a database", "not a database")

    quarantine_path: Path | None = None
    if path.exists():
        try:
            _probe = sqlite3.connect(str(path))
            try:
                # Phase 1.6 / SH-9 / BD-L : check the RESULT of integrity_check,
                # not just whether it raises. Subtle corruptions (B-tree page
                # damage, index inconsistency) can return strings like
                # ``* btree page X is broken`` without throwing — the previous
                # code discarded the result and let those slip through.
                ic_row = _probe.execute("PRAGMA integrity_check").fetchone()
                ic_result = ic_row[0] if ic_row else "unknown"
            finally:
                _probe.close()
            if ic_result != "ok":
                ts = int(time.time())
                quarantine_path = path.parent / f"{path.name}.corrupt-{ts}"
                path.rename(quarantine_path)
                log.error(
                    "indexer.db.integrity_check_failed",
                    original=str(path),
                    quarantine=str(quarantine_path),
                    result=ic_result,
                )
                if not rebuild:
                    raise IndexerCorruptError(path, quarantine_path)
                # rebuild=True: fall through and create a fresh DB
        except sqlite3.DatabaseError as exc:
            if any(signal in str(exc).lower() for signal in _CORRUPT_SIGNALS):
                ts = int(time.time())
                # Use suffix replacement that preserves the full original name
                quarantine_path = path.parent / f"{path.name}.corrupt-{ts}"
                path.rename(quarantine_path)
                log.error(
                    "indexer.db.corrupt",
                    original=str(path),
                    quarantine=str(quarantine_path),
                )
                if not rebuild:
                    raise IndexerCorruptError(path, quarantine_path) from exc
                # rebuild=True: fall through and create a fresh DB
            else:
                raise

    # --- Open and configure ---
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-65536")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA busy_timeout=5000")

    # --- FK orphan pre-check (Phase 1.2 / DEV #19) ---
    # PRAGMA foreign_key_check works regardless of foreign_keys ON/OFF — it
    # scans every FK constraint and reports rows that reference non-existent
    # parents. We run it BEFORE activating FK enforcement: orphans created
    # by a script bypassing open_db (raw sqlite3.connect, sqlite3 CLI) would
    # otherwise stay silently invisible until a write triggers a FK error
    # far from the source.
    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    if orphans:
        log.error(
            "indexer.db.foreign_key_orphans",
            db_path=str(path),
            count=len(orphans),
            sample=[tuple(row) for row in orphans[:5]],
        )
        conn.close()
        raise IndexerFKOrphansError(
            path,
            orphan_count=len(orphans),
            sample=[tuple(row) for row in orphans[:5]],
        )

    conn.execute("PRAGMA foreign_keys=ON")

    return conn


@contextmanager
def indexer_lock(db_path: Path, timeout: float = 0) -> Generator[None, None, None]:
    """Acquire the single-writer lock for the indexer database.

    Two files are used:

    * ``<db_path>.lock`` — the :class:`filelock.FileLock` file (OS-level flock/fcntl).
    * ``<db_path>.lock.json`` — a human-readable JSON sidecar written **after**
      acquiring the OS lock, containing ``{pid, started_at, hostname}``.

    Keeping metadata in a separate file prevents :class:`filelock.FileLock`
    from wiping the content on ``acquire()`` (FileLock truncates the lock file
    when it takes ownership).

    On timeout (``Timeout`` raised by :class:`filelock.FileLock`):

    * Read ``<db_path>.lock.json``, extract ``pid``.
    * ``os.kill(pid, 0)`` — if the process is dead (``OSError``), log
      ``indexer.lock.stale_recovered``, delete both lock files, and acquire.
    * If the process is alive, raise :class:`IndexerLockError`.

    Args:
        db_path: Path of the indexer database (lock file is derived from this).
        timeout: Seconds to wait before declaring a timeout.  ``0`` means
            fail immediately if the lock is unavailable (default).

    Yields:
        ``None`` — the lock is held for the duration of the ``with`` block.

    Raises:
        IndexerLockError: If the lock is held by a live process.
    """
    lock_path = Path(str(db_path) + ".lock")
    meta_path = Path(str(db_path) + ".lock.json")
    lock = FileLock(str(lock_path), timeout=timeout)

    lock_metadata = json.dumps(
        {
            "pid": os.getpid(),
            "started_at": time.time(),
            "hostname": socket.gethostname(),
        }
    )

    # --- Pre-acquisition stale check ---
    # If a metadata sidecar exists before we even try to acquire the OS lock, check
    # whether the recorded PID is still alive.  When a process crashes, the kernel
    # releases the fcntl lock but the metadata file is left behind.  Without this
    # check we would acquire silently and overwrite the stale metadata, losing the
    # opportunity to log the recovery and alert the operator.
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text())
            prior_pid = int(data.get("pid", -1))
            try:
                os.kill(prior_pid, 0)
                # PID is alive — this is a live lock (OS lock will block/timeout below)
            except OSError:
                # PID is dead → stale metadata; clean up and log before acquiring
                log.warning("indexer.lock.stale_recovered", stale_pid=prior_pid)
                for stale in (lock_path, meta_path):
                    try:
                        stale.unlink(missing_ok=True)
                    except OSError:
                        pass
        except (json.JSONDecodeError, ValueError, OSError):
            # Unreadable sidecar; clean up defensively
            try:
                meta_path.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        lock.acquire(timeout=timeout)
    except Timeout:
        # --- Timeout handler: OS lock held by another process ---
        held_pid: int | None = None
        try:
            data_t = json.loads(meta_path.read_text())
            held_pid = int(data_t.get("pid", -1))
        except (OSError, json.JSONDecodeError, ValueError):
            pass

        if held_pid is not None:
            try:
                os.kill(held_pid, 0)
                # Process is alive → cannot acquire
                raise IndexerLockError(held_pid)
            except OSError:
                # Process is dead but OS lock is still held (zombie / timing window);
                # log the recovery and try once more without timeout.
                log.warning("indexer.lock.stale_recovered", stale_pid=held_pid)
                for stale in (lock_path, meta_path):
                    try:
                        stale.unlink(missing_ok=True)
                    except OSError:
                        pass
                lock.acquire(timeout=-1)
        else:
            # Cannot read the metadata file; clear both and try to acquire
            for stale in (lock_path, meta_path):
                try:
                    stale.unlink(missing_ok=True)
                except OSError:
                    pass
            lock.acquire(timeout=-1)

    try:
        meta_path.write_text(lock_metadata)
        yield
    finally:
        lock.release()
        for p in (lock_path, meta_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Migration applier
# ---------------------------------------------------------------------------


def _migration_version(sql_path: Path) -> int:
    """Extract the leading integer from a migration filename.

    For example, ``001_init.sql`` → ``1``, ``042_add_col.sql`` → ``42``.

    Args:
        sql_path: Path to a ``*.sql`` migration file.

    Returns:
        The leading integer portion of the filename as an ``int``.

    Raises:
        ValueError: If the filename does not start with a numeric prefix.
    """
    stem = sql_path.stem  # e.g. "001_init"
    prefix = stem.split("_")[0]
    return int(prefix)


def _db_path_from_conn(conn: sqlite3.Connection) -> Path | None:
    """Attempt to derive the filesystem path of an open connection.

    Queries ``PRAGMA database_list`` for the ``main`` database filename.
    Returns ``None`` for in-memory or unnamed databases.

    Args:
        conn: An open :class:`sqlite3.Connection`.

    Returns:
        The :class:`~pathlib.Path` of the DB file, or ``None`` if in-memory.
    """
    for _seq, _name, filename in conn.execute("PRAGMA database_list"):
        if _name == "main" and filename:
            return Path(filename)
    return None


def apply_migrations(conn: sqlite3.Connection, dir_: Path) -> None:
    """Apply pending SQL migration scripts to *conn* in version order.

    Discovers every ``*.sql`` file in *dir_* whose leading numeric prefix is
    greater than the current ``PRAGMA user_version``, sorts them by that
    number, and applies each in turn.

    For each pending migration:

    1. **Snapshot** — write a ``.pre-migration-<ver>.bak`` backup of the DB
       file (sibling of the DB, via :meth:`~pathlib.Path.read_bytes` /
       :meth:`~pathlib.Path.write_bytes`).  Skipped — with a warning — when
       the connection is in-memory (no derivable DB path).
    2. **Apply** — execute the script via :meth:`~sqlite3.Connection.executescript`
       which runs the SQL in a single implicit transaction.
    3. **Success** — log ``indexer.migration.applied`` with the version number.
    4. **Failure** — restore the DB from the snapshot (if one was taken), log
       ``indexer.migration.failed``, and raise
       :class:`IndexerMigrationError` (chained from the original exception).

    The function is idempotent: if all migrations are already applied
    (``PRAGMA user_version`` ≥ highest script number), it is a no-op.

    Args:
        conn: Open :class:`sqlite3.Connection` to the indexer database.
        dir_: Directory that contains the ``*.sql`` migration scripts.

    Raises:
        IndexerMigrationError: When a migration script fails to apply.
            The database is restored from the pre-migration snapshot before
            the exception propagates.

            **Closed-connection invariant**: when this exception is raised
            because of a restore-from-snapshot, *conn* has already been
            ``.close()``-d (the snapshot is restored by overwriting the DB
            file on disk, which requires the active connection to be closed).
            Callers MUST re-open a fresh connection (e.g. via
            :func:`open_db`) before issuing further queries; reusing the
            closed *conn* will raise ``sqlite3.ProgrammingError``.
    """
    # Resolve current schema version from the database.
    current_version: int = conn.execute("PRAGMA user_version").fetchone()[0]

    # Collect and sort all *.sql migration scripts by their leading number.
    scripts = sorted(
        (p for p in dir_.glob("*.sql") if p.is_file()),
        key=_migration_version,
    )

    db_path: Path | None = _db_path_from_conn(conn)

    for script in scripts:
        try:
            ver = _migration_version(script)
        except (ValueError, IndexError):
            log.warning("indexer.migration.skip_unparseable", file=str(script))
            continue

        if ver <= current_version:
            # Already applied; idempotent skip.
            continue

        # --- Step 1: take a pre-migration snapshot ---
        # Flush the WAL to the main file before snapshotting so that the backup
        # contains all committed writes from prior migrations.  Without the
        # checkpoint the WAL may hold pages that are not yet in the DB file,
        # making a raw file-copy snapshot incomplete.
        bak_path: Path | None = None
        if db_path is not None:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
            bak_path = db_path.parent / f"{db_path.name}.pre-migration-{ver}.bak"
            bak_path.write_bytes(db_path.read_bytes())
        else:
            log.warning(
                "indexer.migration.no_snapshot",
                version=ver,
                reason="in-memory database; skipping backup",
            )

        # --- Step 2: apply the script ---
        sql_text = script.read_text(encoding="utf-8")
        try:
            conn.executescript(sql_text)
        except Exception as exc:  # noqa: BLE001 — catch-all so we can restore + re-raise
            log.error(
                "indexer.migration.failed",
                version=ver,
                error=str(exc),
            )
            # --- Step 4 (failure path): restore from snapshot ---
            if bak_path is not None and db_path is not None and bak_path.exists():
                conn.close()
                db_path.write_bytes(bak_path.read_bytes())
                # Re-open the connection in-place so the caller still holds a valid conn.
                # We cannot reassign the caller's local variable, but we can copy the
                # restored file's pages back into the existing connection object via
                # the backup API.  However, since conn is now closed we cannot use it.
                # The contract: caller must re-open after IndexerMigrationError.
            raise IndexerMigrationError(ver) from exc

        # --- Step 3 (success): log and advance current_version tracker ---
        log.info(
            "indexer.migration.applied",
            version=ver,
            script=script.name,
        )
        current_version = ver
