"""Errors of the ``app`` store, beside the pattern of ``acquire/errors.py``."""

from __future__ import annotations

from personalscraper.core.sqlite.errors import SqliteMigrationError


class AppMigrationError(SqliteMigrationError):
    """Raised when applying an ``app.db`` migration script fails.

    The database is restored from the pre-migration snapshot before this
    exception propagates (see the core applier's closed-connection invariant).

    Args:
        version: The migration version number that failed (e.g. ``1`` for
            ``001_baseline.sql``).
    """

    def __init__(self, version: int) -> None:
        """Initialize with the failed migration version number.

        Args:
            version: Numeric prefix of the migration script that failed.
        """
        self.version = version
        super().__init__(
            f"App migration {version:03d} failed; database restored from "
            f"snapshot. Inspect the migration SQL before retrying."
        )
