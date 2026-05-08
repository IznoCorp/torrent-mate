"""Design-contract tests for the media indexer (codename: ``indexer``).

Pin points for ``docs/reference/indexer.md`` — schema versioning contract.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.indexer.db import apply_migrations, open_db

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


class TestIndexerSchemaContract:
    """Schema versioning — DESIGN indexer.md §Schema Overview."""

    def test_each_migration_registers_in_schema_version_table(self, tmp_path: Path) -> None:
        """Every migration inserts a row into the ``schema_version`` audit table.

        Design: docs/reference/indexer.md#schema-overview
        Contract: Each migration script that bumps ``PRAGMA user_version``
        must also insert a row into the ``schema_version`` table so
        ``library-status`` and downgrade tooling can reason about the
        migration chain. A migration that forgets this insertion is a bug
        (regression captured in fc7d16c).
        """
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path)
        apply_migrations(conn, _MIGRATIONS_DIR)

        rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        recorded_versions = [r[0] for r in rows]

        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert user_version > 0
        for v in range(1, user_version + 1):
            assert v in recorded_versions, f"migration {v} did not record in schema_version"
