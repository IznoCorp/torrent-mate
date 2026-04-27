"""E2E test: OSHash collision detection enqueues repair, never auto-renames.

DESIGN §15.5 + §17.1:

Fabricate two files with *crafted identical OSHash* values (seeded directly in
the DB — constructing a real content collision is impractical).  On a rescan
(``detect_rename``), the engine must:

- NOT apply an auto-rename.
- INSERT a ``repair_queue`` row with ``reason='oshash_collision'``.

This test uses pyfakefs for filesystem isolation and an in-memory SQLite DB.
It calls ``drift.detect_rename`` directly, which is the integration surface
that encodes the collision guard described in DESIGN §17.1.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.drift import detect_rename

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_CRAFTED_OSHASH = "aabbccddeeff0011"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Open a fully-migrated in-memory SQLite DB."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=OFF")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _seed_disk(conn: sqlite3.Connection, mount_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, is_mounted, unreachable_strikes) VALUES (?, ?, ?, 1, 0)",
        ("uuid-collision-test", "CollisionDisk", mount_path),
    )
    disk_id: int = cur.lastrowid  # type: ignore[assignment]
    conn.commit()
    return disk_id


def _seed_path(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
        (disk_id, rel_path),
    )
    path_id: int = cur.lastrowid  # type: ignore[assignment]
    conn.commit()
    return path_id


def _seed_file(conn: sqlite3.Connection, path_id: int, filename: str, oshash_val: str, size: int = 200) -> int:
    cur = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (0, ?, ?, ?, 1000000000, NULL, ?, NULL, NULL, 1, 0, NULL, 0, NULL)
        """,
        (path_id, filename, size, oshash_val),
    )
    fid: int = cur.lastrowid  # type: ignore[assignment]
    conn.commit()
    return fid


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_oshash_collision_enqueues_repair_not_rename(tmp_path: Path) -> None:
    """Two DB rows sharing the same OSHash with both source paths still on disk.

    Expected outcomes:
    - ``detect_rename`` returns ``"oshash_collision"``.
    - At least one ``repair_queue`` row with ``reason='oshash_collision'``.
    - Neither original row's ``path_id`` or ``filename`` is changed.
    """
    # Build fake filesystem: two source files both present.
    dir_a = tmp_path / "movies" / "movie_a"
    dir_b = tmp_path / "movies" / "movie_b"
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)

    file_a = dir_a / "movie_a.mkv"
    file_b = dir_b / "movie_b.mkv"
    file_a.write_bytes(b"AAA" * 100)  # different content, same seeded oshash
    file_b.write_bytes(b"BBB" * 100)

    conn = _open_db()
    disk_id = _seed_disk(conn, mount_path=str(tmp_path))

    path_id_a = _seed_path(conn, disk_id, "movies/movie_a")
    path_id_b = _seed_path(conn, disk_id, "movies/movie_b")
    path_id_new = _seed_path(conn, disk_id, "movies/movie_new")

    # Two existing rows with the crafted same OSHash.
    fid_a = _seed_file(conn, path_id=path_id_a, filename="movie_a.mkv", oshash_val=_CRAFTED_OSHASH, size=300)
    fid_b = _seed_file(conn, path_id=path_id_b, filename="movie_b.mkv", oshash_val=_CRAFTED_OSHASH, size=300)

    # Simulate a new file at a third location; seed it in DB so detect_rename
    # can query its size for the collision guard.
    dir_new = tmp_path / "movies" / "movie_new"
    dir_new.mkdir(parents=True)
    (dir_new / "movie_new.mkv").write_bytes(b"CCC" * 100)
    _seed_file(conn, path_id=path_id_new, filename="movie_new.mkv", oshash_val=_CRAFTED_OSHASH, size=300)

    outcome = detect_rename(
        conn=conn,
        disk_id=disk_id,
        current_path_id=path_id_new,
        filename="movie_new.mkv",
        current_oshash=_CRAFTED_OSHASH,
    )

    assert outcome == "oshash_collision", f"Expected 'oshash_collision', got {outcome!r}"

    # At least one repair entry.
    repair_rows = conn.execute(
        "SELECT id, scope, scope_id, reason FROM repair_queue WHERE reason = 'oshash_collision'",
    ).fetchall()
    assert len(repair_rows) >= 1, f"Expected repair_queue row with reason='oshash_collision'; found {repair_rows}"

    # Neither original row must have been modified.
    row_a = conn.execute("SELECT path_id, filename FROM media_file WHERE id = ?", (fid_a,)).fetchone()
    row_b = conn.execute("SELECT path_id, filename FROM media_file WHERE id = ?", (fid_b,)).fetchone()
    assert row_a[0] == path_id_a, "File A path_id must not change on collision"
    assert row_a[1] == "movie_a.mkv", "File A filename must not change on collision"
    assert row_b[0] == path_id_b, "File B path_id must not change on collision"
    assert row_b[1] == "movie_b.mkv", "File B filename must not change on collision"

    conn.close()


def test_oshash_collision_single_source_still_present(tmp_path: Path) -> None:
    """Single candidate with same OSHash but old path still on disk → collision.

    If the engine finds exactly one OSHash match but the old file still exists
    on disk, it must not treat it as a rename.  The DESIGN §17.1 guard requires
    the old path to be *absent* before applying a rename.
    """
    dir_old = tmp_path / "old_location"
    dir_old.mkdir(parents=True)
    old_file = dir_old / "source.mkv"
    old_file.write_bytes(b"source_content" * 20)  # still present

    conn = _open_db()
    disk_id = _seed_disk(conn, mount_path=str(tmp_path))

    path_id_old = _seed_path(conn, disk_id, "old_location")
    path_id_new = _seed_path(conn, disk_id, "new_location")

    fid_old = _seed_file(conn, path_id=path_id_old, filename="source.mkv", oshash_val=_CRAFTED_OSHASH, size=280)

    dir_new = tmp_path / "new_location"
    dir_new.mkdir(parents=True)
    (dir_new / "destination.mkv").write_bytes(b"different_content" * 20)
    _seed_file(conn, path_id=path_id_new, filename="destination.mkv", oshash_val=_CRAFTED_OSHASH, size=280)

    outcome = detect_rename(
        conn=conn,
        disk_id=disk_id,
        current_path_id=path_id_new,
        filename="destination.mkv",
        current_oshash=_CRAFTED_OSHASH,
    )

    assert outcome == "oshash_collision", f"Expected 'oshash_collision' when old path exists, got {outcome!r}"

    repair_rows = conn.execute(
        "SELECT reason FROM repair_queue WHERE reason = 'oshash_collision'",
    ).fetchall()
    assert len(repair_rows) >= 1, "Expected a repair entry when old path is still present"

    # Original row untouched.
    row_old = conn.execute("SELECT path_id, filename FROM media_file WHERE id = ?", (fid_old,)).fetchone()
    assert row_old[0] == path_id_old
    assert row_old[1] == "source.mkv"

    conn.close()
