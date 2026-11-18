"""Read-only open of a store, for a reader that must outlive the store's last writer.

A WAL database needs its ``-shm`` index to be read. While a process holds the store open the file
is there and ``mode=ro`` works; once the last writer closed cleanly SQLite deletes ``-wal`` and
``-shm``, and some builds (3.51 on the dev host) then refuse a ``mode=ro`` open with « unable to
open database file », though the file is intact. :func:`connect_read_only` answers that one
failure and no other.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

#: The primary result code of « unable to open database file » (``SQLITE_CANTOPEN``).
_SQLITE_CANTOPEN = 14

#: Read through ``sqlite_master``: the first page read is what asks a WAL database for its ``-shm``.
_PROBE_SQL = "SELECT 1 FROM sqlite_master LIMIT 1"


def _cannot_open(exc: sqlite3.Error) -> bool:
    """Tell whether an error is « unable to open database file ».

    Args:
        exc: The error an open or the first read raised.

    Returns:
        ``True`` for ``SQLITE_CANTOPEN`` (its extended codes included).
    """
    code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(code, int):
        return code & 0xFF == _SQLITE_CANTOPEN
    return "unable to open database file" in str(exc)


def _open(db_path: Path, mode: str, connect_args: dict[str, Any]) -> sqlite3.Connection:
    """Open the file in one mode, ``query_only``, and read its first page.

    Args:
        db_path: The store's file.
        mode: ``ro`` or ``rw`` (never ``rwc``: an absent file is never created).
        connect_args: Passed to :func:`sqlite3.connect`.

    Returns:
        The open connection.

    Raises:
        sqlite3.Error: The open or the first read failed; the connection is closed.
    """
    conn: sqlite3.Connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode={mode}", uri=True, **connect_args)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute(_PROBE_SQL).fetchone()
    except sqlite3.Error:
        conn.close()
        raise
    return conn


def connect_read_only(db_path: Path, **connect_args: Any) -> sqlite3.Connection:
    """Open a store read-only: ``mode=ro``, retried once ``mode=rw`` + ``query_only`` when SQLite cannot open it.

    The retry happens only when the first open (or the first page read) fails with
    « unable to open database file » **and** the file exists: that is a WAL store with no live
    ``-shm``. ``mode=rw`` never creates the database, so an absent file stays an error, and
    ``query_only`` makes the connection refuse every write; the only files it can create are the
    ``-wal``/``-shm`` side files, in the store's directory. A file that is no database, a locked
    store or an unwritable directory (the retry fails the same way) raise as they would have.

    Args:
        db_path: The store's file.
        **connect_args: Passed to :func:`sqlite3.connect` on both opens (``timeout``,
            ``isolation_level``, ``check_same_thread`` …).

    Returns:
        An open ``query_only`` connection, its first page read.

    Raises:
        sqlite3.Error: The store cannot be opened, or is no database; the first error when the
            retry fails too.
    """
    try:
        return _open(db_path, "ro", connect_args)
    except sqlite3.OperationalError as first:
        if not _cannot_open(first) or not db_path.is_file():
            raise
        try:
            return _open(db_path, "rw", connect_args)
        except sqlite3.Error:
            raise first from None
