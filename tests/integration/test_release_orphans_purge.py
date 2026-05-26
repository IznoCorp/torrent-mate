"""Regression tests for ``--purge-release-orphans`` flag (Phase 14.8).

Validates that ``library-fix-orphan-files --purge-release-orphans`` correctly
detects and (with ``--apply``) deletes ``media_release`` rows that have no
surviving (non-soft-deleted) ``media_file`` pointing at them.

Background: at the 2026-05-25 23h49 pipeline re-run, ``library-reconcile
--read-only`` reported ``release_orphans_count=172`` — releases that were
created during scrape but whose physical files were never linked (or were
all soft-deleted). Phase 14.8 wires a cleanup path that mirrors the
``detect_release_orphans()`` predicate from ``reconcile.py``.

The tests cover three cases:

- ``detect_release_orphans`` finds the orphan when a media_file is
  soft-deleted (parent release has zero live files).
- The CLI dry-run reports ``would_purge_release_orphans`` but performs no
  DELETE.
- The CLI with ``--apply`` deletes the orphan release and a re-run reports
  ``release_orphans_purged=0`` (idempotent).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from personalscraper.indexer.reconcile import detect_release_orphans
from tests.commands._e2e_helpers import make_synthetic_db, run_cli


def _json_from_result(result: Any) -> dict[str, Any]:
    """Strip ANSI escape codes and parse the trailing JSON object from CLI output.

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
    parsed: dict[str, Any] = json.loads(clean[start:])
    return parsed


def _seed_release_with_softdeleted_file(conn: sqlite3.Connection, suffix: str = "a") -> tuple[int, int, int]:
    """Seed disk → path → media_item → media_release → media_file (soft-deleted).

    The resulting ``media_release`` is orphan because its only ``media_file``
    has ``deleted_at`` set — exactly the scenario produced by the 172
    productions orphans seen at 2026-05-25 23h49.

    Args:
        conn: Open SQLite connection.
        suffix: Disambiguator for unique columns when seeding multiple
            orphans in the same DB.

    Returns:
        ``(item_id, release_id, file_id)`` for follow-up assertions.
    """
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (f"uuid-orphan-{suffix}", f"OrphanDisk-{suffix}", f"/tmp/mount-orphan-{suffix}", now),
    )
    disk_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, f"movies/Orphan-{suffix}"),
    )
    path_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("movie", f"Orphan {suffix}", f"Orphan {suffix}", "movies", now, now),
    )
    item_id = int(cur.lastrowid)  # type: ignore[arg-type]
    cur = conn.execute(
        "INSERT INTO media_release (item_id, quality) VALUES (?, ?)",
        (item_id, "1080p"),
    )
    release_id = int(cur.lastrowid)  # type: ignore[arg-type]
    # Insert a media_file then immediately soft-delete it (set deleted_at).
    cur = conn.execute(
        "INSERT INTO media_file "
        "(release_id, path_id, filename, size_bytes, mtime_ns, scan_generation, last_verified_at, deleted_at) "
        "VALUES (?, ?, ?, 1000, ?, 1, ?, ?)",
        (release_id, path_id, f"Orphan-{suffix}.mkv", now, now, now),
    )
    file_id = int(cur.lastrowid)  # type: ignore[arg-type]
    conn.commit()
    return item_id, release_id, file_id


# ---------------------------------------------------------------------------
# detect_release_orphans: identifies the soft-delete case
# ---------------------------------------------------------------------------


def test_detect_release_orphans_includes_softdeleted_file_case(tmp_path: Path) -> None:
    """``detect_release_orphans`` returns releases whose only file is soft-deleted.

    Pre-fix sanity: this is the exact predicate the CLI's ``--purge-release-orphans``
    will mirror; the test pins their alignment.
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _item_id, release_id, _file_id = _seed_release_with_softdeleted_file(conn, "detect")

        orphan_ids, _null_count = detect_release_orphans(conn)
        assert release_id in orphan_ids, f"expected release {release_id} in orphans, got {orphan_ids}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI: --purge-release-orphans dry-run + apply + idempotency
# ---------------------------------------------------------------------------


def test_purge_release_orphans_dry_run_reports_only(tmp_path: Path, test_config: Any) -> None:
    """``--purge-release-orphans`` without ``--apply`` reports the count but does NOT delete."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _item_id, release_id, _file_id = _seed_release_with_softdeleted_file(conn, "dry")
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(
            [
                "--format",
                "json",
                "library-fix-orphan-files",
                "--db",
                str(db_path),
                "--purge-release-orphans",
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is False
    assert data["purge_release_orphans"] is True
    assert data["would_purge_release_orphans"] == 1

    # Release row still present.
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT id FROM media_release WHERE id = ?", (release_id,)).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_purge_release_orphans_apply_deletes_and_is_idempotent(tmp_path: Path, test_config: Any) -> None:
    """``--purge-release-orphans --apply`` deletes orphan releases; re-run reports 0.

    Validates the happy path the production cleanup of the 172 orphans
    relies on, and the idempotency contract required by Phase 14.8.
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _ia, release_a, _fa = _seed_release_with_softdeleted_file(conn, "apply-a")
    _ib, release_b, _fb = _seed_release_with_softdeleted_file(conn, "apply-b")
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
                "--purge-release-orphans",
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["purge_release_orphans"] is True
    assert data["release_orphans_purged"] == 2

    # Releases are gone.
    conn = sqlite3.connect(str(db_path))
    try:
        for rid in (release_a, release_b):
            row = conn.execute("SELECT id FROM media_release WHERE id = ?", (rid,)).fetchone()
            assert row is None, f"release_id={rid} should have been purged"
        # And the reconcile probe confirms zero orphans remain.
        orphan_ids, _null_count = detect_release_orphans(conn)
        assert orphan_ids == []
    finally:
        conn.close()

    # Idempotency: a second run on the now-clean DB reports zero purged.
    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result2 = run_cli(
            [
                "--format",
                "json",
                "library-fix-orphan-files",
                "--db",
                str(db_path),
                "--apply",
                "--purge-release-orphans",
            ]
        )
    assert result2.exit_code == 0, result2.output
    data2 = _json_from_result(result2)
    assert data2["release_orphans_purged"] == 0
