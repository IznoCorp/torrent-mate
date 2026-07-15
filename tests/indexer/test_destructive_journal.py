"""Unit tests for the §7 append-only destructive-op journal (Star City)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import personalscraper.indexer.migrations as _migrations_pkg
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.destructive_journal import (
    OP_DELETE,
    OP_OVERWRITE,
    list_recent,
    record_destruction,
)


def _db(tmp_path: Path) -> Path:
    """Create a migrated library.db and return its path."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    apply_migrations(conn, Path(_migrations_pkg.__file__).parent)
    conn.close()
    return db_path


def test_record_and_list_round_trip(tmp_path: Path) -> None:
    """A recorded op is readable back, newest first."""
    db_path = _db(tmp_path)
    record_destruction(
        db_path, op=OP_OVERWRITE, path="/disk/Ferrari (2023)", actor="dispatch", detail="REPLACE film", run_uid="r1"
    )
    record_destruction(db_path, op=OP_DELETE, path="/disk/.actors", actor="disk-clean", detail="Nettoyage")

    rows = list_recent(db_path)
    assert len(rows) == 2
    # Newest first.
    assert rows[0]["op"] == OP_DELETE
    assert rows[0]["actor"] == "disk-clean"
    assert rows[1]["op"] == OP_OVERWRITE
    assert rows[1]["path"] == "/disk/Ferrari (2023)"
    assert rows[1]["run_uid"] == "r1"


def test_record_is_fail_soft_on_missing_table(tmp_path: Path) -> None:
    """A DB without the table never raises — the destruction it records must proceed."""
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()
    # Must not raise.
    record_destruction(db_path, op=OP_DELETE, path="/x", actor="dispatch")
    assert list_recent(db_path) == []


def test_append_only_accumulates(tmp_path: Path) -> None:
    """Every record adds a row — nothing is overwritten (append-only)."""
    db_path = _db(tmp_path)
    for i in range(5):
        record_destruction(db_path, op=OP_DELETE, path=f"/disk/item{i}", actor="disk-clean")
    assert len(list_recent(db_path)) == 5
