# personalscraper/core/sqlite/_migrate.py
"""SQL migration applier — applies pending *.sql scripts in sorted order.

Event-free: no EventBus, no domain imports.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from personalscraper.core.sqlite.errors import SqliteMigrationError
from personalscraper.logger import get_logger

log = get_logger("core.sqlite.migrate")


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


def apply_migrations(
    conn: sqlite3.Connection,
    dir_: Path,
    *,
    error_factory: Callable[[int], BaseException] | None = None,
) -> None:
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
    3. **Success** — log ``core.sqlite.migration.applied`` with the version number.
    4. **Failure** — restore the DB from the snapshot (if one was taken), log
       ``core.sqlite.migration.failed``, and raise an exception
       (chained from the original exception).

    The function is idempotent: if all migrations are already applied
    (``PRAGMA user_version`` ≥ highest script number), it is a no-op.

    Args:
        conn: Open :class:`sqlite3.Connection` to the database.
        dir_: Directory that contains the ``*.sql`` migration scripts.
        error_factory: Optional callable that builds a rich exception from
            the failed migration version.  When ``None``, a bare
            :class:`SqliteMigrationError` with a human-readable message is raised.

    Raises:
        SqliteMigrationError: When a migration script fails and no
            ``error_factory`` is supplied.
        BaseException: Whatever ``error_factory(version)`` returns, when supplied.

            **Closed-connection invariant**: when this exception is raised
            because of a restore-from-snapshot, *conn* has already been
            ``.close()``-d (the snapshot is restored by overwriting the DB
            file on disk, which requires the active connection to be closed).
            Callers MUST re-open a fresh connection before issuing further
            queries; reusing the closed *conn* will raise
            ``sqlite3.ProgrammingError``.
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
            log.warning("core.sqlite.migration.skip_unparseable", file=str(script))
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
                "core.sqlite.migration.no_snapshot",
                version=ver,
                reason="in-memory database; skipping backup",
            )

        # --- Step 2: apply the script ---
        sql_text = script.read_text(encoding="utf-8")
        try:
            conn.executescript(sql_text)
        except Exception as exc:  # noqa: BLE001 — catch-all so we can restore + re-raise
            log.error(
                "core.sqlite.migration.failed",
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
                # The contract: caller must re-open after error.
            raise (
                error_factory(ver) if error_factory is not None else SqliteMigrationError(f"Migration {ver} failed")
            ) from exc

        # --- Step 3 (success): log and advance current_version tracker ---
        log.info(
            "core.sqlite.migration.applied",
            version=ver,
            script=script.name,
        )
        current_version = ver
