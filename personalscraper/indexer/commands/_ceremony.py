"""Shared indexer CLI open-DB + migrations ceremony (INDEXER-08).

Every indexer command (``library-index`` / ``library-status`` / ``library-show``
/ ``library-search`` / ``library-repair`` / ``library-reconcile`` / the
category-migrate maintenance command …) repeated the same ~25-line preamble:
make the DB parent dir, ``open_db`` under a five-way ``Indexer*Error`` guard,
``apply_migrations`` under the *same* five-way guard, then ``close`` the
connection on the way out — echoing ``str(exc)`` to stderr and returning a
non-zero code on any failure. :func:`open_indexer_db` collapses that ceremony
into ONE context manager so the shape is declared, not re-hand-wired per command.

Return-convention seam
----------------------

The pre-refactor ceremony *echoed* the error and then ``return``-ed the command's
own failure code (``return 1`` for most commands, ``return 1, {"error": ...}`` for
the tuple-returning ``library-reconcile``). A context manager cannot ``return``
from its caller, so on a ceremony failure :func:`open_indexer_db` echoes the
message (byte-identical to before) and raises :class:`IndexerCeremonyError`; the
command wraps the ``with`` block in ``except IndexerCeremonyError: return <code>``
to map the failure onto its own convention. The already-echoed message is carried
on ``.message`` for the callers that fold it into a returned payload.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus


class IndexerCeremonyError(Exception):
    """Raised when the open-DB / apply-migrations ceremony fails.

    The human-readable cause has ALREADY been echoed to stderr by
    :func:`open_indexer_db` — parity with the ``typer.echo(str(exc), err=True)``
    line every indexer command duplicated. A command catches this exception to
    map the failure onto its own return convention (``return 1`` — or ``return
    1, {"error": ...}`` for the tuple-returning reconcile command, which reads
    the original message off :attr:`message`).

    Attributes:
        message: The ``str(exc)`` of the underlying ``Indexer*Error`` that was
            already echoed to stderr.
    """

    def __init__(self, message: str) -> None:
        """Store the already-echoed message.

        Args:
            message: The ``str`` of the underlying ``Indexer*Error``.
        """
        super().__init__(message)
        self.message = message


@contextmanager
def open_indexer_db(
    db_path: Path,
    *,
    event_bus: EventBus,
    rebuild: bool = False,
    allow_fk_orphans: bool = False,
    writer_lock_timeout: float | None = None,
) -> Iterator[sqlite3.Connection]:
    """Open the indexer DB, apply pending migrations, and yield the connection.

    Collapses the identical ``open_db`` + ``apply_migrations`` + five-way
    ``Indexer*Error`` mapping + ``close`` ceremony every indexer command
    duplicated (INDEXER-08). Migrations are applied exactly once per ``with``
    block, and the connection is closed when the block exits (success or error).

    On any of the five ceremony errors — ``IndexerLockError``,
    ``IndexerCorruptError``, ``IndexerDiskFullError``, ``IndexerInvalidPathError``,
    ``IndexerMigrationError`` (the writer-lock timeout, when
    ``writer_lock_timeout`` is set, surfaces as ``IndexerLockError``) — the
    message is echoed to stderr (byte-identical to the pre-refactor
    ``typer.echo(str(exc), err=True)``) and :class:`IndexerCeremonyError` is
    raised. The caller maps that onto its own return code.

    Args:
        db_path: Filesystem path of the indexer SQLite database. Its parent
            directory is created if missing (``parents=True, exist_ok=True``).
        event_bus: Required :class:`EventBus` forwarded to ``open_db`` so the
            pre-open free-space guard emits ``DiskFullWarning`` on the run's
            subscriber-wired bus.
        rebuild: Passthrough to ``open_db`` — quarantine a corrupt DB and create
            a fresh one instead of raising ``IndexerCorruptError`` (``library-index
            --rebuild``).
        allow_fk_orphans: Passthrough to ``open_db`` — tolerate a DB with
            foreign-key orphans instead of raising ``IndexerFKOrphansError`` (the
            ``library-reconcile --clean-fk-orphans`` repair path, DEV #3).
        writer_lock_timeout: When not ``None``, hold the indexer single-writer
            lock (``indexer_lock``) for the whole ``with`` block, waiting up to
            this many seconds for it. Only the FS-mutating scan command opts in.

    Yields:
        The open :class:`sqlite3.Connection` with migrations applied.

    Raises:
        IndexerCeremonyError: On any ceremony failure, after echoing the cause to
            stderr. The caller maps it onto its own return convention.
    """
    # Lazy imports: pulls the SQLite machinery + migrations package. Deferred so
    # importing this helper module stays cheap for command modules that only
    # sometimes reach the ceremony.
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import (  # noqa: PLC0415
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerLockError,
        IndexerMigrationError,
        apply_migrations,
        indexer_lock,
        open_db,
    )

    ceremony_errors = (
        IndexerLockError,
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerMigrationError,
    )
    migrations_dir = Path(_migrations_pkg.__file__).parent

    with ExitStack() as stack:
        try:
            # The writer lock (when requested) wraps the whole block, matching the
            # pre-refactor scan command that held indexer_lock across open +
            # migrate + scan; a timeout surfaces as IndexerLockError.
            if writer_lock_timeout is not None:
                stack.enter_context(indexer_lock(db_path, timeout=writer_lock_timeout))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = open_db(
                db_path,
                rebuild=rebuild,
                allow_fk_orphans=allow_fk_orphans,
                event_bus=event_bus,
            )
            # Register close BEFORE apply_migrations: a failed migration leaves a
            # closed connection (core contract), and closing an already-closed
            # sqlite3.Connection is a harmless no-op.
            stack.enter_context(closing(conn))
            apply_migrations(conn, migrations_dir)
        except ceremony_errors as exc:
            typer.echo(str(exc), err=True)
            raise IndexerCeremonyError(str(exc)) from exc
        yield conn


__all__ = ["IndexerCeremonyError", "open_indexer_db"]
