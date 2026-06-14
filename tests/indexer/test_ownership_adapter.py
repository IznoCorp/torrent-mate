"""Unit tests for IndexerOwnershipChecker: port conformance + lazy + fail-soft.

NON-VACUOUS discipline:
- isinstance check: IndexerOwnershipChecker satisfies the OwnershipChecker
  runtime-checkable Protocol.
- lazy: constructing the checker opens NO connection (no boot I/O / no lock) —
  the regression-prevention invariant. The connection opens on the first
  ``owns`` call.
- read-only / lock-free: the lazily-opened connection rejects writes
  (``PRAGMA query_only=ON``), proving it can never take a writer lock.
- live file: ``owns`` delegates correctly to ``is_owned`` (seeded library.db).
- fail-soft (LOAD-BEARING): a missing/broken db OR any predicate exception →
  ``False``, no raise — the caller (a future grab loop) must never crash.

The fixtures seed provider IDs through ``media_item.external_ids_json``
(migration 005 dropped the flat tvdb_id/tmdb_id/imdb_id columns), mirroring
``tests/indexer/test_ownership_predicate.py``.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.identity import MediaRef
from personalscraper.core.ownership import OwnershipChecker
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.ownership import IndexerOwnershipChecker

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

NOW = int(time.time())


def _external_ids_json(*, tvdb_id: int | None = None) -> str:
    """Build an external_ids_json payload mirroring migration 005's shape."""
    payload: dict[str, dict[str, str | None]] = {}
    if tvdb_id is not None:
        payload["tvdb"] = {"series_id": str(tvdb_id), "episode_id": None}
    return json.dumps(payload)


def _seed_library_db(db_path: Path, *, tvdb_id: int = 9001) -> None:
    """Create a library.db at db_path with one owned movie (live file)."""
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    # disk CHECK: mount_path must be NOT NULL when is_mounted=1.
    conn.execute(
        "INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1','D1','/Volumes/D1',1)",
    )
    conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1,'001-MOVIES/Test')")
    conn.execute(
        "INSERT INTO media_item(kind,title,title_sort,year,category_id,external_ids_json,date_created,date_modified)"
        " VALUES ('movie','Test','Test',2020,'movies',?,?,?)",
        (_external_ids_json(tvdb_id=tvdb_id), NOW, NOW),
    )
    conn.execute("INSERT INTO media_release(item_id) VALUES (1)")
    conn.execute(
        "INSERT INTO media_file(release_id,path_id,filename,size_bytes,mtime_ns,"
        "oshash,scan_generation,last_verified_at)"
        " VALUES (1,1,'t.mkv',1000000000,?,?,1,?)",
        (NOW * 10**9, "abcd1234abcd1234", NOW),
    )
    conn.close()


def test_implements_protocol(tmp_path: Path) -> None:
    """IndexerOwnershipChecker satisfies the OwnershipChecker runtime Protocol."""
    checker = IndexerOwnershipChecker(tmp_path / "library.db")
    assert isinstance(checker, OwnershipChecker)


def test_construction_opens_no_connection(tmp_path: Path) -> None:
    """LAZINESS: constructing the checker opens NO connection (no boot I/O).

    Mirrors the acquire-store regression fix: the composition root must not
    open library.db (and thus must not take any lock) at boot, so unrelated
    commands are never serialised.
    """
    db_path = tmp_path / "library.db"
    _seed_library_db(db_path)
    checker = IndexerOwnershipChecker(db_path)
    assert checker._conn is None  # never opened at construction


def test_owns_live_movie_returns_true(tmp_path: Path) -> None:
    """owns() returns True when a live file exists for the matched tvdb_id."""
    db_path = tmp_path / "library.db"
    _seed_library_db(db_path, tvdb_id=9001)
    checker = IndexerOwnershipChecker(db_path)
    ref = MediaRef(tvdb_id=9001)
    assert checker.owns(ref, kind="movie") is True
    assert checker._conn is not None  # opened lazily on first owns()
    checker.close()


def test_owns_unknown_movie_returns_false(tmp_path: Path) -> None:
    """owns() returns False when no item matches the given tvdb_id."""
    db_path = tmp_path / "library.db"
    _seed_library_db(db_path, tvdb_id=9001)
    checker = IndexerOwnershipChecker(db_path)
    ref = MediaRef(tvdb_id=9999)
    assert checker.owns(ref, kind="movie") is False
    checker.close()


def test_lazy_connection_is_read_only(tmp_path: Path) -> None:
    """LOCK-FREE: the lazily-opened connection rejects writes (query_only=ON).

    Proves the connection can never take a writer lock — a write attempt on it
    raises ``sqlite3.OperationalError`` ("attempt to write a readonly database").
    """
    db_path = tmp_path / "library.db"
    _seed_library_db(db_path)
    checker = IndexerOwnershipChecker(db_path)
    checker.owns(MediaRef(tvdb_id=9001), kind="movie")  # force lazy open
    assert checker._conn is not None
    with pytest.raises(sqlite3.OperationalError):
        checker._conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1,'x')")
    checker.close()


def test_fail_soft_missing_db_returns_false(tmp_path: Path) -> None:
    """LOAD-BEARING: a missing/unopenable library.db → False, no raise.

    A directory path is unopenable by sqlite3, so _ensure_open raises — owns()
    must swallow it and return False silently.
    """
    broken = tmp_path  # a directory, not a valid sqlite file
    checker = IndexerOwnershipChecker(broken)
    result = checker.owns(MediaRef(tvdb_id=9001), kind="movie")
    assert result is False


def test_fail_soft_closed_checker_returns_false(tmp_path: Path) -> None:
    """LOAD-BEARING: owns() on a closed checker → False, no raise.

    _ensure_open raises RuntimeError once closed; owns() must swallow it.
    """
    db_path = tmp_path / "library.db"
    _seed_library_db(db_path)
    checker = IndexerOwnershipChecker(db_path)
    checker.owns(MediaRef(tvdb_id=9001), kind="movie")  # open then close
    checker.close()
    result = checker.owns(MediaRef(tvdb_id=9001), kind="movie")
    assert result is False


def test_fail_soft_does_not_raise_on_any_exception(tmp_path: Path) -> None:
    """LOAD-BEARING: any Exception from is_owned → False, never propagates."""
    db_path = tmp_path / "library.db"
    _seed_library_db(db_path)
    checker = IndexerOwnershipChecker(db_path)
    ref = MediaRef(tvdb_id=9001)

    with patch("personalscraper.indexer.ownership.is_owned", side_effect=RuntimeError("boom")):
        result = checker.owns(ref, kind="movie")

    assert result is False
    checker.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    """close() is safe to call twice and on a never-opened checker."""
    checker = IndexerOwnershipChecker(tmp_path / "library.db")
    checker.close()  # never opened — pure no-op
    checker.close()  # double close — no-op
