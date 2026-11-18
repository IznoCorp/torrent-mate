# personalscraper/core/sqlite/__init__.py
"""Neutral SQLite machinery — event-free, shared by indexer/ and acquire/.

Public API:
  apply_pragmas(conn)          — canonical 8-PRAGMA set
  open_db(path, ...)           — event-free open + corruption-quarantine
  db_lock(path, *, timeout=0)  — flock + PID sidecar + stale-sidecar recovery
  apply_migrations(conn, dir_) — apply *.sql migration scripts
  refuse_newer_schema(conn, dir_) — refuse a store migrated past the code (raw writers)
  safe_rollback(conn)          — best-effort ROLLBACK, no error when no transaction
  probe_mount(path)            — filesystem-type probe
  serialised                   — a store method run under its connection lock
  Sqlite*Error                 — marker exception hierarchy
"""

from __future__ import annotations

from personalscraper.core.sqlite._fs_probe import MountInfo, probe_mount
from personalscraper.core.sqlite._lock import db_lock
from personalscraper.core.sqlite._migrate import apply_migrations, refuse_newer_schema, safe_rollback
from personalscraper.core.sqlite._open import open_db
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.core.sqlite._serialised import serialised
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
    SqliteLockError,
    SqliteMigrationError,
    SqliteSchemaNewerError,
)

__all__ = [
    "MountInfo",
    "SqliteCorruptError",
    "SqliteDiskFullError",
    "SqliteFKOrphansError",
    "SqliteInvalidPathError",
    "SqliteLockError",
    "SqliteMigrationError",
    "SqliteSchemaNewerError",
    "apply_migrations",
    "apply_pragmas",
    "db_lock",
    "open_db",
    "probe_mount",
    "refuse_newer_schema",
    "safe_rollback",
    "serialised",
]
