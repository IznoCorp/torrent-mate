# personalscraper/core/sqlite/__init__.py
"""Neutral SQLite machinery — event-free, shared by indexer/ and acquire/.

Public API:
  apply_pragmas(conn)          — canonical 8-PRAGMA set
  open_db(path, ...)           — event-free open + corruption-quarantine
  db_lock(path, *, timeout=0)  — FileLock + sidecar + stale-PID recovery
  apply_migrations(conn, dir_) — apply *.sql migration scripts
  probe_mount(path)            — filesystem-type probe
  Sqlite*Error                 — marker exception hierarchy
"""

from __future__ import annotations

from personalscraper.core.sqlite._fs_probe import MountInfo, probe_mount
from personalscraper.core.sqlite._lock import db_lock
from personalscraper.core.sqlite._migrate import apply_migrations
from personalscraper.core.sqlite._open import open_db
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
    SqliteLockError,
    SqliteMigrationError,
)

__all__ = [
    "MountInfo",
    "SqliteCorruptError",
    "SqliteDiskFullError",
    "SqliteFKOrphansError",
    "SqliteInvalidPathError",
    "SqliteLockError",
    "SqliteMigrationError",
    "apply_migrations",
    "apply_pragmas",
    "db_lock",
    "open_db",
    "probe_mount",
]
