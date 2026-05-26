"""open_db PRAGMA integrity_check result validation (Phase 1.6 / SH-9 / BD-L).

Background — the pre-Phase-1.6 ``open_db()`` ran ``PRAGMA integrity_check``
inside the corruption pre-probe but **discarded the result row**: only an
exception raised by the PRAGMA itself would be caught (and only signals like
``"malformed"`` would trigger quarantine). Subtle corruption — B-tree page
damage, index inconsistency, page-level checksum mismatch — typically returns
a non-``"ok"`` string from integrity_check **without raising**, so it slipped
through silently.

Phase 1.6 adds: if ``integrity_check`` returns anything other than ``"ok"``,
the file is quarantined (same pattern as the DatabaseError branch) and
``IndexerCorruptError`` is raised unless ``rebuild=True``.

Tests in this file:

- ``test_open_db_quarantines_on_non_ok_integrity_check`` — when ``integrity_check``
  returns a non-``"ok"`` string, the file is renamed to ``.corrupt-{ts}`` and
  ``IndexerCorruptError`` is raised.
- ``test_open_db_rebuild_skips_quarantine_raise_on_integrity_failure`` — with
  ``rebuild=True``, the failure still quarantines (audit) but the open
  proceeds with a fresh DB instead of raising.
- ``test_open_db_succeeds_when_integrity_check_returns_ok`` — happy path
  preservation : a clean DB returns ``"ok"`` and open_db proceeds normally.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import (
    IndexerCorruptError,
    apply_migrations,
    open_db,
)

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _bootstrap_db(db_path: Path) -> None:
    """Create a valid migrated DB at *db_path*."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    conn.close()


def test_open_db_succeeds_when_integrity_check_returns_ok(tmp_path: Path) -> None:
    """Happy path: a clean migrated DB returns 'ok' and open_db proceeds.

    Baseline pin — adding the result check must not break the normal flow.
    """
    db_path = tmp_path / "library.db"
    _bootstrap_db(db_path)

    conn = open_db(db_path, event_bus=EventBus())
    try:
        # Direct re-check confirms the assumption that the migrated DB is healthy
        ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert ic == "ok", f"Expected 'ok', got {ic!r}"
    finally:
        conn.close()


class _SpoofedConnection(sqlite3.Connection):
    """Connection subclass that spoofs ``PRAGMA integrity_check`` result.

    Subclassing is the supported pattern for sqlite3 connection customization
    (the ``factory`` parameter to ``sqlite3.connect``). Direct method patching
    on a Connection instance fails because ``sqlite3.Connection`` is an
    immutable C type.

    The spoofed result is read from the class attribute ``_spoof_value`` so
    different tests can inject different values without redefining the class.
    """

    _spoof_value: str = "ok"

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        cursor = super().execute(sql, *args, **kwargs)
        if sql.strip().upper().startswith("PRAGMA INTEGRITY_CHECK"):
            spoofed = self._spoof_value

            class _SpoofedCursor:
                def fetchone(self_inner):
                    return (spoofed,)

                def fetchall(self_inner):
                    return [(spoofed,)]

            return _SpoofedCursor()
        return cursor


def _open_with_spoofed_integrity(db_path: Path, spoof_value: str) -> None:
    """Patch sqlite3.connect to use _SpoofedConnection with the given spoof value.

    Patches the symbol as referenced from the module under test —
    ``personalscraper.indexer.db.sqlite3.connect`` — so open_db's probe call
    routes through the spoofed Connection class. Releases the patch via
    contextmanager pattern (caller wraps in with-block via the helper).
    """
    raise NotImplementedError("use the patch fixture directly in tests below")


def test_open_db_quarantines_on_non_ok_integrity_check(tmp_path: Path) -> None:
    """A non-'ok' integrity_check result triggers quarantine + IndexerCorruptError.

    Pre-Phase-1.6, the probe ran integrity_check but discarded the result —
    only an exception would trigger quarantine. Subtle corruptions returning
    non-``"ok"`` strings (B-tree page damage, index inconsistency, freelist
    drift) slipped through. This test uses a Connection subclass that spoofs
    integrity_check's return so we can exercise the new result-check branch
    without having to engineer a real binary corruption that produces a
    non-throw + non-ok signal (very few patterns do — most either parse
    cleanly or throw on connect).
    """
    db_path = tmp_path / "library.db"
    _bootstrap_db(db_path)

    _SpoofedConnection._spoof_value = "* btree page 7 is broken"

    # Patch the sqlite3.connect symbol the module imports, so open_db's
    # probe uses our subclass via factory= argument.
    real_connect = sqlite3.connect

    def patched_connect(database, *args, **kwargs):
        # Only spoof the probe (no factory passed by the production code).
        # The post-probe `sqlite3.connect(str(path), isolation_level=None, ...)`
        # call DOES pass kwargs but no factory — we add it.
        kwargs.setdefault("factory", _SpoofedConnection)
        return real_connect(database, *args, **kwargs)

    with patch("personalscraper.indexer.db.sqlite3.connect", side_effect=patched_connect):
        with pytest.raises(IndexerCorruptError) as exc_info:
            open_db(db_path, event_bus=EventBus())

    # File quarantined
    assert not db_path.exists(), "Original file must have been quarantined (renamed)"
    quarantined = list(tmp_path.glob("library.db.corrupt-*"))
    assert len(quarantined) == 1, f"Expected exactly 1 quarantine file, got {quarantined}"

    # Exception carries db_path + quarantine_path
    assert exc_info.value.db_path == db_path
    assert exc_info.value.quarantine_path == quarantined[0]


def test_open_db_rebuild_skips_quarantine_raise_on_integrity_failure(tmp_path: Path) -> None:
    """rebuild=True quarantines the corrupt DB then proceeds with a fresh one.

    Mirrors the existing DatabaseError-branch behavior : rebuild=True signals
    operator consent to losing the corrupt file's contents in exchange for a
    working DB.
    """
    db_path = tmp_path / "library.db"
    _bootstrap_db(db_path)

    _SpoofedConnection._spoof_value = "* freelist count mismatch"

    real_connect = sqlite3.connect

    def patched_connect(database, *args, **kwargs):
        kwargs.setdefault("factory", _SpoofedConnection)
        return real_connect(database, *args, **kwargs)

    with patch("personalscraper.indexer.db.sqlite3.connect", side_effect=patched_connect):
        # rebuild=True : no raise, returns a fresh connection
        conn = open_db(db_path, event_bus=EventBus(), rebuild=True)
        try:
            # The new connection is on a fresh path (the corrupt one was renamed),
            # so the path should exist again as an empty SQLite file.
            assert db_path.exists(), "rebuild=True must create a fresh DB at db_path"
        finally:
            conn.close()

    # The corrupt file was quarantined alongside the fresh one.
    quarantined = list(tmp_path.glob("library.db.corrupt-*"))
    assert len(quarantined) == 1, f"Expected 1 quarantine file post-rebuild, got {quarantined}"
