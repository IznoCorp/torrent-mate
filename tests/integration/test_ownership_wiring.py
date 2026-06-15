"""Integration test: ownership wiring through the composition root (RP6).

Exercises the full RP6 wiring end-to-end, the way ``_build_app_context`` does:

    _build_ownership_checker(config)  ->  build_acquire_context(..., ownership=…)
                                      ->  ctx.ownership.owns(...)

Three load-bearing cases:
- a seeded ``library.db`` on disk → ``ctx.ownership`` is an
  ``IndexerOwnershipChecker`` that returns the real booleans (owned → True,
  unknown → False);
- NO ``library.db`` → ``ctx.ownership`` is a ``NullOwnershipChecker`` (always
  False), so a command with no library wired is safe;
- a broken/unopenable ``library.db`` path → ``owns`` is fail-soft (False, no
  raise), so building the app context never crashes a command.

It also pins the lock-free invariant: building the context opens NO connection
(``_conn is None`` until the first ``owns()``), so the shared composition root
takes no lifetime lock on ``library.db``.

Provider IDs are seeded through ``media_item.external_ids_json`` (migration 005),
mirroring ``tests/indexer/test_ownership_predicate.py``.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.cli_helpers import _build_ownership_checker
from personalscraper.core.identity import MediaRef
from personalscraper.core.ownership import NullOwnershipChecker, OwnershipChecker
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.ownership import IndexerOwnershipChecker

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"
NOW = int(time.time())


def _seed_library_db(db_path: Path, *, tvdb_id: int = 1001) -> None:
    """Create a library.db at db_path and seed one owned movie (live file)."""
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    # disk CHECK: mount_path must be NOT NULL when is_mounted=1.
    conn.execute("INSERT INTO disk(uuid,label,mount_path,is_mounted) VALUES ('u1','D1','/Volumes/D1',1)")
    conn.execute("INSERT INTO path(disk_id,rel_path) VALUES (1,'001-MOVIES/Owned')")
    external_ids = json.dumps({"tvdb": {"series_id": str(tvdb_id), "episode_id": None}})
    conn.execute(
        "INSERT INTO media_item(kind,title,title_sort,year,category_id,external_ids_json,date_created,date_modified)"
        " VALUES ('movie','Owned Movie','Owned Movie',2020,'movies',?,?,?)",
        (external_ids, NOW, NOW),
    )
    conn.execute("INSERT INTO media_release(item_id) VALUES (1)")
    conn.execute(
        "INSERT INTO media_file(release_id,path_id,filename,size_bytes,mtime_ns,"
        "oshash,scan_generation,last_verified_at) VALUES (1,1,'owned.mkv',1000000,?,?,1,?)",
        (NOW * 10**9, "abcd1234abcd1234", NOW),
    )
    conn.close()


def _config_with_db_path(db_path: Path | None) -> MagicMock:
    """Return a minimal MagicMock config with indexer.db_path set to ``db_path``."""
    cfg = MagicMock()
    cfg.indexer.db_path = db_path
    return cfg


def _build_ctx_with_ownership(ownership: OwnershipChecker):
    """Build an AcquireContext via build_acquire_context, injecting ``ownership``.

    Mirrors how ``_build_app_context`` injects the composition-root-built checker
    into ``build_acquire_context``; the tracker registry is patched out so the
    test stays focused on the ownership wiring.
    """
    from personalscraper.acquire._factory import build_acquire_context

    config = MagicMock()
    with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
        mock_build.return_value = MagicMock()
        return build_acquire_context(
            config,
            MagicMock(),
            event_bus=MagicMock(),
            cb_policy=MagicMock(),
            ownership=ownership,
        )


def test_ownership_wired_with_library_db(tmp_path: Path) -> None:
    """With a seeded library.db, ctx.ownership answers real ownership booleans."""
    db_path = tmp_path / "library.db"
    _seed_library_db(db_path, tvdb_id=1001)

    # Composition-root build: an IndexerOwnershipChecker over the real db.
    checker = _build_ownership_checker(_config_with_db_path(db_path))
    assert isinstance(checker, IndexerOwnershipChecker)
    # LOCK-FREE: building the checker opens NO connection at the composition root.
    assert checker._conn is None

    ctx = _build_ctx_with_ownership(checker)
    assert isinstance(ctx.ownership, IndexerOwnershipChecker)
    assert isinstance(ctx.ownership, OwnershipChecker)

    # Owned movie → True; the connection opens lazily on this first owns() call.
    assert ctx.ownership.owns(MediaRef(tvdb_id=1001), kind="movie") is True
    # Unknown movie → False.
    assert ctx.ownership.owns(MediaRef(tvdb_id=9999), kind="movie") is False

    ctx.close()


def test_ownership_null_when_no_library_db(tmp_path: Path) -> None:
    """With no library.db on disk, the checker is a NullOwnershipChecker (always False)."""
    db_path = tmp_path / "nonexistent_library.db"  # not created

    checker = _build_ownership_checker(_config_with_db_path(db_path))
    assert isinstance(checker, NullOwnershipChecker)

    ctx = _build_ctx_with_ownership(checker)
    assert isinstance(ctx.ownership, NullOwnershipChecker)
    assert ctx.ownership.owns(MediaRef(tvdb_id=1001), kind="movie") is False

    ctx.close()


def test_ownership_null_when_db_path_unconfigured() -> None:
    """When indexer.db_path is None, the checker is a NullOwnershipChecker."""
    checker = _build_ownership_checker(_config_with_db_path(None))
    assert isinstance(checker, NullOwnershipChecker)


def test_ownership_fail_soft_on_broken_db(tmp_path: Path) -> None:
    """A path that exists but is NOT a valid sqlite db → fail-soft False, no raise.

    LOAD-BEARING: the ownership lookup must never crash a command that built the
    app context. A garbage file at the configured db_path opens (or queries) with
    an error that owns() swallows, returning False.
    """
    db_path = tmp_path / "library.db"
    db_path.write_bytes(b"this is not a sqlite database, it is garbage bytes")

    # The file exists, so the composition root builds a real IndexerOwnershipChecker.
    checker = _build_ownership_checker(_config_with_db_path(db_path))
    assert isinstance(checker, IndexerOwnershipChecker)

    ctx = _build_ctx_with_ownership(checker)
    # Must NOT raise — must return False silently (fail-soft).
    assert ctx.ownership.owns(MediaRef(tvdb_id=1001), kind="movie") is False

    ctx.close()
