"""``library-remove-phantom-rows``: a dry-run-first action removing the 0-file phantom index rows.

A phantom is a row holding no live file beside a row of the same provider id that
holds some. Without ``--apply`` nothing is written; with it the phantoms are removed
from the index, each journaled, and no file nor row holding a file is touched.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

from personalscraper.app.maintenance.registry import REGISTRY
from personalscraper.app.maintenance.runner import _DRY_RUN_STYLE
from tests.commands._e2e_helpers import make_synthetic_db, run_cli

_SEASON = "series/House of the Dragon (2022)/Saison 01"
_EPISODES = 70


def _json_from(result: Any) -> dict[str, Any]:
    """Extract the last JSON object from CLI output (strips ANSI codes).

    Args:
        result: CliRunner result.

    Returns:
        The decoded payload.
    """
    raw = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    return json.loads(raw[raw.find("{") :])


def _show(conn: sqlite3.Connection, title: str, tvdb: str) -> int:
    """Insert one show row carrying *tvdb* and return its id.

    Args:
        conn: Open connection.
        title: Row title.
        tvdb: TVDB series id.

    Returns:
        The new ``media_item.id``.
    """
    ids = json.dumps({"tvdb": {"series_id": tvdb, "episode_id": None}})
    cur = conn.execute(
        "INSERT INTO media_item(kind, title, title_sort, category_id, date_created, date_modified,"
        " external_ids_json) VALUES ('show', ?, ?, 'tv_shows', 0, 0, ?)",
        (title, title, ids),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed(db_path: Path, mount: Path) -> None:
    """Seed "House of the Dragon (2022)" (70 files on disk) and its 0-file twin, plus two all-empty rows.

    Rows: 1 holds the files, 2 is its phantom (same tvdb 371572), 3 and 4 share tvdb 1 and
    both hold no file (a group that must stay untouched).

    Args:
        db_path: Path of the migrated database.
        mount: The disk's mount point, where the 70 episode files are written.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u', 'Disk1', ?, 1)", (str(mount),))
    real = _show(conn, "House of the Dragon (2022)", "371572")
    _show(conn, "House of the Dragon", "371572")
    _show(conn, "Empty A", "1")
    _show(conn, "Empty B", "1")
    path_id = conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1, ?)", (_SEASON,)).lastrowid
    season = conn.execute("INSERT INTO season(item_id, number) VALUES (?, 1)", (real,)).lastrowid
    (mount / _SEASON).mkdir(parents=True)
    for number in range(1, _EPISODES + 1):
        name = f"e{number:02d}.mkv"
        (mount / _SEASON / name).write_bytes(b"x")
        episode = conn.execute("INSERT INTO episode(season_id, number) VALUES (?, ?)", (season, number)).lastrowid
        release = conn.execute("INSERT INTO media_release(episode_id) VALUES (?)", (episode,)).lastrowid
        conn.execute(
            "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
            " scan_generation, last_verified_at) VALUES (?, ?, ?, 1, 1, '0', 1, 1)",
            (release, path_id, name),
        )
    conn.commit()
    conn.close()


def _read(db_path: Path, sql: str) -> list[tuple[Any, ...]]:
    """Run one read query on *db_path*.

    Args:
        db_path: The database.
        sql: The query.

    Returns:
        Its rows.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_apply_removes_the_phantom_and_keeps_the_row_and_its_files(tmp_path: Path, test_config: Any) -> None:
    """After ``--apply``: one "House of the Dragon" row, its 70 files and their index rows unchanged."""
    db_path = make_synthetic_db(tmp_path)
    mount = tmp_path / "disk"
    _seed(db_path, mount)
    files_before = _read(db_path, "SELECT id, release_id, path_id, deleted_at FROM media_file ORDER BY id")

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-remove-phantom-rows", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, result.output
    assert _json_from(result) == {"apply": True, "phantom_rows": [2], "deleted": 1}
    assert _read(db_path, "SELECT id FROM media_item ORDER BY id") == [(1,), (3,), (4,)]
    assert _read(db_path, "SELECT id, release_id, path_id, deleted_at FROM media_file ORDER BY id") == files_before
    assert len(list((mount / _SEASON).iterdir())) == _EPISODES
    assert _read(db_path, "SELECT op, path, actor FROM destructive_op") == [
        ("delete", "index:media_item/2", "maintenance")
    ]


def test_dry_run_is_the_default_and_writes_nothing(tmp_path: Path, test_config: Any) -> None:
    """Without ``--apply`` the phantoms are listed and the database is byte-identical."""
    db_path = make_synthetic_db(tmp_path)
    _seed(db_path, tmp_path / "disk")
    before = db_path.read_bytes()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-remove-phantom-rows", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert _json_from(result) == {"apply": False, "phantom_rows": [2], "would_delete": 1}
    assert db_path.read_bytes() == before


def test_the_action_is_registered_destructive_and_dry_run_first() -> None:
    """The registry lists it destructive with a dry run, and the runner adds ``--apply`` only on a live run."""
    (action,) = [a for a in REGISTRY if a.id == "library-remove-phantom-rows"]
    assert (action.risk, action.dry_run, action.category) == ("destructive", "supported", "fix")
    assert _DRY_RUN_STYLE["library-remove-phantom-rows"] == "apply"
