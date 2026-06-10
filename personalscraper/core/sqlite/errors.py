# personalscraper/core/sqlite/errors.py
"""Minimal marker exceptions for the core SQLite layer.

These are bare base classes only — they carry NO attributes.
The attribute-bearing ``IndexerXxxError`` subclasses live in
``personalscraper.indexer.db`` and re-parent onto these markers so
``isinstance(IndexerLockError(...), SqliteLockError)`` is True.

Import direction: this module imports only stdlib (RuntimeError, ValueError,
OSError) — never from any package in personalscraper.
"""

from __future__ import annotations

__all__ = [
    "SqliteLockError",
    "SqliteCorruptError",
    "SqliteInvalidPathError",
    "SqliteDiskFullError",
    "SqliteFKOrphansError",
    "SqliteMigrationError",
]


class SqliteLockError(RuntimeError):
    """Base marker: writer lock held by another process."""


class SqliteCorruptError(RuntimeError):
    """Base marker: database file is malformed."""


class SqliteInvalidPathError(ValueError):
    """Base marker: db_path is on an unsupported filesystem."""


class SqliteDiskFullError(OSError):
    """Base marker: insufficient free disk space."""


class SqliteFKOrphansError(RuntimeError):
    """Base marker: foreign-key orphan rows detected."""


class SqliteMigrationError(RuntimeError):
    """Base marker: migration script failed."""
