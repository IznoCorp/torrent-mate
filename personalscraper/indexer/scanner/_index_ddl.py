"""Index management helpers for the scanner (drop_indexes_during_full_scan, DESIGN §11.7).

Provides:
- :func:`_capture_index_ddl` — capture CREATE INDEX statements.
- :func:`_drop_secondary_indexes` — drop non-autoindex secondary indexes.
- :func:`_recreate_indexes` — recreate indexes from captured DDL.
"""

from __future__ import annotations

import sqlite3

from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


def _capture_index_ddl(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Capture CREATE INDEX statements for ``media_file`` and ``media_stream``.

    Excludes SQLite auto-indexes (``sqlite_autoindex_*``) that are tied to
    ``UNIQUE`` constraints and cannot be recreated manually.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(index_name, create_sql)`` tuples for non-autoindex entries.
    """
    rows = conn.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'index'
          AND tbl_name IN ('media_file', 'media_stream')
          AND sql IS NOT NULL
          AND name NOT LIKE 'sqlite_autoindex_%'
        """
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _drop_secondary_indexes(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Drop all non-autoindex secondary indexes on ``media_file`` and ``media_stream``.

    Captures the DDL first, drops each index, and returns the captured DDL so
    the caller can recreate the indexes via :func:`_recreate_indexes`.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(index_name, create_sql)`` pairs that were dropped.
    """
    ddl_pairs = _capture_index_ddl(conn)
    for name, _ in ddl_pairs:
        conn.execute(f"DROP INDEX IF EXISTS {name}")
        log.debug("indexer.scan.index_dropped", index_name=name)
    return ddl_pairs


def _recreate_indexes(conn: sqlite3.Connection, ddl_pairs: list[tuple[str, str]]) -> None:
    """Recreate indexes from previously captured CREATE INDEX statements.

    The captured DDL comes verbatim from ``sqlite_master.sql``, which omits
    the ``IF NOT EXISTS`` clause. When several disk workers run the full
    scan concurrently they each drop + recreate the same set of indexes
    against the shared database; the first worker to recreate wins and the
    others raise ``index <name> already exists`` (DEV #13, C5 race in
    matrix v2.0 invariants). Injecting ``IF NOT EXISTS`` makes the
    recreate idempotent so concurrent workers cannot race each other.

    Args:
        conn: Open SQLite connection.
        ddl_pairs: List of ``(index_name, create_sql)`` tuples as returned by
            :func:`_drop_secondary_indexes`.
    """
    for name, sql in ddl_pairs:
        idempotent_sql = sql.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
        conn.execute(idempotent_sql)
        log.debug("indexer.scan.index_recreated", index_name=name)
