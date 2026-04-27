"""Outbox module for the media indexer sub-system.

This module is a **no-op stub** for Phase 5, where the outbox will emit
change-events to downstream consumers (e.g. Plex library refresh triggers,
notification queues).

In the current phase (Phase 2) the function exists solely so that
:func:`~personalscraper.indexer.cli.library_index_command` can call it
without a conditional.  The real implementation will be wired here in Phase 5.
"""

from __future__ import annotations

import sqlite3

from personalscraper.logger import get_logger

log = get_logger("indexer.outbox")


def drain_if_present(conn: sqlite3.Connection) -> int:
    """Drain pending outbox events and return the count of events drained.

    This is a **no-op stub** — it always returns ``0``.  Phase 5 will replace
    this body with logic that reads pending rows from the ``outbox`` table and
    dispatches them to registered consumers.

    Args:
        conn: Open SQLite connection (unused in the stub; accepted so the real
            Phase 5 implementation can reuse the same signature without a
            signature change at call sites).

    Returns:
        Number of outbox events drained.  Always ``0`` until Phase 5.
    """
    log.debug("indexer.outbox.drain_noop")
    return 0
