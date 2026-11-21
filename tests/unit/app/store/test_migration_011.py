"""Unit tests for ``011_run_request_kind.sql`` — the ``run_request`` kind widened to ``acquisition``.

SQLite cannot alter a ``CHECK``, so the migration rebuilds the table: every row of a 010 store
must come out identical (each column), the ``run_request_state_asked`` index must exist again,
and ``user_version`` must read 11. A row of kind ``acquisition`` is accepted after the migration
(refused before it) and an unknown kind is still refused.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.store.store import _MIGRATIONS_DIR
from personalscraper.core.sqlite import apply_migrations, open_db

_COLUMNS = (
    "uid, kind, trigger, options_json, asked_by, asked_at, state, admitted_at, worker_pid,"
    " heartbeat_at, settled_at, settlement, wait_reason"
)
_INSERT = f"INSERT INTO run_request ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"  # noqa: S608 — fixed names

# One row per state: queued, running (admitted, a worker, a heartbeat, a wait reason) and settled.
_ROWS = [
    (
        "uid-queued",
        "pipeline",
        "manual",
        '{"steps": ["ingest"]}',
        "alice",
        100.0,
        "queued",
        None,
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "uid-running",
        "rescrape",
        "schedule",
        "{}",
        "system",
        200.5,
        "running",
        201.0,
        4242,
        230.25,
        None,
        None,
        "disk busy",
    ),
    (
        "uid-settled",
        "pipeline",
        "manual",
        '{"dry_run": true}',
        "bob",
        300.0,
        "settled",
        301.0,
        99,
        320.0,
        340.75,
        "success",
        None,
    ),
]


def _migrated_to(tmp_path: Path, version: int) -> sqlite3.Connection:
    """Build an ``app.db`` migrated up to *version* only, with the shipped scripts.

    Args:
        tmp_path: The test's temporary directory.
        version: The last migration to apply.

    Returns:
        An open connection with the canonical PRAGMAs; the caller closes it.
    """
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if int(script.stem.split("_")[0]) <= version:
            shutil.copy(script, scripts / script.name)
    conn = open_db(tmp_path / "app.db")
    apply_migrations(conn, scripts)
    return conn


def _apply_011(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Apply the shipped scripts past the file's current version (``011`` only).

    Args:
        conn: The connection of a 010 store.
        tmp_path: The test's temporary directory.
    """
    scripts = tmp_path / "scripts"
    for script in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        shutil.copy(script, scripts / script.name)
    apply_migrations(conn, scripts)


@pytest.fixture
def store_010(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A 010 store holding a queued, a running and a settled request.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The open connection.
    """
    conn = _migrated_to(tmp_path, 10)
    conn.executemany(_INSERT, _ROWS)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def _storage_classes(conn: sqlite3.Connection) -> list[tuple[str, ...]]:
    """Read the SQLite storage class of every column of every ``run_request`` row.

    Args:
        conn: The connection of the store.

    Returns:
        One tuple of ``typeof()`` names per row, ordered by ``asked_at``.
    """
    typeofs = ", ".join(f"typeof({column})" for column in _COLUMNS.split(", "))
    rows = conn.execute(f"SELECT {typeofs} FROM run_request ORDER BY asked_at").fetchall()  # noqa: S608 — fixed names
    return [tuple(row) for row in rows]


def _acquisition_row(uid: str, kind: str = "acquisition") -> tuple[object, ...]:
    """Build a queued request of *kind*.

    Args:
        uid: The request's uid.
        kind: The request's kind.

    Returns:
        The values of one ``run_request`` row.
    """
    return (uid, kind, "manual", "{}", "alice", 400.0, "queued", None, None, None, None, None, None)


def test_the_kind_acquisition_is_refused_before_the_migration(store_010: sqlite3.Connection) -> None:
    """A 010 store accepts only ``pipeline`` and ``rescrape``."""
    assert store_010.execute("PRAGMA user_version").fetchone()[0] == 10
    with pytest.raises(sqlite3.IntegrityError):
        store_010.execute(_INSERT, _acquisition_row("uid-acq"))


def test_every_row_is_identical_after_the_migration(store_010: sqlite3.Connection, tmp_path: Path) -> None:
    """Each column of the queued, the running and the settled row survives the rebuild."""
    types_before = _storage_classes(store_010)
    _apply_011(store_010, tmp_path)

    rows = store_010.execute(f"SELECT {_COLUMNS} FROM run_request ORDER BY asked_at").fetchall()  # noqa: S608 — fixed names
    assert [tuple(row) for row in rows] == _ROWS
    # ``100 == 100.0`` in Python: the storage class of each value is compared too, so a column
    # whose declared type (and so affinity) changed in the rebuild cannot hide behind equality.
    assert _storage_classes(store_010) == types_before


def test_the_columns_are_unchanged_by_the_migration(store_010: sqlite3.Connection, tmp_path: Path) -> None:
    """Name, declared type, NOT NULL, default and primary key of every column are as 010 left them."""
    columns_before = store_010.execute("PRAGMA table_info(run_request)").fetchall()
    _apply_011(store_010, tmp_path)

    assert store_010.execute("PRAGMA table_info(run_request)").fetchall() == columns_before


def test_the_state_index_exists_and_user_version_reads_eleven(store_010: sqlite3.Connection, tmp_path: Path) -> None:
    """The index is recreated on ``(state, asked_at)``; the version commits with the rebuild."""
    _apply_011(store_010, tmp_path)

    assert store_010.execute("PRAGMA user_version").fetchone()[0] == 11
    index = store_010.execute("PRAGMA index_info(run_request_state_asked)").fetchall()
    assert [row[2] for row in index] == ["state", "asked_at"]
    assert store_010.execute("SELECT 1 FROM sqlite_master WHERE name = 'run_request_new'").fetchone() is None


def test_the_kind_acquisition_is_accepted_after_the_migration(store_010: sqlite3.Connection, tmp_path: Path) -> None:
    """The widened ``CHECK`` takes ``acquisition`` and keeps the two older kinds."""
    _apply_011(store_010, tmp_path)

    store_010.execute(_INSERT, _acquisition_row("uid-acq"))
    kinds = {row[0] for row in store_010.execute("SELECT kind FROM run_request")}
    assert kinds == {"pipeline", "rescrape", "acquisition"}


def test_an_unknown_kind_is_still_refused_after_the_migration(store_010: sqlite3.Connection, tmp_path: Path) -> None:
    """The ``CHECK`` stays a closed list."""
    _apply_011(store_010, tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        store_010.execute(_INSERT, _acquisition_row("uid-bad", kind="unknown"))


def test_the_other_constraints_are_unchanged(store_010: sqlite3.Connection, tmp_path: Path) -> None:
    """The state and settlement lists and the primary key survive the rebuild."""
    _apply_011(store_010, tmp_path)

    bad_state = ("uid-s", "pipeline", "manual", "{}", "alice", 1.0, "paused", None, None, None, None, None, None)
    bad_settlement = ("uid-t", "pipeline", "manual", "{}", "alice", 1.0, "settled", None, None, None, 2.0, "lost", None)
    for row in (bad_state, bad_settlement, _ROWS[0]):
        with pytest.raises(sqlite3.IntegrityError):
            store_010.execute(_INSERT, row)
