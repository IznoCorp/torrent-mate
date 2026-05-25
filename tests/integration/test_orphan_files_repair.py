"""Regression tests for ``library-fix-orphan-files`` repair CLI.

Covers:
- Single candidate release → file is linked (``release_id`` set).
- No release → file left alone, reported as ``no_release``.
- Multiple candidate releases → file left alone, reported as ``ambiguous``.
- Dry-run → counts without mutation.
- Idempotence → second pass touches 0 rows.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.commands._e2e_helpers import make_synthetic_db, run_cli


def _json_from_result(result: Any) -> dict[str, Any]:
    raw: str = result.output.strip()
    import re

    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    start = clean.rfind("{")
    if start == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[start:])


def _seed_disk_and_path(conn: sqlite3.Connection, mount_path: str, rel_path: str) -> tuple[int, int]:
    """Seed disk + path rows and return ``(disk_id, path_id)``."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        ("uuid-test", "TestDisk", mount_path, now),
    )
    disk_id: int = cursor.lastrowid  # type: ignore[assignment]
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    conn.commit()
    return disk_id, cursor.lastrowid  # type: ignore[return-value]


def _seed_item_with_dispatch(
    conn: sqlite3.Connection,
    title: str,
    dispatch_path: str,
    kind: str = "movie",
    category_id: str = "movies",
) -> int:
    """Seed media_item + item_attribute(dispatch_path) and return item_id."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (kind, title, title, category_id, now, now),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
        (item_id, dispatch_path),
    )
    conn.commit()
    return item_id


def _seed_release(conn: sqlite3.Connection, item_id: int, quality: str = "1080p") -> int:
    """Seed a media_release for *item_id* and return release_id."""
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, quality) VALUES (?, ?)",
        (item_id, quality),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def _seed_orphan_file(conn: sqlite3.Connection, path_id: int, filename: str = "test.mkv") -> int:
    """Seed an orphan media_file (release_id=NULL) and return file_id."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO media_file "
        "(release_id, path_id, filename, size_bytes, mtime_ns, scan_generation, last_verified_at) "
        "VALUES (NULL, ?, ?, 1000, ?, 1, ?)",
        (path_id, filename, now, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _get_release_id(conn: sqlite3.Connection, file_id: int) -> int | None:
    row = conn.execute("SELECT release_id FROM media_file WHERE id = ?", (file_id,)).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Single release → linked
# ---------------------------------------------------------------------------


def test_orphan_file_with_single_release_is_linked(tmp_path: Path, test_config: Any) -> None:
    """Orphan with exactly one candidate release → release_id is set."""
    db_path = make_synthetic_db(tmp_path)
    mount = str(tmp_path / "mount")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    disk_id, path_id = _seed_disk_and_path(conn, mount, "movies/Test Movie")
    item_id = _seed_item_with_dispatch(conn, "Test Movie", f"{mount}/movies/Test Movie")
    release_id = _seed_release(conn, item_id)
    file_id = _seed_orphan_file(conn, path_id)
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
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["items_scanned"] == 1
    assert data["fixed"] == 1
    assert data["no_release"] == 0
    assert data["ambiguous"] == 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    assert _get_release_id(conn, file_id) == release_id
    conn.close()


# ---------------------------------------------------------------------------
# No release → left alone
# ---------------------------------------------------------------------------


def test_orphan_file_with_no_release_is_left_alone(tmp_path: Path, test_config: Any) -> None:
    """Orphan whose item has no release → reported as no_release, left NULL."""
    db_path = make_synthetic_db(tmp_path)
    mount = str(tmp_path / "mount")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    disk_id, path_id = _seed_disk_and_path(conn, mount, "movies/No Release Movie")
    _seed_item_with_dispatch(conn, "No Release Movie", f"{mount}/movies/No Release Movie")
    # No release inserted.
    file_id = _seed_orphan_file(conn, path_id)
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
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["items_scanned"] == 1
    assert data["fixed"] == 0
    assert data["no_release"] == 1
    assert data["ambiguous"] == 0

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    assert _get_release_id(conn, file_id) is None
    conn.close()


# ---------------------------------------------------------------------------
# Multiple releases → ambiguous
# ---------------------------------------------------------------------------


def test_orphan_file_with_multiple_releases_is_ambiguous(tmp_path: Path, test_config: Any) -> None:
    """Orphan with multiple candidate releases → reported as ambiguous, left NULL."""
    db_path = make_synthetic_db(tmp_path)
    mount = str(tmp_path / "mount")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    disk_id, path_id = _seed_disk_and_path(conn, mount, "movies/Ambiguous Movie")
    item_id = _seed_item_with_dispatch(conn, "Ambiguous Movie", f"{mount}/movies/Ambiguous Movie")
    _seed_release(conn, item_id, quality="1080p")
    _seed_release(conn, item_id, quality="2160p")
    file_id = _seed_orphan_file(conn, path_id)
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
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["items_scanned"] == 1
    assert data["fixed"] == 0
    assert data["ambiguous"] == 1

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    assert _get_release_id(conn, file_id) is None
    conn.close()


# ---------------------------------------------------------------------------
# Dry-run → no mutation
# ---------------------------------------------------------------------------


def test_dry_run_does_not_mutate(tmp_path: Path, test_config: Any) -> None:
    """Dry-run reports would_fix count without mutating the DB."""
    db_path = make_synthetic_db(tmp_path)
    mount = str(tmp_path / "mount")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    disk_id, path_id = _seed_disk_and_path(conn, mount, "movies/Dry Run Movie")
    item_id = _seed_item_with_dispatch(conn, "Dry Run Movie", f"{mount}/movies/Dry Run Movie")
    _seed_release(conn, item_id)
    file_id = _seed_orphan_file(conn, path_id)
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(
            [
                "--format",
                "json",
                "library-fix-orphan-files",
                "--db",
                str(db_path),
            ]
        )

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is False
    assert data["items_scanned"] == 1
    assert data["would_fix"] == 1
    assert data["no_release"] == 0
    assert data["ambiguous"] == 0

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    assert _get_release_id(conn, file_id) is None
    conn.close()


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


def test_idempotent_re_run(tmp_path: Path, test_config: Any) -> None:
    """Re-running repair after a successful pass touches 0 rows."""
    db_path = make_synthetic_db(tmp_path)
    mount = str(tmp_path / "mount")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    disk_id, path_id = _seed_disk_and_path(conn, mount, "movies/Idempotent Movie")
    item_id = _seed_item_with_dispatch(conn, "Idempotent Movie", f"{mount}/movies/Idempotent Movie")
    _seed_release(conn, item_id)
    _seed_orphan_file(conn, path_id)
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        r1 = run_cli(
            [
                "--format",
                "json",
                "library-fix-orphan-files",
                "--db",
                str(db_path),
                "--apply",
            ]
        )
        assert r1.exit_code == 0, r1.output
        d1 = _json_from_result(r1)
        assert d1["fixed"] == 1

        r2 = run_cli(
            [
                "--format",
                "json",
                "library-fix-orphan-files",
                "--db",
                str(db_path),
                "--apply",
            ]
        )
        assert r2.exit_code == 0, r2.output
        d2 = _json_from_result(r2)
        assert d2["items_scanned"] == 0
        assert d2["fixed"] == 0
        assert d2["no_release"] == 0
        assert d2["ambiguous"] == 0
