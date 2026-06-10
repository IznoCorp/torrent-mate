# personalscraper/core/sqlite/_open.py
"""Event-free ``open_db`` for core SQLite connections (SSOT).

No ``event_bus`` parameter, no EventBus import, no domain imports.  This is the
neutral connection-opening machinery shared by ``indexer/`` and ``acquire/``.

The body mirrors the historical ``indexer.db.open_db`` (macFUSE-NTFS rejection,
pre-open free-space guard, corruption quarantine, FK-orphan pre-check) but is
fully event-free: it emits no events and raises only the bare ``Sqlite*Error``
markers — UNLESS the caller supplies an :class:`OpenDbErrorFactories` instance,
in which case each failure path delegates to the matching factory so a richer,
attribute-bearing exception (e.g. ``IndexerCorruptError``) is raised through this
code path.

``indexer/db.py`` wraps this function to add the required ``event_bus``
parameter and the ``DiskFullWarning`` emission (via ``check_free_space``), and
passes a module-level :class:`OpenDbErrorFactories` wiring its four rich
constructors.

Import direction: this module imports only stdlib + sibling ``core.sqlite``
modules + ``personalscraper.logger`` — never from ``personalscraper.indexer``,
``personalscraper.events``, or ``personalscraper.core.event_bus``.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from personalscraper.core.sqlite._fs_probe import probe_mount
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
)
from personalscraper.logger import get_logger

log = get_logger("core.sqlite.open")

# Signals produced by SQLite when the file is corrupt or not a valid DB at all.
_CORRUPT_SIGNALS = ("malformed", "file is not a database", "not a database")


@dataclass(frozen=True)
class OpenDbErrorFactories:
    """Optional factories that turn bare core failures into rich exceptions.

    Each field is a callable that builds a domain-specific exception from the
    same arguments the bare ``Sqlite*Error`` would carry.  When a field is
    ``None`` (the default), the corresponding failure raises the bare core
    marker instead.

    This generalises the ``error_factory`` pattern already used by
    :func:`personalscraper.core.sqlite._lock.db_lock` and
    :func:`personalscraper.core.sqlite._migrate.apply_migrations`, letting the
    indexer wrapper preserve its attribute-bearing ``Indexer*Error`` subclasses
    (``.quarantine_path``, ``.mount_point``, ``.free_bytes``, ``.orphan_count``,
    …) while the core body stays event-free and domain-agnostic.

    Attributes:
        invalid_path: ``(db_path, mount_point) -> BaseException`` — built when
            *db_path* resolves to a macFUSE-NTFS mount.
        corrupt: ``(db_path, quarantine_path) -> BaseException`` — built when the
            existing DB is malformed and has been quarantined.
        disk_full: ``(path, free_bytes, required_bytes) -> BaseException`` —
            built when the pre-open free-space guard fails.
        fk_orphans: ``(db_path, orphan_count, sample) -> BaseException`` — built
            when ``PRAGMA foreign_key_check`` reports orphan rows.
    """

    invalid_path: Callable[[Path, str], BaseException] | None = None
    corrupt: Callable[[Path, Path], BaseException] | None = None
    disk_full: Callable[[Path, int, int], BaseException] | None = None
    fk_orphans: Callable[[Path, int, list[tuple[object, ...]]], BaseException] | None = None


def _find_ntfs_mount(path: Path) -> str | None:
    """Return the macFUSE-NTFS mount point that contains *path*, or ``None``.

    Delegates to :func:`personalscraper.core.sqlite._fs_probe.probe_mount`
    (a single cached ``mount`` shell-out, 10s timeout).

    Args:
        path: Filesystem path to check.

    Returns:
        The matching mount-point string, or ``None`` if the path is not on a
        macFUSE-NTFS volume.
    """
    info = probe_mount(str(path.resolve()))
    if info is None:
        return None
    return info.mount_point if info.fs_type == "ntfs_macfuse" else None


def open_db(
    path: Path,
    expected_growth_bytes: int = 0,
    *,
    rebuild: bool = False,
    allow_fk_orphans: bool = False,
    errors: OpenDbErrorFactories | None = None,
) -> sqlite3.Connection:
    """Open (or create) a SQLite database at *path*, applying the canonical PRAGMAs.

    Event-free: emits no events.  Failures raise the bare ``Sqlite*Error``
    markers unless *errors* supplies a matching factory, in which case the rich
    exception built by that factory is raised instead.

    Applies the PRAGMAs from DESIGN §6.1 (WAL, ``synchronous=NORMAL``,
    ``temp_store=MEMORY``, ``cache_size=-65536``, ``mmap_size=268435456``,
    ``wal_autocheckpoint=1000``, ``busy_timeout=5000``, ``foreign_keys=ON``).

    Pre-open checks (in order):
    1. Reject *path* on a macFUSE-NTFS mount.
    2. If ``expected_growth_bytes > 0``, verify free space inline (statvfs,
       ``free >= 2 × expected_growth_bytes``).
    3. Detect a corrupt DB, quarantine it to ``<path>.corrupt-<unix_ts>`` and
       raise — unless *rebuild* is ``True``, in which case the quarantine still
       happens but a fresh DB is opened.
    4. After opening, run ``PRAGMA foreign_key_check``; orphans raise (or, with
       *allow_fk_orphans*, are logged as a WARNING and the connection returned).

    Args:
        path: Filesystem path of the SQLite database.
        expected_growth_bytes: Estimated write volume for the session.  When
            non-zero, free space is verified before opening.
        rebuild: When ``True``, a corrupt existing DB is quarantined and a fresh
            empty DB is created.  When ``False`` (default), corruption raises.
        allow_fk_orphans: When ``True``, foreign-key orphans are logged as a
            WARNING and the connection is returned instead of raising.
        errors: Optional :class:`OpenDbErrorFactories` wiring rich exception
            constructors.  When ``None``, bare ``Sqlite*Error`` markers are
            raised.

    Returns:
        An open :class:`sqlite3.Connection` with all PRAGMAs applied.

    Raises:
        SqliteInvalidPathError: If *path* is on a macFUSE-NTFS volume and no
            ``errors.invalid_path`` factory is supplied.
        SqliteDiskFullError: If free space < 2 × *expected_growth_bytes* and no
            ``errors.disk_full`` factory is supplied.
        SqliteCorruptError: If the existing DB is malformed, *rebuild* is False,
            and no ``errors.corrupt`` factory is supplied.
        SqliteFKOrphansError: If FK orphans are found, *allow_fk_orphans* is
            False, and no ``errors.fk_orphans`` factory is supplied.
        BaseException: Whatever the matching factory in *errors* returns, when
            supplied.
    """
    factories = errors if errors is not None else OpenDbErrorFactories()

    # --- macFUSE-NTFS check (defense-in-depth; the conf validator catches most) ---
    ntfs_mount = _find_ntfs_mount(path)
    if ntfs_mount is not None:
        raise (
            factories.invalid_path(path, ntfs_mount)
            if factories.invalid_path is not None
            else SqliteInvalidPathError(f"db_path {path} is on a macFUSE/NTFS mount ({ntfs_mount}).")
        )

    # --- Pre-open free-space guard (inlined, event-free) ---
    if expected_growth_bytes > 0:
        stat = os.statvfs(path.parent)
        free_bytes = stat.f_frsize * stat.f_bavail
        required_bytes = 2 * expected_growth_bytes
        if free_bytes < required_bytes:
            raise (
                factories.disk_full(path, free_bytes, required_bytes)
                if factories.disk_full is not None
                else SqliteDiskFullError(
                    f"Insufficient free space at {path.parent}: {free_bytes} bytes available, "
                    f"{required_bytes} bytes required."
                )
            )

    # --- Corruption check + quarantine ---
    # When rebuild=True and the DB was corrupt, _quarantine_if_corrupt renames the
    # file aside (returning the quarantine path, intentionally unused here) so the
    # connect below creates a fresh DB at *path*.  When the DB is healthy it
    # returns None and *path* is left untouched.
    if path.exists():
        _quarantine_if_corrupt(path, rebuild=rebuild, factories=factories)

    # --- Open and configure ---
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    apply_pragmas(conn)

    # --- FK orphan pre-check (DEV #19) ---
    # PRAGMA foreign_key_check scans every FK constraint and reports rows
    # referencing non-existent parents.  It works regardless of whether
    # foreign_keys is ON or OFF on this connection (apply_pragmas already enabled
    # it).  Orphans created by a script bypassing open_db (raw sqlite3.connect,
    # sqlite3 CLI) stay silently invisible until a write triggers a FK error far
    # from the source — surfacing them here provides a clear diagnostic.
    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    if orphans:
        sample = [tuple(row) for row in orphans[:5]]
        if allow_fk_orphans:
            # Opt-in tolerant mode (DEV #3): the FK-orphan cleanup path needs to
            # open a dirty DB to repair it. Warn loudly but return the connection.
            log.warning(
                "core.sqlite.open.foreign_key_orphans_tolerated",
                db_path=str(path),
                count=len(orphans),
                sample=sample,
            )
            return conn
        log.error(
            "core.sqlite.open.foreign_key_orphans",
            db_path=str(path),
            count=len(orphans),
            sample=sample,
        )
        conn.close()
        raise (
            factories.fk_orphans(path, len(orphans), sample)
            if factories.fk_orphans is not None
            else SqliteFKOrphansError(f"Database at {path} has {len(orphans)} foreign-key orphan(s). Sample: {sample}")
        )

    return conn


def _quarantine_if_corrupt(
    path: Path,
    *,
    rebuild: bool,
    factories: OpenDbErrorFactories,
) -> Path | None:
    """Detect a corrupt DB at *path*, quarantine it, and raise unless *rebuild*.

    Opens a throwaway probe connection, applies the canonical PRAGMAs, and runs
    ``PRAGMA integrity_check``.  Two failure shapes are handled:

    * The connection / PRAGMA raises ``sqlite3.DatabaseError`` carrying a
      corruption signal (``malformed`` / ``file is not a database``).
    * ``integrity_check`` returns a non-``ok`` string (subtle B-tree / index
      damage that does not raise — checking the RESULT, not just whether it
      raises, is required: SH-9 / BD-L).

    On detection the file is renamed to ``<path>.corrupt-<unix_ts>``.  When
    *rebuild* is ``False`` the matching exception is raised; when ``True`` the
    quarantine path is returned so the caller creates a fresh DB.

    Args:
        path: Path of an existing DB file to probe.
        rebuild: When ``True``, return the quarantine path instead of raising.
        factories: Factory bundle; ``factories.corrupt`` builds the rich
            exception when supplied.

    Returns:
        The quarantine :class:`~pathlib.Path` when corruption was detected and
        *rebuild* is ``True``; ``None`` when the DB is healthy.

    Raises:
        SqliteCorruptError: When the DB is corrupt, *rebuild* is False, and no
            ``factories.corrupt`` factory is supplied.
        BaseException: Whatever ``factories.corrupt(path, quarantine_path)``
            returns, when supplied.
    """
    try:
        probe = sqlite3.connect(str(path))
        apply_pragmas(probe)
        try:
            ic_row = probe.execute("PRAGMA integrity_check").fetchone()
            ic_result = ic_row[0] if ic_row else "unknown"
        finally:
            probe.close()
    except sqlite3.DatabaseError as exc:
        if any(signal in str(exc).lower() for signal in _CORRUPT_SIGNALS):
            quarantine_path = _quarantine_file(path)
            log.error(
                "core.sqlite.open.corrupt",
                original=str(path),
                quarantine=str(quarantine_path),
            )
            if not rebuild:
                raise (
                    factories.corrupt(path, quarantine_path)
                    if factories.corrupt is not None
                    else SqliteCorruptError(f"Database at {path} is corrupt; quarantined to {quarantine_path}.")
                ) from exc
            return quarantine_path
        raise

    if ic_result != "ok":
        quarantine_path = _quarantine_file(path)
        log.error(
            "core.sqlite.open.integrity_check_failed",
            original=str(path),
            quarantine=str(quarantine_path),
            result=ic_result,
        )
        if not rebuild:
            raise (
                factories.corrupt(path, quarantine_path)
                if factories.corrupt is not None
                else SqliteCorruptError(f"Database at {path} is corrupt; quarantined to {quarantine_path}.")
            )
        return quarantine_path

    return None


def _quarantine_file(path: Path) -> Path:
    """Rename *path* to a timestamped ``.corrupt-<unix_ts>`` sibling and return it.

    Args:
        path: The corrupt DB file to move aside.

    Returns:
        The :class:`~pathlib.Path` the file was renamed to.
    """
    ts = int(time.time())
    quarantine_path = path.parent / f"{path.name}.corrupt-{ts}"
    path.rename(quarantine_path)
    return quarantine_path
