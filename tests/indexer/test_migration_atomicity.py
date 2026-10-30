"""Each indexer migration script is atomic: a crash mid-script leaves ``library.db`` as before it.

``executescript`` auto-commits every statement that runs outside an explicit transaction, so a
script without one, interrupted between two statements, leaves a half-applied schema behind.
The next open then snapshots that broken state into the pre-migration ``.bak``, the retry fails
on what is already there, and the restore puts the broken state back.

The crash is simulated by a failing statement injected just before the script's version bump:
the script raises there, and the connection is closed without a ``COMMIT`` — what a killed
process leaves for SQLite to roll back on the next open.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations, open_db

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_SCRIPTS = sorted(MIGRATIONS_DIR.glob("*.sql"))


def _version(script: Path) -> int:
    """Return the version a migration script brings the store to.

    Args:
        script: A migration script named ``NNN_*.sql``.

    Returns:
        Its leading number.
    """
    return int(script.name.split("_")[0])


def _schema(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    """Return the store's schema as sorted ``(type, name, sql)`` rows.

    Args:
        conn: An open connection.

    Returns:
        Every non-internal ``sqlite_master`` row.
    """
    return conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()


def _user_version(conn: sqlite3.Connection) -> int:
    """Return the store's ``PRAGMA user_version``.

    Args:
        conn: An open connection.

    Returns:
        The schema version in the header.
    """
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return the row count of every table, so a data-only script's half-write shows.

    Args:
        conn: An open connection.

    Returns:
        Table name → its number of rows.
    """
    tables = [
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
    ]
    return {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in tables}


def _store_before(script: Path, tmp_path: Path) -> Path:
    """Build a ``library.db`` migrated up to the version just before *script*.

    Args:
        script: The migration under test.
        tmp_path: The test's temporary directory.

    Returns:
        The store's path, closed.
    """
    earlier = tmp_path / "earlier"
    earlier.mkdir()
    for previous in _SCRIPTS:
        if _version(previous) < _version(script):
            shutil.copy(previous, earlier / previous.name)
    db_path = tmp_path / "library.db"
    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, earlier)
    conn.close()
    return db_path


def _crash_mid_script(db_path: Path, script: Path) -> None:
    """Run *script* until a failing statement just before its version bump, then drop the connection.

    Args:
        db_path: The store.
        script: The migration to interrupt.
    """
    sql = script.read_text(encoding="utf-8")
    bump = f"PRAGMA user_version = {_version(script)};"
    assert sql.count(bump) == 1, f"{script.name}: expected exactly one {bump!r}"
    crashing = sql.replace(bump, f"INSERT INTO crash_injected_here VALUES (1);\n{bump}")
    conn = open_db(db_path, event_bus=EventBus())
    with pytest.raises(sqlite3.OperationalError, match="crash_injected_here"):
        conn.executescript(crashing)
    # No COMMIT, no ROLLBACK: the process is gone; SQLite rolls back what was not committed.
    conn.close()


@pytest.mark.parametrize("script", _SCRIPTS, ids=[script.name for script in _SCRIPTS])
def test_a_crash_mid_script_leaves_the_store_as_before(script: Path, tmp_path: Path) -> None:
    """After a crash inside a script, schema, rows and ``user_version`` are those before the script.

    Args:
        script: An indexer migration script.
        tmp_path: The test's temporary directory.
    """
    db_path = _store_before(script, tmp_path)
    with sqlite3.connect(db_path) as conn:
        schema_before, version_before, rows_before = _schema(conn), _user_version(conn), _row_counts(conn)
    conn.close()

    _crash_mid_script(db_path, script)

    with sqlite3.connect(db_path) as conn:
        assert _user_version(conn) == version_before
        assert _schema(conn) == schema_before
        assert _row_counts(conn) == rows_before
    conn.close()


def test_the_retry_after_a_crash_migrates_and_snapshots_the_state_before_it(tmp_path: Path) -> None:
    """A crash inside 017, then the next open: 017 applies, and its ``.bak`` is the clean 016.

    Before every script ran in one transaction, the crash left 017's first ``ADD COLUMN``
    committed; the retry snapshotted that half-applied store, failed on the duplicate column
    and restored the half-applied store.

    Args:
        tmp_path: The test's temporary directory.
    """
    script = MIGRATIONS_DIR / "017_item_facts.sql"
    db_path = _store_before(script, tmp_path)
    with sqlite3.connect(db_path) as conn:
        schema_before = _schema(conn)
    conn.close()
    _crash_mid_script(db_path, script)

    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, MIGRATIONS_DIR)

    assert _user_version(conn) == 17
    conn.close()
    with sqlite3.connect(db_path.parent / "library.db.pre-migration-17.bak") as bak:
        assert _user_version(bak) == 16
        assert _schema(bak) == schema_before
    bak.close()
