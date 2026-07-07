"""Regression test for migration 006 — schema_version row 3 fixup (DEV #15).

Pins the DEV #15 scenario: a DB built by an earlier buggy build of
``apply_migrations`` (which inserted rows for some migrations but not 003,
even though the 003 schema change was applied) must converge to a clean
``schema_version`` set after migration 006 lands.

Scenarios covered:

- ``test_migration_006_backfills_row_3_when_missing`` — DB with
  ``schema_version`` set to {1,2,4,5} (the production state observed in
  ``.data/library.db`` per the tech-debt audit) gets row 3 backfilled
  alongside the new row 6.
- ``test_migration_006_idempotent_on_fresh_db`` — DB built from scratch
  through migrations 001-005 already has row 3 from the 003 INSERT; 006
  must not duplicate it (``INSERT OR IGNORE`` semantics).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.indexer.db import apply_migrations

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _apply_through_migration(conn: sqlite3.Connection, up_to_version: int) -> None:
    """Apply migration scripts 001..up_to_version on *conn* manually.

    Used to simulate the buggy state where only some migrations recorded
    their schema_version row. We replay the SQL but skip the
    ``schema_version`` INSERT for row 3 to reproduce DEV #15.
    """
    scripts = sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    for script in scripts:
        version = int(script.name.split("_", 1)[0])
        if version > up_to_version:
            break
        sql = script.read_text(encoding="utf-8")
        # Filter out the schema_version row 3 INSERT to reproduce DEV #15.
        # Migration 003 uses `INSERT OR IGNORE INTO schema_version(version) VALUES (3);`
        # (no space after `schema_version`, `OR IGNORE` semantics).
        if version == 3:
            sql = sql.replace(
                "INSERT OR IGNORE INTO schema_version(version) VALUES (3);",
                "",
            )
        conn.executescript(sql)


def test_migration_006_backfills_row_3_when_missing(tmp_path: Path) -> None:
    """A DB in the DEV #15 state (rows {1,2,4,5}) gets row 3 + rows 6+7+8+9 after migrations.

    Reproduces the production state observed in the tech-debt audit, then
    runs the full ``apply_migrations`` chain (which now includes 006-009).
    The final state must be a contiguous ``schema_version`` set {1..9}
    with ``user_version=9``.
    """
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    # Phase 1 — simulate the DEV #15 buggy state by hand: apply 001..005 but
    # drop the schema_version row 3 INSERT.
    _apply_through_migration(conn, up_to_version=5)
    conn.execute("PRAGMA user_version = 5")

    # Verify we successfully reproduced the bug state.
    rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
    versions = [r[0] for r in rows]
    assert versions == [1, 2, 4, 5], f"DEV #15 state must reproduce {{1,2,4,5}}, got {versions}"

    # Phase 2 — apply migrations 006-009 via the real apply_migrations.
    apply_migrations(conn, _MIGRATIONS_DIR)

    # Phase 3 — verify backfill + new rows.
    rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
    versions = [r[0] for r in rows]
    assert versions == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], f"After 006-012, expected [1..12], got {versions}"

    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert user_version == 12, f"user_version must be 12, got {user_version}"

    conn.close()


def test_migration_006_idempotent_on_fresh_db(tmp_path: Path) -> None:
    """A DB built freshly through all migrations has contiguous schema_version rows.

    Validates the ``INSERT OR IGNORE`` semantics in migration 006: when row
    3 is already present, the migration is a no-op for that row but still
    inserts rows 6, 7, 8 (migration 008) and 9 (migration 009).
    """
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    apply_migrations(conn, _MIGRATIONS_DIR)

    rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
    versions = [r[0] for r in rows]
    assert versions == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], f"Fresh DB, expected [1..12], got {versions}"

    # Run apply_migrations a second time — must be a complete no-op.
    apply_migrations(conn, _MIGRATIONS_DIR)
    rows2 = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
    versions2 = [r[0] for r in rows2]
    assert versions == versions2, f"Re-run of apply_migrations changed rows: {versions} -> {versions2}"

    conn.close()
