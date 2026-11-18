"""An SQLite that refuses ``mode=ro`` on a WAL database no process holds.

Whether SQLite opens such a database read-only depends on its version: 3.51 answers « unable to
open database file » (it cannot create the ``-shm`` a read-only connection needs), 3.53 creates the
side files and reads. The dev host runs the first, a fresh ``uv`` environment the second, so a test
that relies on the real library cannot fail the same way everywhere. :func:`refuse_idle_wal_read_only`
makes the refusal deterministic, and the tests that use it prove the fallback, not the SQLite build.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pytest

#: The header byte (offset 18) that says the file is in WAL mode.
_WAL_VERSION_BYTE = 2


def leave_wal_database(path: Path) -> None:
    """Put a database in WAL mode and close it, leaving no ``-wal`` nor ``-shm``: an idle store.

    Args:
        path: An existing SQLite database, closed.
    """
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    left = [suffix for suffix in ("-wal", "-shm") if Path(f"{path}{suffix}").exists()]
    assert left == [], "a writer left side files behind"


def refuse_idle_wal_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``sqlite3.connect`` refuse a ``mode=ro`` open of a WAL database whose ``-shm`` is absent.

    Args:
        monkeypatch: The test's monkeypatch; the real ``connect`` comes back at teardown.
    """
    real_connect = sqlite3.connect

    def connect(database: Any, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        """Open like SQLite 3.51, which cannot read an idle WAL database read-only.

        Args:
            database: The database, a path or a ``file:`` URI.
            *args: Passed to ``sqlite3.connect``.
            **kwargs: Passed to ``sqlite3.connect``.

        Returns:
            The connection.

        Raises:
            sqlite3.OperationalError: ``mode=ro`` on an idle WAL database.
        """
        text = str(database)
        if kwargs.get("uri") and text.startswith("file:") and "mode=ro" in text:
            path = Path(unquote(urlparse(text).path))
            idle = path.is_file() and not Path(f"{path}-shm").exists()
            if idle and path.read_bytes()[18:19] == bytes([_WAL_VERSION_BYTE]):
                raise sqlite3.OperationalError("unable to open database file")
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)
