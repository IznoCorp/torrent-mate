"""The savepoint a store method's several statements run under.

A method writing several statements makes them one unit with :func:`atomic`; it nests inside
:meth:`~personalscraper.app.store.store.AppStore.immediate`, the transaction a service opens
when several calls must be one act.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress


@contextmanager
def atomic(conn: sqlite3.Connection, name: str) -> Iterator[None]:
    """Run one method's several statements as a unit; nests inside ``AppStore.immediate``.

    Args:
        conn: The connection, in autocommit mode.
        name: The savepoint's name (a fixed identifier, never user input).

    Yields:
        Nothing.

    Raises:
        BaseException: Whatever the block raised, after rolling back to the savepoint.
    """
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        # The savepoint is gone when SQLite ended the transaction; keep the original error.
        with suppress(sqlite3.Error):
            conn.execute(f"ROLLBACK TO {name}")
            conn.execute(f"RELEASE {name}")
        raise
    conn.execute(f"RELEASE {name}")
