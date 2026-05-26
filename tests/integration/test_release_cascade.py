"""Regression tests for media_file ON DELETE CASCADE on release_id (Phase 14.4).

When a ``media_release`` row is deleted, every ``media_file`` row pointing at
it must be auto-deleted (CASCADE), not left dangling with
``release_id IS NULL``. Migration 009 changes the FK action from
``ON DELETE SET NULL`` to ``ON DELETE CASCADE`` — this test pins that
contract and prevents regression to the previous SET NULL behaviour, which
produced the 102 unrecoverable orphan files observed at the
``2026-05-25-23h49`` pipeline re-run.

Additional coverage:

- ``library-fix-orphan-files --purge-unrecoverable --apply`` actually deletes
  rows still with ``release_id IS NULL`` post-repair (dry-run does not).
- ``--purge-unrecoverable`` without ``--apply`` only reports ``would_purge``.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.commands._e2e_helpers import make_synthetic_db, run_cli


def _json_from_result(result: Any) -> dict[str, Any]:
    """Strip ANSI escape codes and parse trailing JSON object from CLI output.

    Args:
        result: Typer ``CliRunner`` result.

    Returns:
        Parsed JSON object.
    """
    raw: str = result.output.strip()
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    start = clean.rfind("{")
    if start == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[start:])


def _seed_minimal_file_chain(conn: sqlite3.Connection) -> tuple[int, int, int]:
    """Seed disk → path → media_item → media_release → media_file.

    Args:
        conn: Open SQLite connection (FK enforcement enabled by caller).

    Returns:
        Tuple ``(item_id, release_id, file_id)`` for follow-up assertions.
    """
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        ("uuid-cascade", "TestDisk", "/tmp/mount-cascade", now),
    )
    disk_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, "movies/Test Cascade"),
    )
    path_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("movie", "Test Cascade", "Test Cascade", "movies", now, now),
    )
    item_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO media_release (item_id, quality) VALUES (?, ?)",
        (item_id, "1080p"),
    )
    release_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO media_file "
        "(release_id, path_id, filename, size_bytes, mtime_ns, scan_generation, last_verified_at) "
        "VALUES (?, ?, ?, 1000, ?, 1, ?)",
        (release_id, path_id, "Test Cascade.mkv", now, now),
    )
    file_id = int(cur.lastrowid)  # type: ignore[arg-type]
    conn.commit()
    return item_id, release_id, file_id


# ---------------------------------------------------------------------------
# Migration 009: schema contract
# ---------------------------------------------------------------------------


def test_media_file_release_fk_is_cascade_after_migration(tmp_path: Path) -> None:
    """After all migrations, the FK action on media_file.release_id is CASCADE."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("PRAGMA foreign_key_list(media_file)").fetchall()
        # PRAGMA foreign_key_list columns: id, seq, table, from, to, on_update, on_delete, match
        release_fks = [r for r in rows if r[2] == "media_release" and r[3] == "release_id"]
        assert len(release_fks) == 1, f"expected exactly one FK to media_release, got {release_fks}"
        on_delete = release_fks[0][6]
        assert on_delete == "CASCADE", f"expected CASCADE, got {on_delete!r}"
    finally:
        conn.close()


def test_deleting_release_cascades_to_media_file(tmp_path: Path) -> None:
    """Deleting a media_release row must auto-delete dependent media_file rows.

    Regression for Phase 14.4: previously the FK action was SET NULL which
    produced unrecoverable orphans (file row remains with release_id=NULL,
    no way to reattach). After migration 009 the row must vanish entirely.
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _item_id, release_id, file_id = _seed_minimal_file_chain(conn)

        # Sanity: row exists pre-delete.
        pre = conn.execute("SELECT id, release_id FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert pre is not None
        assert pre[1] == release_id

        # Delete the parent release.
        conn.execute("DELETE FROM media_release WHERE id = ?", (release_id,))
        conn.commit()

        # CASCADE: the media_file row must be gone.
        post = conn.execute("SELECT id, release_id FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert post is None, f"expected CASCADE delete; row still present with release_id={post[1] if post else None}"

        # And no orphan rows linger anywhere.
        orphan_count = conn.execute("SELECT COUNT(*) FROM media_file WHERE release_id IS NULL").fetchone()[0]
        assert orphan_count == 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI: --purge-unrecoverable
# ---------------------------------------------------------------------------


def _seed_pre_existing_orphan(conn: sqlite3.Connection, filename: str = "orphan.mkv") -> int:
    """Seed a media_file with release_id=NULL (pre-migration legacy state).

    Args:
        conn: Open SQLite connection.
        filename: Filename for the orphan row.

    Returns:
        ``file_id`` of the inserted orphan.
    """
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (f"uuid-orphan-{filename}", "OrphanDisk", f"/tmp/mount-orphan-{filename}", now),
    )
    disk_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, f"movies/Orphan {filename}"),
    )
    path_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO media_file "
        "(release_id, path_id, filename, size_bytes, mtime_ns, scan_generation, last_verified_at) "
        "VALUES (NULL, ?, ?, 1000, ?, 1, ?)",
        (path_id, filename, now, now),
    )
    conn.commit()
    return int(cur.lastrowid)  # type: ignore[arg-type]


def test_purge_unrecoverable_dry_run_reports_only(tmp_path: Path, test_config: Any) -> None:
    """``--purge-unrecoverable`` without ``--apply`` reports counts but does NOT delete."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    file_id = _seed_pre_existing_orphan(conn, "dryrun.mkv")
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(
            [
                "--format",
                "json",
                "library-fix-orphan-files",
                "--db",
                str(db_path),
                "--purge-unrecoverable",
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is False
    assert data["purge_unrecoverable"] is True
    assert data["would_purge"] == 1

    # Row still present.
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT id FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_purge_unrecoverable_apply_deletes_orphans(tmp_path: Path, test_config: Any) -> None:
    """``--purge-unrecoverable --apply`` DELETEs every row still with release_id IS NULL.

    The repair pass cannot link these rows (their parent release is gone),
    so the purge step removes them entirely. Verifies the production-cleanup
    path used to drain the 102 pre-existing orphans observed at the
    2026-05-25 re-run.
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    file_id_a = _seed_pre_existing_orphan(conn, "purge-a.mkv")
    file_id_b = _seed_pre_existing_orphan(conn, "purge-b.mkv")
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(
            [
                "--format",
                "json",
                "library-fix-orphan-files",
                "--db",
                str(db_path),
                "--apply",
                "--purge-unrecoverable",
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["purge_unrecoverable"] is True
    assert data["purged"] == 2

    # Rows are gone.
    conn = sqlite3.connect(str(db_path))
    try:
        for fid in (file_id_a, file_id_b):
            row = conn.execute("SELECT id FROM media_file WHERE id = ?", (fid,)).fetchone()
            assert row is None, f"file_id={fid} should have been purged"
        # And no orphans remain.
        remaining = conn.execute("SELECT COUNT(*) FROM media_file WHERE release_id IS NULL").fetchone()[0]
        assert remaining == 0
    finally:
        conn.close()
