"""Unit tests for the indexer open-DB + migrations ceremony (INDEXER-08).

Exercises :func:`personalscraper.indexer.commands._ceremony.open_indexer_db`,
the one context manager that collapses the per-command ``open_db`` +
``apply_migrations`` + five-way error-mapping + ``close`` ceremony:

- happy path yields a usable, migrated connection and closes it on exit;
- migrations are applied **exactly once** per ``with`` block;
- an open-time error (corrupt DB) echoes to stderr and raises
  :class:`IndexerCeremonyError` (parity with the pre-refactor
  ``typer.echo(str(exc), err=True); return 1``);
- a migration-time error echoes and raises :class:`IndexerCeremonyError`;
- writer-lock contention (``writer_lock_timeout`` set) surfaces as
  :class:`IndexerCeremonyError` (parity with the pre-refactor
  ``except IndexerLockError``).
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer import db as indexer_db
from personalscraper.indexer.commands._ceremony import (
    IndexerCeremonyError,
    open_indexer_db,
)


def test_yields_migrated_connection_and_creates_parent(tmp_path) -> None:
    """Happy path: parent dir created, migrations applied, conn usable."""
    # Parent dir intentionally absent — the ceremony must mkdir it.
    db_path = tmp_path / "nested" / "library.db"
    with open_indexer_db(db_path, event_bus=EventBus()) as conn:
        assert isinstance(conn, sqlite3.Connection)
        # ``media_item`` exists only after apply_migrations ran (migration 001).
        conn.execute("SELECT COUNT(*) FROM media_item").fetchone()
    assert db_path.parent.exists()


def test_connection_closed_on_exit(tmp_path) -> None:
    """The yielded connection is closed once the ``with`` block exits."""
    db_path = tmp_path / "library.db"
    with open_indexer_db(db_path, event_bus=EventBus()) as conn:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_migrations_applied_exactly_once(tmp_path) -> None:
    """``apply_migrations`` is invoked exactly once per ``with`` block."""
    db_path = tmp_path / "library.db"
    real_apply = indexer_db.apply_migrations
    # The ceremony imports ``apply_migrations`` from ``indexer.db`` at call
    # time, so patching the attribute there intercepts the single call.
    with patch.object(indexer_db, "apply_migrations", side_effect=real_apply) as spy:
        with open_indexer_db(db_path, event_bus=EventBus()) as conn:
            conn.execute("SELECT COUNT(*) FROM media_item").fetchone()
    assert spy.call_count == 1


def test_open_error_echoes_and_raises_ceremony_error(tmp_path, capsys) -> None:
    """A corrupt DB → stderr echo of the cause + ``IndexerCeremonyError``."""
    db_path = tmp_path / "library.db"
    db_path.write_text("this is not a sqlite database")

    with pytest.raises(IndexerCeremonyError) as excinfo:
        with open_indexer_db(db_path, event_bus=EventBus()):
            pass  # pragma: no cover — never entered on an open failure

    # The message was echoed to stderr (byte-identical to the pre-refactor line)
    # and is carried on ``.message`` for the tuple-returning callers.
    err = capsys.readouterr().err
    assert str(excinfo.value.message) in err
    assert excinfo.value.message  # non-empty cause


def test_migration_error_echoes_and_raises_ceremony_error(tmp_path, capsys) -> None:
    """A migration failure → stderr echo + ``IndexerCeremonyError``."""
    db_path = tmp_path / "library.db"

    def _boom(_conn, _dir):
        raise indexer_db.IndexerMigrationError(42)

    with patch.object(indexer_db, "apply_migrations", side_effect=_boom):
        with pytest.raises(IndexerCeremonyError) as excinfo:
            with open_indexer_db(db_path, event_bus=EventBus()):
                pass  # pragma: no cover — never entered on a migration failure

    # ``IndexerMigrationError(42)`` renders "Migration 042 failed; ...".
    assert "Migration 042 failed" in excinfo.value.message
    assert "Migration 042 failed" in capsys.readouterr().err


def test_writer_lock_contention_raises_ceremony_error(tmp_path, capsys) -> None:
    """A held writer lock + ``writer_lock_timeout=0`` → ``IndexerCeremonyError``."""
    db_path = tmp_path / "library.db"
    # Materialise the DB first so the lock file directory exists.
    with open_indexer_db(db_path, event_bus=EventBus()):
        pass

    # Hold the single-writer lock, then a second ceremony that requests it with a
    # zero timeout must fail-fast — the pre-refactor scan/verify commands echoed
    # the IndexerLockError and returned 1; here it surfaces as IndexerCeremonyError.
    with indexer_db.indexer_lock(db_path, timeout=0):
        with pytest.raises(IndexerCeremonyError):
            with open_indexer_db(db_path, event_bus=EventBus(), writer_lock_timeout=0):
                pass  # pragma: no cover — never entered while the lock is held

    assert capsys.readouterr().err  # the lock error was echoed to stderr
