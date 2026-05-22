"""Tests for ``personalscraper.indexer.scanner._index_ddl``.

Covers:

- :func:`_capture_index_ddl` — captures only secondary indexes on the two
  tables of interest, excluding ``sqlite_autoindex_*``.
- :func:`_drop_secondary_indexes` — drops every captured index and returns
  the DDL for recreation.
- :func:`_recreate_indexes` — recreates indexes idempotently so concurrent
  disk workers cannot race each other (DEV #13).
"""

from __future__ import annotations

import sqlite3

import pytest

from personalscraper.indexer.scanner._index_ddl import (
    _capture_index_ddl,
    _drop_secondary_indexes,
    _recreate_indexes,
)


def _seed_schema(conn: sqlite3.Connection) -> None:
    """Create the minimal subset of tables + indexes used by the helpers.

    Mirrors the columns and indexes captured from production
    ``library.db`` for ``media_file`` and ``media_stream``.
    """
    conn.executescript(
        """
        CREATE TABLE media_file (
          id INTEGER PRIMARY KEY,
          oshash TEXT,
          release_id INTEGER,
          scan_generation INTEGER,
          enriched_at INTEGER,
          deleted_at INTEGER
        );
        CREATE TABLE media_stream (
          id INTEGER PRIMARY KEY,
          file_id INTEGER,
          kind TEXT,
          codec TEXT,
          lang TEXT
        );
        CREATE INDEX idx_file_oshash ON media_file(oshash);
        CREATE INDEX idx_file_release ON media_file(release_id);
        CREATE INDEX idx_file_scan_gen ON media_file(scan_generation);
        CREATE INDEX idx_file_deleted ON media_file(deleted_at) WHERE deleted_at IS NOT NULL;
        CREATE INDEX idx_file_enrich_pending ON media_file(enriched_at)
            WHERE enriched_at IS NULL AND deleted_at IS NULL;
        CREATE INDEX idx_stream_kind_codec ON media_stream(kind, codec);
        CREATE INDEX idx_stream_lang ON media_stream(lang);
        """
    )


@pytest.fixture
def conn(tmp_path):
    """Return a fresh in-memory connection seeded with the schema."""
    c = sqlite3.connect(":memory:")
    _seed_schema(c)
    yield c
    c.close()


class TestCaptureIndexDdl:
    """Tests for :func:`_capture_index_ddl`."""

    def test_returns_all_seven_secondary_indexes(self, conn: sqlite3.Connection) -> None:
        """All seven secondary indexes on the two tables are captured."""
        pairs = _capture_index_ddl(conn)
        names = {name for name, _ in pairs}
        assert names == {
            "idx_file_oshash",
            "idx_file_release",
            "idx_file_scan_gen",
            "idx_file_deleted",
            "idx_file_enrich_pending",
            "idx_stream_kind_codec",
            "idx_stream_lang",
        }

    def test_excludes_sqlite_autoindex(self, conn: sqlite3.Connection) -> None:
        """Auto-indexes (UNIQUE constraint indexes) are not captured."""
        conn.execute("CREATE TABLE media_file_uniq (uuid TEXT UNIQUE)")
        # The auto-index lives on table media_file_uniq, not our two tables —
        # also guarded by the WHERE name NOT LIKE 'sqlite_autoindex_%' clause.
        pairs = _capture_index_ddl(conn)
        names = {name for name, _ in pairs}
        assert not any(n.startswith("sqlite_autoindex_") for n in names)


class TestDropSecondaryIndexes:
    """Tests for :func:`_drop_secondary_indexes`."""

    def test_drops_every_secondary_index(self, conn: sqlite3.Connection) -> None:
        """After drop, ``sqlite_master`` no longer lists the secondary indexes."""
        ddl_pairs = _drop_secondary_indexes(conn)
        assert len(ddl_pairs) == 7
        remaining = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex_%'"
        ).fetchall()
        assert remaining == [], "All secondary indexes must be dropped"

    def test_drop_is_idempotent(self, conn: sqlite3.Connection) -> None:
        """A second drop call after the first succeeds (returns empty)."""
        _drop_secondary_indexes(conn)
        second = _drop_secondary_indexes(conn)
        assert second == [], "Second drop on an empty set yields no DDL"


class TestRecreateIndexesC5Race:
    """Tests for :func:`_recreate_indexes` — DEV #13 idempotence (C5 race)."""

    def test_recreate_once_restores_all_indexes(self, conn: sqlite3.Connection) -> None:
        """One recreate restores the captured indexes."""
        ddl_pairs = _drop_secondary_indexes(conn)
        _recreate_indexes(conn, ddl_pairs)
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex_%'"
            ).fetchall()
        }
        assert names == {name for name, _ in ddl_pairs}

    def test_recreate_twice_does_not_raise(self, conn: sqlite3.Connection) -> None:
        """Calling recreate twice on the same DDL is idempotent (DEV #13 regression).

        Reproduces the C5 race: concurrent disk workers each captured the
        same DDL, dropped it, ran their inserts, and then recreated it.
        Before the fix the second worker raised
        ``index idx_stream_kind_codec already exists``; the
        ``IF NOT EXISTS`` injection makes the second call a no-op.
        """
        ddl_pairs = _drop_secondary_indexes(conn)
        _recreate_indexes(conn, ddl_pairs)
        # Second call: previously raised sqlite3.OperationalError.
        _recreate_indexes(conn, ddl_pairs)

    def test_recreate_preserves_partial_index_clauses(self, conn: sqlite3.Connection) -> None:
        """Partial indexes (``WHERE …``) round-trip through capture+recreate."""
        ddl_pairs = _drop_secondary_indexes(conn)
        _recreate_indexes(conn, ddl_pairs)
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='idx_file_deleted'").fetchone()[0]
        assert "WHERE deleted_at IS NOT NULL" in sql
