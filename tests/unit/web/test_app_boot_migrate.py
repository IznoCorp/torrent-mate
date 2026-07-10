"""Regression tests for web-boot indexer migration (fix/web-boot-migrate).

The autodeploy poller ships code + restarts but does not run indexer
migrations, and the web app opens the DB read-only per request — so a web
wave that adds a migration served ``500`` (``no such table``) on its new
endpoints until an indexer scan next opened the DB (hit on S5: migration 013
``scrape_decision``).  ``_apply_pending_indexer_migrations`` closes that gap on
every prod boot; on the read-only staging clone it must be a no-op.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from personalscraper.web.app import _apply_pending_indexer_migrations

# Latest schema version == number of NNN_*.sql migration scripts on disk.
_LATEST_VERSION = 13


def _user_version(db_path: str) -> int:
    """Return the ``PRAGMA user_version`` of the SQLite DB at *db_path*."""
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def _has_table(db_path: str, table: str) -> bool:
    """Return ``True`` when *table* exists in the DB at *db_path*."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _make_empty_db(db_path: Any) -> None:
    """Create an empty (``user_version=0``) SQLite DB file at *db_path*."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.close()


def test_prod_boot_applies_pending_migrations(test_config: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """On a prod boot, an un-migrated DB is brought to the latest schema.

    _apply_pending_indexer_migrations opens the shared indexer DB and applies
    every pending migration (bringing PRAGMA user_version to the latest and
    creating the scrape_decision table), so the decisions endpoints never 500
    with 'no such table' on a fresh prod deploy.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)  # prod role
    db_path = test_config.indexer.db_path
    _make_empty_db(db_path)
    assert _user_version(str(db_path)) == 0

    _apply_pending_indexer_migrations(test_config)

    assert _user_version(str(db_path)) == _LATEST_VERSION
    assert _has_table(str(db_path), "scrape_decision")


def test_staging_role_skips_migration(test_config: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The read-only staging clone must NOT write to the shared prod DB.

    When PERSONALSCRAPER_WEB_ROLE=staging, the boot-migration helper returns
    without touching the DB — prod and staging share one library.db (ENV-SEP)
    and the staging process must never mutate the prod-owned DB.
    """
    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
    db_path = test_config.indexer.db_path
    _make_empty_db(db_path)

    _apply_pending_indexer_migrations(test_config)

    # No migration applied — the DB is untouched at version 0.
    assert _user_version(str(db_path)) == 0
    assert not _has_table(str(db_path), "scrape_decision")


def test_absent_db_is_noop(test_config: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing indexer DB is left absent (the indexer creates it on first use)."""
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    db_path = test_config.indexer.db_path
    assert not db_path.exists()

    _apply_pending_indexer_migrations(test_config)

    # The helper must not create an empty indexer DB as a side effect.
    assert not db_path.exists()


def test_second_call_is_idempotent(test_config: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-running the boot migration on an up-to-date DB is a clean no-op."""
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    db_path = test_config.indexer.db_path
    _make_empty_db(db_path)

    _apply_pending_indexer_migrations(test_config)
    assert _user_version(str(db_path)) == _LATEST_VERSION

    # Second call: still latest, no exception, table intact.
    _apply_pending_indexer_migrations(test_config)
    assert _user_version(str(db_path)) == _LATEST_VERSION
    assert _has_table(str(db_path), "scrape_decision")
